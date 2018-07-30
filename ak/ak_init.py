"""AK."""
import logging
from pathlib import Path
from plumbum import cli, local
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from plumbum.commands.base import BaseCommand

from .ak_sub import AkSub, Ak

logger = logging.getLogger(__name__)
SPEC_YAML = 'spec.yaml'
"""Goal of this file : generate a project strucutre.
May be it's useless
"""

@Ak.subcommand("init")
class AkInit(AkSub):
    "Build dependencies for odoo"

    @staticmethod
    def _warning_spec():
        logger.warning("""
Missing '%s' file in this folder: aborted operation !

Consider to manually create one like this:
--------

myfolder:
    modules: []
    src: https://github.com/OCA/myrepo 12.0

--------

Or if you want to migrate from buildout, just put your buildout.cfg file here
and trigger: ak migrate""" % SPEC_YAML)

    def main(self, *args):
        print("init project")
        if not Path(SPEC_YAML).is_file():
            self._warning_spec()
