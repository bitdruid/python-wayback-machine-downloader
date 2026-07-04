"""
Single source of truth for waybackup CLI arguments.

Both Arguments (argparse) and Interactive (input prompts) consume this list,
so a new flag only needs to be added in one place. PyWayBackup.__init__ keeps
its explicit signature (vscode autocomplete).
"""

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ArgSpec:
    name: str  # internal key (matches PyWayBackup.__init__ kwarg)
    flags: List[str]  # CLI flags, e.g. ["-u", "--url"]
    group: str  # argparse group label
    help: str  # CLI help text
    prompt: Optional[str] = None  # interactive prompt label (None = skip in interactive)
    type: Optional[type] = None  # str / int / None for store_true
    default: Any = None
    action: str = "store"  # "store" | "store_true" | "optional_value"
    const: Any = None  # used when action="optional_value"
    metavar: str = ""  # argparse metavar; ignored for store_true
    exclusive_group: Optional[str] = None  # name of a mutex group below
    advanced: bool = False  # show in interactive only when advanced opts enabled


# Mutually exclusive groups, keyed by name. Specs join them via exclusive_group=...
EXCLUSIVE_GROUPS = {
    "mode": {"required": True, "parent_group": "required (one exclusive)"},
}

# argparse groups in display order
ARG_GROUPS = [
    "required (one exclusive)",
    "optional query parameters",
    "manipulate behavior",
    "special",
]


ARG_SPECS: List[ArgSpec] = [
    # required
    ArgSpec(
        name="url",
        flags=["-u", "--url"],
        group="required (one exclusive)",
        help="url (with subdir/subdomain) to download",
        prompt="URL to download (with subdir/subdomain)",
        type=str,
    ),
    ArgSpec(
        name="all",
        flags=["-a", "--all"],
        group="required (one exclusive)",
        help="download snapshots of all timestamps",
        action="store_true",
        default=False,
        exclusive_group="mode",
    ),
    ArgSpec(
        name="last",
        flags=["-l", "--last"],
        group="required (one exclusive)",
        help="download the last version of each file snapshot",
        action="store_true",
        default=False,
        exclusive_group="mode",
    ),
    ArgSpec(
        name="first",
        flags=["-f", "--first"],
        group="required (one exclusive)",
        help="download the first version of each file snapshot",
        action="store_true",
        default=False,
        exclusive_group="mode",
    ),
    ArgSpec(
        name="save",
        flags=["-s", "--save"],
        group="required (one exclusive)",
        help="save a page to the wayback machine",
        action="store_true",
        default=False,
        exclusive_group="mode",
    ),
    # -------------------- optional query --------------------
    ArgSpec(
        name="explicit",
        flags=["-e", "--explicit"],
        group="optional query parameters",
        help="search only for the explicit given url",
        action="store_true",
        default=False,
    ),
    ArgSpec(
        name="range",
        flags=["-r", "--range"],
        group="optional query parameters",
        help="range in years to search",
        prompt="Range in years to search",
        type=int,
        advanced=True,
    ),
    ArgSpec(
        name="start",
        flags=["--start"],
        group="optional query parameters",
        help="start timestamp format: YYYYMMDDHHMMSS",
        type=int,
    ),
    ArgSpec(
        name="end",
        flags=["--end"],
        group="optional query parameters",
        help="end timestamp format: YYYYMMDDHHMMSS",
        type=int,
    ),
    ArgSpec(
        name="limit",
        flags=["--limit"],
        group="optional query parameters",
        help="limit the number of snapshots to download",
        prompt="Limit number of snapshots",
        type=int,
        action="optional_value",
        const=True,
        metavar="int",
        advanced=True,
    ),
    ArgSpec(
        name="filetype",
        flags=["--filetype"],
        group="optional query parameters",
        help="filetypes to download comma separated (js,css,...)",
        type=str,
    ),
    ArgSpec(
        name="statuscode",
        flags=["--statuscode"],
        group="optional query parameters",
        help="statuscodes to download comma separated (200,404,...)",
        type=str,
    ),
    # behavior
    ArgSpec(
        name="output",
        flags=["-o", "--output"],
        group="manipulate behavior",
        help="output for all files - defaults to current directory",
        prompt="Output directory",
        type=str,
        advanced=True,
    ),
    ArgSpec(
        name="metadata",
        flags=["-m", "--metadata"],
        group="manipulate behavior",
        help="change directory for db/cdx/csv/log files",
        type=str,
    ),
    ArgSpec(
        name="verbose",
        flags=["-v", "--verbose"],
        group="manipulate behavior",
        help="verbosity level: low, default, high (default if flag set without value)",
        type=str,
        action="optional_value",
        const="default",
    ),
    ArgSpec(
        name="log",
        flags=["--log"],
        group="manipulate behavior",
        help="save a log file into the output folder",
        prompt="Save log file?",
        action="store_true",
        default=False,
        advanced=True,
    ),
    ArgSpec(
        name="progress",
        flags=["--progress"],
        group="manipulate behavior",
        help="show a progress bar",
        prompt="Show progress bar?",
        action="store_true",
        default=False,
        advanced=True,
    ),
    ArgSpec(
        name="no_redirect",
        flags=["--no-redirect"],
        group="manipulate behavior",
        help="do not follow redirects by archive.org",
        action="store_true",
        default=False,
    ),
    ArgSpec(
        name="retry",
        flags=["--retry"],
        group="manipulate behavior",
        help="retry failed downloads (opt tries as int, else infinite)",
        type=int,
        default=0,
    ),
    ArgSpec(
        name="workers",
        flags=["--workers"],
        group="manipulate behavior",
        help="number of workers (simultaneous downloads)",
        prompt="Workers (parallel downloads)",
        type=int,
        default=1,
        advanced=True,
    ),
    ArgSpec(
        name="delay",
        flags=["--delay"],
        group="manipulate behavior",
        help="delay between each download in seconds",
        type=int,
        default=0,
    ),
    ArgSpec(
        name="wait",
        flags=["--wait"],
        group="manipulate behavior",
        help="seconds to wait before renewing connection after HTTP errors or snapshot download errors (default: 15)",
        type=int,
        default=15,
    ),
    # special
    ArgSpec(
        name="reset",
        flags=["--reset"],
        group="special",
        help="reset the job and ignore existing cdx/db/csv files",
        action="store_true",
        default=False,
    ),
    ArgSpec(
        name="keep",
        flags=["--keep"],
        group="special",
        help="keep all files after the job finished",
        action="store_true",
        default=False,
    ),
]


def default_args() -> dict:
    """Return a dict of {name: default} for every spec — the canonical empty arg payload."""
    return {spec.name: spec.default for spec in ARG_SPECS}
