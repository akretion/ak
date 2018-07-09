# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
import os
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

__version__ = "2.0.0"

ERP_CFG = local.env.get('ERP_CFG_PATH', 'odoo.cfg')
WORKSPACE = '.'


class AkSub(cli.Application):

    def _exec(self, *args, **kwargs):
        local.env['WORKON_HOME'] = WORKSPACE
        local.cwd.chdir(WORKSPACE)
        return self.parent._exec(*args, **kwargs)


class Ak(cli.Application):
    PROGNAME = "ak"
    VERSION = __version__

    def _exec(self, cmd, args=[]):
        """Run a command in the same process and log it
        this will replace the current process by the cmd"""
        logging.info([cmd, args])
        os.execvpe(cmd, [cmd] + args, local.env)

    def read_erp_config_file(self):

        if local.path(ERP_CFG).is_file():
            config_path = ERP_CFG
        elif local.path(WORKSPACE + ERP_CFG).is_file():
            config_path = WORKSPACE + ERP_CFG
        else:
            raise Exception("Missing ERP config file %s" % ERP_CFG)
        config = configparser.ConfigParser()
        config.readfp(open(config_path))
        return config

    @cli.switch("--verbose", help="Verbose mode")
    def set_log_level(self):
        logging.root.setLevel(logging.INFO)
        logging.info('Verbose mode activated')

    def main(self, *args):
        if args:
            print ("Unkown command %r", args[0])
            return 1  # return error
        if not self.nested_command:
            print("No command given")
            return 1
