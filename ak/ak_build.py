"""AK."""
import logging
from pathlib import Path
from plumbum import cli, local
from plumbum.cmd import (
    mkdir, ls, find, ln,
    gunzip, git, wget, python)
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from plumbum.commands.base import BaseCommand
from datetime import datetime
import os
import yaml
try:
    import configparser
except ImportError:
    import ConfigParser as configparser


from .ak_sub import AkSub, Ak


REPO_YAML = 'repo.yaml'
SPEC_YAML = 'spec.yaml'
FROZEN_YAML = 'frozen.yaml'
VENDOR_FOLDER = 'external-src'
LOCAL_FOLDER = 'local-src'
LINK_FOLDER = 'links'
ODOO_FOLDER = 'src'
BUILDOUT_SRC = './buildout.cfg'
DEFAULT_DEPTH=20

logger = logging.getLogger(__name__)


def is_sha1(maybe_sha):
    if len(maybe_sha) != 40:
        return False
    try:
        int(maybe_sha, 16)
    except ValueError:
        return False
    return True


@Ak.subcommand("build")
class AkBuild(AkSub):
    "Build dependencies for odoo"

    fileonly = cli.Flag(
        '--fileonly', help="Just generate the %s" % REPO_YAML, group="IO")
    linksonly = cli.Flag(
        '--links', help="Generate links in %s" % LINK_FOLDER, group="IO")
    output = cli.SwitchAttr(
        ["o", "output"], default=REPO_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")

    def _convert_repo(self, repo):
        if repo.get('remotes'):
            repo.pop('modules', None)
            if not repo.get('target'):
                repo['target'] = '%s merged' % list(repo['remotes'].keys())[0]
            if not repo.get('defaults', {}).get('depth'):
                repo['default'] = {'depth' : DEFAULT_DEPTH}
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
                'remotes': {'origin': src},
                'merges': ['origin %s' % (commit or branch)],
                'target': 'origin %s' % branch,
                'default': {'depth': repo.get('depth', DEFAULT_DEPTH)},
            }

    def _generate_repo_yaml(self):
        repo_conf = {}
        config = yaml.safe_load(open(self.config).read())
        for key in config:
            if key == 'odoo':
                # put odoo in a different directory
                repo_key = ODOO_FOLDER
            elif key[0:2] == './':
                # if prefixed with ./ don't change the path
                repo_key = key
            else:
                # put sources in VENDOR_FOLDERS
                repo_key = u'./%s/%s' % (VENDOR_FOLDER, key)
            repo_conf[repo_key] = self._convert_repo(config[key])
        data = yaml.safe_dump(repo_conf)
        with open(self.output, 'w') as output:
            output.write(data)

    def _generate_links(self):
        "Link modules defined in repos.yml/yaml in modules folder"
        spec = yaml.load(open(self.config).read())
        dest_path = local.path(LINK_FOLDER)
        for key, repo in spec.items():
            modules = repo.pop('modules', [])
            self._set_links(key, modules, dest_path)

    def _update_dir(self, path, clear_dir=False):
        "Create dir and remove links"
        if not path.exists():
            logger.debug('mkdir %s' % path)
            mkdir(path)
        if clear_dir:
            with local.cwd(path):
                logger.debug('rm all links from %s' % path)
                find['.']['-type', 'l']['-delete']()

    def _set_links(self, key, modules, dest_path):
        for module in modules:
            if key == 'odoo':
                src = '../src/addons/%s' % module
            else:
                src = '../%s/%s/%s' % (VENDOR_FOLDER, key, module)
            ln['-s', src, dest_path]()


    def _print_addons_path(self, config):
        spec = yaml.load(open(config).read())
        paths = [LINK_FOLDER, LOCAL_FOLDER]
        for repo_path, repo in spec.items():
            if not repo.get('modules'):
                if repo_path == 'odoo':
                    # When odoo, we need to add 2 path
                    paths.append('%s/odoo/addons' % ODOO_FOLDER)
                    paths.append('%s/addons' % ODOO_FOLDER)
                elif repo_path[0:2] == './':
                    paths.append(repo_path)  # don't touch relative paths
                else:
                    # TODO Need to be delete when all spec.yaml files cleaned
                    paths.append('%s/%s' % (VENDOR_FOLDER, repo_path))

        addons_path = ','.join(paths)
        print('Addons path for your config file: ', addons_path)
        return addons_path

    def _ensure_viable_installation(self):
        self._update_dir(local.path(VENDOR_FOLDER))
        self._update_dir(local.path(LINK_FOLDER), clear_dir=True)

    def main(self, *args):
        config_file = self.config
        if self.linksonly:
            self._ensure_viable_installation()
            self._generate_links()
            # Links have been updated then addons path must be updated
            self._print_addons_path(config_file)
            return
        if self.config != SPEC_YAML:
            config_file = self.config
        elif Path(FROZEN_YAML).is_file():
            config_file = FROZEN_YAML
            logging.info("Frozen file exist use it for building the project")

        self.config = config_file

        self._ensure_viable_installation()
        self._generate_repo_yaml()
        self._generate_links()
        config_file = self.output
        if not self.fileonly:
            local['gitaggregate']['-c', config_file] & FG
            self._print_addons_path(config_file)


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
