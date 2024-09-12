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
    # cdx_table = """CREATE TABLE IF NOT EXISTS cdx_tbl (
    #     id INTEGER PRIMARY KEY,
    #     timestamp TEXT,
    #     digest TEXT,
    #     mimetype TEXT,
    #     statuscode TEXT,
    #     original TEXT
    # )"""
    snapshot_table = """CREATE TABLE IF NOT EXISTS snapshot_tbl (
        timestamp TEXT,
        url_archive TEXT,
        url_origin TEXT,
        redirect_url TEXT,
        redirect_timestamp TEXT,
        response TEXT,
        file TEXT
    )"""

    @classmethod
    def init(cls, url, output):
        cls.SNAPSHOT_DB = os.path.join(output, f"waybackup_{sanitize_filename(url)}.db")
        db = Database()
        db.cursor.execute(cls.snapshot_table)
        db.cursor.execute("CREATE TABLE IF NOT EXISTS snapshot_filter_tbl AS SELECT * FROM snapshot_tbl WHERE 0")
        db.cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON snapshot_tbl (timestamp)")
        db.cursor.execute("CREATE INDEX IF NOT EXISTS idx_url_archive ON snapshot_tbl (url_archive)")
        db.conn.commit()
        db.close()

    def __init__(self):
        self.conn = sqlite3.connect(Database.SNAPSHOT_DB)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.commit()
        self.conn.close()
