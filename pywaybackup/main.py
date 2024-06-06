import pywaybackup.archive as archive
import os

from pywaybackup.arguments import parse
from pywaybackup.Verbosity import Verbosity as v

def main():
    args = parse()
    v.open(args.verbosity)        

    if args.full:
        mode = "full"
    if args.current:
        mode = "current"

    if args.output is None:
        args.output = os.path.join(os.getcwd(), "waybackup_snapshots")

    if args.skip is True:
        args.skip = args.output
    if args.csv is True:
        args.csv = args.output

    if args.save:
        archive.save_page(args.url)
    else:
        try:
            skipfile, skipset = archive.skip_open(args.skip, args.url) if args.skip else (None, None)
            archive.query_list(args.url, args.range, args.start, args.end, args.explicit, mode, args.cdxinject)
            if args.list:
                archive.print_list()
            else:
                archive.download_list(args.output, args.retry, args.no_redirect, args.workers, skipset)
        finally:
            archive.skip_close(skipfile, skipset) if args.skip else None
            archive.csv_close(args.csv, args.url) if args.csv else None
    v.close()

if __name__ == "__main__":
    main()