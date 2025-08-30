import pysqlite3 as sqlite3

class Database:

    """
    Creates the snapshot database and the snapshot table when initialized.

    When instantiated, a connection and cursor are created to interact with the database.
    """

    DBFILE = ""
    waybackup_table = """CREATE TABLE IF NOT EXISTS waybackup_table (
        query_identifier TEXT PRIMARY KEY,
        query_progress TEXT,
        insert_complete INTEGER,
        index_complete INTEGER,
        filter_complete INTEGER
    )"""        
    snapshot_table = """CREATE TABLE IF NOT EXISTS snapshot_tbl (
        counter INT,
        timestamp TEXT,
        url_archive TEXT,
        url_origin TEXT,
        redirect_url TEXT,
        redirect_timestamp TEXT,
        response TEXT,
        file TEXT,
        UNIQUE (url_archive)
    )"""
    csv_view = """CREATE VIEW IF NOT EXISTS csv_view
        AS
            SELECT 
                timestamp AS timestamp,
                url_archive AS url_archive,
                url_origin AS url_origin,
                redirect_url AS redirect_url,
                redirect_timestamp AS redirect_timestamp,
                response AS response,
                file AS file
        FROM snapshot_tbl;
    """

    QUERY_EXIST = False
    QUERY_PROGRESS = "0 / 0"

    @classmethod
    def init(cls, dbfile, query_identifier):
        cls.DBFILE = dbfile
        db = Database()
        db.cursor.execute(cls.waybackup_table)
        db.cursor.execute(cls.snapshot_table)
        db.cursor.execute(cls.csv_view)
        db.cursor.execute("SELECT query_identifier FROM waybackup_table WHERE query_identifier = ?", (query_identifier,))
        if db.cursor.fetchone():
            cls.QUERY_EXIST = True
            cls.QUERY_PROGRESS = db.get_progress()
        else:
            db.cursor.execute("INSERT OR IGNORE INTO waybackup_table (query_identifier) VALUES (?)", (query_identifier,))
        db.conn.commit()
        db.close()

    def __init__(self):
        self.conn = sqlite3.connect(Database.DBFILE)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def write_progress(self, done: int, total: int):
        progress = f"{(done):,} / {(total):,}"
        self.cursor.execute("UPDATE waybackup_table SET query_progress = ? WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)", (progress,))
        self.conn.commit()
    def get_progress(self):
        return self.cursor.execute("SELECT query_progress FROM waybackup_table WHERE query_identifier = (SELECT query_identifier FROM waybackup_table)").fetchone()[0]

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

    def count(self, query: str) -> int:
        """
        Pass a COUNT query to get the number of rows in a table.
        """
        try:
            return self.cursor.execute(query).fetchone()[0]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                return 0
            raise
