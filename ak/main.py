#!/usr/bin/env python
# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import configparser

from plumbum.commands.base import BaseCommand

from .ak_sub import AkSub, Ak

__version__ = '1.5.2'

BUILDOUT_FILE = "buildout.%s.cfg"
WORKSPACE = '/workspace/'
MODULE_FOLDER = WORKSPACE + 'parts/'
ENV = os.environ.get('AK_ENV', 'dev')
UPGRADE_LOG_DIR = 'upgrade-log'

# Hack to show the cmd line execute with plumbum
base_call = BaseCommand.__call__

def custom_call(self, *args, **kwargs):
    logging.info("%s, %s", self, args)
    return base_call(self, *args, **kwargs)

BaseCommand.__call__ = custom_call


def main():
    Ak.run()

if __name__ == '__main__':
    main()
