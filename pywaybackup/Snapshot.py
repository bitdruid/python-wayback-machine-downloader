import os
import threading

from pywaybackup.db import Database, select, update, waybackup_snapshots, and_
from pywaybackup.helper import url_split
from pywaybackup.Verbosity import Verbosity as vb


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
            # Atomic claim: find next unprocessed scid, set response='LOCK' only if still unprocessed,
            # then fetch that row. This avoids relying on FOR UPDATE or explicit nested transactions
            # which can trigger "A transaction is already begun on this Session" errors.

            session = self._db.session

            # get next available SnapshotId
            vb.write(verbose="high", content="[Snapshot.fetch] selecting next scid")
            scid = session.execute(
                select(waybackup_snapshots.scid)
                .where(waybackup_snapshots.response.is_(None))
                .order_by(waybackup_snapshots.scid)
                .limit(1)
            ).scalar_one_or_none()

            if scid is None:
                vb.write(verbose="high", content="[Snapshot.fetch] no unprocessed scid found")
                return None

            # try to atomically claim the row by updating only if still unclaimed
            result = session.execute(
                update(waybackup_snapshots)
                .where(and_(waybackup_snapshots.scid == scid, waybackup_snapshots.response.is_(None)))
                .values(response="LOCK")
            )

            # if another worker claimed it first, rowcount will be 0 — retry to get next available row
            vb.write(
                verbose="high", content=f"[Snapshot.fetch] attempted to claim scid={scid}, rowcount={result.rowcount}"
            )
            if result.rowcount == 0:
                # TOCTOU: __get_row(): another worker claimed this row between our SELECT and UPDATE.
                # Retry instead of returning None to avoid premature worker termination.
                try:
                    session.commit()
                except Exception:
                    pass
                vb.write(verbose="high", content=f"[Snapshot.fetch] scid={scid} already claimed, retrying")
                return __get_row()

            # The row has been claimed by the worker and can now be fetched.
            row = session.execute(
                select(waybackup_snapshots).where(waybackup_snapshots.scid == scid)
            ).scalar_one_or_none()
            try:
                session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass
            vb.write(verbose="high", content=f"[Snapshot.fetch] claimed scid={scid} and fetched row")
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
        try:
            vb.write(verbose="high", content=f"[Snapshot.modify] updating scid={self.scid} column={column.key}")
            self._db.session.execute(
                update(waybackup_snapshots).where(waybackup_snapshots.scid == self.scid).values({column: value})
            )
            self._db.session.commit()
            vb.write(verbose="high", content=f"[Snapshot.modify] update committed scid={self.scid} column={column.key}")
        except Exception as e:
            vb.write(
                verbose="high", content=f"[Snapshot.modify] update failed scid={self.scid} error={e}; rolling back"
            )
            try:
                self._db.session.rollback()
            except Exception:
                pass
            raise

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
