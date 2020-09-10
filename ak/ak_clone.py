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

@Ak.subcommand("clone")
class AkClone(AkSub):
    "git clone partial"

    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")
    directory = cli.SwitchAttr(
        ["d", "directory"], group="IO",
        help="Only work in specified directory")
    
    def _generate_git_clone(self, config):
        "'Hide' modules, folder"
        spec = yaml.load(open(config).read(), Loader=yaml.FullLoader)
        for key, repo in spec.items():
            if self.directory and self.directory != key:
                continue
            self._partial_clone(key, repo)

    def _partial_clone(self, key, repo):
        repo_path = get_repo_key_from_spec(key)
        is_new = False
        if not local.path(repo_path).exists():
            # init with no checkout
            local.path(repo_path).mkdir()
            is_new = True
        with local.cwd(repo_path):
            if not is_new:
                return
            if 'src' in repo:
                repo_url, branch, *err = repo['src'].split(' ')
                if len(err) > 0:
                    print('cant parse %s' % repo['src'])
                    clone = False
                else:
                     clone = True
            else:
                clone = False

            if clone:
                print('Will clone fast %s ' % repo_url)
                git['clone', '--filter=blob:none', '--no-checkout', repo_url, '-b', branch, '.']()
        if is_new and not clone:
            print('will delete empty dir')
            local.path(repo_path).delete()
            
    
    def main(self, *args):
        config_file = self.config
        self._generate_git_clone(config_file)
