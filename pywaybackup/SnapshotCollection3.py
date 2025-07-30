import csv
import os

from pywaybackup.helper import url_split
from pywaybackup.db import Database


class SnapshotCollection:
    """
    Represents the interaction with the snapshot-collection contained in the snapshot database.
    """


    @classmethod
    def init(cls, mode):
        """
        Init mode and db
        """
        if mode == "first":
            cls.MODE_FIRST = 1
        if mode == "last":
            cls.MODE_LAST = 1

        cls.db = Database()


    @classmethod
    def csv_create(cls, csvfile):
        """
        Write a CSV file with the list of snapshots.
        """
        row_batchsize = 2500
        cls.db.cursor.execute("UPDATE snapshot_tbl SET response = NULL WHERE response = 'LOCK'")  # reset locked to unprocessed
        cls.db.cursor.execute("SELECT * FROM csv_view WHERE response IS NOT NULL")  # only write processed snapshots
        headers = [description[0] for description in cls.db.cursor.description]
        with open(csvfile, "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            while True:
                rows = cls.db.cursor.fetchmany(row_batchsize)
                if not rows:
                    break
                writer.writerows(rows)
        cls.db.conn.commit()

    @staticmethod
    def modify_snapshot(connection, snapshot_id, column, value):
        """
        Modify a snapshot-row in the snapshot table.
        """
        query = f"UPDATE snapshot_tbl SET {column} = ? WHERE counter = ?"
        connection.cursor.execute(query, (value, snapshot_id))
        connection.conn.commit()

    @staticmethod
    def get_snapshot(connection):
        """
        Get a snapshot-row from the snapshot table with response NULL. (not processed)
        """
        # mark as locked for other workers // only visual because get_snapshot fetches by NULL
        connection.cursor.execute(
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
        row = connection.cursor.fetchone()
        connection.conn.commit()
        return row

    @classmethod
    def create_output(cls, url: str, timestamp: str, output: str):
        """
        Create a file path for the snapshot.

        - If MODE_LAST or MODE_FIRST is enabled, the path does not include the timestamp.
        - Otherwise, include the timestamp in the path.
        """
        domain, subdir, filename = url_split(url.split("id_/")[1], index=True)

        if cls.MODE_LAST or cls.MODE_FIRST:
            download_dir = os.path.join(output, domain, subdir)
        else:
            download_dir = os.path.join(output, domain, timestamp, subdir)

        download_file = os.path.abspath(os.path.join(download_dir, filename))

        return download_file
