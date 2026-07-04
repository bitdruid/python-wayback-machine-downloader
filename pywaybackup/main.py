import signal
import sys

from pywaybackup import PyWayBackup
from pywaybackup.arg_parser import Arguments
from pywaybackup.interactive import Interactive


def cli():
    # interactive only when launched with no args; scripts/cron without a tty get --help instead
    interactive = len(sys.argv) <= 1 and sys.stdin is not None and sys.stdin.isatty()
    try:
        cli_input = Interactive() if interactive else Arguments()
    except (KeyboardInterrupt, EOFError):
        # ignore pyinstaller bl SIGINT while aborting
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("\nAborted.")
        sys.exit(130)
    cli_args = cli_input.get_args()
    config = PyWayBackup(**cli_args)
    try:
        config.run(daemon=False)
    finally:
        if interactive:
            try:
                input("\nPress Enter to exit...")
            except (KeyboardInterrupt, EOFError):
                pass


if __name__ == "__main__":
    cli()
