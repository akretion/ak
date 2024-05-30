"""AK."""
import logging
from plumbum import cli, local
from plumbum.cmd import (mkdir, find, ln, git)
from plumbum.commands.modifiers import FG, TF
from plumbum.commands.processes import ProcessExecutionError
import os
import yaml

from .ak_build import SPEC_YAML, get_repo_key_from_spec

from .ak_sub import AkSub, Ak

@Ak.subcommand("sparse")
class AkSparse(AkSub):
    "git sparse-checkout with modules"

    disable = cli.Flag(
        '--disable', help="disable sparse-checkout", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")
    directory = cli.SwitchAttr(
        ["d", "directory"], group="IO",
        help="Only work in specified directory")
    
    def _generate_sparse_checkout(self, config):
        "'Hide' modules, folder"
        # Do we still need the links when we are using sparse-checkout ?
        # yes, a single dir for addons_path is prefable
        # Plus we don't break compat with "old" version of git for now.
        spec = yaml.load(open(config).read(), Loader=yaml.FullLoader)
        for key, repo in spec.items():
            if self.directory and self.directory != key:
                continue
            modules = repo.pop('modules', False)
            if modules:
                self._set_sparse_checkout(key, modules)

    def _set_sparse_checkout(self, key, paths):
        repo_path = get_repo_key_from_spec(key)
        if not local.path(repo_path + "/.git").exists():
            # directory do not exist
            # or is not managed by git
            # do nothing
            return
        with local.cwd(repo_path):
            if key == 'odoo':
                directories = [
                    dir.name for dir in local.path().list()
                    if dir.isdir() and dir.name[0] != '.' and dir.name != 'addons'
                    # remove files, hiddens (.git), addons
                ]
                paths = ['addons/%s' % path for path in paths]
                paths += directories

            git['sparse-checkout', 'init', '--cone']()
            if self.disable:
               git['sparse-checkout', 'disable']()
            else:
               git['sparse-checkout', "set", paths]()
    
    def main(self, *args):
        config_file = self.config
        self._generate_sparse_checkout(config_file)