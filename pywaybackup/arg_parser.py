import argparse
import sys
from argparse import RawTextHelpFormatter
from importlib.metadata import version

from pywaybackup.arg_specs import ARG_GROUPS, ARG_SPECS, EXCLUSIVE_GROUPS


class Arguments:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description=f"<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>\nby @bitdruid -> https://github.com/bitdruid",
            formatter_class=RawTextHelpFormatter,
        )

        groups = {name: parser.add_argument_group(name) for name in ARG_GROUPS}

        exclusive = {
            ex_name: groups[ex_meta["parent_group"]].add_mutually_exclusive_group(required=ex_meta["required"])
            for ex_name, ex_meta in EXCLUSIVE_GROUPS.items()
        }

        for spec in ARG_SPECS:
            target = exclusive[spec.exclusive_group] if spec.exclusive_group else groups[spec.group]
            target.add_argument(*spec.flags, **_argparse_kwargs(spec))

        args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])  # if no arguments are given, print help

        args.silent = False
        args.debug = True

        self.args = args

    def get_args(self) -> dict:
        """Returns the parsed arguments as a dictionary."""
        return vars(self.args)


def _argparse_kwargs(spec) -> dict:
    """Translate an ArgSpec into kwargs for argparse.add_argument()."""
    kwargs = {"help": spec.help}
    if spec.action == "store_true":
        kwargs["action"] = "store_true"
        kwargs["default"] = bool(spec.default)
    elif spec.action == "optional_value":
        kwargs["type"] = spec.type
        kwargs["nargs"] = "?"
        kwargs["const"] = spec.const
        kwargs["metavar"] = spec.metavar
        kwargs["default"] = spec.default
    else:
        kwargs["type"] = spec.type
        kwargs["metavar"] = spec.metavar
        kwargs["default"] = spec.default
    return kwargs
