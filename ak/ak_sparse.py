"""AK."""

from plumbum import cli, local
from plumbum.cmd import git
import yaml

from .ak_build import SPEC_YAML, get_repo_key_from_spec

from .ak_sub import AkSub, Ak


@Ak.subcommand("sparse")
class AkSparse(AkSub):
    "git sparse-checkout with modules"

    disable = cli.Flag("--disable", help="disable sparse-checkout", group="IO")
    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO"
    )
    directory = cli.SwitchAttr(
        ["d", "directory"], group="IO", help="Only work in specified directory"
    )

    def _generate_sparse_checkout(self, config):
        "'Hide' modules, folder"
        # Do we still need the links when we are using sparse-checkout ?
        # yes, a single dir for addons_path is prefable
        # Plus we don't break compat with "old" version of git for now.
        spec = yaml.load(open(config).read(), Loader=yaml.FullLoader)
        for key, repo in spec.items():
            if self.directory and self.directory != key:
                continue
            modules = repo.pop("modules", False)
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
            if key == "odoo":
                cmd = (
                    # may be we can write a better cone filter
                    # we want everything appart /addons
                    git["ls-tree"]["-d"]["--name-only"]["HEAD"]
                )

                # ls-files gives us all the files
                directories = cmd().splitlines()
                paths = ["addons/%s" % path for path in paths]
                paths += directories
                paths.remove("addons")  # remove ./addons/

            if self.disable:
                git["sparse-checkout", "disable"]()
            else:
                git["sparse-checkout", "set", paths]()

    def main(self, *args):
        config_file = self.config
        self._generate_sparse_checkout(config_file)
