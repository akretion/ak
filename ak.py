#!/usr/bin/env python
# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (test, python, grep, gunzip, pg_isready,
                         createdb, psql, dropdb, pg_restore)
from plumbum.commands.modifiers import RETCODE, FG, TEE, TF
import os
import ConfigParser

BUILDOUT_URL = ('https://raw.github.com/buildout/'
                'buildout/master/bootstrap/bootstrap.py')
ERP_CFG = 'etc/openerp.cfg'
DEV_BUILD = "buildout.dev.cfg"
PROD_BUILD = "buildout.prod.cfg"
WORKSPACE = '/workspace/'


class Ak(cli.Application):
    PROGNAME = "ak"
    VERSION = "1.0"

    dryrunFlag = cli.Flag(["dry-run"], help="Dry run mode")

    def log_and_run(self, cmd, retcode=FG):
        """Log cmd before exec."""
        logging.info(cmd)
        if (self.dryrunFlag):
            print cmd
            return True
        return cmd & RETCODE

    def log_and_exec(self, cmd, args=[], env=None):
        """Log cmd and execve."""
        logging.info([cmd, args])
        if (self.dryrunFlag):
            print "os.execvpe (%s, %s, env)" % (cmd, [cmd] + args)
            return True
        os.execvpe(cmd, [cmd] + args, env)

    @cli.switch("--verbose", help="Verbose mode")
    def set_log_level(self):
        logging.root.setLevel(logging.INFO)
        logging.info('Verbose mode activated')

    def main(self, *args):
        if args:
            print "Unkown command %r" % (args[0],)
            return 1  # return error
        if not self.nested_command:
            print "No command given"
            return 1


@Ak.subcommand("run")
class AkRun(cli.Application):
    """Start openerp."""

    db = cli.SwitchAttr(["d"], str, help="Database")
    debugFlag = cli.Flag(["D", "debug"], help="Debug mode")
    consoleFlag = cli.Flag(['console'], help="Console mode")
    updateFlag = cli.SwitchAttr(
        ["u", "update"], list=True, help="Update module")

    def main(self, *args):
        params = []
        if self.db:
            params += ['--db-filter', self.db]
        if self.debugFlag:
            params += ['--debug']
        if self.updateFlag:
            params += ['-u', str.join(',', self.updateFlag)]

        if self.consoleFlag:
            command = 'bin/python_openerp'
        else:
            command = 'bin/start_openerp'

        return self.parent.log_and_exec(command, params, local.env)


@Ak.subcommand("build")
class AkBuild(cli.Application):
    "Build dependencies for odoo"

    freezeFlag = cli.Flag(
        ["freeze"], help="Freeze dependencies to frozen.cfg")
    offlineFlag = cli.Flag(
        ["o"], help="Build with only local available source (merges, etc)")
    configFlag = cli.SwitchAttr(
        ["c", "config"], help="Config flag")

    def freeze(self):
        cmd = local['bin/buildout']['-o', 'openerp:freeze-to=frozen.cfg']
        print cmd

    def build(self):
        params = []
        if not self.configFlag:
            if os.path.isfile(WORKSPACE + PROD_BUILD):
                self.configFlag = WORKSPACE + PROD_BUILD
            elif os.path.isfile(WORKSPACE + DEV_BUILD):
                self.configFlag = WORKSPACE + DEV_BUILD
            else:
                # TODO replace with an adhoc exception
                raise Exception("Missing buildout config file")
        if self.offlineFlag:
            params.append('-o')
        # how to add params for optionnal args ???
        cmd = local['bin/buildout']['-c', self.configFlag]
        print cmd

    def main(self, *args):
        self.build()
        True

# TODO: is it really ak's job to install buildout ? why not pgsql also ?
#        if not self.is_installed():
#            if cli.terminal.ask(
#                "Buildout not found. Download it ?", default="Y"):
#                self.download_and_install()
#            else:
#                raise Exception("Can't continue without buildout")
#
#
#    def is_installed(self):
#        logging.info('Will check if buildout is installed')
#        return (test["-f", 'bin/buildosut'] & RETCODE)
#
#    def download_and_install(self):
#        logging.info('Will download buildout from %s' % BUILDOUT_URL)
#        wget = local['wget']
#        cmd = wget["BUILDOUT_URL", "-O -"] | python
#        print "c bon"


