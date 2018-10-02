#!/usr/bin/env python3
"""AK."""
import logging

from plumbum.commands.base import BaseCommand

from .ak_sub import Ak

# Hack to show the cmd line execute with plumbum
base_call = BaseCommand.__call__


def custom_call(self, *args, **kwargs):
    logging.info("%s, %s", self, args)
    return base_call(self, *args, **kwargs)


BaseCommand.__call__ = custom_call


def main():
    logging.basicConfig()
    Ak.run()


if __name__ == '__main__':
    main()
