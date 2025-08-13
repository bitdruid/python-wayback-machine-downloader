import os
import json

from pywaybackup.helper import url_split

from pywaybackup.Verbosity import Verbosity as vb, Progressbar
from pywaybackup.db import Database
from pywaybackup.files import CDXfile, CSVfile


class Snapshot:
    def __init__(self, db: Database):
        self._db = db
        self._row = self.fetch()
        if self._row:
            self.counter = self._row["counter"]
            self.timestamp = self._row["timestamp"]
            self.url_archive = self._row["url_archive"]
            self.url_origin = self._row["url_origin"]
            self.redirect_url = self._row["redirect_url"]
            self.redirect_timestamp = self._row["redirect_timestamp"]
            self.response = self._row["response"]
            self.file = self._row["file"]

    def modify(self, snapshot_id, column, value):
        """
        Modify a snapshot-row in the snapshot table.
        """
        query = f"UPDATE snapshot_tbl SET {column} = ? WHERE counter = ?"
        self._db.cursor.execute(query, (value, snapshot_id))
        self._db.conn.commit()

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

    def create_output(self, url: str, timestamp: str, output: str, mode: str):
        """
        Create a file path for the snapshot.

        - If MODE_LAST or MODE_FIRST is enabled, the path does not include the timestamp.
        - Otherwise, include the timestamp in the path.
        """
        domain, subdir, filename = url_split(url.split("id_/")[1], index=True)

        if mode == "last" or mode == "first":
            download_dir = os.path.join(output, domain, subdir)
        else:
            download_dir = os.path.join(output, domain, timestamp, subdir)

        download_file = os.path.abspath(os.path.join(download_dir, filename))

        return download_file


