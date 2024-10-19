
import sys
import os
import argparse

from pywaybackup.helper import url_split, sanitize_filename

from pywaybackup.__version__ import __version__

class Arguments:

    def __init__(self):

        parser = argparse.ArgumentParser(description='Download from wayback machine (archive.org)')
        parser.add_argument('-a', '--about', action='version', version='%(prog)s ' + __version__ + ' by @bitdruid -> https://github.com/bitdruid')

        required = parser.add_argument_group('required (one exclusive)')
        required.add_argument('-u', '--url', type=str, metavar="", help='url (with subdir/subdomain) to download')
        exclusive_required = required.add_mutually_exclusive_group(required=True)
        exclusive_required.add_argument('-c', '--current', action='store_true', help='download the latest version of each file snapshot')
        exclusive_required.add_argument('-f', '--full', action='store_true', help='download snapshots of all timestamps')
        exclusive_required.add_argument('-s', '--save', action='store_true', help='save a page to the wayback machine')

        optional = parser.add_argument_group('optional query parameters')
        optional.add_argument('-e', '--explicit', action='store_true', help='search only for the explicit given url')
        optional.add_argument('-r', '--range', type=int, metavar="", help='range in years to search')
        optional.add_argument('--start', type=int, metavar="", help='start timestamp format: YYYYMMDDhhmmss')
        optional.add_argument('--end', type=int, metavar="", help='end timestamp format: YYYYMMDDhhmmss')
        optional.add_argument('--filetype', type=str, metavar="", help='filetypes to download comma separated (e.g. "html,css")')
        optional.add_argument('--limit', type=int, nargs='?', const=True, metavar='int', help='limit the number of snapshots to download')

        behavior = parser.add_argument_group('manipulate behavior')
        behavior.add_argument('-o', '--output', type=str, metavar="", help='output folder - defaults to current directory')
        behavior.add_argument('--log', action='store_true', help='save a log file into the output folder')
        behavior.add_argument('--progress', action='store_true', help='show a progress bar')
        behavior.add_argument('--no-redirect', action='store_true', help='do not follow redirects by archive.org')
        #behavior.add_argument('--verbosity', type=str, default="info", metavar="", help='verbosity level (info, trace)')
        behavior.add_argument('--retry', type=int, default=0, metavar="", help='retry failed downloads (opt tries as int, else infinite)')
        behavior.add_argument('--workers', type=int, default=1, metavar="", help='number of workers (simultaneous downloads)')
        # behavior.add_argument('--convert-links', action='store_true', help='Convert all links in the files to local paths. Requires -c/--current')
        behavior.add_argument('--delay', type=int, default=0, metavar="", help='delay between each download in seconds')

        special = parser.add_argument_group('special')
        special.add_argument('--reset', action='store_true', help='reset the job and ignore existing cdx/db/csv files')
        special.add_argument('--keep', action='store_true', help='keep all files after the job finished')

        args = parser.parse_args(args=None if sys.argv[1:] else ['--help']) # if no arguments are given, print help

        required_args = {action.dest: getattr(args, action.dest) for action in exclusive_required._group_actions}
        optional_args = {action.dest: getattr(args, action.dest) for action in optional._group_actions}
        args.query_identifier = str(args.url) + str(required_args) + str(optional_args)

        # if args.convert_links and not args.current:
        #     parser.error("--convert-links can only be used with the -c/--current option")

        self.args = args

    def get_args(self):
        return self.args
    
class Configuration:

    @classmethod
    def init(cls):

        cls.args = Arguments().get_args()
        for key, value in vars(cls.args).items():
            setattr(Configuration, key, value)

        # args now attributes of Configuration // Configuration.output, ...
        cls.command = ' '.join(sys.argv[1:])
        cls.domain, cls.subdir, cls.filename = url_split(cls.url)

        if cls.output is None:
            cls.output = os.path.join(os.getcwd(), "waybackup_snapshots")
        os.makedirs(cls.output, exist_ok=True)

        if cls.log is True:
            cls.log = os.path.join(cls.output, f"waybackup_{sanitize_filename(cls.url)}.log")

        if cls.full:
            cls.mode = "full"
        if cls.current:
            cls.mode = "current"

        if cls.filetype:
            cls.filetype = [ft.lower().strip() for ft in cls.filetype.split(",")]

        cls.cdxfile = os.path.join(cls.output, f"waybackup_{sanitize_filename(cls.url)}.cdx")
        cls.dbfile = os.path.join(cls.output, f"waybackup_{sanitize_filename(cls.url)}.db")
        cls.csvfile = os.path.join(cls.output, f"waybackup_{sanitize_filename(cls.url)}.csv")

        if cls.reset:
            os.remove(cls.cdxfile) if os.path.isfile(cls.cdxfile) else None
            os.remove(cls.dbfile) if os.path.isfile(cls.dbfile) else None
            os.remove(cls.csvfile) if os.path.isfile(cls.csvfile) else None