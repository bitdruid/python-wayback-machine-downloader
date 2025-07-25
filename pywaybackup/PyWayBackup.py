import sys
import os
import signal
from pywaybackup.helper import url_split, sanitize_filename

import pywaybackup.archive_download as archive_download
import pywaybackup.archive_save as archive_save
from pywaybackup.db import Database as db
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex
from pywaybackup.SnapshotCollection import SnapshotCollection as sc

class PyWayBackup:
    """
    PyWayBackup: A Python interface for downloading or saving archived web pages from the Wayback Machine (archive.org).

    Supported Modes (only one must be selected):
    - all   : Download all snapshots for a URL within a time range.
    - last  : Download the latest version of each file in the range.
    - first : Download the earliest version of each file in the range.
    - save  : Save a snapshot to the Wayback Machine (beta).

    Args:
        url (str): Target URL to download snapshots for. (Required)
        all (bool): If True, downloads all snapshots within the range.
        last (bool): If True, downloads the last version of each file.
        first (bool): If True, downloads the first version of each file.
        save (bool): If True, saves a new snapshot to archive.org (beta).
        explicit (bool): Only use the explicitly provided URL without wildcards.
        range (str): A year-based or timestamp-based range (e.g., '2020' or '20200101').
        start (str): Start timestamp (YYYYMMDDhhmmss).
        end (str): End timestamp (YYYYMMDDhhmmss).
        limit (int): Limit the number of snapshots queried from the CDX API.
        filetype (str): Comma-separated list of filetypes to include (e.g., 'jpg,css,js').
        statuscode (str): Comma-separated list of HTTP status codes to include (e.g., '200,301').
        output (str): Output path for downloaded files. Defaults to `./waybackup_snapshots`.
        metadata (str): Path to store metadata files (`cdx`, `db`, `csv`, etc.).
        verbose (bool): Enable verbose logging.
        log (bool): Enable writing logs to a file.
        progress (bool): Show a progress bar.
        no_redirect (bool): Disable handling redirects.
        retry (int): Retry attempts for failed downloads.
        workers (int): Number of download workers (default: 1).
        delay (int): Delay between download requests in seconds.
        reset (bool): Reset job metadata (deletes `.cdx`/`.db`/`.csv` files).
        keep (bool): Retain all job metadata after completion.
        silent (bool): Suppress all output (for programmatic use).
        debug (bool): Enable debug mode.
        **kwargs: Catch-all for future expansion or external integration.

    Methods:
        run(): Executes the full download or save operation based on initialized parameters.

    Example:
        >>> from pywaybackup import PyWayBackup
        >>> backup = PyWayBackup(url="https://example.com", all=True, start="20200101", end="20201231")
        >>> backup.run()
        >>> backup_paths = backup.paths(rel=True)
        >>> print(backup_paths)
    """
        
    def __init__(self, url: str = None, all: bool = False, last: bool = False, first: bool = False,
                save: bool = False, explicit: bool = False, range: str = None, start: str = None,
                end: str = None, limit: int = None, filetype: str = None, statuscode: str = None,
                output: str = None, metadata: str = None, verbose: bool = False, log: bool = False,
                progress: bool = False, no_redirect: bool = False, retry: int = 0, workers: int = 1,
                delay: int = 0, reset: bool = False, keep: bool = False, 
                silent: bool = True, debug: bool = False, **kwargs: dict):
                
        # restrictions
        # url must be given
        # all, last, first, save are mutually exclusive
        if not url:
            raise ValueError("URL must be provided")
        if sum([all, last, first, save]) != 1:
            raise ValueError("Exactly one of --all, --last, --first, or --save is allowed")

        self.url = url
        self.all = all
        self.last = last
        self.first = first
        self.save = save
        self.explicit = explicit
        self.range = range
        self.start = start
        self.end = end
        self.limit = limit
        self.filetype = filetype
        self.statuscode = statuscode
        self.output = output
        self.metadata = metadata
        self.verbose = verbose
        self.log = log
        self.progress = progress
        self.no_redirect = no_redirect
        self.retry = retry
        self.workers = workers
        self.delay = delay
        self.reset = reset
        self.keep = keep

        self.silent = silent
        self.debug = debug

        self.query_identifier = (
            str(self.url) +
            # required_args
            str(self.all) + str(self.last) + str(self.first) + str(self.save) +
            # optional_args
            str(self.explicit) + str(self.range) + str(self.start) + str(self.end) +
            str(self.limit) + str(self.filetype) + str(self.statuscode)
        )
        
        # if sys.argv is empty, we assume this is being run as a module
        if not sys.argv[1:]:
            self.command = "pywaybackup_module"
        else:
            # otherwise, we take the command line arguments
            self.command = ' '.join(sys.argv[1:])

        self._init()

    def _init(self):

        self.domain, self.subdir, self.filename = url_split(self.url)

        if self.output is None:
            self.output = os.path.join(os.getcwd(), "waybackup_snapshots")
        if self.metadata is None:
            self.metadata = self.output
        os.makedirs(self.output, exist_ok=True) if not self.save else None
        os.makedirs(self.metadata, exist_ok=True) if not self.save else None

        if self.all:
            self.mode = "all"
        if self.last:
            self.mode = "last"
        if self.first:
            self.mode = "first"
        if self.save:
            self.mode = "save"

        if self.filetype:
            self.filetype = [f.lower().strip() for f in self.filetype.split(",")]
        if self.statuscode:
            self.statuscode = [s.lower().strip() for s in self.statuscode.split(",")]

        base_path = self.metadata
        base_name = f"waybackup_{sanitize_filename(self.url)}"
        self.cdxfile = os.path.join(base_path, f"{base_name}.cdx")
        self.dbfile = os.path.join(base_path, f"{base_name}.db")
        self.csvfile = os.path.join(base_path, f"{base_name}.csv")
        self.log = os.path.join(base_path, f"{base_name}.log") if self.log else None
        self.debug = os.path.join(base_path, "waybackup_error.log") if self.debug else None

        if self.reset:
            os.remove(self.cdxfile) if os.path.isfile(self.cdxfile) else None
            os.remove(self.dbfile) if os.path.isfile(self.dbfile) else None
            os.remove(self.csvfile) if os.path.isfile(self.csvfile) else None

    def paths(self, rel: bool = False) -> dict:
        """
        Return a dictionary of existing file paths associated to the backup process:
            {'shapshots':, 'cdxfile':, 'dbfile':, 'csvfile':, 'log':, 'debug':}

        Parameters:
            rel (bool): If True, return relative paths; otherwise, return absolute paths.

        Returns:
            dict: Mapping of file types to their corresponding paths, including only files that exist.
        """
        files = {
            "snapshots": os.path.join(self.output, self.domain),
            "cdxfile": self.cdxfile,
            "dbfile": self.dbfile,
            "csvfile": self.csvfile,
            "log": self.log,
            "debug": self.debug
        }
        return {
            key: (os.path.relpath(path) if rel else path)
            for key, path in files.items()
            if path and os.path.exists(path)
        }

    def run(self):
        """Run the PyWayBackup process with the given configuration."""
        ex.init(self.debug, self.output, self.command)
        vb.init(self.silent, self.verbose, self.progress, self.log)

        if self.save:
            archive_save.save_page(self.url)

        else:

            db.init(self.dbfile, self.query_identifier)
            sc.init(self.mode)

            if not self.save:
                archive_download.startup()

                try:
                    archive_download.query_list(
                        self.csvfile,
                        self.cdxfile,
                        self.range,
                        self.limit,
                        self.start,
                        self.end,
                        self.explicit,
                        self.filetype,
                        self.statuscode,
                        self.domain,
                        self.subdir,
                        self.filename,
                    )
                    archive_download.download_list(self.output, self.retry, self.no_redirect, self.delay, self.workers)
                except KeyboardInterrupt:
                    print("\nInterrupted by user\n")
                    self.keep = True
                    signal.signal(signal.SIGINT, signal.SIG_IGN)

                except Exception as e:
                    self.keep = True
                    ex.exception(message="", e=e)

                finally:
                    sc.csv_create(self.csvfile)
                    sc.fini()
                    vb.fini()

                    if not self.keep:
                        os.remove(self.dbfile) if os.path.exists(self.dbfile) else None
                        os.remove(self.cdxfile) if os.path.exists(self.cdxfile) else None