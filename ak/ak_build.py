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
       export WORKON_HOME=`pwd`
       git init # -> si ya deja un init, on dit que le projet a deja ete initie
       wget https://raw.githubusercontent.com/odoo/odoo/10.0/requirements.txt
       pipenv install
       pipenv http://nightly.odoo.com/10.0/nightly/src/odoo_10.0.latest.zip
       pipenv install odoo
       #add odoo addons dans le Pipfile

       export ODOO_RC='/workspace/odoo_base.cfg' # project wide

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
        test = 'pipenv graph | grep "^odoo==" -c'
        if not test:
            raise Exception("Odoo project no init")
        self._exec('pipenv', ['install'])


@Ak.subcommand("freeze")
class AkFreeze(AkBuildFreeze):
    "Freeze dependencies for odoo"

    def main(self):
        self._exec(
            'pipenv',
            ['lock'])

