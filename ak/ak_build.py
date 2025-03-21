"""AK."""
import logging
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
PREFIX = '/odoo/'
JOBS = 2

logger = logging.getLogger(__name__)


def is_sha1(maybe_sha):
    if isinstance(maybe_sha, float):
        return False
    maybe_sha = maybe_sha or ''
    if len(maybe_sha) != 40:
        return False
    try:
        int(maybe_sha, 16)
    except ValueError:
        return False
    return True

def parse_src(src):
    """ Src is
    <src> <branch>
    <src> <branch> <commit>
    """
    splitted = src.split(' ')
    if len(splitted) == 2:
        return splitted[0], splitted[1], None
    elif len(splitted) == 3:
        return splitted
    else:
        raise Exception(
            'Src must be in the format '
            'http://github.com/oca/server-tools 10.0 <optional sha>')


def get_repo_key_from_spec(key):
    if key == 'odoo':
        # put odoo in a different directory
        repo_key = ODOO_FOLDER
    elif key[0:2] == './':
        # if prefixed with ./ don't change the path
        repo_key = key
    else:
        # put sources in VENDOR_FOLDERS
        repo_key = u'./%s/%s' % (VENDOR_FOLDER, key)
    return repo_key


def is_spec_simplified_format(yaml_data):
    if yaml_data.get('remotes'):
        return False
    return True


