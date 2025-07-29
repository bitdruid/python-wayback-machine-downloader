from dataclasses import dataclass, field

import os
import sys
import requests
from datetime import datetime
from pywaybackup.helper import url_split, sanitize_filename
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
    filter_filetype: list = field(default_factory=list)
    filter_statuscode: list = field(default_factory=list)

    # in __post_init__
    domain: str = field(init=False)
    subdir: str = field(init=False)
    filename: str = field(init=False)
    query_url: str = field(init=False)

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


class CDXfile:
    def __init__(self, filepath: str):
        self.cdxfile = None
        self._filepath = filepath
        self.new = False if self._exist(filepath=self._filepath) else True

    def _exist(self, filepath):
        if os.path.exists(filepath):
            vb.write(verbose=None, content="\nExisting CDX file found")
            return True
        return False

    def query(self, query: CDXquery):
        try:
            if not self.new:
                with open(self._filepath, "w", encoding="utf-8") as cdxfile_io:
                    with requests.get(query.query_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        progress = Progressbar(unit="B", unit_scale=True, desc="download cdx".ljust(15))
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                progress.update(len(chunk))
                                cdxfile_io.write(chunk.decode("utf-8"))
                
                self.cdxfile = self._filepath
                return True

        except requests.exceptions.ConnectionError:
            vb.write(content="\nCONNECTION REFUSED -> could not query cdx server (max retries exceeded)")
            os.remove(self._filepath)
            return False
        except Exception as e:
            ex.exception(message="\nUnknown error while querying cdx server", e=e)
            os.remove(self._filepath)
            return False

    # cdxinject = inject(cdxfile)
    # if not cdxinject:
    #     cdxquery = create_query(queryrange, limit, filter_filetype, filter_statuscode, start, end, explicit, domain, subdir, filename)
    #     cdxfile =  run_query(cdxfile, cdxquery)
    # sc.process_cdx(cdxfile, csvfile)
    # sc.calculate()