@Ak.subcommand("db")
class AkDb(cli.Application):
    """Db tools.

    Run without args to get a psql prompt
    Credentials are extracted from etc/openerp.cfg

    """

    db = cli.SwitchAttr(["-d"], str, help="Database")
    force = cli.Flag('--force', help="Force", group="IO")

    loadFlag = cli.Flag(["load"], group="IO",
                        help="Load a dump")
    dumpFlag = cli.Flag(["dump"], group="IO", requires=['p'],
                        help="Export a dump")
    path = cli.SwitchAttr(["path", "p"], str, group="IO",
                          help="Path to a file dump")
    waitFlag = cli.Flag(["wait"], group="Other",
                        help="pg_isready")
    infoFlag = cli.Flag(["info"], group="Other",
                        help="info on db crendentials")
    passFlag = cli.Flag(["admin-password"], group="Other",
                        help="Change odoo admin password")

    dbParams = {
        "db_host": "PGHOST",
        "db_port": "PGPORT",
        "db_name": "PGDATABASE",
        "db_user": "PGUSER",
        "db_password": "PGPASSWORD"
    }

    def psql(self):
        """Run psql."""
        self.log_and_exec('psql', [], local.env)

    def load(self, afile, force):
        """Load (restore) a dump from a file.

        Will create a database if not exist already

        :param afile: path to dump (can be .gz or .tar)
        :param foce: db will be dropped before the load
        """
        p = local.path(afile)

        if not p.is_file():
            raise Exception("input file not found")

        # check if db exists
        cmd = psql["-c", ""]

        if (self.log_and_run(cmd, TF)):  # TF = result of cmd as True or False
            if force:
                logging.info('DB already exists. Drop and create it')
                self.log_and_run(dropdb)
                self.log_and_run(createdb)

        else:
            logging.info('DB does ont exists. Create it')
            self.log_and_run(createdb)

        if p.suffix == '.gz':
            self.log_and_run(gunzip['-c', p] | psql)
        else:
            self.log_and_run(pg_restore["-O", p])

        # set cron to inactive
        # TODO give a flag for that
        self.log_and_run(psql["-c", "'UPDATE ir_cron SET active=False;'"])

    def dump(self, afile, force):
        """Dump database to file with pg_dump then gzip.

        :param afile: path to dump file
        :param force: overwrite the file if exists

        """
        # TODO choose format
        p = local.path(afile)

        if p.is_file() and not force:
            raise Exception("output file already exists. Use --force")
        self.log_and_run(local['pg_dump'] | local['gzip'] > afile)

    def wait(self):
        """Run pg_isready."""
        self.log_and_run(pg_isready)

    def info(self):
        """Print db informations from etc/buildout.cfg."""
        for ini_key, pg_key in self.dbParams.iteritems():
            print ini_key, local.env.get(pg_key, '')

    def changeAdminPassword(self, args):
        """Change admin password."""

        new_pass = (args or [False])[0]

        if (not new_pass):  # not provided by cli
            new_pass = cli.terminal.prompt(
                'New admin password ?', str, "admin")

        print "New admin password for %s is : '%s'" % (self.db, new_pass)

        code = """session.open(db='%s')"
user_ids = session.registry('res.users').search(session.cr, 1, [])",
for user in session.registry('res.users').browse(session.cr, 1, user_ids):",
    user.write({'password': '%s' })",
session.cr.commit()
""" % (self.db, new_pass)
        print local['echo'][code] | local['ak']['console']
        # TODO: run this command and test it !

    def determine_db(self):
        """Extract db parameters from openerp.cfg."""
        # internal func

        # read ini file
        if not local.path(ERP_CFG).is_file():
            logging.warn("%s not found" % ERP_CFG)
        else:
            config = ConfigParser.ConfigParser()
            config.readfp(open(ERP_CFG))
            for ini_key, pg_key in self.dbParams.iteritems():
                val = config.get('options', ini_key)
                if not val == "False":
                    logging.info('Set %s to %s' % (pg_key, val))
                    local.env[pg_key] = val

        if self.db:  # if db is forced by flag
            logging.info("PGDATABASE overwitten by %s", self.db)
            local.env["PGDATABASE"] = self.db

    def main(self, *args):

        #  bind functions with AK
        self.log_and_run = self.parent.log_and_run
        self.log_and_exec = self.parent.log_and_exec

        self.determine_db()  # get credentials

        if (self.loadFlag):
            self.load(self.path, self.force)
        elif (self.dumpFlag):
            self.dump(self.path, self.force)
        elif (self.waitFlag):
            self.wait()
        elif (self.infoFlag):
            self.info()
        elif (self.passFlag):
            self.changeAdminPassword(args)
        else:
            self.psql()

if __name__ == "__main__":
    Ak.run()
