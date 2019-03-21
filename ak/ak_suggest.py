"""AK."""
import logging
import yaml
import os
import ast
from plumbum import cli, local


from .ak_sub import AkSub, Ak
from .ak_build import SPEC_YAML, VENDOR_FOLDER


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MANIFEST_FILE_NAME = ('__manifest__', '__openerp__')
UNRELEVANT_DIRECTORIES = ('setup', '.git')


@Ak.subcommand("suggest")
class AkSuggest(AkSub):
    """ Display available modules which are not in modules list of your SPEC_YAML.
        display i.e.
INFO:ak.ak_suggest: 1 modules in branch https://github.com/oca/server-backend/tree/12.0 ['base_suspend_security']

    By using `include` option, you may filter the output
        """

    include = cli.SwitchAttr(
        ["i", "include"],
        help="Only display suggestions when one of the strings provided "
             "is a part of the branch name.\n"
             "Several strings possible with a comma separator.")

    def _ensure_viable_installation(self):
        if not local.path(SPEC_YAML).is_file():
            raise Exception("Config file not found.")

    def _set_suggested(self):
        with open(local.path(SPEC_YAML), 'r') as f:
            spec = yaml.load(f.read())
        for key, branch in spec.items():
            if key == 'odoo':
                continue
            modules = self._search_for_installable_modules_branch(key)
            # We substract modules in SPEC_YAML
            modules = [x for x in modules if x not in branch.get('modules')]
            # We substract useless modules in SPEC_YAML
            if branch.get('useless'):
                modules = [x for x in modules
                           if x not in branch.get('useless')]
            if self._filter_according_branch(branch, modules):
                branch_name = branch.get('src').replace(' ', '/tree/')
                modules_string = ', '.join(modules)
                logger.info(' %s modules in branch %s M: %s',
                            len(modules), branch_name, modules_string)

    def _search_for_installable_modules_branch(self, directory):
        main_path = '%s/%s' % (VENDOR_FOLDER, directory)
        modules = []
        for root, dirs, files in os.walk(main_path):
            logger.debug('\n dirs: %s', dirs)
            for module in [x for x in dirs if x not in UNRELEVANT_DIRECTORIES]:
                for mani in MANIFEST_FILE_NAME:
                    manifest = '%s/%s/%s.py' % (main_path, module, mani)
                    if local.path(manifest).is_file():
                        break
                if local.path(manifest).is_file():
                    with open(manifest, 'r') as f:
                        # when no key 'installable': module is installable
                        # https://github.com/odoo/odoo/blob/77692a84be6a69cc9ecd8bd8789974c721e66ce2/odoo/modules/module.py#L318
                        if ast.literal_eval(f.read()).get('installable', True):
                            modules.append(module)
            logger.debug(' modules: %s', modules)
            break  # prevent to go deeper inside subdirectories
        return modules

    def _filter_according_branch(self, branch, modules):
        allowed = 0
        if self.include:
            strings = self.include.split(',')
            for string in strings:
                if string in branch.get('src'):
                    allowed += 1
        if modules and allowed:
            return True
        return False

    def main(self, *args):
        self._ensure_viable_installation()
        self._set_suggested()
