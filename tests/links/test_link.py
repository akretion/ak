# coding: utf-8
from plumbum import local


"""We ensure ak build -c spec.yaml --links will generate a correct path."""
ak = local['ak']
cp = local['cp']
cat = local['cat']

test = '/tests/links/'
expected_output = local.cwd + test + 'expected_output.txt'


def build_and_cmp(name, target):
    source = local.cwd + test + name
    with local.tempdir() as tmp:
        with local.cwd(tmp):
            cp[source]['spec.yaml']()
            produced = ak['build']['--links']()
            start = len("('Addons path for your config file: , ''")
            end = -len("')\n")

            paths = produced[start:end].split(',')
            paths.sort()

            open('output.txt', 'w').write(','.join(paths))

            assert cat['output.txt']() == cat[target]()


def test_ak_link():
    """Ensure it will construct repos from short version."""
    name = 'spec.yaml'
    build_and_cmp(name, expected_output)
