import sys

from pywaybackup import PyWayBackup
from pywaybackup.arg_parser import Arguments
from pywaybackup.interactive import Interactive


def cli():
    interactive = len(sys.argv) <= 1
    cli_input = Interactive() if interactive else Arguments()
    cli_args = cli_input.get_args()
    config = PyWayBackup(**cli_args)
    try:
        config.run(daemon=False)
    finally:
        if interactive:
            input("\nPress Enter to exit...")


if __name__ == "__main__":
    cli()
