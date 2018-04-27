"""AK."""
from pathlib import Path
import logging
import yaml
from plumbum import cli

from .ak_sub import AkSub, Ak
from .ak_build import SPEC_YAML

logger = logging.getLogger(__name__)

BUILDOUT_SRC = './buildout.cfg'


@Ak.subcommand("migrate")
class AkMigrate(AkSub):
    """Extraction repository/branch data from buildout to build spec file"""

    withrevision = cli.Flag(
        '--withrevision', help="Include merge revisions lines", default=False)

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
                        line[:line.find('git http')].replace(' ', '') == '']
        if not self.withrevision:
            lines = [line for line in lines if 'revisions' not in line]
        return lines

    def _convert2dict(self, lines):
        data = []
        for line in lines:
            subs = line.split()
            repo = subs[1].replace('parts/', '')
            node = {
                'src': '%s %s' % (subs[0], subs[2]),
                'modules': None,
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
            output.write(file_content)