@Ak.subcommand("build")
class AkBuild(AkSub):
    "Build Odoo dependencies"

    fileonly = cli.Flag(
        '--fileonly', help="Just generate the %s" % REPO_YAML, group="IO")
    linksonly = cli.Flag(
        '--links', help="Generate links in %s" % LINK_FOLDER, group="IO")
    output = cli.SwitchAttr(
        ["o", "output"], default=REPO_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")
    frozen = cli.SwitchAttr(
        ["f", "frozen"], default=FROZEN_YAML, help="Frozen file", group="IO")
    directory = cli.SwitchAttr(
        ["d", "directory"], group="IO",
        help="Refresh aggregation of a specific directory "
             "(this directory must exists) "
             "shortcut for `gitaggregate -c repo.yaml -d my_dir`")
    jobs = cli.SwitchAttr(
        ['j', 'jobs'], int,
        default=JOBS,
        help="Number of concurrent jobs")

    def _convert_repo(self, repo, frozen):
        if not is_spec_simplified_format(repo):
            repo.pop('modules', None)
            if not repo.get('target'):
                repo['target'] = '%s merged' % list(repo['remotes'].keys())[0]
            if frozen:
                merges = repo.get('merges', [])
                for index, merge in enumerate(merges):
                    if isinstance(merge, dict):
                        ref = merge['ref']
                        remote = merge['remote']
                        if is_sha1(ref):
                            continue
                        frozen_sha = frozen.get(remote, {}).get(ref)
                        if frozen_sha:
                            merge['ref'] = frozen_sha
                    # simple format
                    else:
                        remote, ref = merge.split(' ')
                        if is_sha1(ref):
                            continue
                        frozen_sha = frozen.get(remote, {}).get(ref)
                        if frozen_sha:
                            merges[index] = "%s %s" % (remote, frozen_sha)
            return repo
        else:
            src, branch, commit = parse_src(repo['src'])
            if not commit:
                commit = frozen.get('origin', {}).get(branch)

            repo_dict = {
                'remotes': {'origin': src},
                'merges': ['origin %s' % (commit or branch)],
                'target': 'origin %s' % branch,
            }
            depth = repo.get('depth')
            if depth:
                logger.warning('Depth is deprecated. Remove it from your spec.yml')
            if repo.get('shell_command_after'):
                repo_dict['shell_command_after'] = repo['shell_command_after']
            return repo_dict

    def _generate_repo_yaml(self, config, frozen):
        repo_conf = {}
        config = yaml.safe_load(open(config).read())
        frozen_data = {}
        if local.path(frozen).is_file():
            frozen_data = yaml.safe_load(open(frozen).read()) or {}

        for key in config:
            if config[key].get("prebuild"):
                print("Use prebuild modules for repo %s" % key)
                continue

            repo_key = get_repo_key_from_spec(key)
            repo_conf[repo_key] = self._convert_repo(
                config[key], frozen_data.get(key, {}))
        data = yaml.safe_dump(repo_conf)
        with open(self.output, 'w') as output:
            output.write(data)

    def _generate_links(self, config):
        "Link modules defined in spec.yml/yaml in modules folder"
        spec = yaml.load(open(config).read(), Loader=yaml.FullLoader)
        dest_path = local.path(LINK_FOLDER)
        for key, repo in spec.items():
            modules = repo.pop('modules', [])
            self._set_links(key, modules, dest_path, repo.get('prebuild'))

    def _update_dir(self, path, clear_dir=False):
        "Create dir and remove links"
        if not path.exists():
            logger.debug('mkdir %s' % path)
            mkdir(path)
        if clear_dir:
            with local.cwd(path):
                logger.debug('rm all links from %s' % path)
                find['.']['-type', 'l']['-delete']()

    def _set_links(self, key, modules, dest_path, prebuild):
        for module in modules:
            if prebuild:
                base = '/prebuild'
            else:
                base = '..'

            if key == 'odoo':
                src = '%s/src/addons/%s' % (base, module)
            else:
                src = '%s/%s/%s/%s' % (base, VENDOR_FOLDER, key, module)
            ln['-s', src, dest_path]()
            if not local.path(dest_path / module).access():
                logger.warning("Module %s/%s not found. Try `ak sparse`" %
                    (key, module))



    def _print_addons_path(self, config):
        """Build the addons path from the spec.yaml file.

        Modules specified in spec.yaml are linked in the "link"
        repos without modules are added explicitely added to the path"""
        spec = yaml.load(open(config).read(), Loader=yaml.FullLoader)
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

        # Construct absolute path, better for odoo config file.
        abs_path = ",".join([PREFIX + repo_path for repo_path in paths])
        print('Addons path for your config file: ', abs_path)

    def _ensure_viable_installation(self, config):
        if not local.path(config).is_file():
            raise Exception("Config file not found.")
        self._update_dir(local.path(VENDOR_FOLDER))
        self._update_dir(local.path(LINK_FOLDER), clear_dir=True)

    def main(self, *args):
        config_file = self.config
        self._ensure_viable_installation(config_file)
        force_directory = self.directory and get_repo_key_from_spec(self.directory) 

        if not self.linksonly:
            self._generate_repo_yaml(config_file, self.frozen)
            aggregator_config_file = self.output
            if self.fileonly:
                return
            args = ['-c', aggregator_config_file]
            if force_directory:
                if not local.path(force_directory).exists():
                    raise Exception(
                        "\nSpecified directory './%s' doesn't "
                        "exists in your system" % force_directory)
                args.append(['-d', force_directory])
            args.append(['-j', self.jobs])
            local['gitaggregate'][args] & FG

        self._generate_links(config_file)
        # print addons_path should be called with spec.yml
        # in order to have the module key
        self._print_addons_path(self.config)


@Ak.subcommand("freeze")
class AkFreeze(AkSub):
    "Freeze Odoo dependencies in a config file formatted for git aggregator"

    output = cli.SwitchAttr(
        ["o", "output"], default=FROZEN_YAML, help="Output file", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")

    def find_branch_last_commit(self, directory, remote, branch):
        repo_path = get_repo_key_from_spec(directory)
        with local.cwd(repo_path):
            try:
                logger.info("get sha for {} {}".format(remote, branch))
                if branch.startswith("refs/pull"):
                    sha = git['ls-remote'][remote, branch]().split()[0]
                else:
                    sha = git['rev-parse']['{}/{}'.format(remote, branch)]().strip()
            except ProcessExecutionError:
                sha = ''
        if not sha:
            raise Exception(
                "Error when trying to find the commit "
                "number for repo %s and branch %s"
                % (directory, branch))
        return sha

    def update_frozen_dict_conf(
            self, frozen, previous_frozen, directory, remote, ref):
        if is_sha1(ref):
            # This branch is already freeze in spec
            # do not add additional freeze here
            return
        sha = previous_frozen.get(directory, {}).get(remote, {}).get(ref)
        if not sha:
            sha = self.find_branch_last_commit(directory, remote, ref)
        frozen_branch = {ref: sha}
        frozen[directory] = frozen.get(directory, {})
        frozen[directory][remote] = frozen[directory].get(remote, {})
        frozen[directory][remote].update(frozen_branch)

    def main(self, *args):
        """
            Build the frozen.yaml file. Take spec.yaml file and for each
            branch, if no commit is specified, add the commit in the frozen file
            If the branch already exists in the frozen file, keep it and do not
            update it.
            Note: the frozen commit is the last commit of the remote branch
            based on existing fetch done by the build
        """
        if not os.path.isfile(self.config):
            raise Exception(
                "Missing yaml config file %s" % self.config)

        with open(self.config, 'r') as myfile:
            conf = yaml.load(myfile, Loader=yaml.FullLoader)
        frozen = {}
        if not os.path.isfile(self.output):
            previous_frozen = {}
        else:
            with open(self.output, 'r') as myfrozenfile:
                previous_frozen = yaml.load(
                    myfrozenfile, Loader=yaml.FullLoader)

        for directory, spec_data in conf.items():
            if is_spec_simplified_format(spec_data):
                remote = 'origin'
                src, ref, commit = parse_src(spec_data['src'])
                self.update_frozen_dict_conf(
                    frozen, previous_frozen, directory, remote, ref)
            else:
                for i, merge in enumerate(spec_data.get('merges')):
                    if isinstance(merge, dict):
                        ref = str(merge.get('ref'))
                        remote = merge.get('remote')
                    else:
                        remote, ref = merge.split(' ')
                    self.update_frozen_dict_conf(
                        frozen, previous_frozen, directory, remote, ref)

        with open(self.output, 'w') as outfile:
            yaml.dump(frozen, outfile, default_flow_style=False)
