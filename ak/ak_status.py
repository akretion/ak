"""AK."""
import logging

import yaml
from plumbum import cli, local
from plumbum.cmd import cat, git, grep
from plumbum.commands.modifiers import FG
from plumbum.commands.processes import ProcessExecutionError

from .ak_sub import Ak, AkSub

REPO_YAML = "repo.yaml"
SPEC_YAML = "spec.yaml"
FROZEN_YAML = "frozen.yaml"
VENDOR_FOLDER = "external-src"
LOCAL_FOLDER = "local-src"
LINK_FOLDER = "links"
ODOO_FOLDER = "src"
BUILDOUT_SRC = "./buildout.cfg"
PREFIX = "/odoo/"
JOBS = 2

logger = logging.getLogger(__name__)


def get_repo_key_from_spec(key):
    if key == "odoo":
        # put odoo in a different directory
        repo_key = ODOO_FOLDER
    elif key[0:2] == "./":
        # if prefixed with ./ don't change the path
        repo_key = key
    else:
        # put sources in VENDOR_FOLDERS
        repo_key = "./%s/%s" % (VENDOR_FOLDER, key)
    return repo_key


@Ak.subcommand("status")
class AkAnalyse(AkSub):
    "dependencies status for odoo"

    config = cli.SwitchAttr(
        ["c", "config"], default=SPEC_YAML, help="Config file", group="IO"
    )

    def _ensure_viable_installation(self, config):
        if not local.path(config).is_file():
            raise Exception("Config file not found.")

    def main(self, *args):
        config_file = self.config
        self._ensure_viable_installation(config_file)

        spec_data = yaml.safe_load(open(self.config).read()) or {}
        serie = False
        for repo, data in spec_data.items():
            logger.debug("********** in", repo)
            remote = False
            remote_main_branch = False
            if "src" in data:
                remote = "origin"
                serie_candidate = data["src"].split(" ")[-1]
                remote_main_branch = serie_candidate
                if (
                    serie_candidate.endswith(".0")
                    and serie_candidate.split(".")[0].isdigit()
                ):
                    serie = serie_candidate

            elif "merges" in data:
                for index, merge in enumerate(data["merges"]):
                    if index == 0:
                        remote = merge.split(" ")[0]
                        serie_candidate = merge.split(" ")[-1]
                        remote_main_branch = serie_candidate
                        if (
                            serie_candidate.endswith(".0")
                            and serie_candidate.split(".")[0].isdigit()
                        ):
                            serie = serie_candidate
            if not serie:
                raise RuntimeError(f"Unable to figure out Odoo serie for {repo}")

            repo_path = get_repo_key_from_spec(repo)
            if not local.path(repo_path).is_dir():
                print(f"{repo_path} NOT  FOUND!")
                continue

            with local.cwd(repo_path):
                local_module_versions = {}
                # fisrt we get the current module versions from their manifest
                for module in data.get("modules", []):
                    if local.path(f"{module}/__manifest__.py").is_file():
                        module_path = f"{module}/__manifest__.py"
                    elif local.path("__manifest__.py").is_file():
                        module_path = "__manifest__.py"
                    else:
                        continue
                    version = ((cat < module_path) | grep[f"{serie}."])().split(":")[1]
                    local_module_versions[module] = (
                        version.replace('"', "").replace(",", "").strip()
                    )

                # TODO see if we cannot hide the stdout here:
                local["git"]["fetch", remote, remote_main_branch] & FG

                # now we will scan the log between the latest upstream and the common ancestor:
                current_branch = git["rev-parse", "--abbrev-ref", "HEAD"]().strip()
                try:
                    ancestor = git[
                        "merge-base", current_branch, f"{remote}/{remote_main_branch}"
                    ]().strip()
                except ProcessExecutionError:
                    logger.debug("Unable to find merge-base")
                    continue

                # now we will scan the change log for module version bumps:
                try:
                    changes = (
                        git[
                            "log",
                            f"{ancestor}..{remote}/{remote_main_branch}",
                            "--author",
                            "OCA-git-bot",
                        ]
                        | grep[f"{serie}.", "-B4"]
                    )()
                except ProcessExecutionError:
                    logger.debug("UNABLE TO READ CHANGE LOG, LIKELY NO CHANGE")
                    continue
                module_changes = {}
                for module, version in local_module_versions.items():
                    module_changes[module] = []
                    if module in changes:
                        module_change = False
                        upgrade_version = version
                        lines = changes.splitlines()
                        lines.reverse()
                        for line in lines:
                            if line.strip().startswith(f"{module} "):
                                new_version = line.split(" ")[-1]
                                new_version_major = new_version.split(".")[2]
                                version_major = upgrade_version.split(".")[2]
                                if version_major != new_version_major:
                                    module_change = [
                                        "MAJOR",
                                        upgrade_version,
                                        new_version,
                                    ]
                                    upgrade_version = new_version
                                else:
                                    new_version_minor = new_version.split(".")[3]
                                    version_minor = upgrade_version.split(".")[3]
                                    if version_minor != new_version_minor:
                                        module_change = [
                                            "minor",
                                            upgrade_version,
                                            new_version,
                                        ]
                                        upgrade_version = new_version

                            # we got a version change bump commit,
                            # but now we should search for the merge commit
                            # in the commits just before:
                            elif line.strip().startswith("commit ") and module_change:
                                bump_commit = line.strip().split(" ")[1]
                                log = git["log", f"{bump_commit}~", "-n8"]()
                                scan_commit = False
                                for log_line in log.splitlines():
                                    if log_line.strip().startswith("commit "):
                                        scan_commit = log_line.strip().split(" ")[1]
                                    elif log_line.strip().startswith("Merge PR #"):
                                        commit = scan_commit
                                        pr = log_line.split("Merge PR #")[1].split(" ")[
                                            0
                                        ]
                                        module_change.append(commit)
                                        module_change.append(f"gh pr view {pr}")
                                        break
                                if not module_changes.get(module):
                                    module_changes[module] = []
                                module_changes[module].append(module_change)
                                module_change = False

                # print the changes if any:
                if module_changes:
                    repo_printed = False
                    for module, changes in module_changes.items():
                        if not changes:
                            continue
                        if not repo_printed:
                            print(f"\nin {repo}:")
                            repo_printed = True
                        print(f"  {module}:")
                        for change in changes:
                            if len(change) < 5:
                                change.append("undef")
                                change.append("undef")
                            print(
                                f"    {change[1]} -> {change[2]} ({change[0]}) - {change[4]} - ({change[3]})"
                            )
