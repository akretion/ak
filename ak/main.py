#!/usr/bin/env python
# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import ConfigParser

from plumbum.commands.base import BaseCommand

from .ak_sub import AkSub, Ak

__version__ = '1.5.2'

BUILDOUT_FILE = "buildout.%s.cfg"
WORKSPACE = '/workspace/'
MODULE_FOLDER = WORKSPACE + 'parts/'
ENV = os.environ.get('AK_ENV', 'dev')
UPGRADE_LOG_DIR = 'upgrade-log'


def main():
    Ak.run()

if __name__ == '__main__':
    main()