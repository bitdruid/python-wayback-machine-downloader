import json
import csv
import os

from tqdm import tqdm

from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.helper import url_split
from pywaybackup.db import Database

class SnapshotCollection:
    """
    Represents the interaction with the snapshot-collection contained in the snapshot database.
    """

    MODE_LAST = 0           # given by argument --last
    MODE_FIRST = 0          # given by --first

    CDX_TOTAL = 0           # absolute amount of snapshots in cdx file
    SNAPSHOT_TOTAL = 0      # absolute amount of snapshots in db

    SNAPSHOT_UNHANDLED = 0  # all unhandled snapshots in the db (without response)
    SNAPSHOT_HANDLED = 0    # snapshots with a response

    SNAPSHOT_REMOVALS = 0   # not to be utilized (total - unhandled - skip)
    SNAPSHOT_FAULTY = 0     # snapshots which could not be loaded from cdx file into db
    FILTER_DUPLICATES = 0   # with identical url_archive
    FILTER_MODE = 0         # all snapshots filtered by the MODE (last or first)
    FILTER_SKIP = 0         # content of the csv file

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
    def fini(cls):
        """
        Close the database connection and write progress to the database.
        """
        cls.db.write_progress(cls.SNAPSHOT_HANDLED, cls.SNAPSHOT_TOTAL)
        cls.db.conn.commit()
        cls.db.conn.close()





    @classmethod
    def process_cdx(cls, cdxfile, csvfile):
        """
        Insert the content of the cdx file into the snapshot table.
        """
        line_count = sum(1 for _ in open(cdxfile, encoding="utf-8")) - 1
        cls.CDX_TOTAL = line_count
        if not cls.db.get_insert_complete():
            cls.insert_cdx(cdxfile)
            cls.db.set_insert_complete()
        else: 
            vb.write(verbose=True, content="\nAlready inserted CDX data into database")
        if not cls.db.get_index_complete():
            vb.write(content="\nIndexing snapshots...")
            cls.index_snapshots() # create indexes for the snapshot table
            cls.db.set_index_complete()
        else: 
            vb.write(verbose=True, content="\nAlready indexed snapshots")
        if cls.MODE_LAST or cls.MODE_FIRST:
            if not cls.db.get_filter_complete():
                vb.write(content="\nFiltering snapshots (last or first version)...")
                cls.filter_snapshots() # filter: keep newest or oldest based on MODE
                cls.db.set_filter_complete()
            else:
                vb.write(verbose=True, content="\nAlready filtered snapshots (last or first version)")

        cls.skip_set(csvfile)  # set response to NULL or read csv file and write values into db
        cls.SNAPSHOT_UNHANDLED = cls.count_totals(unhandled=True)  # count all unhandled in db
        cls.SNAPSHOT_HANDLED = cls.count_totals(handled=True)  # count all handled in db
        cls.SNAPSHOT_TOTAL = cls.count_totals(total=True)  # count all in db
        cls.SNAPSHOT_REMOVALS = cls.CDX_TOTAL - cls.SNAPSHOT_UNHANDLED - cls.FILTER_SKIP  # count all removals

        vb.write(content="\nSnapshot calculation:")
        vb.write(content=f"-----> {'in CDX file'.ljust(18)}: {cls.CDX_TOTAL:,}")

        if cls.FILTER_DUPLICATES == 0 and cls.FILTER_MODE == 0:
            vb.write(content=f"-----> {'total removals'.ljust(18)}: {cls.SNAPSHOT_REMOVALS:,}")
        if cls.SNAPSHOT_FAULTY > 0:
            vb.write(content=f"-----> {'removed faulty'.ljust(18)}: {cls.SNAPSHOT_FAULTY}")
        if cls.FILTER_DUPLICATES > 0:
            vb.write(content=f"-----> {'removed duplicates'.ljust(18)}: {cls.FILTER_DUPLICATES:,}")
        if cls.FILTER_MODE > 0:
            vb.write(content=f"-----> {'removed versions'.ljust(18)}: {cls.FILTER_MODE:,}")
        if cls.FILTER_SKIP > 0:
            vb.write(content=f"-----> {'skipped existing'.ljust(18)}: {cls.FILTER_SKIP:,}")

        vb.write(content=f"\n-----> {'to utilize'.ljust(18)}: {cls.SNAPSHOT_UNHANDLED:,}")





    @classmethod
    def insert_cdx(cls, cdxfile):
        """
        Insert the content of the cdx file into the snapshot table.
        - Removes duplicates by url_archive (same timestamp and url_origin)
        - Filters the snapshots by the given mode (last or first)
        """
        vb.write(verbose=None, content="\nInserting CDX data into database...")
        with open(cdxfile, "r", encoding="utf-8") as f, tqdm(
            unit=" lines",
            total=cls.CDX_TOTAL,
            desc="insert cdx".ljust(15),
            ascii="░▒█",
            bar_format="{l_bar}{bar:50}{r_bar}{bar:-10b}",
        ) as pbar:
            line_batchsize = 2500
            line_batch = []
            total_inserted = 0
            faulty_lines = 0
            query_duplicates = (
                """INSERT OR IGNORE INTO snapshot_tbl (timestamp, url_archive, url_origin) VALUES (?, ?, ?)"""
            )
            first_line = True
            for line in f:
                if first_line:
                    first_line = False
                    continue
                line = line.strip()
                if line.endswith("]]"):
                    line = line.rsplit("]", 1)[0]
                if line.endswith(","):
                    line = line.rsplit(",", 1)[0]
                try:
                    line = json.loads(line)
                    line = {
                        "timestamp": line[0],
                        "digest": line[1],
                        "mimetype": line[2],
                        "status": line[3],
                        "url": line[4],
                    }
                    url_archive = f"https://web.archive.org/web/{line['timestamp']}id_/{line['url']}"
                    line_batch.append((line["timestamp"], url_archive, line["url"]))
                    if len(line_batch) >= line_batchsize:
                        total_inserted += len(line_batch)
                        cls.db.cursor.executemany(query_duplicates, line_batch)
                        line_batch = []
                        pbar.update(line_batchsize)
                except json.JSONDecodeError as e:
                    faulty_lines += 1
                    vb.write(
                        verbose=None,
                        content=f"JSONDecodeError: {e} on line {cls.CDX_TOTAL}",
                    )
                    continue
            if line_batch:
                total_inserted += len(line_batch)
                cls.db.cursor.executemany(query_duplicates, line_batch)
                pbar.update(len(line_batch))

        cls.db.conn.commit()

        cls.SNAPSHOT_FAULTY = faulty_lines
        cls.FILTER_DUPLICATES = cls.CDX_TOTAL - cls.count_totals(unhandled=True) + cls.SNAPSHOT_FAULTY





    @classmethod
    def csv_create(cls, csvfile):
        """
        Write a CSV file with the list of snapshots.
        """
        row_batchsize = 2500
        cls.db.cursor.execute("UPDATE snapshot_tbl SET response = NULL WHERE response = 'LOCK'") # reset locked to unprocessed
        cls.db.cursor.execute("SELECT * FROM snapshot_tbl WHERE response IS NOT NULL") # only write processed snapshots
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





    @classmethod
    def index_snapshots(cls):
        """
        Create indexes for the snapshot table.
        """
        # index for filtering last snapshots
        cls.db.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_tbl_url_origin_timestamp_desc ON snapshot_tbl(url_origin, timestamp DESC);"
        )
        # index for filtering first snapshots
        cls.db.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_tbl_url_origin_timestamp_asc ON snapshot_tbl(url_origin, timestamp ASC);"
        )
        # index for skippable snapshots
        cls.db.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_tbl_timestamp_url_origin_response ON snapshot_tbl(timestamp, url_origin);"
        )





    @classmethod
    def filter_snapshots(cls):
        """
        Filter the snapshot table.

        - When mode is `MODE_LAST`, keep only the latest snapshot (highest timestamp) for each file.
        - When mode is `MODE_FIRST`, keep only the earliest snapshot (lowest timestamp) for each file.
        """
        # rows get a row number based on the timestamp per url_origin and are deleted if the row number is greater / lower than 1
        if cls.MODE_LAST or cls.MODE_FIRST:
            if cls.MODE_LAST:
                ordering = "DESC"
            if cls.MODE_FIRST:
                ordering = "ASC"
            cls.db.cursor.execute(
                f"""
                DELETE FROM snapshot_tbl
                WHERE rowid IN (
                    SELECT rowid FROM (
                        SELECT rowid,
                            ROW_NUMBER() OVER (PARTITION BY url_origin ORDER BY timestamp {ordering}) AS ranking
                        FROM snapshot_tbl
                    ) tmp
                    WHERE ranking > 1
                );
                """
            )
            cls.FILTER_MODE = cls.db.cursor.rowcount

        cls.db.conn.commit()





    @classmethod
    def skip_set(cls, csvfile):
        """
        If an existing csv-file for the job exists, the responses will be overwritten by the csv-content.
        """
        cls.db.cursor.execute(
            """
            UPDATE snapshot_tbl
            SET response = NULL
            """
        )
        cls.db.conn.commit()
        if not os.path.isfile(csvfile):
            return
        else:
            with open(csvfile, "r", encoding="utf-8") as f:
                csv_content = csv.DictReader(f)
                row_batchsize = 2500
                row_batch = []
                total_skipped = 0
                query = """
                        UPDATE snapshot_tbl SET
                        url_archive = ?,
                        redirect_url = ?,
                        redirect_timestamp = ?,
                        response = ?,
                        file = ?
                        WHERE timestamp = ? AND url_origin = ?
                        """
                for row in csv_content:
                    row_batch.append(
                        (
                            row["url_archive"],
                            row["redirect_url"],
                            row["redirect_timestamp"],
                            row["response"],
                            row["file"],
                            row["timestamp"],
                            row["url_origin"],
                        )
                    )
                    if len(row_batch) >= row_batchsize:
                        total_skipped += len(row_batch)
                        cls.db.cursor.executemany(query, row_batch)
                        row_batch = []
                if row_batch:
                    total_skipped += len(row_batch)
                    cls.db.cursor.executemany(query, row_batch)
                cls.db.conn.commit()
                cls.FILTER_SKIP = total_skipped





    @classmethod
    def count_totals(cls, total=False, handled=False, unhandled=False, success=False, fail=False):
        """
        Counts several types of snapshots in the snapshot table.

        Only one parameter should be set to True at a time. If multiple parameters are True,
        only the first condition that evaluates to True will be executed.
        """

        if total:
            return cls.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl").fetchone()[0]
        if handled:
            return cls.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE response IS NOT NULL").fetchone()[
                0
            ]
        if unhandled:
            return cls.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE response IS NULL").fetchone()[0]
        if success:
            return cls.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE file IS NOT NULL").fetchone()[0]
        if fail:
            return cls.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE file IS NULL").fetchone()[0]

    @staticmethod
    def modify_snapshot(connection, snapshot_id, column, value):
        """
        Modify a snapshot-row in the snapshot table.
        """
        query = f"UPDATE snapshot_tbl SET {column} = ? WHERE rowid = ?"
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