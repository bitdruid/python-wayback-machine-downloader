import pywaybackup.archive as archive
import pywaybackup.SnapshotCollection as sc
import argparse
import os

from pywaybackup.Verbosity import Verbosity as v

from pywaybackup.__version__ import __version__

def main():
    parser = argparse.ArgumentParser(description='Download from wayback machine (archive.org)')
    parser.add_argument('-a', '--about', action='version', version='%(prog)s ' + __version__ + ' by @bitdruid -> https://github.com/bitdruid')
    required = parser.add_argument_group('required')
    required.add_argument('-u', '--url', type=str, help='URL to use')
    exclusive_required = required.add_mutually_exclusive_group(required=True)
    exclusive_required.add_argument('-c', '--current', action='store_true', help='Download the latest version of each file snapshot (opt range in y)')
    exclusive_required.add_argument('-f', '--full', action='store_true', help='Download snapshots of all timestamps (opt range in y)')
    exclusive_required.add_argument('-s', '--save', action='store_true', help='Save a page to the wayback machine')
    optional = parser.add_argument_group('optional')
    optional.add_argument('-l', '--list', action='store_true', help='Only print snapshots (opt range in y)')
    optional.add_argument('-e', '--explicit', action='store_true', help='Search only for the explicit given url')
    optional.add_argument('-o', '--output', type=str, help='Output folder')
    optional.add_argument('-r', '--range', type=int, help='Range in years to search')
    optional.add_argument('--start', type=int, help='Start timestamp format: YYYYMMDDhhmmss')
    optional.add_argument('--end', type=int, help='End timestamp format: YYYYMMDDhhmmss')
    special = parser.add_argument_group('special')
    special.add_argument('--redirect', action='store_true', help='Follow redirects by archive.org')
    # special.add_argument('--harvest', action='store_true', help='Harvest location tags from snapshots and try to get as much as possible')
    special.add_argument('--verbosity', type=str, default="standard", choices=["standard", "progress", "json"], help='Verbosity level')
    special.add_argument('--retry', type=int, default=0, metavar="X-TIMES", help='Retry failed downloads (opt tries as int, else infinite)')
    special.add_argument('--worker', type=int, default=1, metavar="AMOUNT", help='Number of worker (simultaneous downloads)')

    args = parser.parse_args()
    snapshots = sc.SnapshotCollection()
    v.open(args.verbosity, snapshots)

    if args.current:
        mode = "current"
    elif args.full:
        mode = "full"

    if args.save:
        archive.save_page(args.url)
    else:
        if args.output is None:
            args.output = os.path.join(os.getcwd(), "waybackup_snapshots")
        archive.query_list(snapshots, args.url, args.range, args.start, args.end, args.explicit, mode)
        if args.list:
            archive.print_list(snapshots)
        else:
            archive.download_list(snapshots, args.output, args.retry, args.redirect, args.worker)            
            archive.remove_empty_folders(args.output)
    v.close()

if __name__ == "__main__":
    main()