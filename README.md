## Ak

```

Usage:
    ak [SWITCHES] [SUBCOMMAND [SWITCHES]] args...

Meta-switches
    -h, --help         Prints this help message and quits
    --help-all         Print help messages of all subcommands and quit
    -v, --version      Prints the program's version and quits

Switches
    --dry-run          Dry run mode
    --verbose          Verbose mode

Subcommands:
    build              Build dependencies for odoo; see 'ak build --help' for more info
    db                 Read db credentials from ERP_CFG.  Add -d flag to the current command to override PGDATABASE Add self.db  Usage: Heritate from this
                       class and call determine_db()  class AkSomething(cli.Application, DbTools): def main(self): self.set_db() # your stuff here print
                       self.db; see 'ak db --help' for more info
    diff               Diff tools. Scan all Odoo module repositories, based on addons_path in the erp config file. For each repository, launch a diff
                       command. For the time being, only git is implemented.; see 'ak diff --help' for more info
    freeze             Freeze dependencies for odoo; see 'ak freeze --help' for more info
    run                Start odoo.; see 'ak run --help' for more info
    upgrade            Upgrade odoo.; see 'ak upgrade --help' for more info
```
