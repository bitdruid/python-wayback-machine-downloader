"""
Interactive mode: prompt the user for arguments instead of parsing sys.argv.

Used when waybackup is launched without CLI arguments (e.g. double-clicking
the Windows .exe). Produces the same dict shape as Arguments.get_args() so
PyWayBackup(**args) works either way. The arguments and their grouping are read
from the argparse parser, so a new argument is offered here automatically - it
only has to be added in arguments.py.
"""

from importlib.metadata import version

from pywaybackup.arguments import build_parser


class Interactive:
    def __init__(self):
        print(f"<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")
        print("Interactive mode - press Ctrl+C to abort.\n")

        parser = build_parser()
        actions = [action for action in parser._actions if action.dest != "help"]
        args = {action.dest: action.default for action in actions}

        # 1. Required url
        url = _action_by_dest(actions, "url")
        args["url"] = self._prompt_required(url.help)

        # 2. Required exclusive group(s) - pick exactly one member
        exclusive = set()
        for group in parser._mutually_exclusive_groups:
            members = group._group_actions
            exclusive.update(action.dest for action in members)
            if not group.required:
                continue
            choice = self._prompt_choice("Mode", [(a.dest, a.help) for a in members])
            for action in members:
                args[action.dest] = action.dest == choice

        # 3. Every other argument, offered group by group as defined in the parser
        handled = exclusive | {"url"}
        for group in parser._action_groups:
            members = [a for a in group._group_actions if a.dest not in handled and a.dest != "help"]
            if not members:
                continue
            if not self._prompt_yes_no(f"\nConfigure {group.title}?", default=False):
                continue
            for action in members:
                args[action.dest] = self._prompt_for(action, args[action.dest])

        # internal flags (parity with Arguments.py)
        args["silent"] = False
        args["debug"] = True

        self.args = args
        print()

    def get_args(self) -> dict:
        return self.args

    def _prompt_for(self, action, current):
        label = action.help
        if action.nargs == 0:  # store_true
            return self._prompt_yes_no(label, default=bool(current))
        if action.type is int:
            if current is None:
                return self._prompt_optional_int(label)
            return self._prompt_int(label, default=current)
        if current is None:
            return self._prompt_optional_str(label)
        return self._prompt_str(label, default=current)

    @staticmethod
    def _prompt_required(label):
        while True:
            value = input(f"{label}: ").strip()
            if value:
                return value
            print("  (required, please enter a value)")

    @staticmethod
    def _prompt_optional_str(label):
        value = input(f"{label} (blank to skip): ").strip()
        return value or None

    @staticmethod
    def _prompt_str(label, default):
        value = input(f"{label} [{default}]: ").strip()
        return value if value else default

    @staticmethod
    def _prompt_optional_int(label):
        while True:
            value = input(f"{label} (blank to skip): ").strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                print("  (please enter an integer or leave blank)")

    @staticmethod
    def _prompt_int(label, default):
        while True:
            value = input(f"{label} [{default}]: ").strip()
            if not value:
                return default
            try:
                return int(value)
            except ValueError:
                print("  (please enter an integer)")

    @staticmethod
    def _prompt_yes_no(label, default):
        suffix = "[Y/n]" if default else "[y/N]"
        while True:
            value = input(f"{label} {suffix}: ").strip().lower()
            if not value:
                return default
            if value in ("y", "yes"):
                return True
            if value in ("n", "no"):
                return False
            print("  (please answer y or n)")

    @staticmethod
    def _prompt_choice(label, options):
        # use first letter of each name as key, fall back to position number on collision
        keys = []
        used = set()
        for name, _ in options:
            k = name[0]
            if k in used:
                k = str(len(keys) + 1)
            keys.append(k)
            used.add(k)
        print(f"\n{label}:")
        for k, (name, desc) in zip(keys, options):
            print(f"  [{k}] {name}: {desc}")
        valid = dict(zip(keys, [name for name, _ in options]))
        while True:
            value = input("Choice: ").strip().lower()
            if value in valid:
                return valid[value]
            print(f"  (please enter one of: {', '.join(sorted(valid))})")


def _action_by_dest(actions, dest):
    for action in actions:
        if action.dest == dest:
            return action
    raise KeyError(dest)