class SnapshotCollection:
    """
    Represents the interaction with the snapshot-collection contained in the snapshot database.
    """

    def __init__(self, cdxfile: CDXfile, csvfile: CSVfile, mode: str):
        self._status = 0  # 0 = unprocessed, 1 = inserted, 2 = downloaded
        self._mode_first = False
        self._mode_last = False

        self._cdx_total = 0  # absolute amount of snapshots in cdx file
        self._snapshot_total = 0  # absolute amount of snapshots in db

        self._snapshot_unhandled = 0  # all unhandled snapshots in the db (without response)
        self._snapshot_handled = 0  # snapshots with a response

        self._snapshot_faulty = 0  # error while parsing cdx line

        self._filter_duplicates = 0  # with identical url_archive
        self._filter_mode = 0  # all snapshots filtered by the MODE (last or first)
        self._filter_skip = 0  # content of the csv file
        self._filter_response = 0  # snapshots which could not be loaded from cdx file into db or 404

        self.cdxfile = cdxfile
        self.csvfile = csvfile
        self.db = Database()
        if mode == "first":
            self._mode_first = True
        if mode == "last":
            self._mode_last = True

    def close(self):
        """
        Close up the collection as work is done.
        """
        self.db.write_progress(self._snapshot_handled, self._snapshot_total)
        self.db.conn.close()

    def load(self):
        """
        Insert the content of the cdx file into the snapshot table.
        """
        line_count = self.csvfile.count_rows()
        self._cdx_total = line_count
        if not self.db.get_insert_complete():
            self._insert_cdx(self.cdxfile)
            self.db.set_insert_complete()
        else:
            vb.write(verbose=True, content="\nAlready inserted CDX data into database")
        if not self.db.get_index_complete():
            vb.write(content="\nIndexing snapshots...")
            self._index_snapshots()  # create indexes for the snapshot table
            self.db.set_index_complete()
        else:
            vb.write(verbose=True, content="\nAlready indexed snapshots")
        if not self.db.get_filter_complete():
            vb.write(content="\nFiltering snapshots (last or first version)...")
            self._filter_snapshots()  # filter: keep newest or oldest based on MODE
            self.db.set_filter_complete()
        else:
            vb.write(verbose=True, content="\nAlready filtered snapshots (last or first version)")

        self._skip_set(self.csvfile)  # set response to NULL or read csv file and write values into db
        self._status = 1

    def _insert_cdx(self, cdxfile):
        """
        Insert the content of the cdx file into the snapshot table.
        - Removes duplicates by url_archive (same timestamp and url_origin)
        - Filters the snapshots by the given mode (last or first)
        """

        def __parse_line(line):
            line = json.loads(line)
            line = {
                "timestamp": line[0],
                "digest": line[1],
                "mimetype": line[2],
                "statuscode": line[3],
                "origin": line[4],
            }
            url_archive = f"https://web.archive.org/web/{line['timestamp']}id_/{line['origin']}"
            statuscode = line["statuscode"] if line["statuscode"] in ("301", "404") else None
            return (line["timestamp"], url_archive, line["origin"], statuscode)

        vb.write(verbose=None, content="\nInserting CDX data into database...")

        progress = Progressbar(
            unit=" lines",
            total=self._cdx_total,
            desc="process cdx".ljust(15),
            ascii="░▒█",
            bar_format="{l_bar}{bar:50}{r_bar}{bar:-10b}",
        )
        line_batchsize = 2500
        line_batch = []
        total_inserted = 0
        query_duplicates = """INSERT OR IGNORE INTO snapshot_tbl (timestamp, url_archive, url_origin, response) VALUES (?, ?, ?, ?)"""
        first_line = True

        with self.cdxfile as f:
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
                    line_batch.append(__parse_line(line))
                except json.decoder.JSONDecodeError:
                    self._snapshot_faulty += 1
                    continue

                if len(line_batch) >= line_batchsize:
                    total_inserted += len(line_batch)
                    self.db.cursor.executemany(query_duplicates, line_batch)
                    line_batch = []
                    progress.update(line_batchsize)

            if line_batch:
                total_inserted += len(line_batch)
                self.db.cursor.executemany(query_duplicates, line_batch)
                progress.update(len(line_batch))

        self.db.conn.commit()

    def _index_snapshots(self):
        """
        Create indexes for the snapshot table.
        """
        # index for filtering last snapshots
        if self._mode_last:
            self.db.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_tbl_url_origin_timestamp_desc ON snapshot_tbl(url_origin, timestamp DESC);"
            )
        # index for filtering first snapshots
        if self._mode_first:
            self.db.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_tbl_url_origin_timestamp_asc ON snapshot_tbl(url_origin, timestamp ASC);"
            )
        # index for skippable snapshots
        self.db.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_tbl_timestamp_url_origin_response ON snapshot_tbl(timestamp, url_origin);"
        )

    def _filter_snapshots(self):
        """
        Filter the snapshot table.

        - When mode is `MODE_LAST`, keep only the latest snapshot (highest timestamp) for each file.
        - When mode is `MODE_FIRST`, keep only the earliest snapshot (lowest timestamp) for each file.
        """
        # rows get a row number based on the timestamp per url_origin and are deleted if the row number is greater / lower than 1
        if self._mode_last or self._mode_first:
            ordering = ""
            if self._mode_last:
                ordering = "DESC"
            if self._mode_first:
                ordering = "ASC"
            self.db.cursor.execute(
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
            self._filter_mode = self.db.cursor.rowcount

        self.db.cursor.execute(
            """
        SELECT COUNT(*) FROM snapshot_tbl WHERE response IN ('404', '301')
        """
        )
        self._filter_response = self.db.cursor.fetchone()[0]

        self.db.cursor.execute(
            """
            WITH numbered AS (
                SELECT rowid, ROW_NUMBER() OVER (ORDER BY rowid) AS rn
                FROM snapshot_tbl
            )
            UPDATE snapshot_tbl
            SET counter = (
                SELECT rn FROM numbered WHERE numbered.rowid = snapshot_tbl.rowid
            );
            """
        )

        self.db.conn.commit()

    def _skip_set(self, csvfile):
        """
        If an existing csv-file for the job exists, the responses will be overwritten by the csv-content.
        """
        if not csvfile.file:
            return
        else:
            with self.csvfile as f:
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
                for row in f:
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
                        self.db.cursor.executemany(query, row_batch)
                        row_batch = []
                if row_batch:
                    total_skipped += len(row_batch)
                    self.db.cursor.executemany(query, row_batch)
                self.db.conn.commit()
                self._filter_skip = total_skipped

    def print_calculation(self):
        def __count(self, duplicate=False, total=False, handled=False, unhandled=False, success=False, fail=False):
            """
            Counts several types of snapshots in the snapshot table.

            Only one parameter should be set to True at a time. If multiple parameters are True,
            only the first condition that evaluates to True will be executed.
            """
            if duplicate:
                return self._cdx_total - __count(self, total=True)
            if total:
                return self.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl").fetchone()[0]
            if handled:
                return self.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE response IS NOT NULL").fetchone()[0]
            if unhandled:
                return self.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE response IS NULL").fetchone()[0]
            if success:
                return self.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE file IS NOT NULL AND file != ''").fetchone()[0]
            if fail:
                return self.db.cursor.execute("SELECT COUNT(rowid) FROM snapshot_tbl WHERE file IS NULL OR file = ''").fetchone()[0]

        if self._status == 1:
            self._filter_duplicates = __count(self, duplicate=True)  # duplicates are in CDX but not written to DB again (skipped)
            self._snapshot_unhandled = __count(self, unhandled=True)  # count all unhandled in db
            self._snapshot_handled = __count(self, handled=True)  # count all handled in db
            self._snapshot_total = __count(self, total=True)  # count all in db

            vb.write(content="\nSnapshot calculation:")
            vb.write(content=f"-----> {'in CDX file'.ljust(18)}: {self._cdx_total:,}")

            if self._filter_duplicates > 0:
                vb.write(content=f"-----> {'removed duplicates'.ljust(18)}: {self._filter_duplicates:,}")
            if self._filter_mode > 0:
                vb.write(content=f"-----> {'removed versions'.ljust(18)}: {self._filter_mode:,}")

            if self._filter_skip > 0:
                vb.write(content=f"-----> {'skip existing'.ljust(18)}: {self._filter_skip:,}")
            if self._filter_response > 0:
                vb.write(content=f"-----> {'skip statuscode'.ljust(18)}: {self._filter_response}")

            if self._snapshot_unhandled > 0:
                vb.write(content=f"\n-----> {'to utilize'.ljust(18)}: {self._snapshot_unhandled:,}")

            if self._snapshot_faulty > 0:
                vb.write(content=f"\n-----> {'!!! parsing error'.ljust(18)}: {self._snapshot_faulty:,}")

        if self._status == 2:
            success = __count(self, success=True)
            fail = __count(self, fail=True)
            vb.write(content=f"\nFiles downloaded: {success}")
            vb.write(content=f"Not downloaded: {fail}")