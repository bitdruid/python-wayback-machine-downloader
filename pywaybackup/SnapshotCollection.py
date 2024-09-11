from pywaybackup.helper import url_split
from pywaybackup.db import Database
import json
import os

class SnapshotCollection:
    """
    Represents the interaction with the snapshot-collection contained in the snapshot database.
    """

    SNAPSHOT_AMOUNT = 0

    MODE_CURRENT = 0
    MODE_SKIP = 0

    FILTER_TIME_URL = 0

    @classmethod
    def init(cls, mode, skip):
        """
        Initialize the snapshot collection by inserting the content of the cdx file into the snapshot table.
        """        
        if mode == "current": 
            cls.MODE_CURRENT = 1
        if skip:
            cls.MODE_SKIP = 1

        cls.db = Database()
        
    @classmethod
    def fini(cls):
        """
        Close the connection to the snapshot database and remove the database file.
        """
        cls.db.conn.commit()
        cls.db.conn.close()
        os.remove(cls.db.SNAPSHOT_DB)

    @classmethod
    def insert_cdx(cls, cdxfile):
        """
        Insert the content of the cdx file into the snapshot table while setting up the snapshot-collection columns.
        """
        with open(cdxfile, "r") as f:
            line_batchsize = 1000
            line_batch = []
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
                    url_archive = f"https://web.archive.org/web/{line["timestamp"]}id_/{line["url"]}"
                    line_batch.append((line["timestamp"], url_archive, line["url"]))
                    if len(line_batch) >= line_batchsize:
                        cls.db.cursor.executemany("INSERT INTO snapshot_tbl (timestamp, url_archive, url_origin) VALUES (?, ?, ?)", line_batch)
                        line_batch = []
                except json.JSONDecodeError:
                    continue
            if line_batch:
                cls.db.cursor.executemany("INSERT INTO snapshot_tbl (timestamp, url_archive, url_origin) VALUES (?, ?, ?)", line_batch)
        cls.db.conn.commit()
        cls.filter_snapshots()
        cls.skip_set()





    @classmethod
    def csv_close(cls, csv_path):
        import csv
        """
        Write a CSV file with the list of snapshots. Append new snapshots to the existing file.
        """
        row_batchsize = 1000
        cls.db.cursor.execute("SELECT * FROM snapshot_tbl")
        headers = [description[0] for description in cls.db.cursor.description]
        with open(csv_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            while True:
                rows = cls.db.cursor.fetchmany(row_batchsize)
                if not rows:
                    break
                writer.writerows(rows)
        cls.db.conn.commit()





    @classmethod
    def filter_snapshots(cls):

        """
        Filter the snapshot table.

        - Remove entries which have the same timestamp AND url.
        - When mode is `current`, remove entries which are not the latest snapshot of each file.
        """

        # count the amount of snapshots that were filtered
        cls.db.cursor.execute(
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
        cls.FILTER_TIME_URL = cls.db.cursor.rowcount

        # filter the snapshot table by timestamp and url
        cls.db.cursor.execute(
            """
            DELETE FROM snapshot_tbl
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM snapshot_tbl
                GROUP BY timestamp, url_origin
            );
            """
        )
        cls.db.cursor.execute("DELETE FROM snapshot_filter_tbl")

        # filter the snapshot table and keep only the latest (timestamp) snapshot of each file
        if cls.MODE_CURRENT:
            cls.db.cursor.execute(
                """
                DELETE FROM snapshot_tbl
                WHERE timestamp NOT IN (
                    SELECT MAX(timestamp)
                    FROM snapshot_tbl
                    GROUP BY url_origin
                )
                """
            )

        # count snapshots
        cls.db.cursor.execute(
            """
            SELECT COUNT(id) FROM snapshot_tbl
            """
        )
        cls.SNAPSHOT_AMOUNT = cls.db.cursor.fetchone()[0]

        cls.db.conn.commit()

    @classmethod
    def skip_set(cls):
        """
        If --skip was not set, response is set to 'None' for all snapshots.
        """
        if cls.MODE_SKIP:
            cls.db.cursor.execute(
                """
                UPDATE snapshot_tbl
                SET response = 'None'
                """
            )
            cls.db.conn.commit()

    @classmethod
    def count_totals(cls, collection=False, success=False, fail=False, skip=False):
        if collection:
            return cls.SNAPSHOT_AMOUNT
        if success:
            cls.db.cursor.execute(
                """
                SELECT COUNT(id) FROM snapshot_tbl WHERE file IS NOT NULL
                """
            )
            return cls.db.cursor.fetchone()[0]
        if fail:
            cls.db.cursor.execute(
                """
                SELECT COUNT(id) FROM snapshot_tbl WHERE file IS NULL
                """
            )
            return cls.db.cursor.fetchone()[0]
        if skip:
            cls.db.cursor.execute(
                """
                SELECT COUNT(id) FROM snapshot_tbl WHERE response != 'None'
                """
            )
            return cls.db.cursor.fetchone()[0]
        return cls.SNAPSHOT_AMOUNT





    def modify_snapshot(connection, snapshot_id, column, value):
        """
        Modify a snapshot-row in the snapshot table.
        """
        connection.cursor.execute(
            f"""
            UPDATE snapshot_tbl
            SET {column} = ?
            WHERE id = ?
            """,
            (value, snapshot_id)
        )
        connection.conn.commit()

    def get_snapshot(connection, skip=False):
        """
        Get a snapshot-row from the snapshot table with response 'None'. (not processed)
        """
        connection.cursor.execute(
            """
            SELECT * FROM snapshot_tbl WHERE response = 'None' LIMIT 1
            """
        )
        return connection.cursor.fetchone()





    @classmethod
    def create_output(cls, url: str, timestamp: str, output: str):
        domain, subdir, filename = url_split(url.split("id_/")[1], index=True)
        if cls.MODE_CURRENT:
            download_dir = os.path.join(output, domain, subdir)
        else:
            download_dir = os.path.join(output, domain, timestamp, subdir)
        download_file = os.path.abspath(os.path.join(download_dir, filename))
        return download_file

