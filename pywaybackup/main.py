import os
import signal

import pywaybackup.archive_download as archive_download
import pywaybackup.archive_save as archive_save

from pywaybackup.SnapshotCollection import SnapshotCollection as sc
from pywaybackup.Arguments import Configuration as config
from pywaybackup.db import Database as db
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex

def main():

    config.init()
    ex.init(config.output, config.command)
    vb.init(config.verbose, config.progress, config.log)

    if config.save:
        archive_save.save_page(config.url)
        os._exit(1)

    db.init(config.dbfile, config.query_identifier)
    sc.init(config.mode)


    if not config.save:

        archive_download.startup()

        try:
            archive_download.query_list(config.csvfile, config.cdxfile, config.range, config.limit, config.start, config.end, config.explicit, config.filetype, config.statuscode)
            archive_download.download_list(config.output, config.retry, config.no_redirect, config.delay, config.workers)
        except KeyboardInterrupt:
            print("\nInterrupted by user\n")
            config.keep = True
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        except Exception as e:
            config.keep = True
            ex.exception(message="", e=e)

        finally:
            sc.csv_create(config.csvfile)
            sc.fini()
            vb.fini()

            if not config.keep:
                os.remove(config.dbfile) if os.path.exists(config.dbfile) else None
                os.remove(config.cdxfile) if os.path.exists(config.cdxfile) else None

            os._exit(1)

if __name__ == "__main__":
    main()
