#!/usr/bin/env python
# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (
    gunzip, pg_isready, createdb, psql, dropdb, pg_restore, git, wget, python)
from plumbum.commands.modifiers import FG, TF
import os
import ConfigParser

__version__ = '1.1.1'

BUILDOUT_URL = ('https://raw.github.com/buildout/'
                'buildout/master/bootstrap/bootstrap.py')
ERP_CFG = 'etc/openerp.cfg'
DEV_BUILD = "buildout.dev.cfg"
PROD_BUILD = "buildout.prod.cfg"
WORKSPACE = '/workspace/'
MODULE_FOLDER = WORKSPACE + 'parts/'



class Ak(cli.Application):
    PROGNAME = "ak"
    VERSION = __version__

    dryrun = cli.Flag(["dry-run"], help="Dry run mode")

    def _run(self, cmd, retcode=FG):
        """Run a command in a new process and log it"""
        logging.info(cmd)
        if (self.dryrun):
            print cmd
            return True
        return cmd & retcode

    def _exec(self, cmd, args=[]):
        """Run a command in the same process and log it
        this will replace the current process by the cmd"""
        logging.info([cmd, args])
        if (self.dryrun):
            print "os.execvpe (%s, %s, env)" % (cmd, [cmd] + args)
            return True
        os.execvpe(cmd, [cmd] + args, local.env)

    def read_erp_config_file(self):
        if not local.path(ERP_CFG).is_file():
            raise Exception("Missing ERP config file %s" % ERP_CFG)
        config = ConfigParser.ConfigParser()
        config.readfp(open(ERP_CFG))
        return config

    @cli.switch("--verbose", help="Verbose mode")
    def set_log_level(self):
        logging.root.setLevel(logging.INFO)
        logging.info('Verbose mode activated')

    def main(self, *args):
        if args:
            print "Unkown command %r" % (args[0],)
            return 1  # return error
        if not self.nested_command:
            print "No command given"
            return 1

class AkSub(cli.Application):

    def _exec(self, *args, **kwargs):
        return self.parent._exec(*args, **kwargs)

    def _run(self, *args, **kwargs):
        return self.parent._run(*args, **kwargs)


@Ak.subcommand("run")
class AkRun(AkSub):
    """Start odoo."""

    def _parse_args(self, argv):
        self.argv = argv
        argv = []
        return super(AkRun, self)._parse_args(argv)

    def main(self):
        return self._exec('bin/start_openerp', self.argv)


@Ak.subcommand("console")
class AkConsole(AkSub):
    """Start a python console."""

    def main(self):
        return self._exec('bin/python_openerp')


@Ak.subcommand("upgrade")
class AkUpgrade(AkSub):
    """Upgrade odoo."""

    db = cli.SwitchAttr(
        ["d"], help="Force Database")

    def main(self, *args):
        params = []
        if self.db:
            params += ['-d', self.db]
        return self._exec('bin/upgrade_openerp', params)


class AkBuildFreeze(AkSub):

    config = cli.SwitchAttr(
        ["c", "config"], help="Config flag")

    def __init__(self, *args, **kwargs):
        super(AkBuildFreeze, self).__init__(*args, **kwargs)
        if not self.config:
            if os.path.isfile(WORKSPACE + PROD_BUILD):
                self.config = WORKSPACE + PROD_BUILD
            elif os.path.isfile(WORKSPACE + DEV_BUILD):
                self.config = WORKSPACE + DEV_BUILD
            else:
                # TODO replace with an adhoc exception
                raise Exception("Missing buildout config file")


@Ak.subcommand("build")
class AkBuild(AkBuildFreeze):
    "Build dependencies for odoo"

    offline = cli.Flag(
        ["o"], help="Build with only local available source (merges, etc)")

    def download_and_install(self):
        logging.info('Will download buildout from %s' % BUILDOUT_URL)
        wget = local['wget']
        cmd = wget[BUILDOUT_URL]
        cmd()
        python('bootstrap.py')
        os.remove('bootstrap.py')

    def main(self, *args):
        if not os.path.exists('bin/buildout'):
            self.download_and_install()
        params = ['-c', self.config]
        if self.offline:
            params.append('-o')
        self._exec('bin/buildout', params)


