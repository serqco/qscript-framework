"""
Extends argparse.ArgumentParser with a facility for configuring subcommands by convention.
Each subcommand lives in its separate Python module.
The name of the subcommand is the module name (without superpackage names)
with underscore replaced by dash.
To be a subcommand module, a module must have 

meaning = "some help text for the subcommand"
def add_arguments(parser: ArgumentParser): ...  # configure the subcommand's sub-parser
def execute(args: argparse.Namespace): ...  # run the subcommand

The module can also optionally have:

aliases = ["subcmd-alias1", "subcmd-alias2"]  # optional.

for calling the same subcommand by a different name (e.g. an abbreviation).

To use the mechanism, create the parser as usual and then call the submodule scanner:

parser = ArgumentParser(epilog=explanation)
parser.scan("mysubcmds.subcmd1", "mysubcmds.subcmd2")  # or provide module object instead of str
args = parser.parse_args()
parser.execute_subcommand(args)  # or supply nothing, then parse_args() will be called internally

The mechanism uses only one sub-parser group (which is rarely a relevant limitation).
It will execute importlib.import_module() on all modules mentioned in a scan() call as strings. 
Multiple calls to scan() are allowed, each can have one or more arguments.
Subcommands cannot be nested, there is only one level of subcommands.
"""


import argparse
import importlib
import re
import warnings
import typing as tg


moduletype = type(argparse)
functiontype = type(lambda: 1)  # TODO: get this from stdlib


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subparsers = self.add_subparsers(parser_class=argparse.ArgumentParser,
                                              dest='subcommand', required=True)
        self.subcommand_modules = dict()  # map subcommand name to module
        self.aliases = dict()  # map alias name to subcommand name and subcommand name to itself

    def scan (self, *modules):
        for module in modules:
            # ----- obtain module and names:
            if isinstance(module, str):
                module = importlib.import_module(module)  # turn str into module
            if not isinstance(module, moduletype):
                warnings.warn(f"scan() arguments must be str or module: {type(module)} ignored.")
                continue  # skip non-modules. 
            module_fullname = module.__name__  # includes superpackages
            mm = re.search(r"\.?(\w+)$", module_fullname)  # match last component or entire name
            module_name = mm.group(1)
            subcommand_name = module_name.replace("_", "-")
            # ----- check for subcommand module:
            required_attrs = (('meaning', str), 
                              ('execute', functiontype), 
                              ('configure_argparser', functiontype))
            if self._misses_any_of(module, required_attrs):
                continue  # silently skip modules that are not proper subcommand modules
            # ----- configure subcommand:
            self.subcommand_modules[subcommand_name] = module
            aliases = module.aliases if hasattr(module, 'aliases') else []
            for alias in aliases:
                self.subcommand_modules[alias] = module
            subparser = self.subparsers.add_parser(subcommand_name, help=module.meaning,
                                                   aliases=aliases)
            module.add_arguments(subparser)

    def execute_subcommand(self, args: tg.Optional[argparse.Namespace] = None):
        if args is None:
            args = self.parse_args()
        self.subcommand_modules[args.subcommand].execute(args)

    @staticmethod
    def _misses_any_of(module: moduletype, required: tg.Sequence[tg.Tuple[str, type]]) -> bool:
        for name, _type in required:
            module_elem = getattr(module, name, None)
            if not module_elem or not isinstance(module_elem, _type):
                return True  # this is not a subcommand-shaped submodule
        return False
