import http.client

from pywaybackup.db import Database
from pywaybackup.Verbosity import Verbosity as vb

from pywaybackup.SnapshotCollection import SnapshotCollection as sc


class Worker:
    """
    Represents the storage for the worker thread - contains the workers connections and its currently assigned snapshot.

    If a relevant property of the assigned snapshot is modified, the worker will push the change to the database.

    - _redirect_url
    - _redirect_timestamp
    - _response
    - _file

    Worker buffers its messages in a Message object. Output has to be done with write() method.
    """

    def __init__(self, id: int):
        self.id = id
        self.message = Message(self)

        self._redirect_url = None
        self._redirect_timestamp = None
        self._response = None
        self._file = None

    def init(self):
        self.db = Database()
        self.connection = http.client.HTTPSConnection("web.archive.org")

    def assign_snapshot(self):
        self.snapshot = sc.get_snapshot(self.db)
        if not self.snapshot:
            return
        self.counter = self.snapshot["counter"]
        self.timestamp = self.snapshot["timestamp"]
        self.url_archive = self.snapshot["url_archive"]
        self.url_origin = self.snapshot["url_origin"]
        self.redirect_url = self.snapshot["redirect_url"]
        self.redirect_timestamp = self.snapshot["redirect_timestamp"]
        self.response = self.snapshot["response"]
        self.file = self.snapshot["file"]

        self.attempt = 1

    def refresh_connection(self):
        """
        Refreshes the connection to the Wayback Machine.
        """
        self.connection.close()
        self.connection = http.client.HTTPSConnection("web.archive.org")

    @property
    def redirect_url(self):
        return self._redirect_url

    @redirect_url.setter
    def redirect_url(self, value):
        if self.redirect_timestamp is None and value is None:
            return
        self._redirect_url = value
        sc.modify_snapshot(self.db, self.counter, "redirect_url", value)

    @property
    def redirect_timestamp(self):
        return self._redirect_timestamp

    @redirect_timestamp.setter
    def redirect_timestamp(self, value):
        if self.redirect_url is None and value is None:
            return
        self._redirect_timestamp = value
        sc.modify_snapshot(self.db, self.counter, "redirect_timestamp", value)

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        if self.redirect_url is None and value is None:
            return
        self._response = value
        sc.modify_snapshot(self.db, self.counter, "response", value)

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self, value):
        if self.redirect_url is None and value is None:
            return
        self._file = value
        sc.modify_snapshot(self.db, self.counter, "file", value)


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
            "content": f"{self.worker.counter}/{sc.SNAPSHOT_TOTAL} - W:{self.worker.id} - {result}{content}{self.worker.timestamp} - {self.worker.url_origin}",
            }
            self.buffer.append(self.message)

    def write(self):
        """
        Writes all messages in the buffer to the log and clears the buffer.
        """
        vb.write(content=self.buffer)
        self.buffer = []
