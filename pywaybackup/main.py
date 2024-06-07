import pywaybackup.archive as archive
import os
import sys

from pywaybackup.arguments import parse
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex

def main():
    args, command = parse()

    if args.output is None:
        args.output = os.path.join(os.getcwd(), "waybackup_snapshots")
        os.makedirs(args.output, exist_ok=True)

    ex.init(args.debug, args.output, command)
    vb.open(args.verbosity)

    int('a') # test exception
    exit()

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
            skipfile, skipset = archive.skip_open(args.skip, args.url) if args.skip else (None, None)
            archive.query_list(args.url, args.range, args.start, args.end, args.explicit, mode, args.cdxbackup, args.cdxinject)
            if args.list:
                archive.print_list()
            else:
                archive.download_list(args.output, args.retry, args.no_redirect, args.workers, skipset)
        finally:
            archive.skip_close(skipfile, skipset) if args.skip else None
            archive.csv_close(args.csv, args.url) if args.csv else None
    vb.close()

if __name__ == "__main__":
    main()