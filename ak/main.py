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

BUILDOUT_URL = ('https://raw.github.com/buildout/'
                'buildout/master/bootstrap/bootstrap.py')
ERP_CFG = 'etc/openerp.cfg'
DEV_BUILD = "buildout.dev.cfg"
PROD_BUILD = "buildout.prod.cfg"
WORKSPACE = '/workspace/'
MODULE_FOLDER = WORKSPACE + 'parts/'



class Ak(cli.Application):
    PROGNAME = "ak"
    VERSION = "1.0"

    dryrun = cli.Flag(["dry-run"], help="Dry run mode")

    def _exec(self, cmd, retcode=FG):
        """Log cmd before exec."""
        logging.info(cmd)
        if (self.dryrun):
            print cmd
            return True
        return cmd & retcode

    def log_and_exec(self, cmd, args=[], env=None):
        """Log cmd and execve."""
        logging.info([cmd, args])
        if (self.dryrun):
            print "os.execvpe (%s, %s, env)" % (cmd, [cmd] + args)
            return True
        os.execvpe(cmd, [cmd] + args, env)

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


@Ak.subcommand("run")
class AkRun(AkSub):
    """Start openerp."""

    debug = cli.Flag(["D", "debug"], help="Debug mode")
    console = cli.Flag(['console'], help="Console mode")
    update = cli.SwitchAttr(
        ["u", "update"], list=True, help="Update module")
    db = cli.SwitchAttr(
        ["d"], help="Force Database")

    def main(self, *args):
        if self.console:
            cmd = local['bin/python_openerp']
        else:
            params = []
            if self.db:
                params += ['--db-filter', self.db]
            if self.debug:
                params += ['--debug']
            if self.update:
                params += ['-u', str.join(',', self.update)]
            cmd = local['bin/start_openerp'].__getitem__(params)
        return self._exec(cmd)


@Ak.subcommand("upgrade")
class AkUpgrade(AkSub):
    """Upgrade odoo."""

    db = cli.SwitchAttr(
        ["d"], help="Force Database")

    def main(self, *args):
        cmd = local['bin/upgrade_openerp']
        if self.db:
            cmd = cmd['-d', self.db]
        return self._exec(cmd)


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
        self._exec(local['bin/buildout'].__getitem__(params))


@Ak.subcommand("freeze")
class AkFreeze(AkBuildFreeze):
    "Freeze dependencies for odoo"

    def main(self):
        self._exec(local['bin/buildout'][
            '-c', self.config, '-o', 'openerp:freeze-to=frozen.cfg'])


class AkSubDb(AkSub):
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
        super(AkSubDb, self).__init__(executable)
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


@Ak.subcommand("db:load")
class AkDbLoad(AkSubDb):

    force = cli.Flag('--force', help="Force", group="IO")

    def main(self, dump_file):
        """Load (restore) a dump from a file.

        Will create a database if not exist already

        :param dump_file: path to dump (can be .gz or .tar)
        :param foce: db will be dropped before the load
        """
        p = local.path(dump_file)

        if not p.is_file():
            raise Exception("input file not found")

        # check if db exists
        cmd = psql["-c", ""]
        if (self._exec(cmd, TF)):  # TF = result of cmd as True or False
            if self.force:
                logging.info('DB already exists. Drop and create it')
                self._exec(dropdb[self.db])
                self._exec(createdb[self.db])
            else:
                print "DB already exist, use --force to force loading"
                return
        else:
            logging.info('DB does ont exists. Create it')
            self._exec(createdb)

        if p.suffix == '.gz':
            self._exec(gunzip['-c', p] | psql)
        else:
            self._exec(pg_restore["-O", p, '-d', self.db])

        # set cron to inactive
        # TODO give a flag for that
        self._exec(psql["-c", "'UPDATE ir_cron SET active=False;'"])


@Ak.subcommand("db:console")
class AkDbConsole(AkSubDb):

    def main(self):
        """Run psql."""
        self._exec(psql)


@Ak.subcommand("db:dump")
class AkDbDump(AkSubDb):

    def main(self, output_name):
        """Dump database to file with pg_dump then gzip.

        :param afile: path to dump file
        :param force: overwrite the file if exists

        """
        # TODO choose format
        p = local.path(afile)

        if p.is_file() and not force:
            raise Exception("output file already exists. Use --force")
        self.log_and_run(local['pg_dump'] | local['gzip'] > afile)


@Ak.subcommand("db")
class AkDb(AkSubDb):
    """Db tools.

    Run without args to get a psql prompt
    Credentials are extracted from etc/openerp.cfg

    """

    infoFlag = cli.Flag(["info"], group="Other",
                        help="info on db crendentials")
    passFlag = cli.Flag(["admin-password"], group="Other",
                        help="Change odoo admin password")

    def info(self):
        """Print db informations from etc/buildout.cfg."""
        for ini_key, pg_key in self.dbParams.iteritems():
            print ini_key, local.env.get(pg_key, '')

    def changeAdminPassword(self, args):
        """Change admin password."""

        new_pass = (args or [False])[0]

        if (not new_pass):  # not provided by cli
            new_pass = cli.terminal.prompt(
                'New admin password ?', str, "admin")

        print "New admin password for %s is : '%s'" % (self.db, new_pass)

        code = """session.open(db='%s')"
user_ids = session.registry('res.users').search(session.cr, 1, [])",
for user in session.registry('res.users').browse(session.cr, 1, user_ids):",
    user.write({'password': '%s' })",
session.cr.commit()
""" % (self.db, new_pass)
        print local['echo'][code] | local['ak']['console']
        # TODO: run this command and test it !


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
                    self.parent.log_and_run(git['status'])


def main():
    Ak.run()