@Ak.subcommand("freeze")
class AkFreeze(AkBuildFreeze):
    "Freeze dependencies for odoo"

    def main(self):
        self._exec(
            'bin/buildout',
            ['-c', self.config, '-o', 'openerp:freeze-to=frozen.cfg'])


@Ak.subcommand("db")
class AkDb(AkSub):
    """Read db credentials from ERP_CFG.

    Add -d flag to the current command to override PGDATABASE
    Add self.db

    Usage:
      Heritate from this class and call determine_db()

        class AkSomething(cli.Application, DbTools):
            def main(self):
                self.set_db()
                # your stuff here
                print self.db
    """

    dbParams = {
        "db_host": "PGHOST",
        "db_port": "PGPORT",
        "db_name": "PGDATABASE",
        "db_user": "PGUSER",
        "db_password": "PGPASSWORD"
    }

    db = cli.SwitchAttr(["d"], str, help="Database")

    def __init__(self, executable):
        super(AkDb, self).__init__(executable)
        """Extract db parameters from ERP_CFG."""
        config = self.parent.read_erp_config_file()
        for ini_key, pg_key in self.dbParams.iteritems():
            val = config.get('options', ini_key)
            if not val == "False":
                logging.info('Set %s to %s' % (pg_key, val))
                local.env[pg_key] = val

        if self.db:  # if db is forced by flag
            logging.info("PGDATABASE overwitten by %s", self.db)
            local.env["PGDATABASE"] = self.db
        else:
            self.db = local.env["PGDATABASE"]

    def main(self):
        """Run psql."""
        self._exec('psql')


@AkDb.subcommand("load")
class AkDbLoad(AkSub):

    force = cli.Flag('--force', help="Force", group="IO")

    def main(self, dump_file):
        """Load (restore) a dump from a file.

        Will create a database if not exist already

        :param dump_file: path to dump (can be .gz or .tar)
        :param force: db will be dropped before the load
        """
        p = local.path(dump_file)

        if not p.is_file():
            raise Exception("input file not found")

        # check if db exists
        cmd = psql["-c", ""]
        if (self._run(cmd, TF)):  # TF = result of cmd as True or False
            if self.force:
                logging.info('DB already exists. Drop and create it')
                self._run(dropdb[self.db])
                self._run(createdb[self.db])
            else:
                print "DB already exist, use --force to force loading"
                return
        else:
            logging.info('DB does ont exists. Create it')
            self._run(createdb)

        if p.suffix == '.gz':
            self._run(gunzip['-c', p] | psql)
        else:
            self._run(pg_restore["-O", p, '-d', self.db])

        # set cron to inactive
        # TODO give a flag for that
        self._run(psql["-c", "'UPDATE ir_cron SET active=False;'"])


@AkDb.subcommand("console")
class AkDbConsole(AkSub):

    def main(self):
        """Run psql."""
        self.parent.main()


@AkDb.subcommand("dump")
class AkDbDump(AkSub):

    def main(self, output_name):
        """Dump database to file with pg_dump then gzip.

        :param afile: path to dump file
        :param force: overwrite the file if exists

        """
        # TODO choose format
        p = local.path(afile)

        if p.is_file() and not force:
            raise Exception("outut file already exists. Use --force")
        self._run(local['pg_dump'] | local['gzip'] > afile)


@AkDb.subcommand("info")
class AkDbInfo(AkSub):
    """Print db informations from etc/buildout.cfg."""

    def main(self):
        for ini_key, pg_key in self.parent.dbParams.iteritems():
            print ini_key, local.env.get(pg_key, '')


@Ak.subcommand("diff")
class AkDiff(cli.Application):
    """Diff tools.
        Scan all Odoo module repositories, based on addons_path in the
        erp config file.
        For each repository, launch a diff command.
        For the time being, only git is implemented.
    """
    def main(self, *args):
        config = self.parent.read_erp_config_file()
        paths = config.get('options', 'addons_path').split(',')
        for path in paths:
            # Skip voodoo folder (module path) and do not consider double paths
            # for odoo
            if path.startswith(MODULE_FOLDER) and not\
                    path.endswith('openerp/addons'):
                print "\n"
                print "".ljust(100, '~')
                print ("~~~ Scanning folder %s" % path).ljust(100, '~')
                print "".ljust(100, '~')
                with local.cwd(path):
                    self.parent._run(git['status'])


def main():
    Ak.run()
