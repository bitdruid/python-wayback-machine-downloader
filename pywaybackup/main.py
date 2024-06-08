import os

import signal

import pywaybackup.archive as archive

from pywaybackup.arguments import parse
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex

def main():
    args, command = parse()

    if args.output is None:
        args.output = os.path.join(os.getcwd(), "waybackup_snapshots")
        os.makedirs(args.output, exist_ok=True)

    ex.init(args.debug, args.output, command)
    vb.init(args.verbosity)

    if args.full:
        mode = "full"
    if args.current:
        mode = "current"

    if args.skip is True:
        args.skip = args.output
    if args.csv is True:
        args.csv = args.output
    if args.cdxbackup is True:
        args.cdxbackup = args.output
    if args.cdxinject is True:
        args.cdxinject = args.output

    if args.save:
        archive.save_page(args.url)
    else:
        try:
            skipset = archive.skip_open(args.skip, args.url) if args.skip else None
            archive.query_list(args.url, args.range, args.start, args.end, args.explicit, mode, args.cdxbackup, args.cdxinject)
            if args.list:
                archive.print_list()
            else:
                archive.download_list(args.output, args.retry, args.no_redirect, args.workers, skipset)
        except KeyboardInterrupt:
            print("\nInterrupted by user\n")
        finally:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            archive.csv_close(args.csv, args.url) if args.csv else None
    vb.fini()
    os._exit(0) # kill all threads

if __name__ == "__main__":
    main()