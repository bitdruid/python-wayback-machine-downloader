import os
import threading

from pywaybackup.db import Database, select, update, waybackup_snapshots
from pywaybackup.helper import url_split


class Snapshot:
    """
    Represents a single snapshot entry and manages its state and persistence.

    When a relevant property of the snapshot is modified, the change is automatically
    pushed to the database:
        - redirect_url
        - redirect_timestamp
        - response_status
        - file

    Thread-safe for SQLite operations using a lock.
    """

    __sqlite_lock = threading.Lock()

    def __init__(self, db: Database, output: str, mode: str):
        """
        Initialize a Snapshot instance and fetch its database row if available.

        Args:
            db (Database): Database connection/session manager.
            output (str): Output directory for downloaded files.
            mode (str): Download mode ('first', 'last', or default).
        """
        self._db = db
        self.output = output
        self.mode = mode

        self._redirect_url = None
        self._redirect_timestamp = None
        self._response_status = None
        self._file = None

        self._row = self.fetch()
        if self._row:
            self.scid = self._row.scid
            self.counter = self._row.counter
            self.timestamp = self._row.timestamp
            self.url_archive = self._row.url_archive
            self.url_origin = self._row.url_origin
            self.redirect_url = self._row.redirect_url
            self.redirect_timestamp = self._row.redirect_timestamp
            self.response_status = self._row.response
            self.file = self._row.file
        else:
            self.counter = False

    def fetch(self):
        """
        Fetch a snapshot row from the database with response=NULL (not processed).
        Uses row locking to prevent concurrent workers from processing the same row.

        Returns:
            waybackup_snapshots or None: The next unprocessed snapshot row, or None if none available.
        """
        # mark as locked for other workers // only visual because get_snapshot fetches by NULL
        # prevent another worker from fetching between LOCK-update (for sqlite by threading.Lock, else lock row)

        def __on_sqlite():
            if self._db.session.bind.dialect.name == "sqlite":
                return True
            return False

        def __get_row():
            with self._db.session.begin():
                row = self._db.session.execute(
                    select(waybackup_snapshots)
                    .where(waybackup_snapshots.response.is_(None))
                    .order_by(waybackup_snapshots.scid)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                ).scalar_one_or_none()

                if row is None:
                    return None

                row.response = "LOCK"

            return row

        if __on_sqlite():
            with self.__sqlite_lock:
                return __get_row()
        else:
            return __get_row()

    def modify(self, column, value):
        """
        Update a column value for this snapshot in the database.

        Args:
            column (str): Name of the column to update.
            value: New value to set for the column.
        """
        column = getattr(waybackup_snapshots, column)
        self._db.session.execute(update(waybackup_snapshots).where(waybackup_snapshots.scid == self.scid).values({column: value}))
        self._db.session.commit()

    def create_output(self):
        """
        Generate the file path for the snapshot download.

        If mode is 'first' or 'last', the path does not include the timestamp.
        Otherwise, the timestamp is included in the path.

        Returns:
            str: Absolute path to the output file for the snapshot.
        """
        domain, subdir, filename = url_split(self.url_archive.split("id_/")[1], index=True)

        if self.mode == "last" or self.mode == "first":
            download_dir = os.path.join(self.output, domain, subdir)
        else:
            download_dir = os.path.join(self.output, domain, self.timestamp, subdir)

        download_file = os.path.abspath(os.path.join(download_dir, filename))

        return download_file

    @property
    def redirect_url(self):
        """
        str: The redirect URL for this snapshot, if any.
        """
        return self._redirect_url

    @redirect_url.setter
    def redirect_url(self, value):
        """
        Set the redirect URL and update the database.

        Args:
            value (str): The new redirect URL.
        """
        if self.redirect_timestamp is None and value is None:
            return
        self._redirect_url = value
        self.modify(column="redirect_url", value=value)

    @property
    def redirect_timestamp(self):
        """
        str: The timestamp of the redirect, if any.
        """
        return self._redirect_timestamp

    @redirect_timestamp.setter
    def redirect_timestamp(self, value):
        """
        Set the redirect timestamp and update the database.

        Args:
            value (str): The new redirect timestamp.
        """
        if self.redirect_url is None and value is None:
            return
        self._redirect_timestamp = value
        self.modify(column="redirect_timestamp", value=value)

    @property
    def response_status(self):
        """
        str: The HTTP response/status for this snapshot.
        """
        return self._response_status

    @response_status.setter
    def response_status(self, value):
        """
        Set the response status and update the database.

        Args:
            value (str): The new response status.
        """
        if self.response_status is None and value is None:
            return
        self._response_status = value
        self.modify(column="response", value=value)

    @property
    def file(self):
        """
        str: The file path for the downloaded snapshot.
        """
        return self._file

    @file.setter
    def file(self, value):
        """
        Set the file path and update the database.

        Args:
            value (str): The new file path.
        """
        if self.file is None and value is None:
            return
        self._file = value
        self.modify(column="file", value=value)
