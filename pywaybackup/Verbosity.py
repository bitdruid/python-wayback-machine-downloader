import tqdm
import json
from pywaybackup.SnapshotCollection import SnapshotCollection as sc

class Verbosity:

    LEVELS = ["trace", "info"]
    level = None

    mode = None
    args = None
    pbar = None

    log = None

    @classmethod
    def init(cls, v_args: list, log=None):
        cls.args = v_args
        cls.log = open(log, "w") if log else None
        if cls.args == "progress":
            cls.mode = "progress"
        elif cls.args == "json":
            cls.mode = "json"
        cls.level = cls.args if cls.args in cls.LEVELS else "info"

    @classmethod
    def fini(cls):
        if cls.mode == "progress":
            if cls.pbar is not None:
                cls.pbar.close()
        if cls.mode == "json":
            print(json.dumps(sc.SNAPSHOT_COLLECTION, indent=4, sort_keys=True))
        if cls.log:
            cls.log.close()

    @classmethod
    def write(cls, status="", type="", message=""):
        """
        Write a log line based on the provided status, type, and message.
        
        Args:
            status (str): The status of the log line. (e.g. "SUCCESS", "REDIRECT")
            type (str): The type of the log line. (e.g. "URL", "FILE")
            message (str): The message to be logged. (e.g. actual url, file path)
        """
        logline = cls.generate_logline(status=status, type=type, message=message)
        if cls.mode != "progress" and cls.mode != "json":
            if logline:
                print(logline)
        if cls.log:
            cls.log.write(logline + "\n")
            cls.log.flush()

    @classmethod
    def progress(cls, progress: int):
        if cls.mode == "progress":
            if cls.pbar is None and progress == 0:
                maxval = sc.count(collection=True)
                cls.pbar = tqdm.tqdm(total=maxval, desc="Downloading", unit=" snapshot", ascii="░▒█")
            if cls.pbar is not None and progress is not None and progress > 0:
                cls.pbar.update(progress)
                cls.pbar.refresh()

    @classmethod
    def generate_logline(cls, status: str = "", type: str = "", message: str = ""):

        if not status and not type:
            return message

        status_length = 11
        type_length = 5

        status = status.ljust(status_length)
        type = type.ljust(type_length)

        log_entry = f"{status} -> {type}: {message}"

        return log_entry

class Message(Verbosity):
    """
    Message class representing a message-buffer for the Verbosity class.

    If a message should be stored and stacked for later output.
    """

    def __init__(self):
        self.message = {}

    def __str__(self):
        return self.message

    def store(self, status: str = "", type: str = "", message: str = "", level: str = "info"):
        if level not in self.message:
            self.message[level] = []
        self.message[level].append(super().generate_logline(status, type, message))

    def clear(self):
        self.message = {}

    def write(self):
        for level in self.message:
            if self.check_level(level):
                for message in self.message[level]:
                    super().write(message=message)
        self.clear()
            
    def check_level(self, level: str):
        return super().LEVELS.index(level) >= super().LEVELS.index(self.level)

    def trace(self, status: str = "", type: str = "", message: str = ""):
        self.store(status, type, message, "trace")

        