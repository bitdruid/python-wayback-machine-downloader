import sqlite3
import os
from pywaybackup.helper import sanitize_filename

class Database:

    """
    Creates the snapshot database and the snapshot table when initialized.

    When instantiated, a connection and cursor are created to interact with the database.

    Interaction with the database is done through the SnapshotCollection class.
    """

    SNAPSHOT_DB = ""
    snapshot_table = """CREATE TABLE IF NOT EXISTS snapshot_tbl (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        url_archive TEXT,
        url_origin TEXT,
        redirect_url TEXT,
        redirect_timestamp TEXT,
        response TEXT,
        file TEXT,
        status boolean DEFAULT 0
    )"""

    @classmethod
    def init(cls, url, output):
        cls.SNAPSHOT_DB = os.path.join(output, f"waybackup_{sanitize_filename(url)}.db")
        db = Database()
        db.cursor.execute(cls.snapshot_table)
        db.cursor.execute("CREATE TABLE IF NOT EXISTS snapshot_filter_tbl AS SELECT * FROM snapshot_tbl WHERE 0")
        db.conn.commit()
        db.close()

    def __init__(self):
        self.conn = sqlite3.connect(Database.SNAPSHOT_DB)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.commit()
        self.conn.close()
