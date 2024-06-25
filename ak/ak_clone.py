"""AK."""
import logging
from plumbum import cli, local
from plumbum.cmd import (mkdir, find, ln, git)
from plumbum.commands.modifiers import FG, TF
from plumbum.commands.processes import ProcessExecutionError
import yaml

from .ak_build import SPEC_YAML, get_repo_key_from_spec

from .ak_sub import AkSub, Ak
logger = logging.getLogger(__name__)


@Ak.subcommand("clone")
class AkClone(AkSub):
    "git clone partial"

    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO")
    directory = cli.SwitchAttr(
        ["d", "directory"], group="IO",
        help="Only work in specified directory")

    def _generate_git_clone(self, config):
        "Partial clone if possible"
        spec = yaml.load(open(config).read(), Loader=yaml.FullLoader)
        for key, repo in spec.items():
            if self.directory and self.directory != key:
                continue
            self._partial_clone(key, repo)

    def _partial_clone(self, key, repo):
        repo_path = get_repo_key_from_spec(key)
        if local.path(repo_path + '/.git').exists():
            # we test .git existence because odoo folder
            # may already exists but is empty

            # .git already defined; we quit
            return

        if 'src' in repo:
            repo_url, branch, *err = repo['src'].split(' ')
            if len(err) > 0:
                logger.warning("Can't parse %s" % repo['src'])
                clone_with_filter = False
            else:
                clone_with_filter = True
        else:
            clone_with_filter = False

            # if modules: add --sparse

        if clone_with_filter:
            logger.warning('Will clone fast %s in %s ' % (repo_url, key))
            if not local.path(repo_path).exists():
                # ensure dir exists
                local.path(repo_path).mkdir()

            with local.cwd(repo_path):
                # was previously blob:none
                # changed to tree:0 because it as very positive impact on odoo
                # git['clone', '--filter=blob:none', '--no-checkout', repo_url, '-b', branch, '.']()
                git['clone', '--filter=tree:0', '--no-checkout', repo_url, '-b', branch, '.']()
        else:
            # long format are not supported
            # but if a empty dir already exist
            # we git init inside to not fail in a strange
            # behavior of git-aggretator
            # we want to preserve the dir because it may
            # be a subvolume or a mounted directory
            if local.path(repo_path).exists():
                with local.cwd(repo_path):
                    # clone without filter
                    git["init", "."]()

    def main(self, *args):
        config_file = self.config
        self._generate_git_clone(config_file)
