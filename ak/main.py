#!/usr/bin/env python
# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (
    gunzip, pg_isready, createdb, psql, dropdb, pg_restore, git, wget, python)
from plumbum.commands.modifiers import FG, TF
from datetime import datetime
import os
import ConfigParser

from plumbum.commands.base import BaseCommand


__version__ = '1.2.2'

BUILDOUT_URL = ('https://raw.github.com/buildout/'
                'buildout/master/bootstrap/bootstrap.py')
ERP_CFG = 'etc/openerp.cfg'
BUILDOUT_FILE = "buildout.%s.cfg"
WORKSPACE = '/workspace/'
MODULE_FOLDER = WORKSPACE + 'parts/'
ENV=os.environ.get('AK_ENV', 'dev')
UPGRADE_LOG_DIR = 'upgrade-log'
DRYRUN = False

# Hack to set/unset log and dryrun to plumbum
base_call = BaseCommand.__call__

def custom_call(self, *args, **kwargs):
    logging.info("%s, %s", self, args)
    if DRYRUN:
        print 'dryrun : ', self, args
        return True
    base_call(self, *args, **kwargs)

BaseCommand.__call__ = custom_call


class Ak(cli.Application):
    PROGNAME = "ak"
    VERSION = __version__

    dryrun = cli.Flag(["dry-run"], help="Dry run mode")

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
        global DRYRUN
        DRYRUN = self.dryrun
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

    def _get_log_params(self):
        config = self.parent.read_erp_config_file()
        data_dir = config.get('options', 'data_dir')
        upgrade_dir_full_path = os.path.join(data_dir, UPGRADE_LOG_DIR)
        if not os.path.exists(upgrade_dir_full_path):
            os.makedirs(upgrade_dir_full_path)
        version = open('VERSION.txt', 'r').read().strip()
        upgrade_file_path = os.path.join(
            upgrade_dir_full_path, '%s.log' % version)
        return ['--log-level', 'debug', '--log-file', upgrade_file_path]

    def main(self, *args):
        params = []
        if ENV != 'dev':
            params += self._get_log_params()
        if self.db:
            params += ['-d', self.db]
        return self._exec('bin/upgrade_openerp', params)


class AkBuildFreeze(AkSub):

    config = cli.SwitchAttr(
        ["c", "config"], help="Config flag")

    def __init__(self, *args, **kwargs):
        super(AkBuildFreeze, self).__init__(*args, **kwargs)
        if not self.config:
            buildout_file_path = os.path.join(WORKSPACE, BUILDOUT_FILE % ENV)
            if os.path.isfile(buildout_file_path):
                self.config = buildout_file_path
            else:
                raise Exception(
                    "Missing buildout config file, %s" % buildout_file_path)


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
        if psql["-c", ""] & TF:  # TF = result of cmd as True or False
            if self.force:
                logging.info('DB already exists. Drop and create it')
                dropdb(self.db)
                createdb(self.db)
            else:
                print "DB already exist, use --force to force loading"
                return
        else:
            logging.info('DB does ont exists. Create it')
            createdb(self.db)

        if p.suffix == '.gz':
            gunzip['-c', p] | psql()
        else:
            pg_restore("-O", p, '-d', self.db)

        # set cron to inactive
        # TODO give a flag for that
        psql("-c", "'UPDATE ir_cron SET active=False;'")


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
        pg_dump | local['gzip'] > afile


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
                    git['status']


@Ak.subcommand("project")
class AkProject(AkSub):
    """Project task related"""


@AkProject.subcommand("check-update")
class AkProjectCheckUpdate(AkSub):

    apply = cli.Flag(
        '--apply',
        help="Apply update version in the frozen file",
        group="IO")

    def main(self, *args):
        params = ['frozen.cfg']
        if self.apply:
            params += ['-w', '--indent', '2']
        self._exec('check-buildout-updates', params)


@AkProject.subcommand("release")
class AkProjectRelease(AkSub):

    def main(self, *args):
        base_version = datetime.now().strftime('%y.%W')
        version = open('VERSION.txt', 'r').read().strip()
        if base_version > version:
            increment = 1
        else:
            increment = int(version.split('.')[2]) + 1
        new_version = "%s.%s" % (base_version, increment)
        f = open('VERSION.txt', 'w')
        f.write(new_version)
        f.close()
        migration_file_path = os.path.join('upgrade', 'current.py')
        if os.path.exists(migration_file_path):
            new_path = os.path.join('upgrade', '%s.py' % new_version)
            git('mv', migration_file_path, new_path)
            git('add', new_path)
        message = '[BUMP] version %s' % new_version
        git('add', 'VERSION.txt')
        git('commit', '-m', message)
        git('tag', '-a', new_version, '-m', message)


def main():
    Ak.run()
