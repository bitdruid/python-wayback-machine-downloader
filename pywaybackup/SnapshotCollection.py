import json

from pywaybackup.db import Database, Index, and_, delete, func, or_, select, tuple_, update, waybackup_snapshots
from pywaybackup.files import CDXfile, CSVfile
from pywaybackup.Verbosity import Progressbar
from pywaybackup.Verbosity import Verbosity as vb

func: callable


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
        self.db.session.execute(
            update(waybackup_snapshots).where(waybackup_snapshots.response == "LOCK").values(response=None)
        )
        self.db.session.commit()

    def _finalize_db(self):
        """Commit and close the database connection, and write progress."""
        self.db.write_progress(self._snapshot_handled, self._snapshot_total)
        self.db.session.close()

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
            return {
                "timestamp": line["timestamp"],
                "url_archive": url_archive,
                "url_origin": line["origin"],
                "response": statuscode,
            }

        def _insert_batch_safe(line_batch):
            # removes duplicates within the line_batch itself
            seen_keys = set()
            unique_batch = []
            for row in line_batch:
                key = (row["timestamp"], row["url_origin"], row["url_archive"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_batch.append(row)

            # removes duplicates from the line_batch if they are already in the database
            # get existing entries by tuple, remove existing rows from the unique_batch
            keys = [(row["timestamp"], row["url_origin"], row["url_archive"]) for row in unique_batch]
            existing = (
                self.db.session.query(
                    waybackup_snapshots.timestamp,
                    waybackup_snapshots.url_origin,
                    waybackup_snapshots.url_archive,
                )
                .filter(
                    tuple_(
                        waybackup_snapshots.timestamp, waybackup_snapshots.url_origin, waybackup_snapshots.url_archive
                    ).in_(keys)
                )
                .all()
            )
            existing_rows = set(existing)
            new_rows = [
                row
                for row in unique_batch
                if (row["timestamp"], row["url_origin"], row["url_archive"]) not in existing_rows
            ]
            if new_rows:
                self.db.session.bulk_insert_mappings(waybackup_snapshots, new_rows)
                self.db.session.commit()
            self._filter_duplicates += len(line_batch) - len(new_rows)
            return len(new_rows)

        vb.write(verbose=None, content="\nInserting CDX data into database...")

        try:
            vb.write(verbose=True, content="[SnapshotCollection._insert_cdx] starting insert_cdx operation")
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
                        total_inserted += _insert_batch_safe(line_batch=line_batch)
                        line_batch = []
                        progressbar.update(line_batchsize)

                if line_batch:
                    total_inserted += _insert_batch_safe(line_batch=line_batch)
                    progressbar.update(len(line_batch))

            self.db.session.commit()
            vb.write(verbose=True, content="[SnapshotCollection._insert_cdx] insert_cdx commit successful")
        except Exception as e:
            vb.write(verbose=True, content=f"[SnapshotCollection._insert_cdx] exception: {e}; rolling back")
            try:
                self.db.session.rollback()
                vb.write(verbose=True, content="[SnapshotCollection._insert_cdx] rollback successful")
            except Exception:
                vb.write(verbose=True, content="[SnapshotCollection._insert_cdx] rollback failed")
            raise

    def _index_snapshots(self):
        """
        Create indexes for the snapshot table.
        """
        # index for filtering last snapshots
        if self._mode_last:
            idx1 = Index(
                "idx_waybackup_snapshots_url_origin_timestamp_desc",
                waybackup_snapshots.url_origin,
                waybackup_snapshots.timestamp.desc(),
            )
            idx1.create(self.db.session.bind, checkfirst=True)
        # index for filtering first snapshots
        if self._mode_first:
            idx2 = Index(
                "idx_waybackup_snapshots_url_origin_timestamp_asc",
                waybackup_snapshots.url_origin,
                waybackup_snapshots.timestamp.asc(),
            )
            idx2.create(self.db.session.bind, checkfirst=True)
        # index for skippable snapshots
        idx3 = Index(
            "idx_waybackup_snapshots_timestamp_url_origin_response",
            waybackup_snapshots.timestamp,
            waybackup_snapshots.url_origin,
        )
        idx3.create(self.db.session.bind, checkfirst=True)

    def _filter_snapshots(self):
        """
        Filter the snapshot table.

        - MODE_LAST → keep only the latest snapshot (highest timestamp) per url_origin.
        - MODE_FIRST → keep only the earliest snapshot (lowest timestamp) per url_origin.
        """

        def _filter_mode():
            self._filter_mode = 0
            if self._mode_last or self._mode_first:
                ordering = (
                    waybackup_snapshots.timestamp.desc() if self._mode_last else waybackup_snapshots.timestamp.asc()
                )
                # assign row numbers per url_origin
                rownum = (
                    func.row_number()
                    .over(
                        partition_by=waybackup_snapshots.url_origin,
                        order_by=ordering,
                    )
                    .label("rn")
                )
                subq = select(waybackup_snapshots.scid, rownum).subquery()
                # keep rn == 1, delete all others
                keepers = select(subq.c.scid).where(subq.c.rn == 1)
                stmt = delete(waybackup_snapshots).where(~waybackup_snapshots.scid.in_(keepers))
                result = self.db.session.execute(stmt)
                self.db.session.commit()
                self._filter_mode = result.rowcount

        def _enumerate_counter():
            # this sets the counter (snapshot number x / y) to 1 ... n
            offset = 1
            batch_size = 5000
            while True:
                rows = (
                    self.db.session.execute(
                        select(waybackup_snapshots.scid)
                        .where(waybackup_snapshots.counter.is_(None))
                        .order_by(waybackup_snapshots.scid)
                        .limit(batch_size)
                    )
                    .scalars()
                    .all()
                )
                if not rows:
                    break
                mappings = [{"scid": scid, "counter": i} for i, scid in enumerate(rows, start=offset)]
                self.db.session.bulk_update_mappings(waybackup_snapshots, mappings)
                self.db.session.commit()
                offset += len(rows)

        _filter_mode()
        _enumerate_counter()
        self._filter_response = (
            self.db.session.query(waybackup_snapshots).where(waybackup_snapshots.response.in_(["404", "301"])).count()
        )
        self.db.session.commit()

    def _skip_set(self):
        """
        If an existing csv-file for the job was found, the responses will be overwritten by the csv-content.
        """

        # ? for now per row / no bulk for compatibility
        try:
            vb.write(verbose=True, content="[SnapshotCollection._skip_set] applying CSV skips to DB")
            with self.csvfile as f:
                total_skipped = 0
                for row in f:
                    self.db.session.execute(
                        update(waybackup_snapshots)
                        .where(
                            and_(
                                waybackup_snapshots.timestamp == row["timestamp"],
                                waybackup_snapshots.url_origin == row["url_origin"],
                            )
                        )
                        .values(
                            url_archive=row["url_archive"],
                            redirect_url=row["redirect_url"],
                            redirect_timestamp=row["redirect_timestamp"],
                            response=row["response"],
                            file=row["file"],
                        )
                    )
                    total_skipped += 1

            self.db.session.commit()
            self._filter_skip = total_skipped
            vb.write(verbose=True, content=f"[SnapshotCollection._skip_set] commit successful, total_skipped={total_skipped}")
        except Exception as e:
            vb.write(verbose=True, content=f"[SnapshotCollection._skip_set] exception: {e}; rolling back")
            try:
                self.db.session.rollback()
                vb.write(verbose=True, content="[SnapshotCollection._skip_set] rollback successful")
            except Exception:
                vb.write(verbose=True, content="[SnapshotCollection._skip_set] rollback failed")
            raise

    def count_total(self) -> int:
        return self.db.session.query(waybackup_snapshots.scid).count()

    def count_handled(self) -> int:
        return self.db.session.query(waybackup_snapshots.scid).where(waybackup_snapshots.response.is_not(None)).count()

    def count_unhandled(self) -> int:
        return self.db.session.query(waybackup_snapshots.scid).where(waybackup_snapshots.response.is_(None)).count()

    def count_success(self) -> int:
        return (
            self.db.session.query(waybackup_snapshots.scid)
            .where(and_(waybackup_snapshots.file.is_not(None), waybackup_snapshots.file != ""))
            .count()
        )

    def count_fail(self) -> int:
        return (
            self.db.session.query(waybackup_snapshots.scid)
            .where(or_(waybackup_snapshots.file.is_(None), waybackup_snapshots.file == ""))
            .count()
        )

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
