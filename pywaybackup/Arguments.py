import sys
import argparse

from argparse import RawTextHelpFormatter

from importlib.metadata import version


class Arguments:
    def __init__(self):
        parser = argparse.ArgumentParser(
            description=f"<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>\nby @bitdruid -> https://github.com/bitdruid",
            formatter_class=RawTextHelpFormatter,
        )

        required = parser.add_argument_group("required (one exclusive)")
        required.add_argument("-u", "--url", type=str, metavar="", help="url (with subdir/subdomain) to download")
        exclusive_required = required.add_mutually_exclusive_group(required=True)
        exclusive_required.add_argument("-a", "--all", action="store_true", help="download snapshots of all timestamps")
        exclusive_required.add_argument("-l", "--last", action="store_true", help="download the last version of each file snapshot")
        exclusive_required.add_argument("-f", "--first", action="store_true", help="download the first version of each file snapshot")
        exclusive_required.add_argument("-s", "--save", action="store_true", help="save a page to the wayback machine")

        optional = parser.add_argument_group("optional query parameters")
        optional.add_argument("-e", "--explicit", action="store_true", help="search only for the explicit given url")
        optional.add_argument("-r", "--range", type=int, metavar="", help="range in years to search")
        optional.add_argument("--start", type=int, metavar="", help="start timestamp format: YYYYMMDDHHMMSS")
        optional.add_argument("--end", type=int, metavar="", help="end timestamp format: YYYYMMDDHHMMSS")
        optional.add_argument("--limit", type=int, nargs="?", const=True, metavar="int", help="limit the number of snapshots to download")
        optional.add_argument("--filetype", type=str, metavar="", help="filetypes to download comma separated (js,css,...)")
        optional.add_argument("--statuscode", type=str, metavar="", help="statuscodes to download comma separated (200,404,...)")

        behavior = parser.add_argument_group("manipulate behavior")
        behavior.add_argument("-o", "--output", type=str, metavar="", help="output for all files - defaults to current directory")
        behavior.add_argument("-m", "--metadata", type=str, metavar="", help="change directory for db/cdx/csv/log files")
        behavior.add_argument("-v", "--verbose", action="store_true", help="overwritten by progress - gives detailed output")
        behavior.add_argument("--log", action="store_true", help="save a log file into the output folder")
        behavior.add_argument("--progress", action="store_true", help="show a progress bar")
        behavior.add_argument("--no-redirect", action="store_true", help="do not follow redirects by archive.org")
        behavior.add_argument("--retry", type=int, default=0, metavar="", help="retry failed downloads (opt tries as int, else infinite)")
        behavior.add_argument("--workers", type=int, default=1, metavar="", help="number of workers (simultaneous downloads)")
        behavior.add_argument("--delay", type=int, default=0, metavar="", help="delay between each download in seconds")

        special = parser.add_argument_group("special")
        special.add_argument("--reset", action="store_true", help="reset the job and ignore existing cdx/db/csv files")
        special.add_argument("--keep", action="store_true", help="keep all files after the job finished")

        args = parser.parse_args(args=None if sys.argv[1:] else ["--help"])  # if no arguments are given, print help

        args.silent = False
        args.debug = True

        self.args = args

    def get_args(self) -> dict:
        """Returns the parsed arguments as a dictionary."""
        return vars(self.args)

