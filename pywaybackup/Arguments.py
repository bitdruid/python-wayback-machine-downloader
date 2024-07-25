
import sys
import os
import argparse

from pywaybackup.helper import url_split, sanitize_filename

from pywaybackup.__version__ import __version__

class Arguments:

    def __init__(self):

        parser = argparse.ArgumentParser(description='Download from wayback machine (archive.org)')
        parser.add_argument('-a', '--about', action='version', version='%(prog)s ' + __version__ + ' by @bitdruid -> https://github.com/bitdruid')
        parser.add_argument('-d', '--debug', action='store_true', help='Debug mode (Always full traceback and creates an error.log')

        required = parser.add_argument_group('required (one exclusive)')
        required.add_argument('-u', '--url', type=str, metavar="", help='url (with subdir/subdomain) to download')
        exclusive_required = required.add_mutually_exclusive_group(required=True)
        exclusive_required.add_argument('-c', '--current', action='store_true', help='download the latest version of each file snapshot')
        exclusive_required.add_argument('-f', '--full', action='store_true', help='download snapshots of all timestamps')
        exclusive_required.add_argument('-s', '--save', action='store_true', help='save a page to the wayback machine')

        optional = parser.add_argument_group('optional query parameters')
        optional.add_argument('-l', '--list', action='store_true', help='only print snapshots (opt range in y)')
        optional.add_argument('-e', '--explicit', action='store_true', help='search only for the explicit given url')
        optional.add_argument('-o', '--output', type=str, metavar="", help='output folder - defaults to current directory')
        optional.add_argument('-r', '--range', type=int, metavar="", help='range in years to search')
        optional.add_argument('--start', type=int, metavar="", help='start timestamp format: YYYYMMDDhhmmss')
        optional.add_argument('--end', type=int, metavar="", help='end timestamp format: YYYYMMDDhhmmss')

        special = parser.add_argument_group('manipulate behavior')
        special.add_argument('--csv', type=str, nargs='?', const=True, metavar='path', help='save a csv file with the json output - defaults to output folder')
        special.add_argument('--skip', type=str, nargs='?', const=True, metavar='path', help='skips existing files in the output folder by checking the .csv file - defaults to output folder')
        special.add_argument('--no-redirect', action='store_true', help='do not follow redirects by archive.org')
        special.add_argument('--verbosity', type=str, default="info", metavar="", help='["progress", "json"] for different output or ["trace"] for very detailed output')
        special.add_argument('--log', type=str, nargs='?', const=True, metavar='path', help='save a log file - defaults to output folder')
        special.add_argument('--retry', type=int, default=0, metavar="", help='retry failed downloads (opt tries as int, else infinite)')
        special.add_argument('--workers', type=int, default=1, metavar="", help='number of workers (simultaneous downloads)')
        # special.add_argument('--convert-links', action='store_true', help='Convert all links in the files to local paths. Requires -c/--current')
        special.add_argument('--delay', type=int, default=0, metavar="", help='delay between each download in seconds')

        cdx = parser.add_argument_group('cdx (one exclusive)')
        exclusive_cdx = cdx.add_mutually_exclusive_group()
        exclusive_cdx.add_argument('--cdxbackup', type=str, nargs='?', const=True, metavar='path', help='Save the cdx query-result to a file for recurent use - defaults to output folder')
        exclusive_cdx.add_argument('--cdxinject', type=str, nargs='?', const=True, metavar='path', help='Inject a cdx backup-file to download according to the given url')

        auto = parser.add_argument_group('auto')
        auto.add_argument('--auto', action='store_true', help='includes automatic csv, skip and cdxbackup/cdxinject to resume a stopped download')

        args = parser.parse_args(args=None if sys.argv[1:] else ['--help']) # if no arguments are given, print help

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

        if cls.auto:
            cls.skip = cls.output
            cls.csv = cls.output
            cls.cdxbackup = cls.output
            cls.cdxinject = os.path.join(cls.output, f"waybackup_{sanitize_filename(cls.url)}.cdx")
        else:
            if cls.skip is True:
                cls.skip = cls.output
            if cls.csv is True:
                cls.csv = cls.output
            if cls.cdxbackup is True:
                cls.cdxbackup = cls.output
            if cls.cdxinject is True:
                cls.cdxinject = cls.output


