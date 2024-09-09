import sqlite3
from pywaybackup.helper import url_split
from pywaybackup.helper import sanitize_filename
import json
import os

class SnapshotCollection:

    SNAPSHOT_AMOUNT = 0
    MODE_CURRENT = 0

    FILTER_TIME_URL = 0

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

    def connect_worker() -> sqlite3.Connection:
        return sqlite3.connect(SnapshotCollection.SNAPSHOT_DB)
    def close_worker(connection=sqlite3.Connection):
        sqlite3.Connection.commit()
        sqlite3.Connection.close()

    @classmethod
    def init(cls, cdxfile, mode, url, output):
        
        if mode == "current": 
            cls.MODE_CURRENT = 1
        cls.SNAPSHOT_DB = os.path.join(output, f"waybackup_{sanitize_filename(url)}.db")
        cls.conn = sqlite3.connect(cls.SNAPSHOT_DB)
        cls.cursor = cls.conn.cursor()
        cls.cursor.execute(cls.snapshot_table)
        cls.insert_cdx(cdxfile)
        cls.conn.commit()
        
    @classmethod
    def fini(cls):
        cls.conn.commit()
        cls.conn.close()
        os.remove(cls.SNAPSHOT_DB)

    @classmethod
    def insert_cdx(cls, cdxfile):
        """
        Insert the content of the cdx file into the snapshot table while setting up the snapshot-collection columns.
        """
        with open(cdxfile, "r") as f:
            first_line = True
            for line in f:
                if first_line:
                    first_line = False
                    continue
                line = line.strip()
                if line.endswith("]]"): line = line.rsplit("]", 1)[0]
                if line.endswith(","): line = line.rsplit(",", 1)[0]
                try:
                    line = json.loads(line)
                    line = {"timestamp": line[0], "digest": line[1], "mimetype": line[2], "status": line[3], "url": line[4]}
                except json.JSONDecodeError:
                    continue
                url_archive = f"https://web.archive.org/web/{line["timestamp"]}id_/{line["url"]}"
                cls.cursor.execute("INSERT INTO snapshot_tbl (timestamp, url_archive, url_origin) VALUES (?, ?, ?)", (line["timestamp"], url_archive, line["url"]))
        cls.conn.commit()
        cls.filter_snapshots()

    @classmethod
    def filter_snapshots(cls):

        """
        Filter the snapshot table.

        - Remove entries which have the same timestamp AND url.
        - When mode is `current`, remove entries which are not the latest snapshot of each file.
        """
        cls.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshot_filter_tbl AS SELECT * FROM snapshot_tbl WHERE 0;
            """
        )

        cls.cursor.execute(
            """
            INSERT INTO snapshot_filter_tbl
            SELECT * FROM snapshot_tbl
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM snapshot_tbl
                GROUP BY timestamp, url_origin
            )    
            """
        )
        cls.FILTER_TIME_URL = cls.cursor.rowcount

        cls.cursor.execute(
            """
            DELETE FROM snapshot_tbl
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM snapshot_tbl
                GROUP BY timestamp, url_origin
            )
            """
        )

        if cls.MODE_CURRENT:
            cls.cursor.execute(
                """
                DELETE FROM snapshot_tbl
                WHERE url_origin NOT IN (
                    SELECT url_origin
                    FROM snapshot_tbl
                    GROUP BY url_origin
                    HAVING MAX(timestamp) = timestamp
                )
                """
            )

        # count snapshots
        cls.cursor.execute(
            """
            SELECT COUNT(id) FROM snapshot_tbl
            """
        )
        cls.SNAPSHOT_AMOUNT = cls.cursor.fetchone()[0]

        cls.conn.commit()

    @classmethod
    def skip_snapshots(cls, skipset):
        """
        Skip snapshots in the snapshot table by url_archive.
        """
        skip_count = 0
        if not skipset:
            return skip_count
        for url_archive in skipset:
            cls.cursor.execute(
                """
                DELETE FROM snapshot_tbl
                WHERE url_archive = ?
                """,
                (url_archive,)
            )
            skip_count += cls.cursor.rowcount
        cls.conn.commit()
        return skip_count

    @classmethod
    def count_totals(cls, collection=False, success=False, fail=False):
        if collection:
            return cls.SNAPSHOT_AMOUNT
        if success:
            cls.cursor.execute(
                """
                SELECT COUNT(id) FROM snapshot_tbl WHERE file IS NOT NULL
                """
            )
            return cls.cursor.fetchone()[0]
        if fail:
            cls.cursor.execute(
                """
                SELECT COUNT(id) FROM snapshot_tbl WHERE file IS NULL
                """
            )
            return cls.cursor.fetchone()[0]
        return cls.SNAPSHOT_AMOUNT





    def modify_snapshot(connection, snapshot_id, column, value):
        """
        Modify a snapshot-row in the snapshot table.
        """
        cursor = connection.cursor()
        cursor.execute(
            f"""
            UPDATE snapshot_tbl
            SET {column} = ?
            WHERE id = ?
            """,
            (value, snapshot_id)
        )
        connection.commit()

    def get_snapshot(connection):
        """
        Get a snapshot-row from the snapshot table with status = 0 (not processed).
        """
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT * FROM snapshot_tbl WHERE status = 0 LIMIT 1
            """
        )
        return cursor.fetchone()





    @classmethod
    def create_output(cls, url: str, timestamp: str, output: str):
        domain, subdir, filename = url_split(url.split("id_/")[1], index=True)
        if cls.MODE_CURRENT:
            download_dir = os.path.join(output, domain, subdir)
        else:
            download_dir = os.path.join(output, domain, timestamp, subdir)
        download_file = os.path.abspath(os.path.join(download_dir, filename))
        return download_file

