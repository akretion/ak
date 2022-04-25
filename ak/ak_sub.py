"""AK."""
import logging

from plumbum import cli, local
import os
import configparser

__version__ = "3.0.0"

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
