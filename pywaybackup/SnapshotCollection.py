import json

from pywaybackup.db import Database
from pywaybackup.files import CDXfile, CSVfile
from pywaybackup.Verbosity import Progressbar
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex


class SnapshotCollection:
    """
    Represents the interaction with the snapshot-collection contained in the snapshot database.
    """

    def __init__(self):
        self.db = Database()
        self.cdxfile = None
        self.csvfile = None
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

    def close(self):
        """
        Close up the collection, write result into csv, totals into db.
        """
        self._write_summary()
        self._reset_locked_snapshots()
        self._finalize_db()

    def _write_summary(self):
        """Write summary of download and skip counts."""
        success = self.count_success()
        fail = self.count_fail()
        vb.write(content=f"\n{'downloaded'.ljust(12)}: {success}")
        vb.write(content=f"{'skipped'.ljust(12)}: {fail}")

    def _reset_locked_snapshots(self):
        """Reset locked snapshots to unprocessed in the database."""
        self.db.cursor.execute("UPDATE snapshot_tbl SET response = NULL WHERE response = 'LOCK'")

    def _finalize_db(self):
        """Commit and close the database connection, and write progress."""
        self.db.conn.commit()
        self.db.write_progress(self._snapshot_handled, self._snapshot_total)
        self.db.conn.close()

    def load(self, mode: str, cdxfile: CDXfile, csvfile: CSVfile):
        """
        Insert the content of the cdx and csv file into the snapshot table.
        """
        self.cdxfile = cdxfile
        self.csvfile = csvfile
        if mode == "first":
            self._mode_first = True
        if mode == "last":
            self._mode_last = True

        line_count = self.cdxfile.count_rows()
        self._cdx_total = line_count
        if not self.db.get_insert_complete():
            vb.write(content="\ninserting snapshots...")
            self._insert_cdx()
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

        self._skip_set()  # set response to NULL or read csv file and write values into db

        self._filter_duplicates = self.count_duplicates()  # duplicates are in CDX but not written to DB again (skipped)
        self._snapshot_unhandled = self.count_unhandled()  # count all unhandled in db
        self._snapshot_handled = self.count_handled()  # count all handled in db
        self._snapshot_total = self.count_total()  # count all in db

    def _insert_cdx(self):
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

        progressbar = Progressbar(
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
                    progressbar.update(line_batchsize)

            if line_batch:
                total_inserted += len(line_batch)
                self.db.cursor.executemany(query_duplicates, line_batch)
                progressbar.update(len(line_batch))

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

    def _skip_set(self):
        """
        If an existing csv-file for the job exists, the responses will be overwritten by the csv-content.
        """
        if not self.csvfile.file:
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

    def count_total(self) -> int:
        return self.db.count("SELECT COUNT(rowid) FROM snapshot_tbl")

    def count_handled(self) -> int:
        return self.db.count("SELECT COUNT(rowid) FROM snapshot_tbl WHERE response IS NOT NULL")

    def count_unhandled(self) -> int:
        return self.db.count("SELECT COUNT(rowid) FROM snapshot_tbl WHERE response IS NULL")

    def count_success(self) -> int:
        return self.db.count("SELECT COUNT(rowid) FROM snapshot_tbl WHERE file IS NOT NULL AND file != ''")

    def count_fail(self) -> int:
        return self.db.count("SELECT COUNT(rowid) FROM snapshot_tbl WHERE file IS NULL OR file = ''")

    def count_duplicates(self) -> int:
        """duplicates = total CDX records - total in db"""
        return self._cdx_total - self.count_total()

    def print_calculation(self):
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
        else:
            vb.write(content=f"-----> {'unhandled'.ljust(18)}: {self._snapshot_unhandled:,}")

        if self._snapshot_faulty > 0:
            vb.write(content=f"\n-----> {'!!! parsing error'.ljust(18)}: {self._snapshot_faulty:,}")
