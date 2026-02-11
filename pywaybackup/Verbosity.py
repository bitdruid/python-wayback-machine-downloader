from enum import IntEnum
from tqdm import tqdm
from typing import Union


# outside enum to avoid cls membership
_VERBOSITY_ALIASES = {
    "NORMAL": "DEFAULT",
    "VERBOSE": "DEFAULT",
    "DETAIL": "HIGH",
    "DETAILED": "HIGH",
    "MAX": "HIGH",
    "QUIET": "LOW",
    "MINIMAL": "LOW",
    "MIN": "LOW",
}


class VerbosityLevel(IntEnum):
    """
    Verbosity levels for output control.

    - LOW: Essential output only (no verbose flag)
    - DEFAULT: Standard verbose output (--verbose or --verbose default)
    - HIGH: Detailed verbose output (--verbose high)
    """

    LOW = 0
    DEFAULT = 1
    HIGH = 2

    @classmethod
    def from_value(cls, value) -> "VerbosityLevel":
        """
        Convert various input types to VerbosityLevel.

        Args:
            value: Can be:
                - None/False: LOW
                - True: DEFAULT
                - str: "low", "default", "high" (+ aliases: normal, info, debug, quiet, etc.)
                - int: 0, 1, 2
                - VerbosityLevel: returned as-is

        Returns:
            VerbosityLevel enum value

        Raises:
            ValueError: If string value is not a valid level or alias
        """
        if value is None or value is False:
            return cls.LOW
        if value is True:
            return cls.DEFAULT
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                raise ValueError(f"Invalid verbosity level: {value}. Valid levels: 0 (low), 1 (default), 2 (high)")
        if isinstance(value, str):
            upper_value = value.upper()
            # check for aliases first
            if upper_value in _VERBOSITY_ALIASES:
                upper_value = _VERBOSITY_ALIASES[upper_value]
            # try to get the enum member
            try:
                return cls[upper_value]
            except KeyError:
                valid = ", ".join([m.name.lower() for m in cls] + list(set(a.lower() for a in _VERBOSITY_ALIASES)))
                raise ValueError(f"Invalid verbosity level: '{value}'. Valid levels: {valid}")
        return cls.LOW


class Verbosity:
    """
    A class to manage verbosity levels, logging, progress and output.

    Verbosity tiers:
    - LOW (0): Essential output only - no verbose flag set
    - DEFAULT (1): Standard verbose - --verbose or --verbose default
    - HIGH (2): Detailed verbose - --verbose high
    """

    level = VerbosityLevel.LOW

    PROGRESS = None
    pbar = None

    log = None

    @classmethod
    def init(cls, logfile=None, silent: bool = False, verbose: Union[bool, str, int] = False, progress=None):
        cls.silent = silent
        cls.level = VerbosityLevel.from_value(verbose)
        cls.logfile = open(logfile, "w", encoding="utf-8") if logfile else None
        cls.PROGRESS = progress

    @classmethod
    def fini(cls):
        if cls.PROGRESS:
            if cls.pbar is not None:
                cls.pbar.close()
        if cls.logfile:
            cls.logfile.close()

    @classmethod
    def write(cls, verbose: Union[bool, str, int, None] = None, content: Union[str, list] = None):
        """
        Writes log entries to stdout or logfile based on verbosity level and progress-bar status.

        Determines if the message should be printed based on verbosity level.

        Args:
            verbose: The required verbosity level for this message:
                - None: Always printed (essential output)
                - False/0/"low": Printed at LOW level and above
                - True/1/"default": Printed at DEFAULT level and above
                - 2/"high": Printed at HIGH level only
            content: The message string or list of message dicts to log.
        """
        if not cls.silent:
            if isinstance(content, str):
                content = [{"verbose": verbose, "content": content}]
            logline = cls.filter_verbosity(content)
            if logline:
                if cls.logfile:
                    cls.logfile.write(logline + "\n")
                    cls.logfile.flush()
                if not cls.PROGRESS:
                    print(logline)

    @classmethod
    def progress(cls, progress: int, maxval: int = None):
        """
        Updates the progress bar.

        - bar is initialized if calling with progress=0
        - bar is updated if calling with progress > 0

        """
        if not cls.silent:
            if cls.PROGRESS:
                if cls.pbar is None and progress == 0:
                    cls.pbar = Progressbar(
                        unit=" snapshot",
                        desc="download file".ljust(15),
                        total=maxval,
                        ascii="░▒█",
                        bar_format="{l_bar}{bar:50}{r_bar}{bar:-10b}",
                    )
                if cls.pbar is not None and progress is not None and progress > 0:
                    cls.pbar.update(progress)

    @classmethod
    def filter_verbosity(cls, message: list):
        """
        Removes messages from the list that do not match the verbosity level.

        Messages are printed if:
        - verbose is None (always print - essential output)
        - The message's required level <= configured level

        Returns a string containing the filtered messages, joined by newlines.
        """
        filtered_message = []
        for msg in message:
            msg_verbose = msg.get("verbose", None)
            if msg_verbose is None:
                # NONE is always printed
                filtered_message.append(msg["content"])
            else:
                # convert message verbosity and compare
                msg_level = VerbosityLevel.from_value(msg_verbose)
                if msg_level <= cls.level:
                    filtered_message.append(msg["content"])
        return "\n".join(filtered_message)


class Progressbar(Verbosity):
    def __init__(
        self,
        unit: str,
        desc: str,
        unit_scale: bool = False,
        total: int = None,
        ascii: str = None,
        bar_format: str = None,
    ):
        if not super().silent:
            self.unit = unit
            self.desc = desc
            self.unit_scale = unit_scale
            self.total = total
            self.ascii = ascii
            self.bar_format = bar_format
            self.pbar = tqdm(
                unit=self.unit,
                desc=self.desc,
                unit_scale=self.unit_scale,
                total=self.total,
                ascii=self.ascii,
                bar_format=self.bar_format,
            )

    def update(self, progress: int):
        """
        Updates the progress bar with the given progress value.
        """
        if not super().silent:
            if self.pbar is not None:
                self.pbar.update(progress)
                self.pbar.refresh()

    def close(self):
        """
        Close the progress bar.
        """
        if self.pbar is not None:
            self.pbar.close()
