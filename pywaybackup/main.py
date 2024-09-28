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
    db.init(config.dbfile, config.query_identifier)
    sc.init(config.mode)
    ex.init(config.output, config.command)
    vb.init(config.progress, config.log)
    if config.save:
        archive.save_page(config.url)

    else:

        try:
            archive.query_list(config.csvfile, config.cdxfile, config.range, config.limit, config.start, config.end, config.explicit, config.filetype)
            archive.download_list(config.output, config.retry, config.no_redirect, config.delay, config.workers)
        except KeyboardInterrupt:
            print("\nInterrupted by user\n")
            config.keep = True
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        except Exception as e:
            config.keep = True
            ex.exception(message="", e=e)

        finally:
            if not config.keep:
                os.remove(config.dbfile)
                os.remove(config.cdxfile)

            sc.csv_create(config.csvfile)
            vb.fini()
            sc.fini()
            os._exit(1)

if __name__ == "__main__":
    main()
