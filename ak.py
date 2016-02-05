#!/usr/bin/env python
import logging
import os
from plumbum import cli, local
from plumbum.cmd import (cat, ls, test, python, grep, gunzip,
    pg_isready, createdb, psql, dropdb, pg_restore)
from plumbum.commands.modifiers import RETCODE, FG, TEE, TF
import os, ConfigParser

BUILDOUT_URL = 'https://raw.github.com/buildout/buildout/master/bootstrap/bootstrap.py'
OPENRPCFG = 'etc/openerp.cfg'

class Ak(cli.Application):
    PROGNAME = "ak"
    VERSION = "1.0"

    @cli.switch("--verbose", help="Verbose mode")
    def set_log_level(self):
        logging.root.setLevel(logging.INFO)
        logging.info('Verbose mode activated')

    def main(self, *args):
        if args:
            print "Unkown command %r" % (args[0],)
            return 1 #return error
        if not self.nested_command:
            print "No command given"
            return 1


@Ak.subcommand("run")
class AkRun(cli.Application):
    """Start openerp"""
    db = cli.SwitchAttr(["d"], str, help="Database")
    debugFlag = cli.Flag(["D", "debug"], help="Debug mode")
    consoleFlag = cli.Flag(['console'], help="Console mode")
    updateFlag = cli.SwitchAttr(["u", "update"], list=True, help="Update module")

    def main(self, *args):
        params = []
        if self.db:
            params += ['-d', self.db]
        if self.debugFlag:
            params += ['--debug']
        if self.updateFlag:
            params += ['-u', str.join(',',self.updateFlag)]

        if self.consoleFlag:
            command = 'bin/python_openerp'
        else:
            command = 'bin/start_openerp'

        return os.execvpe(command, ['command'], local.env)


@Ak.subcommand("build")
class AkBuild(cli.Application):
    "Build dependencies for odoo"

    freezeFlag = cli.Flag(["freeze"], help="Freeze dependencies to frozen.cfg")
    configFlag = cli.SwitchAttr(["c","config"],default=OPENRPCFG, help="Config flag")

    def freeze(self):
        cmd = local['bin/buildout']['-o', 'openerp:freeze-to=frozen.cfg']
        print cmd

    def build(self):
        cmd = local['bin/buildout']['-c', configFlag]
        print cmd

    def main(self, *args):
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
    """Db tools
    Run without args to get a psql prompt
    Credentials are extracted from etc/openerp.cfg
    """
    db = cli.SwitchAttr(["-d"], str, help="Database")
    force = cli.Flag('--force', help="Force", group="IO")

    loadFlag = cli.Flag(["load"], help="Load a dump", group="IO")
    dumpFlag = cli.Flag(["dump"], help="Export a dump", group="IO", requires=['p'])
    path = cli.SwitchAttr(["path","p"], str, help="Path to a file dump", group="IO")

    waitFlag = cli.Flag(["wait"], help="pg_isready", group="Other")
    infoFlag = cli.Flag(["info"], help="info on db crendentials", group="Other")

    dbParams = {
     "db_host": "PGHOST",
     "db_port": "PGPORT",
     "db_name": "PGDATABASE",
     "db_user": "PGUSER",
     "db_password": "PGPASSWORD"
    }

    def log_and_run(self, cmd):
        logging.info(cmd)
        cmd & FG


    def psql(self):
        """Run psql"""
        import os
        os.execvpe('psql',['psql'], local.env)

    def load(self, afile, force):
        p = local.path(afile)

        if not p.is_file():
            raise Exception("input file not found")

        #check if db exists
        cmd = psql["-c", ""]

        if (cmd & TF): #TF = result of cmd as True or False
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

        #set cron to inactive
        #TODO give a flag for that
        self.log_and_run(psql["-c", "UPDATE ir_cron SET active=False;"])


    def dump(self, afile, force):
        """Dump database to file"""
        #TODO choose format
        p = local.path(afile)

        if p.is_file() and not force:
            raise Exception("output file already exists. Use --force")
        self.log_and_run(local['pg_dump'] | local['gzip'] > afile)

    def wait(self):
        """Run pg_isready """
        self.log_and_run(pg_isready)

    def determine_db(self):
        """Extract db parameters from openerp.cfg"""

        #read ini file
        config = ConfigParser.ConfigParser()
        config.readfp(open(OPENRPCFG))
        for ini_key, pg_key in self.dbParams.iteritems():
            val = config.get('options', ini_key)
            if not val == "False":
                logging.info('Set %s to %s' % (pg_key, val))
                local.env[pg_key] = val

        if self.db: #if db is forced by flag
            logging.info("PGDATABASE overwitten by %s", self.db)
            local.env["PGDATABASE"] = self.db

    def info(self):
        """Print information from etc/buildout.cfg"""
        for ini_key, pg_key in self.dbParams.iteritems():
            print ini_key, local.env[pg_key]


    def main(self, *args):
        self.determine_db() #get credentials

        if (self.loadFlag):
            self.load(self.path, self.force)
        elif (self.dumpFlag):
            self.dump(self.path, self.force)
        elif (self.waitFlag):
            self.wait()
        elif (self.infoFlag):
            self.info()
        else:
            self.psql()

if __name__ == "__main__":
    Ak.run()
