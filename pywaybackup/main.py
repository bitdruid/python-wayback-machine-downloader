import os

import signal

import pywaybackup.archive as archive

from pywaybackup.Arguments import Configuration as config
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex
from pywaybackup.Converter import Converter as convert

def main():

    config.init()
    ex.init(config.debug, config.output, config.command)
    vb.init(config.verbosity, config.log)
    if config.save:
        archive.save_page(config.url)
    else:
        try:
            skipset = archive.skip_open(config.skip, config.url) if config.skip else None
            archive.query_list(config.range, config.start, config.end, config.explicit, config.mode, config.cdxbackup, config.cdxinject)
            if config.list:
                archive.print_list()
            else:
                archive.download_list(config.output, config.retry, config.no_redirect, config.delay, config.workers, skipset)
        except KeyboardInterrupt:
            print("\nInterrupted by user\n")
        finally:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            archive.csv_close(config.csv, config.url) if config.csv else None

    vb.fini()
    os._exit(0) # kill all threads

if __name__ == "__main__":
    main()