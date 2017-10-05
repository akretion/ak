# coding: utf-8
"""AK."""
import logging

from plumbum import cli, local
from plumbum.cmd import (
    gunzip, pg_isready, createdb, psql,
    dropdb, pg_restore, pg_dump, git, wget, python)
from plumbum.commands.modifiers import FG, TF, BG, RETCODE
from datetime import datetime
import os
import ConfigParser

from plumbum.commands.base import BaseCommand
from .ak_sub import AkSub, Ak


@Ak.subcommand("db")
class AkDb(AkSub):
    """Read db credentials from ERP_CFG.

    Add -d flag to the current command to override PGDATABASE
    Add self.db

    Usage:
      Heritate from this class and call determine_db()

        class AkSomething(cli.Application, DbTools):
            def main(self):
                self.set_db()
                # your stuff here
                print self.db
    """
    CALL_MAIN_IF_NESTED_COMMAND = False

    dbParams = {
        "db_host": "PGHOST",
        "db_port": "PGPORT",
        "db_name": "PGDATABASE",
        "db_user": "PGUSER",
        "db_password": "PGPASSWORD"
    }

    db = cli.SwitchAttr(["d"], str, help="Database")

    def __init__(self, executable):
        super(AkDb, self).__init__(executable)
        """Extract db parameters from ERP_CFG."""

        config = self.parent.read_erp_config_file()
        for ini_key, pg_key in self.dbParams.iteritems():
            val = config.get('options', ini_key)
            if not val == "False":
                logging.info('Set %s to %s' % (pg_key, val))
                local.env[pg_key] = val

        if self.db:  # if db is forced by flag
            logging.info("PGDATABASE overwitten by %s", self.db)
            local.env["PGDATABASE"] = self.db
        else:
            self.db = local.env["PGDATABASE"]

    def main(self):
        """Run psql."""
        self._exec('psql')


@AkDb.subcommand("load")
class AkDbLoad(AkSub):

    force = cli.Flag('--force', help="Force", group="IO")
    keep_cron = cli.Flag(
        '--keep-cron', help="Keep the cron active", group="IO")

    def main(self, dump_file):
        """Load (restore) a dump from a file.

        Will create a database if not exist already

        :param dump_file: path to dump (can be .gz or .dump)
        :param force: db will be dropped before the load
        """
        p = local.path(dump_file)

        if not p.is_file():
            raise Exception("input file not found")

        # check if db exists
        db = self.parent.db
        if psql[db, "-c", ""] & TF:  # TF = result of cmd as True or False
            if self.force:
                logging.info('DB already exists. Drop and create it')
                dropdb(db)
                createdb(db)
            else:
                print "DB already exist, use --force to force loading"
                return
        else:
            logging.info('DB does ont exists. Create it')
            createdb(db)

        if p.suffix == '.gz':
            gunzip['-c', p] | psql()
        else:
            pg_restore("-O", "-j8", p, '-d', db)

        if not self.keep_cron:
            psql(db, "-c", "UPDATE ir_cron SET active=False")


@AkDb.subcommand("console")
class AkDbConsole(AkSub):

    def main(self):
        """Run psql."""
        self.parent.main()


@AkDb.subcommand("dump")
class AkDbDump(AkSub):

    force = cli.Flag('--force', help="Force", group="IO")

    def main(self, output_name):
        """Dump database to file with pg_dump to native pg format.

        :param output_name: path to dump file
        :param force: overwrite the file if exists

        """
        output_name += '.dump'
        p = local.path(output_name)

        if p.is_file() and not self.force:
            raise Exception("outut file already exists. Use --force")
        (pg_dump["-Fc", self.parent.db] > output_name)()


@AkDb.subcommand("info")
class AkDbInfo(AkSub):
    """Print db informations from etc/buildout.cfg."""

    def main(self):
        for ini_key, pg_key in self.parent.dbParams.iteritems():
            print ini_key, local.env.get(pg_key, '')
