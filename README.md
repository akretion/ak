## Ak

### What it is

Ak is a command-line utility that is built on top of [gitaggregator](https://github.com/acsone/git-aggregator).

### Why use it

#### ak build

This is the main command. In your project, you want to organize all of your modules, repos and dependencies without 
too many headaches.
You can define all of your sources from a readable YAML file.

#### other ak commands

There are other useful commands (TODO)

### How to use it

#### ak build, simple version 
* Create a spec.yaml file according to the example (link). Refer to commented lines for
  more explanation on the individual markup lines (TODO)
* Run 'ak build'. The result will be:
  - new ./external-src directory containing all the git repos of your sources with the appropriate branches and merges 
  - new ./links directory containing links to the relevant modules across all repos ./external-src 
* In your Odoo config file, you only need to specify in addons_path:
  - Odoo Core sources
  - The newly created ./links directory

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


### Installation

We strongly recommend using pipx for installing python cli

Install with pipx

```
pipx install -e --spec git+https://github.com/akretion/ak ak --force --include-deps
```

If you don't want to use pipx, you can still use something like this: 

```
python3 -m pip install git+https://github.com/akretion/ak --user
```

Install for dev purpose
```
git clone https://github.com/akretion/ak
cd ak
pipx install -e --spec . ak --force --include-deps
```

