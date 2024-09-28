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
    waybackup_table = """CREATE TABLE IF NOT EXISTS waybackup_table (
        query_identifier TEXT PRIMARY KEY,
        insert_complete INTEGER,
        index_complete INTEGER,
        filter_complete INTEGER
    )"""        
    snapshot_table = """CREATE TABLE IF NOT EXISTS snapshot_tbl (
        timestamp TEXT,
        url_archive TEXT,
        url_origin TEXT,
        redirect_url TEXT,
        redirect_timestamp TEXT,
        response TEXT,
        file TEXT,
        UNIQUE (url_archive)
    )"""

    @classmethod
    def init(cls, dbfile, query_identifier):
        cls.SNAPSHOT_DB = dbfile
        db = Database()
        db.cursor.execute(cls.waybackup_table)
        db.cursor.execute(cls.snapshot_table)
        db.cursor.execute("INSERT OR IGNORE INTO waybackup_table (query_identifier) VALUES (?)", (query_identifier,))
        db.conn.commit()
        db.close()

    def __init__(self):
        self.conn = sqlite3.connect(Database.SNAPSHOT_DB)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def get_insert_complete(self):
        return self.cursor.execute("SELECT insert_complete FROM waybackup_table WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)").fetchone()[0]
    def get_index_complete(self):
        return self.cursor.execute("SELECT index_complete FROM waybackup_table WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)").fetchone()[0]
    def get_filter_complete(self):
        return self.cursor.execute("SELECT filter_complete FROM waybackup_table WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)").fetchone()[0]
    def set_insert_complete(self):
        self.cursor.execute("UPDATE waybackup_table SET insert_complete = 1 WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)")
        self.conn.commit()
    def set_index_complete(self):
        self.cursor.execute("UPDATE waybackup_table SET index_complete = 1 WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)")
        self.conn.commit()
    def set_filter_complete(self):
        self.cursor.execute("UPDATE waybackup_table SET filter_complete = 1 WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)")
        self.conn.commit()