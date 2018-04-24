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
import configparser

from plumbum.commands.base import BaseCommand

from .ak_sub import AkSub, Ak


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
            if self.path:
                path = self.path
            else:
                path = '/workspace/modules'

        print("Launch flake8 and pylint tests on path : %s" % path)

        with local.cwd(path):
            travis_dir = local.env['MAINTAINER_QUALITY_TOOLS'] + '/travis/'
            flake8 = local[travis_dir + 'test_flake8'](retcode=None)
            print(flake8)
            with local.env(
                    TRAVIS_PULL_REQUEST="true",
                    TRAVIS_BRANCH="HEAD",
                    TRAVIS_BUILD_DIR='.'):
                pylint = local[travis_dir + 'test_pylint'](retcode=None)
                print(pylint)


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
                print("\n")
                print("".ljust(100, '~'))
                print(("~~~ Scanning folder %s" % path).ljust(100, '~'))
                print("".ljust(100, '~'))
                with local.cwd(path):
                    status = git['status'](retcode=None)
                    print(status)

@AkModule.subcommand("diff")
class AkDiff(AkSub):
    """Diff tools.
        Based on installed module in your database scan the directory
        and show the diff between the version requested and the current
        version
    """

    def main(self, commit):
        if not local.path('.git').is_dir():
            print("no git repository found")
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

