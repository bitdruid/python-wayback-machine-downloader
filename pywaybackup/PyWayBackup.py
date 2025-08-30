import sys
import os
import time
import signal
import threading
from pywaybackup.helper import url_split, sanitize_filename
from importlib.metadata import version

import pywaybackup.archive_save as archive_save
from pywaybackup.db import Database as db
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex
from pywaybackup.SnapshotCollection import SnapshotCollection
from pywaybackup.archive_download import DownloadArchive
from pywaybackup.files import CDXquery, CDXfile, CSVfile


class _Status:
    def __init__(self):
        self.sc = None
        self.task = "initializing"
        self.handled = 0
        self.total = 0
        self.progress = 0

    @property
    def status(self):
        if not self.sc:
            self.sc = SnapshotCollection(mode=None)
        if self.task != "done":
            self.handled = self.sc.count_handled()
            self.total = self.sc.count_total()
        return {
            "task": self.task,
            "current": self.handled,
            "total": self.total,
            "progress": f"{self.handled / self.total:.0%}" if self.total > 0 else "0",
        }


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
    """

    def __init__(
        self,
        url: str = None,
        all: bool = False,
        last: bool = False,
        first: bool = False,
        save: bool = False,
        explicit: bool = False,
        range: str = None,
        start: str = None,
        end: str = None,
        limit: int = None,
        filetype: str = None,
        statuscode: str = None,
        output: str = None,
        metadata: str = None,
        verbose: bool = False,
        log: bool = False,
        progress: bool = False,
        no_redirect: bool = False,
        retry: int = 0,
        workers: int = 1,
        delay: int = 0,
        reset: bool = False,
        keep: bool = False,
        silent: bool = True,
        debug: bool = False,
        **kwargs: dict,
    ):
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

        # module exclusive
        self.silent = silent
        self.debug = debug

        # internal
        self._status = _Status()

        self.query_identifier = (
            str(self.url)
            +
            # required_args
            str(self.all)
            + str(self.last)
            + str(self.first)
            + str(self.save)
            +
            # optional_args
            str(self.explicit)
            + str(self.range)
            + str(self.start)
            + str(self.end)
            + str(self.limit)
            + str(self.filetype)
            + str(self.statuscode)
        )

        # if sys.argv is empty, we assume this is being run as a module
        if not sys.argv[1:]:
            self.command = "pywaybackup_module"
        else:
            # otherwise, we take the command line arguments
            self.command = " ".join(sys.argv[1:])

        self._verify()
        self._setup()

    def _verify(self):
        """
        Verify correct input.
        """
        # url must be given
        if not self.url:
            raise ValueError("URL must be provided")
        # all, last, first, save are mutually exclusive
        if sum([self.all, self.last, self.first, self.save]) != 1:
            raise ValueError("Exactly one of --all, --last, --first, or --save is allowed")

    def _setup(self):
        self.domain, self.subdir, self.filename = url_split(self.url)

        self.output = os.path.join(os.getcwd(), "waybackup_snapshots") if not self.output else self.output
        self.metadata = self.metadata if self.metadata else self.output

        if self.all:
            self.mode = "all"
        elif self.last:
            self.mode = "last"
        elif self.first:
            self.mode = "first"
        elif self.save:
            self.mode = "save"

        self.filetype = [f.lower().strip() for f in self.filetype.split(",")] if self.filetype else []
        self.statuscode = [s.lower().strip() for s in self.statuscode.split(",")] if self.statuscode else []

        base_name = f"waybackup_{sanitize_filename(self.url)}"
        self.cdxfile = os.path.join(self.metadata, f"{base_name}.cdx")
        self.dbfile = os.path.join(self.metadata, f"{base_name}.db")
        self.csvfile = os.path.join(self.metadata, f"{base_name}.csv")
        self.logfile = os.path.join(self.metadata, f"{base_name}.log") if self.log else None
        self.debugfile = os.path.join(self.metadata, "waybackup_error.log") if self.debug else None

        os.makedirs(self.output, exist_ok=True)
        os.makedirs(self.metadata, exist_ok=True)

    def _f_reset(self):
        """
        Reset files if True.
        """
        if self.reset:
            os.remove(self.dbfile) if os.path.isfile(self.dbfile) else None
            os.remove(self.cdxfile) if os.path.isfile(self.cdxfile) else None
            os.remove(self.csvfile) if os.path.isfile(self.csvfile) else None

    def _f_keep(self):
        """
        Keep files if True
        """
        if not self.keep:
            os.remove(self.dbfile) if os.path.isfile(self.dbfile) else None
            os.remove(self.cdxfile) if os.path.isfile(self.cdxfile) else None

    def paths(self, rel: bool = False) -> dict:
        """
        Return a dictionary of existing file paths associated to the backup process:
            {'shapshots':, 'cdxfile':, 'dbfile':, 'csvfile':, 'log':, 'debug':}

        Example:
        >>> backup_paths = backup.paths(rel=True)
        >>> print(backup_paths)
        ... {
        ... 'snapshots': 'waybackup_snapshots/example.com',
        ... 'cdxfile': 'waybackup_snapshots/waybackup_example.com.cdx',
        ... 'dbfile': 'waybackup_snapshots/waybackup_example.com.db',
        ... 'csvfile': 'waybackup_snapshots/waybackup_example.com.csv',
        ... 'log': 'waybackup_snapshots/waybackup_example.com.log',
        ... 'debug': 'waybackup_snapshots/waybackup_error.log'
        ... }
        """
        files = {
            "snapshots": os.path.join(self.output, self.domain),
            "cdxfile": self.cdxfile,
            "dbfile": self.dbfile,
            "csvfile": self.csvfile,
            "log": self.log,
            "debug": self.debug,
        }
        return {key: (os.path.relpath(path) if rel else path) for key, path in files.items() if path and os.path.exists(path)}

    def status(self):
        """
        Return the current status of the backup process by a dictionary:
            {'task':, 'current':, 'total':, 'progress':}

        Example:
        >>> print(backup.status())
        ... {
        ... 'task': 'downloading snapshots',
        ... 'current': 150,
        ... 'total': 300,
        ... 'progress': '50%'
        ... }
        """
        return self._status.status

    def run(self, daemon=False):
        """
        Run the PyWayBackup process according to the current configuration.

        This method initializes logging, exception handling, and database state, then either saves the current page
        or starts the download process. The download process can be run in a separate daemon thread or synchronously.

        Args:
            daemon (bool, optional): If True, runs the download process in a separate daemon thread. Defaults to False.

        Example:
        >>> backup.run(daemon=True)
        >>> while True:
        ...     print(backup.status())
        ...     time.sleep(2)
        """

        def __startup():
            try:
                vb.write(content=f"\n<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")

                if db.QUERY_EXIST:
                    vb.write(
                        content=f"\nDOWNLOAD job exist - processed: {db.QUERY_PROGRESS}\nResuming download... (to reset the job use '--reset')"
                    )

                    if not self.silent:
                        for i in range(5, -1, -1):
                            vb.write(content=f"\r{i}...")
                            print("\033[F", end="")
                            print("\033[K", end="")

                            time.sleep(1)

            except KeyboardInterrupt:
                os._exit(1)

        def __async():
            def _prep_cdx() -> CDXfile:
                self._status.task = "downloading cdx"
                cdxquery = CDXquery(
                    url=self.url,
                    range=self.range,
                    start=self.start,
                    end=self.end,
                    limit=self.limit,
                    explicit=self.explicit,
                    filter_filetype=self.filetype,
                    filter_statuscode=self.statuscode,
                )
                cdx = CDXfile(self.cdxfile)
                if cdx.request_snapshots(cdxquery):
                    return cdx

            def _prep_collection(cdx: CDXfile) -> SnapshotCollection:
                csv = CSVfile(self.csvfile)
                self._status.task = "preparing snapshots"
                collection = SnapshotCollection(mode=self.mode)
                collection.load(cdxfile=cdx, csvfile=csv)
                collection.print_calculation()
                return collection

            def _dl_download(collection: SnapshotCollection):
                self._status.task = "downloading snapshots"
                downloader = DownloadArchive(
                    mode=self.mode,
                    output=self.output,
                    retry=self.retry,
                    no_redirect=self.no_redirect,
                    delay=self.delay,
                    workers=self.workers,
                )
                downloader.run(SnapshotCollection=collection)

            try:
                cdx = _prep_cdx()

                if cdx:
                    collection = _prep_collection(cdx=cdx)

                    if collection:
                        _dl_download(collection=collection)

            except KeyboardInterrupt:
                print("\nInterrupted by user\n")
                self.keep = True
                signal.signal(signal.SIGINT, signal.SIG_IGN)

            except Exception as e:
                self.keep = True
                ex.exception(message="", e=e)

            finally:
                self._status.task = "done"
                collection.close()
                self._f_keep()
                vb.fini()

        self._f_reset()

        ex.init(debugfile=self.debugfile, output=self.output, command=self.command)
        vb.init(logfile=self.logfile, silent=self.silent, verbose=self.verbose, progress=self.progress)

        if self.save:
            archive_save.save_page(self.url)

        else:
            db.init(self.dbfile, self.query_identifier)

            __startup()

            if daemon:
                pywaybackup_async = threading.Thread(target=__async, daemon=True)
                pywaybackup_async.start()
            else:
                __async()
