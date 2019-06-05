"""ak clean"""
import logging
import yaml
from plumbum import local


from .ak_sub import AkSub, Ak
from .ak_build import SPEC_YAML

CESURE_LIMIT = 80
INITIAL_INDENT = 14

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@Ak.subcommand("clean")
class AkClean(AkSub):
    """ Clean spec.yaml file:
        - sort modules list
        - format modules list
    """

    def _ensure_viable_installation(self):
        if not local.path(SPEC_YAML).is_file():
            raise Exception("Config file not found.")

    def _format_string_with_cesure(self, string):
        rstring = string
        final_string = ''
        while rstring:
            if len(rstring) <= CESURE_LIMIT:
                lstring = rstring
                rstring = False
            else:
                lstring = rstring[:CESURE_LIMIT]
                real_cesure = lstring.rfind(',')
                logger.debug('initial lstring: ', lstring)
                logger.debug('real_cesure: ', real_cesure)
                lstring = "%s,\n%s" % (
                    lstring[:real_cesure], ' ' * INITIAL_INDENT)
                rstring = rstring[real_cesure + 1:]
                logger.debug('lstring: ', lstring)
                logger.debug('rstring: ', rstring)
            final_string = final_string + lstring
        logger.debug('  >>> final_string: ', final_string)
        return final_string

    def _define_new_string(
            self, key, modules_list, spec_string, type_list='modules'):
        if isinstance(modules_list, str):
            print(key)
            print(modules_list)
            import pdb; pdb.set_trace()
        modules_list.sort()
        search_string = "\n%s:" % key
        # TODO improve
        replace_mask = "\nreplace\n    %s: replace" % type_list
        replace_mask = replace_mask.replace('replace', '%s')
        module_string = "[%s]" % self._format_string_with_cesure(
            ",".join(modules_list))
        return spec_string.replace(search_string, replace_mask % (
                                   search_string, module_string))

    def _clean(self):
        ""
        with open(local.path(SPEC_YAML), 'r') as f:
            spec = yaml.load(f.read(), Loader=yaml.FullLoader)
            f.seek(0)
            spec_string = f.read()
        with open(local.path(SPEC_YAML), 'w') as f:
            for key, branch in spec.items():
                modules = branch.get('modules')
                if modules:
                    spec_string = self._define_new_string(
                        key, modules, spec_string)
                # useless is only use in combination with `ak suggest` cmd
                modules = branch.get('useless')
                if modules:
                    spec_string = self._define_new_string(
                        key, modules, spec_string, type_list='useless')
            f.write(spec_string)

    def main(self, *args):
        self._ensure_viable_installation()
        self._clean()
