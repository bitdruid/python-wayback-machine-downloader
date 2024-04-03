import pywaybackup.archive as archive
import pywaybackup.SnapshotCollection as sc
import os

from pywaybackup.arguments import parse
from pywaybackup.Verbosity import Verbosity as v

def main():
    args = parse()
    v.open(args.verbosity)

    if args.current:
        mode = "current"
    elif args.full:
        mode = "full"

    if args.save:
        archive.save_page(args.url)
    else:
        if args.output is None:
            args.output = os.path.join(os.getcwd(), "waybackup_snapshots")
        archive.query_list(args.url, args.range, args.start, args.end, args.explicit, mode)
        if args.list:
            archive.print_list()
        else:
            archive.download_list(args.output, args.retry, args.no_redirect, args.worker)            
            #archive.remove_empty_folders(args.output)
    v.close()

if __name__ == "__main__":
    main()