import http.client

from pywaybackup.db import Database
from pywaybackup.Verbosity import Verbosity as vb

from pywaybackup.Snapshot import Snapshot


class Worker:
    """
    Represents the storage for the worker thread - contains the workers connections and its currently assigned snapshot.
    Worker buffers its messages in a Message object. Output has to be done with write() method.
    """

    def __init__(self, id: int, output: str, mode: str):
        self.id = id
        self.output = output
        self.mode = mode
        self.message = Message(self)

    def init(self):
        self.db = Database()
        self.connection = http.client.HTTPSConnection("web.archive.org")

    def assign_snapshot(self, total_amount: int):
        self.snapshot = Snapshot(self.db, output=self.output, mode=self.mode)
        self.total_amount = total_amount
        if not self.snapshot.counter:  # counter only if a row was fetched
            self.snapshot = None
            return
        self.attempt = 1

    def refresh_connection(self):
        """
        Refreshes the connection to the Wayback Machine.
        """
        self.connection.close()
        self.connection = http.client.HTTPSConnection("web.archive.org")


class Message(Worker):
    """
    Extends Worker to manage a message buffer for logging.
    """

    def __init__(self, worker: object = None):
        self.worker = worker
        self.buffer = []

    def __str__(self):
        return str(self.buffer)

    def store(self, verbose: bool = None, result: str = "", info: str = "", content: str = ""):
        """
        Stores a log message in the workers buffer for later output. If verbose=None, the message will always be generated.
        """

        def _format_verbose(message: dict):
            """
            Formatting a logline for verbose output:

            [result] -> [info: ] [content]

            - result: 10 characters
            - info: 6 characters
            - content: any message to be logged
            """
            result = message.get("result", "")
            info = message.get("info", "")
            content = message.get("content", "")

            if not result and not info:
                return content

            return f"{result.ljust(10)} -> {(info + ': ').ljust(6) if info else ''}{content}"

        if verbose is True or verbose is None:
            self.message = {
                "verbose": True,
                "content": _format_verbose({"result": result, "info": info, "content": content}),
            }
            self.buffer.append(self.message)
        if verbose is False or verbose is None:
            result = result + " - " if result else ""
            content = content + " - " if content else ""
            self.message = {
                "verbose": False,
                "content": f"{self.worker.snapshot.counter}/{self.worker.total_amount} - W:{self.worker.id} - {result}{content}{self.worker.snapshot.timestamp} - {self.worker.snapshot.url_origin}",
            }
            self.buffer.append(self.message)

    def write(self):
        """
        Writes all messages in the buffer to the log and clears the buffer.
        """
        vb.write(content=self.buffer)
        self.buffer = []
