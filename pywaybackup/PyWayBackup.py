import sys
import os
import time
import signal
import multiprocessing
from pywaybackup.helper import url_split, sanitize_filename
from importlib.metadata import version

import pywaybackup.archive_save as archive_save
from pywaybackup.db import Database as db
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex
from pywaybackup.SnapshotCollection import SnapshotCollection
from pywaybackup.archive_download import DownloadArchive
from pywaybackup.files import CDXquery, CDXfile, CSVfile, File


class _Status:
    """
    Internal class to track and report the status of the backup process. A new instance of the SnapshotCollection is created
    without loading any data into it. This creates a connection to the database and gives access to the required methods to count
    the total and handled snapshots.

    Attributes:
        sc (SnapshotCollection): The current snapshot collection being processed.
        task (str): The current task being performed (e.g., 'initializing', 'downloading cdx', 'preparing snapshots', 'downloading snapshots', 'done').
        handled (int): The number of snapshots that have been processed so far.
        total (int): The total number of snapshots to be processed.
        progress (float): The progress of the backup process as a percentage.

    Methods:
        status(): Returns a dictionary with the current status of the backup process.

    """

    def __init__(self):
        self.sc = None
        self.task = "initializing"
        self.handled = 0
        self.total = 0
        self._progress = 0

    @property
    def status(self):
        """
        Returns a dictionary with the current status of the backup process:
            {'task':, 'current':, 'total':, 'progress':}
        """
        if not self.sc:
            self.sc = SnapshotCollection()
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
        self._url = url
        self._all = all
        self._last = last
        self._first = first
        self._save = save
        self._explicit = explicit
        self._range = range
        self._start = start
        self._end = end
        self._limit = limit
        self._filetype = filetype
        self._statuscode = statuscode
        self._output = output
        self._metadata = metadata
        self._verbose = verbose
        self._log = log
        self._progress = progress
        self._no_redirect = no_redirect
        self._retry = retry
        self._workers = workers
        self._delay = delay
        self._reset = reset
        self._keep = keep

        # module exclusive
        self._silent = silent
        self._debug = debug

        # internal
        self._status = _Status()
        self.pywaybackup_process = None
        self._cdxfile = None
        self._csvfile = None

        self._query_identifier = (
            str(self._url)
            +
            # required_args
            str(self._all)
            + str(self._last)
            + str(self._first)
            + str(self._save)
            +
            # optional_args
            str(self._explicit)
            + str(self._range)
            + str(self._start)
            + str(self._end)
            + str(self._limit)
            + str(self._filetype)
            + str(self._statuscode)
        )

        # if sys.argv is empty, we assume this is being run as a module
        if not sys.argv[1:]:
            self._command = "pywaybackup_module"
        else:
            # otherwise, we take the command line arguments
            self._command = " ".join(sys.argv[1:])

        self._verify()
        self._setup()
        self._init()

    def _verify(self):
        """
        Verify correctness of input parameters.
        """
        # url must be given
        if not self._url:
            raise ValueError("URL must be provided")
        # all, last, first, save are mutually exclusive
        if sum([self._all, self._last, self._first, self._save]) != 1:
            raise ValueError("Exactly one of --all, --last, --first, or --save is allowed")

    def _setup(self):
        """
        Initialize internal variables and prepare working directories and files.

        Splits up the domain, subdirectory, and filename from the provided URL.
        Initializes output and metadata directories and prepares file paths for
        CDX, DB, and CSV files used for tracking snapshots and metadata.
        """
        self._domain, self._subdir, self._filename = url_split(self._url)

        self._output = os.path.join(os.getcwd(), "waybackup_snapshots") if not self._output else self._output
        self._metadata = self._metadata if self._metadata else self._output

        if self._all:
            self._mode = "all"
        elif self._last:
            self._mode = "last"
        elif self._first:
            self._mode = "first"
        elif self._save:
            self._mode = "save"

        self._filetype = [f.lower().strip() for f in self._filetype.split(",")] if self._filetype else []
        self._statuscode = [s.lower().strip() for s in self._statuscode.split(",")] if self._statuscode else []

        base_name = f"waybackup_{sanitize_filename(self._url)}"
        self._cdxfile = os.path.join(self._metadata, f"{base_name}.cdx")
        self._dbfile = os.path.join(self._metadata, f"{base_name}.db")
        self._csvfile = os.path.join(self._metadata, f"{base_name}.csv")
        self._logfile = os.path.join(self._metadata, f"{base_name}.log") if self._log else None
        self._debugfile = os.path.join(self._metadata, "waybackup_error.log") if self._debug else None

        os.makedirs(self._output, exist_ok=True)
        os.makedirs(self._metadata, exist_ok=True)

    def _init(self):
        """
        Initialize logging, exception handling, database, and internal state.
        Resets metadata files if the `reset` flag is set and initializes the database.
        """
        self._cdxfile = CDXfile(self._cdxfile)
        self._csvfile = CSVfile(self._csvfile)
        # self._dbfile = File(self._dbfile)

        self._f_reset()
        ex.init(debugfile=self._debugfile, output=self._output, command=self._command)
        vb.init(logfile=self._logfile, silent=self._silent, verbose=self._verbose, progress=self._progress)
        db.init(dbfile=self._dbfile, query_identifier=self._query_identifier)

        vb.write(content=f"\n<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")

        self._cdxfile.create()
        self._csvfile.create()

    def _f_reset(self):
        """
        Reset metadata files if the `reset` flag is set.

        Deletes the existing `.cdx`, `.db`, and `.csv` files if they exist,
        ensuring a fresh start for the backup job.
        """
        if self._reset:
            self._cdxfile.remove()
            self._csvfile.remove()
            os.remove(self._dbfile) if os.path.exists(self._dbfile) else None

    def _f_keep(self):
        """
        Retain or delete metadata files based on the `keep` flag.

        If `keep` is False, deletes the `.cdx`, `.db`, and `.csv` files after
        processing is complete.
        """
        if not self._keep:
            os.remove(self._dbfile) if os.path.exists(self._dbfile) else None
            self._cdxfile.remove()

    def _prep_cdx(self) -> bool:
        """
        Prepare and query the CDX file from the Wayback Machine.

        Initializes a `CDXfile` object and queries the Wayback Machine to
        retrieve snapshot information. Returns the CDXfile instance if the
        query is successful.

        Returns:
            bool: True if the CDX query was successful and snapshots were found, False otherwise.
        """
        cdxquery = CDXquery(
            url=self._url,
            range=self._range,
            start=self._start,
            end=self._end,
            limit=self._limit,
            explicit=self._explicit,
            filter_filetype=self._filetype,
            filter_statuscode=self._statuscode,
        )
        if self._cdxfile.request_snapshots(cdxquery):
            return True
        return False

    def _prep_collection(self) -> SnapshotCollection:
        """
        Load CDX and CSV data into a SnapshotCollection.

        Initializes the `SnapshotCollection` object and loads the CDX and CSV
        data into it. This collection is used to manage and process the
        list of snapshots for the backup job.

        Returns:
            SnapshotCollection: The initialized and loaded snapshot collection.
        """
        collection = SnapshotCollection()
        collection.load(mode=self._mode, cdxfile=self._cdxfile, csvfile=self._csvfile)
        collection.print_calculation()
        return collection

    def _dl_download(self, collection: SnapshotCollection):
        """
        Execute the download process using the SnapshotCollection.

        Initializes the download of the created SnapshotCollection with the current configuration
        and uses it to download the snapshots represented in the collection.

        Args:
            collection (SnapshotCollection): The snapshot collection to be downloaded.
        """
        downloader = DownloadArchive(
            mode=self._mode,
            output=self._output,
            retry=self._retry,
            no_redirect=self._no_redirect,
            delay=self._delay,
            workers=self._workers,
        )
        downloader.run(SnapshotCollection=collection)

    def _workflow(self):
        """
        Executes the steps required to perform the backup process:
            1. Prepare and query the CDX file.
            2. Load CDX and CSV data into a SnapshotCollection.
            3. Execute the download process using the collection.

        Handles exceptions and ensures proper cleanup and finalization of
        resources after the backup is complete.

        """
        try:
            self._startup()

            self._status.task = "downloading cdx"
            cdx = self._prep_cdx()

            if cdx:
                self._status.task = "preparing snapshots"
                collection = self._prep_collection()

                if collection:
                    self._status.task = "downloading snapshots"
                    self._dl_download(collection=collection)

        except KeyboardInterrupt:
            self._keep = True
            vb.write(content="\nInterrupted by user\n")
        except Exception as e:
            self._keep = True
            ex.exception(message="", e=e)
        finally:
            self._shutdown()

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
            "snapshots": os.path.join(self._output, self._domain),
            "cdxfile": self._cdxfile,
            "dbfile": self._dbfile,
            "csvfile": self._csvfile,
            "log": self._log,
            "debug": self._debug,
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

        if self._save:
            archive_save.save_page(self._url)

        else:
            self.pywaybackup_process = multiprocessing.Process(target=self._workflow, daemon=True)
            if daemon:
                self.pywaybackup_process.start()
            else:
                self.pywaybackup_process.run()

    def stop(self) -> bool:
        """
        Stop the PyWayBackup process gracefully when used in daemon-mode.

        This method sets the internal task status to 'done', and signals the
        running workflow to terminate.
        Returns:
            bool: True if the process was stopped successfully, False otherwise.

        Example:
        >>> backup.run(daemon=True)
        >>> time.sleep(10)
        >>> backup.stop()
        """
        if self.pywaybackup_process and self.pywaybackup_process.is_alive():
            vb.write(content="\nExternal stop signal received...")
            self.pywaybackup_process.terminate()
            self.pywaybackup_process.join()
            self._shutdown()
            return True
        return False

    def _startup(self):
        if db.QUERY_EXIST:
            self._status.task = "resuming"
            vb.write(
                content=f"\nDOWNLOAD job exist - processed: {db.QUERY_PROGRESS}\nResuming download... (to reset the job use '--reset')"
            )

            if not self._silent:
                for i in range(5, -1, -1):
                    vb.write(content=f"\r{i}...")
                    print("\033[F", end="")
                    print("\033[K", end="")

                    time.sleep(1)

    def _shutdown(self):
        self._status.task = "done"
        collection = SnapshotCollection()
        collection.close()
        self._csvfile.store_result()
        self._f_keep()
        vb.fini()
        signal.signal(signal.SIGINT, signal.SIG_IGN)
