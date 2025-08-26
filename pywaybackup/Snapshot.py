import os

from pywaybackup.db import Database
from pywaybackup.helper import url_split


class Snapshot:
    """
    If a relevant property of the snapshot is modified, the change will be pushed to the database.

    - _redirect_url
    - _redirect_timestamp
    - _response
    - _file
    """

    def __init__(self, db: Database, output: str, mode: str):
        self._db = db
        self.output = output
        self.mode = mode

        self._redirect_url = None
        self._redirect_timestamp = None
        self._response_status = None
        self._file = None

        self._row = self.fetch()
        if self._row:
            self.counter = self._row["counter"]
            self.timestamp = self._row["timestamp"]
            self.url_archive = self._row["url_archive"]
            self.url_origin = self._row["url_origin"]
            self.redirect_url = self._row["redirect_url"]
            self.redirect_timestamp = self._row["redirect_timestamp"]
            self.response_status = self._row["response"]
            self.file = self._row["file"]
        else:
            self.counter = False

    def fetch(self):
        """
        Get a snapshot-row from the snapshot table with response NULL. (not processed)
        """
        # mark as locked for other workers // only visual because get_snapshot fetches by NULL
        self._db.cursor.execute(
            """
            UPDATE snapshot_tbl
            SET response = 'LOCK'
            WHERE rowid = (
                SELECT rowid FROM snapshot_tbl 
                WHERE response IS NULL
                LIMIT 1
            )
            RETURNING rowid, *;
            """
        )
        row = self._db.cursor.fetchone()
        self._db.conn.commit()
        return row

    def modify(self, column, value):
        """
        Modify the snapshot in the database.
        """
        query = f"UPDATE snapshot_tbl SET {column} = ? WHERE counter = ?"
        self._db.cursor.execute(query, (value, self.counter))
        self._db.conn.commit()

    def create_output(self):
        """
        Create a file path for the snapshot.

        - If MODE_LAST or MODE_FIRST is enabled, the path does not include the timestamp.
        - Otherwise, include the timestamp in the path.
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
        return self._redirect_url

    @redirect_url.setter
    def redirect_url(self, value):
        if self.redirect_timestamp is None and value is None:
            return
        self._redirect_url = value
        self.modify(column="redirect_url", value=value)

    @property
    def redirect_timestamp(self):
        return self._redirect_timestamp

    @redirect_timestamp.setter
    def redirect_timestamp(self, value):
        if self.redirect_url is None and value is None:
            return
        self._redirect_timestamp = value
        self.modify(column="redirect_timestamp", value=value)

    @property
    def response_status(self):
        return self._response_status

    @response_status.setter
    def response_status(self, value):
        if self.response_status is None and value is None:
            return
        self._response_status = value
        self.modify(column="response", value=value)

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self, value):
        if self.file is None and value is None:
            return
        self._file = value
        self.modify(column="file", value=value)
