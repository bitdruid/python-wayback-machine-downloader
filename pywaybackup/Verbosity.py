from tqdm import tqdm

class Verbosity:

    verbose = False

    mode = None
    args = None

    PROGRESS = None
    pbar = None

    log = None

    #stdout = None

    @classmethod
    def init(cls, verbose: bool = False, progress=None, log=None):
        cls.verbose = verbose
        cls.log = open(log, "w") if log else None
        cls.PROGRESS = progress
        # if progress:
        #     cls.PROGRESS = True
        #     cls.stdout = sys.stdout
        #     sys.stdout = open(os.devnull, "w")

    @classmethod
    def fini(cls):
        #sys.stdout = cls.stdout
        if cls.PROGRESS:
            if cls.pbar is not None:
                cls.pbar.close()
        if cls.log:
            cls.log.close()

    @classmethod
    def write(cls, info="", type="", message=""):
        """
        Write a log line based on the provided info, type, and message.
        
        Args:
            info (str): "SUCCESS", "REDIRECT", ...
            type (str): "URL", "FILE", ...
            message (str): actual url, file path, ...
        """

        #mode = 0 if cls.verbose else 1
        logline = cls.generate_logline(info, type, message)
        if not cls.PROGRESS:
            if logline:
                print(logline)
            if cls.log:
                cls.log.write(logline + "\n")
                cls.log.flush()

    @classmethod
    def progress(cls, progress: int, maxval: int = None):
        if cls.PROGRESS:
            if cls.pbar is None and progress == 0:
                cls.pbar = tqdm(total=maxval, desc="download file".ljust(15), unit=" snapshot", ascii="░▒█", bar_format='{l_bar}{bar:50}{r_bar}{bar:-10b}')
            if cls.pbar is not None and progress is not None and progress > 0:
                cls.pbar.update(progress)
                cls.pbar.refresh()

    @classmethod
    def generate_logline(cls, info: str, type: str, message: str):
        """
        mode 0:
        [INFO]     ➔ [TYPE]: [MESSAGE]
        """

        if not info and not type:
            return message
            
        info_length = 10
        type_length = 5

        info = info.ljust(info_length)
        info = f"{info} -> "

        type = type.ljust(type_length)
        type = f"{type}: " if type.strip() else ""

        log_entry = f"{info}{type}{message}"

        return log_entry


class Message(Verbosity):
    """
    Message class representing a message-buffer for the Verbosity class.

    If a message should be stored and stacked for later output.
    """

    def __init__(self):
        self.message = []

    def __str__(self):
        return str(self.message)

    def store(self, info: str = "", type: str = "", message: str = ""):
        #mode = 0 if super().verbose else 1
        self.message.append(super().generate_logline(info, type, message))

    def clear(self):
        self.message = []

    def write(self):
        for message in self.message:
            super().write(message=message)
        self.clear()