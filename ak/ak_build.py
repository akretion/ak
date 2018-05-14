"""AK."""
import logging
from pathlib import Path

from plumbum import cli, local
from plumbum.cmd import (
    mkdir, ls, find, ln,
    gunzip, git, wget, python)
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import yaml
import configparser

from plumbum.commands.base import BaseCommand

from .ak_sub import AkSub, Ak

MODULE_FOLDER = 'module_links'


REPO_YAML = 'repo.yaml'
SPEC_YAML = 'spec.yaml'
FROZEN_YAML = 'frozen.yaml'
VENDOR_FOLDER = 'external-src'
BUILDOUT_SRC = './buildout.cfg'

logger = logging.getLogger(__name__)


def is_sha1(maybe_sha):
    if len(maybe_sha) != 40:
        return False
    try:
        int(maybe_sha, 16)
    except ValueError:
        return False
    return True


@Ak.subcommand("init")
class AkInit(AkSub):
    "Build dependencies for odoo"

    @staticmethod
    def _warning_spec():
        logger.warning("""
Missing '%s' file in this folder: aborted operation !

Consider to manually create one like this:
--------

./myfolder:
    modules: []
    src: https://github.com/OCA/myrepo 12.0

--------

Or if you want to migrate from buildout, just put your buildout.cfg file here
and trigger: ak migrate""" % SPEC_YAML)

    def main(self, *args):
        print("init project")
        if not Path(SPEC_YAML).is_file():
            self._warning_spec()
        print("""
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

        """)


@Ak.subcommand("build")
class AkBuild(AkSub):
    "Build dependencies for odoo"

    fileonly = cli.Flag(
        '--fileonly', help="Just generate the %s" % REPO_YAML, group="IO")
    linksonly = cli.Flag(
        '--linksonly', help="Generate links in %s" % MODULE_FOLDER, group="IO")
    output = cli.SwitchAttr(
        ["o", "output"], default=REPO_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")

    def _convert_repo(self, repo):
        if repo.get('remotes'):
            repo.pop('modules', None)
            if not repo.get('target'):
                repo['target'] = '%s fake' % repo['remotes'].keys()[0]
            return repo
        else:
            src = repo['src'].split(' ')
            # case we have specify the url and the branch
            if len(src) == 2:
                src, branch = src
                commit = None
            # case we have specify the url and the branch and the commit
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

    def _generate_links(self):
        "Link modules defined in repos.yml/yaml in modules folder"
        spec = yaml.load(open(self.config).read())
        dest_path = local.path(MODULE_FOLDER)
        self._update_dir(VENDOR_FOLDER)
        self._update_dir(dest_path, clear_dir=True)
        for repo_path, repo in spec.items():
            modules = repo.pop('modules', [])
            self._set_links(repo_path, modules, dest_path)

    def _update_dir(self, path, clear_dir=False):
        "Create dir or remove links"
        if not path.exists():
            mkdir(path)
        if clear_dir:
            with local.cwd(path):
                find['.']['-type', 'l']['-delete']()

    def _set_links(self, repo_path, modules, dest_path):
        for module in modules:
            src = '../%s/%s/%s' % (VENDOR_FOLDER, repo_path[2:], module)
            ln['-s', src, dest_path]()

    def _print_addons_path(self):
        spec = yaml.load(open(self.config).read())
        paths = []
        current_folder = os.getcwd()
        for repo_path, repo in spec.items():
            if not repo.get('modules'):
                paths.append(repo_path.replace('./', ''))
        addons_path = ','.join(['%s/%s/%s' % (current_folder, VENDOR_FOLDER, x)
                                for x in paths])
        addons_path = '%s/%s,%s' % (current_folder, MODULE_FOLDER, addons_path)
        print('Addons path for your config file: ', addons_path)
        return addons_path

    def main(self, *args):
        if not Path(SPEC_YAML).is_file():
            return AkInit._warning_spec()
        self._print_addons_path()
        if self.linksonly:
            return self._generate_links()
        self._generate_repo_yaml()
        if not self.fileonly:
            with local.cwd(VENDOR_FOLDER):
                local['gitaggregate']['-c', '../' + self.output] & FG
        self._generate_links()


@Ak.subcommand("freeze")
class AkFreeze(AkSub):
    "Freeze dependencies for odoo in config file formated for git aggregator"

    output = cli.SwitchAttr(
        ["o", "output"], default=FROZEN_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=REPO_YAML, help="Config file", group="IO")

    def find_branch_last_commit(self, remote, repo, branch):
        with local.cwd(repo):
            sha = git['rev-parse'][remote + '/' + branch]().strip()
        return sha

    def main(self, *args):
        if not os.path.isfile(self.config):
            raise Exception(
                "Missing yaml config file %s" % self.config)
        # TODO implement method to check config file format is good (should
        # probably call git aggregator get_repos method)

        # Do not use load_config from git aggregator for now as it modify the
        # yaml file a lot Which is not good, because we want to re-create it
        # after
        with open(self.config, 'r') as myfile:
            conf = yaml.load(myfile)
        for directory, repo_data in conf.items():
            i = 0
            for merge in repo_data.get('merges'):
                parts = merge.split(' ')
                # branch is already frozen with commit
                if is_sha1(parts[1]):
                    i += 1
                    continue
                else:
                    sha = self.find_branch_last_commit(parts[0],
                                                       directory, parts[1])
                    parts[1] = sha
                    repo_data.get('merges')[i] = ' '.join(parts)
                    i -= 1
        with open(self.output, 'w') as outfile:
            yaml.dump(conf, outfile, default_flow_style=False)
