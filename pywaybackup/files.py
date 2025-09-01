from dataclasses import dataclass

import os
import csv
import requests
from datetime import datetime
from pywaybackup.helper import url_split
from pywaybackup.db import Database
from pywaybackup.Verbosity import Verbosity as vb, Progressbar
from pywaybackup.Exception import Exception as ex


@dataclass
class CDXquery:
    """
    Represents a query configuration for CDXfile.
    Validates the given parameters and sets the query-url.
    """

    url: str
    range: int = None
    start: int = None
    end: int = None
    limit: int = None
    explicit: bool = False
    filter_filetype: list[str] = None
    filter_statuscode: list[str] = None

    def __post_init__(self):
        self.domain, self.subdir, self.filename = url_split(self.url)
        self.query_url = self._build_query()

    def _build_query(self):
        if self.range:
            period = f"&from={datetime.now().year - self.range}"
        else:
            period = ""
            if self.start:
                period += f"&from={self.start}"
            if self.end:
                period += f"&to={self.end}"

        cdx_url = self.domain or ""

        if self.subdir:
            cdx_url += f"/{self.subdir}"
        if self.filename:
            cdx_url += f"/{self.filename}"
        if not self.explicit:
            cdx_url += "/*"

        limit = f"&limit={self.limit}" if self.limit else ""

        filter_statuscode = f"&filter=statuscode:({'|'.join(self.filter_statuscode)})$" if self.filter_statuscode else ""
        filter_filetype = f"&filter=original:.*\\.({'|'.join(self.filter_filetype)})$" if self.filter_filetype else ""

        return f"https://web.archive.org/cdx/search/cdx?output=json&url={cdx_url}{period}&fl=timestamp,digest,mimetype,statuscode,original{limit}{filter_filetype}{filter_statuscode}"


class File:
    def __init__(self, filepath: str):
        self._filepath = filepath
        self._file_handler = None
        self._file_writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()

    def _open(self, mode: str):
        if not self._file_handler:
            self._file_handler = open(self._filepath, mode, encoding="utf-8", newline="")

    def _close(self):
        if self._file_handler and not self._file_handler.closed:
            self._file_handler.close()
        self._file_handler = None

    def create(self):
        if not os.path.exists(self._filepath):
            vb.write(verbose=None, content=f"\nCreating new {self.__class__.__name__}")
            open(self._filepath, "a").close()
            self.new = True
        else:
            vb.write(verbose=None, content=f"\nExisting {self.__class__.__name__} found")
            self.new = False

    def remove(self):
        if os.path.exists(self._filepath):
            os.remove(self._filepath)

    @property
    def file(self):
        if os.path.exists(self._filepath):
            return True
        return False


class CDXfile(File):
    def __init__(self, filepath: str):
        super().__init__(filepath=filepath)
        self._cdxquery = None

    def __iter__(self):
        self._open(mode="r")
        return iter(self._file_handler)

    def request_snapshots(self, query: CDXquery):
        try:
            if not self.new:
                return True
            else:
                with open(self._filepath, "w", encoding="utf-8") as cdxfile_io:
                    with requests.get(query.query_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        progress = Progressbar(unit="B", unit_scale=True, desc="download cdx".ljust(15))
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                progress.update(len(chunk))
                                cdxfile_io.write(chunk.decode("utf-8"))

                return True

        except requests.exceptions.ConnectionError:
            vb.write(content="\nCONNECTION REFUSED -> could not query cdx server (max retries exceeded)")
            os.remove(self._filepath)
            return False
        except Exception as e:
            ex.exception(message="\nUnknown error while querying cdx server", e=e)
            os.remove(self._filepath)
            return False

    def count_rows(self) -> str:
        """
        Count the containing rows.
        """
        self._open(mode="r")
        count = sum(1 for _ in self._file_handler) - 1
        self._close()
        return count


class CSVfile(File):
    def __init__(self, filepath: str):
        super().__init__(filepath=filepath)

    def __iter__(self):
        self._open(mode="r")
        return csv.DictReader(self._file_handler)

    def write_rows(self, rows: list):
        """
        Write rows to the csv file.
        """
        self._open(mode="w")
        self._file_writer = csv.writer(self._file_handler)
        if isinstance(rows[0], str):
            self._file_writer.writerow(rows)
        else:
            self._file_writer.writerows(rows)

    def store_result(self):
        """
        Store all processed snapshots from the database to the CSV file.
        """
        db = Database()
        db.cursor.execute("SELECT * FROM csv_view WHERE response IS NOT NULL")
        headers = [description[0] for description in db.cursor.description]
        row_batchsize = 2500
        with self as f:
            f.write_rows(headers)
            while True:
                rows = db.cursor.fetchmany(row_batchsize)
                if not rows:
                    break
                f.write_rows(rows)
        db.close()
