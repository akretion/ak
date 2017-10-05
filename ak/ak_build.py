# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (
    gunzip, git, wget, python)
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import ConfigParser

from plumbum.commands.base import BaseCommand

from .ak_sub import AkSub, Ak


@Ak.subcommand("init")
class AkInit(AkSub):
    "Build dependencies for odoo"

    def main(self, *args):
       print "init project"
       print """
       propose de selectionner une majeur ?
       pipenv --two
       pip install nightly.odoo.com
       add odoo addons dans le Pipfile
       """




class AkBuildFreeze(AkSub):

    config = cli.SwitchAttr(
        ["c", "config"], help="Config flag")

    def __init__(self, *args, **kwargs):
        super(AkBuildFreeze, self).__init__(*args, **kwargs)
        if not self.config:
            buildout_file_path = os.path.join(WORKSPACE, BUILDOUT_FILE % ENV)
            if os.path.isfile(buildout_file_path):
                self.config = buildout_file_path
            else:
                raise Exception(
                    "Missing buildout config file, %s" % buildout_file_path)


@Ak.subcommand("build")
class AkBuild(AkBuildFreeze):
    "Build dependencies for odoo"

    def main(self, *args):
        if not os.path.exists('bin/buildout'):
            self.download_and_install()
        params = ['-c', self.config]
        if self.offline:
            params.append('-o')
        self._exec('bin/buildout', params)


@Ak.subcommand("freeze")
class AkFreeze(AkBuildFreeze):
    "Freeze dependencies for odoo"

    def main(self):
        self._exec(
            'bin/buildout',
            ['-c', self.config, '-o', 'openerp:freeze-to=frozen.cfg'])

