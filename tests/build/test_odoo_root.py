# coding: utf-8
"""Test the --odoo-root CLI option and AK_ODOO_ROOT env var."""
import os
import sys
from plumbum import local
from plumbum.commands.modifiers import TF

import yaml

# Use the local ak package, not any system-installed binary
sys.path.insert(0, str(local.cwd))
from ak.main import main as ak_main

cp = local['cp']

test = '/tests/build/'
spec = local.cwd + test + 'short.yaml'


def _run_ak_build(*args, env=None):
    """Run ak build with given args, returning stdout."""
    import io
    from contextlib import redirect_stdout
    
    old_argv = sys.argv[:]
    old_env = {}
    try:
        sys.argv = ['ak', 'build'] + list(args)
        if env:
            for k, v in env.items():
                old_env[k] = os.environ.get(k)
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        
        f = io.StringIO()
        with redirect_stdout(f):
            try:
                ak_main()
            except SystemExit:
                pass
        return f.getvalue()
    finally:
        sys.argv = old_argv
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_default_prefix():
    """Ensure default prefix is '/odoo/'."""
    with local.tempdir() as tmp:
        with local.cwd(tmp):
            cp[spec]['spec.yaml']()
            output = _run_ak_build('--links', env={'AK_ODOO_ROOT': None})
            assert "Addons path for your config file:  /odoo/" in output


def test_env_var_prefix():
    """Ensure AK_ODOO_ROOT env var is used."""
    with local.tempdir() as tmp:
        with local.cwd(tmp):
            cp[spec]['spec.yaml']()
            output = _run_ak_build(
                '--links', env={'AK_ODOO_ROOT': '/custom/path/'})
            assert "Addons path for your config file:  /custom/path/" in output


def test_cli_option_prefix():
    """Ensure --odoo-root CLI option overrides env var."""
    with local.tempdir() as tmp:
        with local.cwd(tmp):
            cp[spec]['spec.yaml']()
            output = _run_ak_build(
                '--links', '--odoo-root', '/from/cli/',
                env={'AK_ODOO_ROOT': '/from/env/'})
            assert "Addons path for your config file:  /from/cli/" in output


def test_cli_option_without_trailing_slash():
    """Ensure prefix without trailing slash works (user responsibility)."""
    with local.tempdir() as tmp:
        with local.cwd(tmp):
            cp[spec]['spec.yaml']()
            output = _run_ak_build(
                '--links', '--odoo-root', '~/DEV/odoo18')
            assert "Addons path for your config file:  ~/DEV/odoo18" in output
