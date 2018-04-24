# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (
    gunzip, git, wget, python)
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import ConfigParser
import yaml

from .ak_sub import AkSub, Ak

MODULE_FOLDER = 'modules'


@Ak.subcommand("init")
class AkInit(AkSub):
    "Build dependencies for odoo"

    def main(self, *args):
       print "init project"
       print """
       propose de selectionner une majeur ?
       export WORKON_HOME=`pwd`
       if requirements or pipfile exit
       echo 'workspace-*' >> .gitignore
       wget https://raw.githubusercontent.com/odoo/odoo/10.0/requirements.txt
       pipenv install
       pipenv install http://nightly.odoo.com/10.0/nightly/src/odoo_10.0.latest.zip
       git add requirements.txt
       git add Pipfile
       #add odoo addons dans le Pipfile

       export ODOO_RC='/workspace/odoo_base.cfg' # project wide

       """



class AkBuildFreeze(AkSub):

    config = cli.SwitchAttr(
        ["c", "config"], help="Config flag")

    def __init__(self, *args, **kwargs):
        super(AkBuildFreeze, self).__init__(*args, **kwargs)
        if not local.path('spec.yaml').exists():
            raise Exception("File spec.yaml is missing")
        else:
            self.config = yaml.load(open('spec.yaml').read())


@Ak.subcommand("build")
class AkBuild(AkBuildFreeze):
    "Build dependencies for odoo"

    fileonly = cli.Flag(
        '--fileonly', help="Just generate the repo.yaml", group="IO")

    def _convert_repo(self, repo):
        if repo.get('remotes'):
            repo.pop('modules', None)
            return repo
        else:
            src = repo['src'].split(' ')
            if len(src) == 2:
                src, branch = src
                commit = None
            elif len(src) == 3:
                src, branch, commit = src
            else:
                raise Exception(
                    'Src must be in the format'
                    'http://github.com/oca/server-tools 10.0 <optional sha>')
            return {
                'remotes': {'src': src},
                'merges': ['src %s' % (commit or branch)],
                'target': 'src fake'
                }

    def _generate_repo_yaml(self):
        repo_conf = {}
        for key in self.config:
            repo_conf[key] = self._convert_repo(self.config[key])
        data = yaml.dump(repo_conf)
        output = open('repo.yaml', 'w')
        output.write(data)
        output.close()

    def main(self, *args):
        self._generate_repo_yaml()
        if not self.fileonly:
            with local.cwd('external-src'):
                local['gitaggregate']['-c', '../repo.yaml'] & FG


@Ak.subcommand("freeze")
class AkFreeze(AkBuildFreeze):
    "Freeze dependencies for odoo"

    def main(self):
        self._exec(
            'pipenv',
            ['lock'])


@Ak.subcommand("link")
class AkLink(AkBuildFreeze):
    "Link modules defined in repos.yml/yaml in modules folder"

    def main(self, file=None, config=None):
        if self.config:
            local['rm']('-rf', MODULE_FOLDER)
            local['mkdir'](MODULE_FOLDER)
        for key, vals in self.config.items():
            if 'modules' in vals:
                modules = extract_module_names(vals['modules'])
                self._set_links(key, modules)

    def _set_links(self, path, modules):
        for module in modules:
            src = '../%s/%s' % (path[2:], module)
            arguments = ['-s', src, MODULE_FOLDER]
            local['ln'](arguments)


def extract_module_names(modules):
    if isinstance(modules, (str, unicode)):
        return modules.split(' ')
    return modules
