# coding: utf-8
from plumbum import local
from plumbum.commands.modifiers import FG, TF

"""We ensure ak build spec.yaml will generate a correct repos.yaml ."""
ak = local['ak']
cmp = local['cmp']

test = '/tests/build/'
repos = local.cwd + test + 'repos.yaml'


def build_and_cmp(name, target):
    source = local.cwd + test + name
    with local.tempdir() as tmp:
        with local.cwd(tmp):
            # local['cp'][target][name]()
            ak['build']['--fileonly'][source] & FG
            assert cmp[target][name] & TF


def test_no_changes():
    """Ensure repos.yaml can be build."""
    name = 'repos.yaml'
    build_and_cmp(name, repos)


def test_without_target():
    """Ensure target can be reconstructed."""
    name = 'without_target.yaml'
    build_and_cmp(name, repos)


def test_with_modules():
    """Ensure modules will be removed from gitaggregate."""
    name = 'with_modules.yaml'
    build_and_cmp(name, repos)


def test_short():
    """Ensure it will construct repos from short version."""
    name = 'short.yaml'
    build_and_cmp(name, repos)
