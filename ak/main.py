#!/usr/bin/env python
# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (
    gunzip, pg_isready, createdb, psql,
    dropdb, pg_restore, pg_dump, git, wget, python)
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import ConfigParser

from plumbum.commands.base import BaseCommand


__version__ = '1.4.0'

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
    return base_call(self, *args, **kwargs)

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

        if local.path(ERP_CFG).is_file():
            config_path = ERP_CFG
        elif local.path(WORKSPACE + ERP_CFG).is_file():
            config_path = WORKSPACE + ERP_CFG
        else:
            raise Exception("Missing ERP config file %s" % ERP_CFG)
        config = ConfigParser.ConfigParser()
        config.readfp(open(config_path))
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
        wget = local['wget']
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
    CALL_MAIN_IF_NESTED_COMMAND = False

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
    keep_cron = cli.Flag(
        '--keep-cron', help="Keep the cron active", group="IO")

    def main(self, dump_file):
        """Load (restore) a dump from a file.

        Will create a database if not exist already

        :param dump_file: path to dump (can be .gz or .dump)
        :param force: db will be dropped before the load
        """
        p = local.path(dump_file)

        if not p.is_file():
            raise Exception("input file not found")

        # check if db exists
        db = self.parent.db
        if psql[db, "-c", ""] & TF:  # TF = result of cmd as True or False
            if self.force:
                logging.info('DB already exists. Drop and create it')
                dropdb(db)
                createdb(db)
            else:
                print "DB already exist, use --force to force loading"
                return
        else:
            logging.info('DB does ont exists. Create it')
            createdb(db)

        if p.suffix == '.gz':
            gunzip['-c', p] | psql()
        else:
            pg_restore("-O", "-j8", p, '-d', db)

        if not self.keep_cron:
            psql(db, "-c", "UPDATE ir_cron SET active=False")


@AkDb.subcommand("console")
class AkDbConsole(AkSub):

    def main(self):
        """Run psql."""
        self.parent.main()


@AkDb.subcommand("dump")
class AkDbDump(AkSub):

    force = cli.Flag('--force', help="Force", group="IO")

    def main(self, output_name):
        """Dump database to file with pg_dump to native pg format.

        :param output_name: path to dump file
        :param force: overwrite the file if exists

        """
        output_name += '.dump'
        p = local.path(output_name)

        if p.is_file() and not self.force:
            raise Exception("outut file already exists. Use --force")
        (pg_dump["-Fc", self.parent.db] > output_name)()


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
                    status = git['status'](retcode=None)
                    print status


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


@Ak.subcommand("module")
class AkModule(AkSub):
    """Testing Module"""


@AkModule.subcommand("syntax")
class AkModuleSyntax(AkSub):
    """Pylint and Flake8 testing tools.
        Launch pylint and flake8 tests on 'modules' folder files
        or files of a specific folder in 'parts'
        using OCA quality tools configuration.
    """

    module = cli.SwitchAttr(["m", "module"], str, help="Concerned module")
    path = cli.SwitchAttr(["p", "path"], str, help="Path to a git repository")

    def main(self, *args):
        if self.path and self.module:
            raise Exception(
                "Can not have the params path and module at the same time")
        if self.module:
            find = local['find']['/workspace/parts', '-name', self.module] & BG
            path = find.stdout.split('\n')[0]
        else:
            version = None
            if self.path:
                path = self.path
            else:
                path = '/workspace/modules'

        print "Launch flake8 and pylint tests on path : %s" % path

        with local.cwd(path):
            travis_dir = local.env['MAINTAINER_QUALITY_TOOLS'] + '/travis/'
            flake8 = local[travis_dir + 'test_flake8'](retcode=None)
            print flake8
            with local.env(
                    TRAVIS_PULL_REQUEST="true",
                    TRAVIS_BRANCH="HEAD",
                    TRAVIS_BUILD_DIR='.'):
                pylint = local[travis_dir + 'test_pylint'](retcode=None)
                print pylint


@AkModule.subcommand("test")
class AkModuleTest(AkSub):
    """Module testing tools.
        Start Odoo with test enabled.
        Possibilty to choose the db and one specific or all installed modules.
    """

    module = cli.SwitchAttr(["m", "module"], str, help="Concerned module")
    db = cli.SwitchAttr(['d'], str, help="Database for the tests")

    def main(self, *args):
        params = []
        if self.db:
            db = self.db
        else:
            config = self.parent.parent.read_erp_config_file()
            db = config.get('options', 'db_name')
        params += ['-d', db]
        module = self.module or 'all'
        if psql[db, "-c", ""] & TF:  # TF = result of cmd as True or False
            params += ['-u', module]
        else:
            createdb(db)
            params += ['-i', module]
        params += ['--stop-after-init', '--test-enable']
        cmd = 'bin/start_openerp'
        return self._exec(cmd, params)

@AkModule.subcommand("diff")
class AkDiff(AkSub):
    """Diff tools.
        Based on installed module in your database scan the directory
        and show the diff between the version requested and the current
        version
    """

    def main(self, commit):
        if not local.path('.git').is_dir():
            print "no git repository found"
            return
        config = self.parent.parent.read_erp_config_file()
        db = config.get('options', 'db_name')
        res = psql(db, "-c", """SELECT name
             FROM ir_module_module
             WHERE state in ('installed', 'to upgrade')""")
        installed_modules = [m.strip() for m in res.split('\n')]
        local_modules = [m.name for m in local.path('.').list()
                         if m.name in installed_modules]
        params = ['diff', commit, 'HEAD', '--'] + local_modules\
                + [':!*.po', ':!*.pot']
        self.parent.parent._exec("git", params)

def main():
    Ak.run()
