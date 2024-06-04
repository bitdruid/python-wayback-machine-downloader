import pywaybackup.archive as archive
import os

from pywaybackup.arguments import parse
from pywaybackup.Verbosity import Verbosity as v

def main():
    args = parse()
    v.open(args.verbosity)
    file = None

    if args.full:
        mode = "full"
    if args.current:
        mode = "current"

    if args.output is None:
        args.output = os.path.join(os.getcwd(), "waybackup_snapshots")
    if args.csv is True:
        args.csv = args.output

    if args.save:
        archive.save_page(args.url)
    else:
        try:
            if args.csv:
                file = archive.csv_open(args.csv, args.url)
            archive.query_list(args.url, args.range, args.start, args.end, args.explicit, mode)
            if args.list:
                archive.print_list(file)
            else:
                archive.download_list(args.output, args.retry, args.no_redirect, args.workers, file)
        finally:
            if args.csv:
                archive.csv_close(file)
    v.close()

if __name__ == "__main__":
    main()