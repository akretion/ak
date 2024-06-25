## ak


Installation:

We strongly recommend using pipx for installing Python CLI tools such as ak.

Install with pipx

```
pipx install git+https://github.com/akretion/ak --force --include-deps
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
    build              Build Odoo dependencies; see 'ak build --help' for more info
    freeze             Freeze Odoo dependencies in a config file formatted for git aggregator; see 'ak freeze --help'
                       for more info
    suggest            Display available modules that are not already listed in your SPEC_YAML. display i.e.
                       INFO:ak.ak_suggest:   1 modules in branch https://github.com/oca/.../tree/12.0 ['base_...']  By
                       using `include` option, you may filter the output ; see 'ak suggest --help' for more info
```
