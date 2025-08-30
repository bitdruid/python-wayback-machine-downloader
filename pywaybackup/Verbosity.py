from tqdm import tqdm
from typing import Union


class Verbosity:
    """
    A class to manage verbosity levels, logging, progress and output.
    """

    verbose = False

    PROGRESS = None
    pbar = None

    log = None

    @classmethod
    def init(cls, logfile=None, silent: bool = False, verbose: bool = False, progress=None):
        cls.silent = silent
        cls.verbose = verbose
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
    def write(cls, verbose: bool = None, content: Union[str, list] = None):
        """
        Writes log entries to stdout or logfile based on verbosity level and progress-bar status.

        Determines if the message should be printed based on verbosity level.
        - If None, the message is always printed.

        Content is a list and is filtered and concatenated to a single block of loglines.
        It should contain dictionaries with keys:
        - 'verbose': The verbosity level of the message (True/False).
        - 'content': The actual message to be logged.
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
                        total=maxval, ascii="░▒█",
                        bar_format="{l_bar}{bar:50}{r_bar}{bar:-10b}"
                        )
                if cls.pbar is not None and progress is not None and progress > 0:
                    cls.pbar.update(progress)

    @classmethod
    def filter_verbosity(cls, message: list):
        """
        Removes messages from the list that do not match the verbosity level.

        - True if message is verbose None (print always)
        - True if message has same verbosity as configured

        Returns a string containing the filtered messages, joined by newlines.
        """
        filtered_message = []
        for msg in message:
            verbose = msg.get("verbose", None)
            if verbose is None or verbose == cls.verbose:
                filtered_message.append(msg["content"])
        return "\n".join(filtered_message)


class Progressbar(Verbosity):
    def __init__(self, unit: str, desc: str, unit_scale: bool = False, total: int = None, ascii: str = None, bar_format: str = None):
        if not super().silent:
            self.unit = unit
            self.desc = desc
            self.unit_scale = unit_scale
            self.total = total
            self.ascii = ascii
            self.bar_format = bar_format
            self.pbar = tqdm(unit=self.unit, desc=self.desc, unit_scale=self.unit_scale, total=self.total, ascii=self.ascii, bar_format=self.bar_format)

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
