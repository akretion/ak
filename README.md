## Ak


Installation:

We deeply recommand you to use pipx for installing python cli

Install

```
pipx install -e --spec git+https://github.com/akretion/ak-odoo-incubator  ak --force --include-deps
```

Install for dev purpose
```
git clone https://github.com/akretion/ak
cd ak
pipx install -e --spec . ak --force --include-deps
```

Usage

```

Usage:
    ak [SWITCHES] [SUBCOMMAND [SWITCHES]] args...

Meta-switches:
    -h, --help         Prints this help message and quits
    --help-all         Prints help messages of all sub-commands and quits
    -v, --version      Prints the program's version and quits

Switches:
    --verbose          Verbose mode

Sub-commands:
    build              Build dependencies for odoo; see 'ak build --help' for more info
    db                 Read db credentials from ERP_CFG.  Add -d flag to the current command to override PGDATABASE
                       Add self.db  Usage: Heritate from this class and call determine_db()  class
                       AkSomething(cli.Application, DbTools): def main(self): self.set_db() # your stuff here print
                       self.db; see 'ak db --help' for more info
    diff               Diff tools. Scan all Odoo module repositories, based on addons_path in the erp config file. For
                       each repository, launch a diff command. For the time being, only git is implemented.; see 'ak
                       diff --help' for more info
    freeze             Freeze dependencies for odoo in config file formated for git aggregator; see 'ak freeze --help'
                       for more info
    migrate            Extraction repository/branch data from buildout to build spec file; see 'ak migrate --help' for
                       more info
    module             Testing Module; see 'ak module --help' for more info
    project            Project task related; see 'ak project --help' for more info
    suggest            Display available modules which are not in modules list of your SPEC_YAML. display i.e.
                       INFO:ak.ak_suggest:   1 modules in branch https://github.com/oca/.../tree/12.0 ['base_...']  By
                       using `include` option, you may filter the output ; see 'ak suggest --help' for more info
```
