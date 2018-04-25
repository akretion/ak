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


REPO_YAML = 'repo.yaml'
SPEC_YAML = 'spec.yaml'
VENDOR_FOLDER = 'external-src'


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



@Ak.subcommand("build")
class AkBuild(AkSub):
    "Build dependencies for odoo"

    fileonly = cli.Flag(
        '--fileonly', help="Just generate the %s" % REPO_YAML, group="IO")
    output = cli.SwitchAttr(
        ["o", "output"], default=REPO_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")

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
                    'Src must be in the format '
                    'http://github.com/oca/server-tools 10.0 <optional sha>')
            return {
                'remotes': {'src': src},
                'merges': ['src %s' % (commit or branch)],
                'target': 'src fake'
                }

    def _generate_repo_yaml(self):
        repo_conf = {}
        config = yaml.load(open(self.config).read())
        for key in config:
            repo_conf[key] = self._convert_repo(config[key])
        data = yaml.dump(repo_conf)
        with open(self.output, 'w') as output:
            output.write(data)

    def main(self, *args):
        self._generate_repo_yaml()
        if not self.fileonly:
            with local.cwd(VENDOR_FOLDER):
                local['gitaggregate']['-c', '../' + self.output] & FG


@Ak.subcommand("freeze")
class AkFreeze(AkSub):
    "Freeze dependencies for odoo"

    def main(self):
        self._exec(
            'pipenv',
            ['lock'])
