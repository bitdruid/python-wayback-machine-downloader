# python wayback machine downloader

[![PyPI](https://img.shields.io/pypi/v/pywaybackup)](https://pypi.org/project/pywaybackup/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pywaybackup)](https://pypi.org/project/pywaybackup/)
![Python Version](https://img.shields.io/badge/Python-3.8-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Downloading archived web pages from the [Wayback Machine](https://archive.org/web/).

Internet-archive is a nice source for several OSINT-information. This tool is a work in progress to query and fetch archived web pages.

This tool allows you to download content from the Wayback Machine (archive.org). You can use it to download either the latest version or all versions of web page snapshots within a specified range.

# Content

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

## cli

- `-h`, `--help`: Show the help message and exit.
- `-v`, `--version`: Show information about the tool and exit.

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

- **`--verbose`**:<br>
  Increase output verbosity.

- **`--log`** <!-- `<path>` -->:<br>
  Saves a log file into the output-dir. `waybackup_<sanitized_url>.log`.

- **`--progress`**:<br>
  Shows a progress bar instead of the default output.

- **`--workers`** `<count>`:<br>
  Number of simultaneous download workers. Default is 1, safe range is about 10. Too many workers may lead to refused connections by archive.org.

- **`--no-redirect`**:<br>
  Disables following redirects of snapshots. Can prevent timestamp-folder mismatches caused by redirects.

- **`--retry`** `<attempts>`:<br>
  Retry attempts for failed downloads.

- **`--delay`** `<seconds>`:<br>
  Delay between download requests in seconds. Default is no delay (0).

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