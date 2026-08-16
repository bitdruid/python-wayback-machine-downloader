# python wayback machine downloader

[![PyPI](https://img.shields.io/pypi/v/pywaybackup)](https://pypi.org/project/pywaybackup/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pywaybackup)](https://pypi.org/project/pywaybackup/)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Downloading archived web pages from the [Wayback Machine](https://archive.org/web/).

Internet-archive is a nice source for several OSINT-information. This tool is a work in progress to query and fetch archived web pages.

This tool allows you to download content from the Wayback Machine (archive.org). You can use it to download either the latest version or all versions of web page snapshots within a specified range.

## Fair use of archive.org

As i stumbled across projects which also reuse code from this repo...

The Wayback Machine is a free service run by a non-profit and funded by donations. Every request this tool makes is paid for by someone else.

There are projects out there tuned for maximum extraction — as many workers as the server will tolerate, no delay, whole domains pulled for the sake of it. I don't agree with that approach. The predictable end of it is rate limits, API tokens or IP blocks, and then nobody gets the open access we have today.

If you download here, please be a decent guest:

- Keep `--workers` low. The default is 1, and about 10 is the upper end of reasonable.
- Use `--delay` on larger jobs.
- Narrow the query with `--range`/`--start`/`--end`, `--filetype` and `--explicit` instead of pulling a whole domain and sorting it out afterwards.
- Prefer `--last` or `--first` over `--all` unless you genuinely need every version.
- Don't delete a finished job's metadata just to run it again — resume is there for that.

If archive.org is useful to you, [consider donating](https://archive.org/donate).

# Content

➡️ [Fair use of archive.org](#fair-use-of-archiveorg) <br>
➡️ [Installation](#installation) <br>
➡️ [notes / issues / hints](#notes--issues--hints) <br>
➡️ [import](#import) <br>
➡️ [cli](#cli) <br>
➡️ [Usage](#usage) <br>
➡️ [Examples](#examples) <br>
➡️ [Output](#output) <br>
➡️ [Contributing](#contributing) <br>

## Installation

### Pip

1. Install the package <br>
   `pip install pywaybackup`
2. Run the tool <br>
   `waybackup -h`

### Standalone binary

Prebuilt executables for Windows, Linux and macOS are attached to each [release](https://github.com/bitdruid/python-wayback-machine-downloader/releases). No Python required.

- Run from a terminal with arguments like the pip version: `waybackup -h`
- Or start it without arguments (e.g. double-click on Windows) to enter **interactive mode** — the tool will prompt you for URL, mode and optional settings.

On Linux/macOS the downloaded file has to be made executable first:

```bash
curl -L -o waybackup https://github.com/bitdruid/python-wayback-machine-downloader/releases/latest/download/waybackup-linux
chmod +x waybackup
./waybackup -h
```

Move it to a directory in your `PATH` (e.g. `~/.local/bin`) to call it as `waybackup` from anywhere.

### Manual

1. Clone the repository <br>
   `git clone https://github.com/bitdruid/python-wayback-machine-downloader.git`
2. Install <br>
   `pip install .`
   - in a virtual env or use `--break-system-package`

## notes / issues / hints

- Linux recommended: On Windows machines, the path length is limited. Files that exceed the path length will not be downloaded.
- The tool uses a sqlite database to handle snapshots. The database will only persist while the download is running.
- If you query an explicit file (e.g. a query-string `?query=this` or `login.html`), the `--explicit`-argument is recommended as a wildcard query may lead to an empty result.
- Downloading directly into a network share is not recommended. The sqlite locking mechanism may cause issues. If you need to download into a network share, set the `--metadata` argument to a local path.

<br>
<br>

## import

You can import pywaybackup into your own scripts and run it. Args are the same as cli.

Additional args:
- `silent` (default False): If True, suppresses all output to the console.
- `debug` (default True): If False, disables writing errors to the error log file.
- `progress_callback` (default None): A function receiving the `status()` dict on every progress update.
- `progress_interval` (default 5): Seconds between callback updates while snapshots are downloading.

Use:
- `run()`
- `status()`
- `paths()`
- `stop()`

```python
from pywaybackup import PyWayBackup

backup = PyWayBackup(
  url="https://example.com",
  all=True,
  start="20200101",
  end="20201231",
  silent=False,
  debug=True,
  log=True,
  keep=True
)

backup.run()
backup_paths = backup.paths(rel=True)
print(backup_paths)
```
output:
```bash
{
  'snapshots': 'output/example.com',
  'cdxfile': 'output/waybackup_example.cdx',
  'dbfile': 'output/waybackup_example.com.db',
  'csvfile': 'output/waybackup_https.example.com.csv',
  'log': 'output/waybackup_example.com.log',
  'debug': 'output/waybackup_error.log'
}
```

... or run it asynchronously and print the current status or stop it whenever needed.

```python
import time
from pywaybackup import PyWayBackup

backup = PyWayBackup( ... )
backup.run(daemon=True)
print(backup.status())
time.sleep(10)
print(backup.status())
backup.stop()
```
output:
```bash
{
  'task': 'downloading snapshots',
  'current': 15,
  'total': 84,
  'progress': '18%'
}
```

Instead of polling `status()`, pass a callback to receive the `status` dict every `progress_interval` seconds (works on `silent` and `progress` disabled).

```python
from pywaybackup import PyWayBackup

def on_progress(status):
    print(status)

backup = PyWayBackup(
  url="https://example.com",
  last=True,
  silent=True,
  progress=False,
  progress_callback=on_progress,
  progress_interval=5
)

backup.run()
```
output:
```bash
{'task': 'downloading cdx', 'current': 0, 'total': 0, 'progress': '0'}
{'task': 'preparing snapshots', 'current': 0, 'total': 0, 'progress': '0'}
{'task': 'downloading snapshots', 'current': 15, 'total': 84, 'progress': '18%'}
{'task': 'downloading snapshots', 'current': 54, 'total': 84, 'progress': '64%'}
{'task': 'downloading snapshots', 'current': 84, 'total': 84, 'progress': '100%'}
{'task': 'done', 'current': 84, 'total': 84, 'progress': '100%'}
```

Any callable taking one argument works - a function, a bound method, or a lambda for something short.

An exception raised inside the callback is logged and ignored - it will not abort a running job. When using `run(daemon=True)`, the callback runs inside the spawned process, so its side effects are not visible to the parent.

## cli

- `-h`, `--help`: Show the help message and exit. Version info is shown in the help header.

> **Interactive mode:** running `waybackup` without any arguments in a terminal starts a guided prompt for URL, mode and optional settings. Without a terminal (scripts/cron), the help is printed instead.

#### Required

- **`-u`**, **`--url`**:<br>
  The URL of the web page to download. This argument is required.

#### Mode Selection (Choose One)

- **`-a`**, **`--all`**:<br>
  All timestamps. Gives one folder per timestamp.
- **`-l`**, **`--last`**:<br>
  Last Version. Gives one folder containing the last version of each file of specified `--range`.
- **`-f`**, **`--first`**:<br>
  First Version. Gives one folder containing the first version of each file of specified `--range`.
- **`-s`**, **`--save`**:<br>
  Save a page to the wayback machine (no download).

#### Optional query parameters

Parameters for archive.org CDX query. No effect on snapshot download itself.

- **`-e`**, **`--explicit`**:<br>
  Only the explicit URL. No wildcard subdomains or paths. For example get: root-only (`https://example.com`) or specific file (`login.html`, `?query=this`).

- **`--limit`** `<count>`:<br>
  Limits the snapshots fetched from archive.org CDX. (Will have no effect on existing CDX files)

- **Range Selection:**<br>
  Set the query range in years (`range`) or a timestamp (`start` and/or `end`). If `range` then ignores `start` and `end`. Format for timestamps: YYYYMMDDhhmmss. Timestamp can as specific as needed (year 2019, year+month+day 20190101, ...).

  - **`-r`**, **`--range`**:<br>
    Specify the range in years for which to search and download snapshots.
  - **`--start`**:<br>
    Timestamp to start searching.
  - **`--end`**:<br>
    Timestamp to end searching.

- **Filtering:**<br>

  - **`--filetype`** `<filetype>`:<br>
    Specify filetypes to download. Example: `--filetype jpg,css,js`. You can only filter filetypes which are stored by archive.org (.html mostly not)

  - **`--statuscode`** `<statuscode>`:<br>
    Specify HTTP status codes to download. Example: `--statuscode 200,301`. PyWayBackup will always skip `404` and `301`.<br>
    Common status codes you may want to handle/filter:
      - `200` (OK)
      - `301` (Moved Permanently)
      - `404` (Not Found - snapshot seems to be empty)
      - `500` (Internal Server Error - snapshot is at least for now not available)

#### Optional Behavior Manipulation

Parameters will change the download behavior for snapshots.

- **`-o`**, **`--output`**:<br>
  Defaults to `waybackup_snapshots` in the current directory. The folder where downloaded files will be saved.

- **`-m`**, **`--metadata`**<br>
  Folder where metadata will be saved (`cdx`/`db`/`csv`/`log`). If you are downloading into a network share, you SHOULD set this to a local path because sqlite locking mechanism may cause issues with network shares.

- **`-v`**, **`--verbose`** `[level]`:<br>
  Set verbosity level. Available levels:
  - `low` (or `quiet`, `minimal`, `min`): Essential output only (same as no flag)
  - `default` (or `normal`, `verbose`): Standard verbose output (default when flag is set)
  - `high` (or `detailed`, `max`): Detailed verbose output
  
  Examples: `--verbose`, `--verbose default`, `--verbose high`, `-v high`

- **`--log`** <!-- `<path>` -->:<br>
  Saves a log file into the output-dir. `waybackup_<sanitized_url>.log`.

- **`--progress`**:<br>
  Shows a progress bar instead of the default output.

- **`--workers`** `<count>`:<br>
  Number of simultaneous download workers. Default is 1, safe range is about 10. Too many workers may lead to refused connections by archive.org.

- **`--no-redirect`**:<br>
  Disables following redirects of snapshots. Can prevent timestamp-folder mismatches caused by redirects.

- **`--no-merge-www`**:<br>
  Keeps `www.example.com` and `example.com` in separate folders. By default both are treated as the same site and written into one folder, as archive.org returns them mixed together for a single query. Only use this if the two hosts served genuinely different content.

- **`--retry`** `<attempts>`:<br>
  Retry attempts for failed downloads.

- **`--delay`** `<seconds>`:<br>
  Delay between download requests in seconds. Default is no delay (0).

- **`--wait`** `<seconds>`:<br>
  Seconds to wait before renewing connection after HTTP errors or snapshot download errors. Default is 15 seconds.

#### Job Handling:

- **`--reset`**:  
  If set, the job will be reset, and `cdx`, `db`, `csv` files will be **deleted**. This allows you to start the job from scratch.

- **`--keep`**:  
  If set, `cdx` and `db` files will be kept after the job is finished. Otherwise they will be deleted.

<br>
<br>

## Usage

### Handling Interrupted Jobs

`pywaybackup` resumes interrupted jobs. The tool automatically continues from where it left off.

Only resumes queries if:
- existing `.cdx` and `.db` files in an `output dir`
- command is identical by `URL`, `mode`, and `optional query parameters`
  > **Note:** Changing URL, mode selection, query parameters or output prevents automatic resumption.

<br>
<br>

## Examples

1. Download a specific single snapshot of all available files (starting from root):<br>
   `waybackup -u https://example.com -a --start 20210101000000 --end 20210101000000`
2. Download a specific single snapshot of all available files (starting from a subdirectory):<br>
   `waybackup -u https://example.com/subdir1/subdir2/assets/ -a --start 20210101000000 --end 20210101000000`
3. Download a specific single snapshot of the exact given URL (no subdirs):<br>
   `waybackup -u https://example.com -a --start 20210101000000 --end 20210101000000 --explicit`
4. Download all snapshots of all available files in the given range:<br>
   `waybackup -u https://example.com -a --start 20210101000000 --end 20231122000000`

<br>
<br>

## Output

### Path Structure

The output path is currently structured as follows by an example for the query:<br>
`http://example.com/subdir1/subdir2/assets/`
<br><br>
For the first and last version (`-f` or `-l`):

- Will only include all files/folders starting from your query-path.

```
your/path/waybackup_snapshots/
└── the_root_of_your_query/ (example.com/)
    └── subdir1/
        └── subdir2/
            └── assets/
                ├── image.jpg
                ├── style.css
                ...
```

For all versions (`-a`):

- Will create a folder named as the root of your query. Inside this folder, you will find all timestamps and per timestamp the path you requested.

```
your/path/waybackup_snapshots/
└── the_root_of_your_query/ (example.com/)
    ├── yyyymmddhhmmss/
    │   ├── subidr1/
    │   │   └── subdir2/
    │   │       └── assets/
    │   │           ├── image.jpg
    │   │           └── style.css
    ├── yyyymmddhhmmss/
    │   ├── subdir1/
    │   │   └── subdir2/
    │   │       └── assets/
    │   │           ├── image.jpg
    │   │           └── style.css
    ...
```

### CSV

The CSV contains a snapshot per row:

```
[
   {
      "file": "/your/path/waybackup_snapshots/example.com/yyyymmddhhmmss/index.html",
      "id": 1,
      "redirect_timestamp": "yyyymmddhhmmss",
      "redirect_url": "http://web.archive.org/web/yyyymmddhhmmssid_/http://example.com/",
      "response": 200,
      "timestamp": "yyyymmddhhmmss",
      "url_archive": "http://web.archive.org/web/yyyymmddhhmmssid_/http://example.com/",
      "url_origin": "http://example.com/"
   },
    ...
]
```

### Log

Verbose:

```
-----> Worker: 2 - Attempt: [1/1] Snapshot ID: [23/81]
SUCCESS   -> 200 OK
          -> URL:  https://web.archive.org/web/20240225193302id_/https://example.com/assets/css/custom-styles.css
          -> FILE: /home/manjaro/Stuff/python-wayback-machine-downloader/waybackup_snapshots/example.com/20240225193302id_/assets/css/custom-styles.css
```

Non-verbose:

```
55/81 - W:2 - SUCCESS - 20240225193302 - https://example.com/assets/css/custom-styles.css
```

### Debugging

Exceptions will be written into `waybackup_error.log` (each run overwrites the file).

<br>
<br>

## Future ideas (long run)

- More module functionality
- Docker UI

## Contributing

I'm always happy for some feature requests to improve the usability of this tool.
Feel free to give suggestions and report issues. Project is still far from being perfect.