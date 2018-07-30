"""AK."""
from pathlib import Path
import logging
import yaml
from plumbum import cli, local
import os

from .ak_sub import AkSub, Ak
from .ak_build import SPEC_YAML, BUILDOUT_SRC

logger = logging.getLogger(__name__)


@Ak.subcommand("migrate")
class AkMigrate(AkSub):
    """Extraction repository/branch data from buildout to build spec file"""

    withrevision = cli.Flag(
        '--withrevision', help="Include merge revisions lines", default=False)
    db = cli.SwitchAttr(
        ["d", "database"],
        help="Populate modules variable from specified database")

    def main(self):
        if not Path(BUILDOUT_SRC).is_file():
            logger.warning("Missing %s file in this folder: "
                           "nothing to migrate" % BUILDOUT_SRC[2:])
        else:
            logger.info(self.__doc__)
            lines = self._extract_git_lines()
            lines.sort()
            data = self._convert2dict(lines)
            self._write_yaml(data)

    def _extract_git_lines(self):
        with open(BUILDOUT_SRC, 'r') as f:
            lines = [line.rstrip('\n')[line.find('git http') + 4:]
                     for line in f
                     if 'git http' in line and
                        (line[:line.find('git http')].replace(' ', '') in
                         ('', 'version='))]
        if not self.withrevision:
            lines = [line for line in lines if 'revisions' not in line]
        return lines

    def _get_repo_installed_modules(self, modules, rel_path):
        with local.cwd(rel_path):
            files = os.listdir(os.getcwd())
            repo_modules = [m for m in files if m in modules]
            return repo_modules

    def _convert2dict(self, lines):
        data = []
        if self.db:
            res_sql = local['psql'](
                self.db, "-c",
                "SELECT name FROM ir_module_module WHERE state in "
                "('installed', 'to upgrade')")
            modules = res_sql.split('\n')
            modules = [m.strip()
                       for m in modules
                       if m.strip() != 'name' and
                       '---' not in m.strip() and
                       'lignes)' not in m.strip() and
                       m.strip()]
        for line in lines:
            repo_modules = []
            subs = line.split()
            if self.db:
                rel_path = subs[1]
                if 'parts' not in rel_path:
                    rel_path = 'parts/' + rel_path
                repo_modules = self._get_repo_installed_modules(
                    modules, rel_path)
            repo = subs[1].replace('parts/', '')
            node = {
                'src': '%s %s' % (subs[0], subs[2]),
                # Put a random char '-' so that yaml does not consider it as a
                # list when dumping it and we can remove it at this end...
                'modules': repo_modules and (
                    "-[%s]" % ','.join(repo_modules) or None)
            }
            data.append({'./%s' % repo: node})
        return data

    def _write_yaml(self, data):
        with open(SPEC_YAML, 'w') as output:
            file_content = yaml.dump(data, default_flow_style=False)
            # format fine tuneed
            file_content = file_content.replace('- ./', '\n./')
            file_content = file_content.replace('null', '[]')
            file_content = file_content.replace('.git', '')
            # Ugly workaround to avoid wrong display of modules in file
            file_content = file_content.replace('modules: -[', 'modules: [')
            output.write(file_content)
