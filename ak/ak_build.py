"""AK."""
import logging
from pathlib import Path
from plumbum import cli, local
from plumbum.cmd import (mkdir, find, ln, git)
from plumbum.commands.modifiers import FG
from plumbum.commands.processes import ProcessExecutionError
import os
import yaml


from .ak_sub import AkSub, Ak


REPO_YAML = 'repo.yaml'
SPEC_YAML = 'spec.yaml'
FROZEN_YAML = 'frozen.yaml'
VENDOR_FOLDER = 'external-src'
LOCAL_FOLDER = 'local-src'
LINK_FOLDER = 'links'
ODOO_FOLDER = 'src'
BUILDOUT_SRC = './buildout.cfg'
DEFAULT_DEPTH = 20
PREFIX = '/odoo/'

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
    directory = cli.SwitchAttr(
        ["d", "directory"], group="IO",
        help="Refresh aggregation of a specific directory "
             "(this directory must exists) "
             "shortcut for `gitaggregate -c repo.yaml -d my_dir`")

    def _convert_repo(self, repo):
        if repo.get('remotes'):
            repo.pop('modules', None)
            if not repo.get('target'):
                repo['target'] = '%s merged' % list(repo['remotes'].keys())[0]
            if not repo.get('defaults', {}).get('depth'):
                repo['default'] = {'depth': DEFAULT_DEPTH}
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
            repo_dict = {
                'remotes': {'origin': src},
                'merges': ['origin %s' % (commit or branch)],
                'target': 'origin %s' % branch,
                'default': {'depth': repo.get('depth', DEFAULT_DEPTH)},
            }
            if commit:
                repo_dict['fetch_all'] = ['origin']
            return repo_dict

    def _generate_repo_yaml(self, config):
        repo_conf = {}
        config = yaml.safe_load(open(config).read())
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

    def _generate_links(self, config):
        "Link modules defined in repos.yml/yaml in modules folder"
        spec = yaml.load(open(config).read())
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
        """Construct addon path based on spec.yaml

        modules specified in spec.yaml are linked in "link"
        repos without modules are added explicitely to the path"""
        spec = yaml.load(open(config).read())
        paths = [LINK_FOLDER, LOCAL_FOLDER]
        relative_paths = []
        for repo_path, repo in spec.items():
            if not repo.get('modules'):
                if repo_path == 'odoo':
                    # When odoo, we need to add 2 path
                    paths.append('%s/odoo/addons' % ODOO_FOLDER)
                    paths.append('%s/addons' % ODOO_FOLDER)
                elif repo_path[0:2] == './':
                    relative_paths.append(repo_path)
                else:
                    # TODO Need to be delete when all spec.yaml files cleaned
                    # Update 2019/04 No it should not?
                    paths.append('%s/%s' % (VENDOR_FOLDER, repo_path))

        addons_path = ','.join(paths + relative_paths)
        # Construct absolute path, better for odoo config file.
        abs_path = ",".join([PREFIX + repo_path for repo_path in paths])
        print('Addons path for your config file: ', abs_path)
        return addons_path

    def _ensure_viable_installation(self, config):
        if not local.path(config).is_file():
            raise Exception("Config file not found.")
        self._update_dir(local.path(VENDOR_FOLDER))
        self._update_dir(local.path(LINK_FOLDER), clear_dir=True)

    def main(self, *args):
        config_file = self.config
        if self.linksonly:
            self._ensure_viable_installation(config_file)
            self._generate_links(config_file)

            # Links have been updated then addons path must be updated
            self._print_addons_path(config_file)
            return
        if self.config != SPEC_YAML:
            config_file = self.config
        elif Path(FROZEN_YAML).is_file():
            config_file = FROZEN_YAML
            logging.info("Frozen file exist use it for building the project")

        self._ensure_viable_installation(config_file)
        self._generate_repo_yaml(config_file)
        self._generate_links(config_file)

        config_file = self.output
        if not self.fileonly:
            args = ['-c', config_file]
            if self.directory:
                # TODO externalise it in a function
                if self.directory == 'odoo':
                    path = ODOO_FOLDER
                else:
                    path = '%s/%s' % (VENDOR_FOLDER, self.directory)
                args.append(['-d', './%s' % path])
                if not local.path(path).exists():
                    raise Exception(
                        "\nSpecified file './%s' doesn't "
                        "exists in your system" % path)
            local['gitaggregate'][args] & FG
            # print addons_path should be called with spec.yml
            # in order to have the module key
            self._print_addons_path(self.config)


@Ak.subcommand("freeze")
class AkFreeze(AkSub):
    "Freeze dependencies for odoo in config file formated for git aggregator"

    output = cli.SwitchAttr(
        ["o", "output"], default=FROZEN_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=REPO_YAML, help="Config file", group="IO")

    def find_branch_last_commit(self, remote, repo, branch):
        with local.cwd(repo):
            try:
                # We do not freeze this kind of refs for now :
                # refs/pull/780/head
                sha = git['rev-parse'][remote + '/' + branch]().strip()
            except ProcessExecutionError:
                sha = ''
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
            for i, merge in enumerate(repo_data.get('merges')):
                if isinstance(merge, dict):
                    if is_sha1(merge.get('ref', '')):
                        continue
                    else:
                        sha = self.find_branch_last_commit(
                            merge.get('remote'), directory, merge.get('ref'))
                        if not sha:
                            continue
                        merge['ref'] = sha
                else:
                    remote, ref = merge.split(' ')
                    # branch is already frozen with commit
                    if is_sha1(ref):
                        continue
                    else:
                        sha = self.find_branch_last_commit(
                            remote, directory, ref)
                        if not sha:
                            continue
                        ref = sha
                        repo_data.get('merges')[i] = ' '.join([remote, ref])
            # Since we freeze every merges, we should always fetch all remotes
            remotes = list(repo_data.get('remotes').keys())
            repo_data['fetch_all'] = remotes
        with open(self.output, 'w') as outfile:
            yaml.dump(conf, outfile, default_flow_style=False)
