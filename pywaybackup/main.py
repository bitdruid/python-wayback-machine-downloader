import os

import signal

import pywaybackup.archive as archive

from pywaybackup.SnapshotCollection import SnapshotCollection as sc

from pywaybackup.Arguments import Configuration as config
from pywaybackup.db import Database as db
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex

def main():

    config.init()
    db.init(config.url, config.output)
    sc.init(config.mode, config.skip)
    ex.init(config.output, config.command)
    vb.init(config.verbosity, config.log)
    if config.save:
        archive.save_page(config.url)
    else:
        try:
            archive.query_list(config.range, config.limit, config.start, config.end, config.explicit, config.filetype, config.output, config.cdxbackup, config.cdxinject)
            archive.download_list(config.output, config.retry, config.no_redirect, config.delay, config.workers)
        except KeyboardInterrupt:
            print("\nInterrupted by user\n")
        finally:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            sc.csv_close(config.csv) if config.csv else None

    vb.fini()
    os._exit(0) # kill all threads

if __name__ == "__main__":
    main()