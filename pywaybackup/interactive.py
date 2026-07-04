"""
Interactive mode: prompt the user for arguments instead of parsing sys.argv.

Used when waybackup is launched without CLI arguments (e.g. double-clicking
the Windows .exe). Produces the same dict shape as Arguments.get_args() so
PyWayBackup(**args) works either way. Argument metadata is read from
arg_specs.ARG_SPECS so flags only have to be declared in one place.
"""

from importlib.metadata import version

from pywaybackup.arg_specs import ARG_SPECS, EXCLUSIVE_GROUPS, default_args


class Interactive:
    def __init__(self):
        print(f"<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")
        print("Interactive mode - press Ctrl+C to abort.\n")

        args = default_args()

        # 1. Required URL
        url_spec = _spec_by_name("url")
        args["url"] = self._prompt_required(url_spec.prompt or url_spec.help)

        # 2. Required exclusive group(s) — pick exactly one member
        for ex_name in EXCLUSIVE_GROUPS:
            members = [s for s in ARG_SPECS if s.exclusive_group == ex_name]
            choice = self._prompt_choice(
                ex_name.capitalize(),
                [(s.name, s.help) for s in members],
            )
            for s in members:
                args[s.name] = s.name == choice

        # 3. Advanced options
        if self._prompt_yes_no("Configure advanced options?", default=False):
            for spec in ARG_SPECS:
                if not spec.advanced:
                    continue
                args[spec.name] = self._prompt_for(spec, args[spec.name])

        # internal flags (parity with Arguments.py)
        args["silent"] = False
        args["debug"] = True

        self.args = args
        print()

    def get_args(self) -> dict:
        return self.args

    def _prompt_for(self, spec, current):
        label = spec.prompt or spec.help
        if spec.action == "store_true":
            return self._prompt_yes_no(f"{label}", default=bool(current))
        if spec.type is int:
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


def _spec_by_name(name):
    for s in ARG_SPECS:
        if s.name == name:
            return s
    raise KeyError(name)
