from pywaybackup import PyWayBackup
from pywaybackup.Arguments import Arguments as args


def cli():
    cli_input = args()
    cli_args = cli_input.get_args()
    config = PyWayBackup(**cli_args)
    config.run(daemon=False)


if __name__ == "__main__":
    cli()
