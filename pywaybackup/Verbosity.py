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
    def init(cls, verbose: bool = False, progress=None, log=None):
        cls.verbose = verbose
        cls.log = open(log, "w", encoding="utf-8") if log else None
        cls.PROGRESS = progress

    @classmethod
    def fini(cls):
        if cls.PROGRESS:
            if cls.pbar is not None:
                cls.pbar.close()
        if cls.log:
            cls.log.close()

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
        if isinstance(content, str):
            content = [{"verbose": verbose, "content": content}]
        logline = cls.filter_verbosity(content)
        if logline:
            if cls.log:
                cls.log.write(logline + "\n")
                cls.log.flush()
            if not cls.PROGRESS:
                print(logline)

    @classmethod
    def progress(cls, progress: int, maxval: int = None):
        """
        Updates the progress bar.

        - bar is initialized if calling with progress=0
        - bar is updated if calling with progress > 0

        """
        if cls.PROGRESS:
            if cls.pbar is None and progress == 0:
                cls.pbar = tqdm(
                    total=maxval,
                    desc="download file".ljust(15),
                    unit=" snapshot",
                    ascii="░▒█",
                    bar_format="{l_bar}{bar:50}{r_bar}{bar:-10b}",
                )
            if cls.pbar is not None and progress is not None and progress > 0:
                cls.pbar.update(progress)
                cls.pbar.refresh()

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
