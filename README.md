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
  Download snapshots of all timestamps. You will get a folder per timestamp with the files available at that time.
- **`-l`**, **`--last`**:<br>
  Download the last version of each file snapshot. You will get one directory with a rebuild of the page. It contains the last version of each file of your specified `--range`.
- **`-f`**, **`--first`**:<br>
  Download the first version of each file snapshot. You will get one directory with a rebuild of the page. It contains the first version of each file of your specified `--range`.
- **`-s`**, **`--save`**:<br>
  Save a page to the Wayback Machine. (beta)

#### Optional query parameters

- **`-e`**, **`--explicit`**:<br>
  Only download the explicit given URL. No wildcard subdomains or paths. Use e.g. to get root-only snapshots. This is recommended for explicit files like `login.html` or `?query=this`.

- **`--limit`** `<count>`:<br>
  Limits the amount of snapshots to query from the CDX server. If an existing CDX file is injected, the limit will have no effect. So you would need to set `--keep`.

- **Range Selection:**<br>
  Specify the range in years or a specific timestamp either start, end, or both. If you specify the `range`, the `start` and `end` will be ignored. Format for timestamps: YYYYMMDDhhmmss. You can only give a year or increase specificity by going through the timestamp starting on the left.<br>
  (year 2019, year+month+day 20190101, year+month+day+hour 2019010112)

  - **`-r`**, **`--range`**:<br>
    Specify the range in years for which to search and download snapshots.
  - **`--start`**:<br>
    Timestamp to start searching.
  - **`--end`**:<br>
    Timestamp to end searching.

- **Filtering:**<br>
  A filter will result in a filtered cdx-file. So if you want to download all files later, you need to query again without the filter.

  - **`--filetype`** `<filetype>`:<br>
    Specify filetypes to download. Default is all filetypes. Separate multiple filetypes with a comma. Example: `--filetype jpg,css,js`. Filetypes are filtered as they are in the snapshot. So if there is no explicit `html` file in the path (common practice) then you cant filter them.

  - **`--statuscode`** `<statuscode>`:<br>
    Specify HTTP status codes to download. Default is all statuscodes. Separate multiple status codes with a comma. Example: `--statuscode 200,301`. Pywaybackup will try to download any snapshot regardless of it's statuscode. For 404 of course this means logged errors and corresponding entries in the csv. However, you may want to get a csv that includes these negative attempts for your needs.<br>
    Common status codes you may want to handle/filter:
      - `200` (OK)
      - `301` (Moved Permanently - will redirect snapshot)
      - `404` (Not Found - snapshot seems to be empty)
      - `500` (Internal Server Error - snapshot is at least for now not available)

### Optional

#### Behavior Manipulation

- **`-o`**, **`--output`**:<br>
  Defaults to `waybackup_snapshots` in the current directory. The folder where downloaded files will be saved.

- **`-m`**, **`--metadata`**<br>
  Change the folder where metadata will be saved (`cdx`/`db`/`csv`/`log`). Especially if you are downloading into a network share, you SHOULD set this to a local path because sqlite locking mechanism may cause issues with network shares.

- **`--verbose`**:<br>
  Increase output verbosity.

- **`--log`** <!-- `<path>` -->:<br>
  Saves a log file into the output-dir. Named as `waybackup_<sanitized_url>.log`.

- **`--progress`**:<br>
  Shows a progress bar instead of the default output.

- **`--workers`** `<count>`:<br>
  Sets the number of simultaneous download workers. Default is 1, safe range is about 10. Be cautious as too many workers may lead to refused connections from the Wayback Machine.

- **`--no-redirect`**:<br>
  Disables following redirects of snapshots. Useful for preventing timestamp-folder mismatches caused by Archive.org redirects.

- **`--retry`** `<attempts>`:<br>
  Specifies number of retry attempts for failed downloads.

- **`--delay`** `<seconds>`:<br>
  Specifies delay between download requests in seconds. Default is no delay (0).

#### Job Handling:

- **`--reset`**:  
  If set, the job will be reset, and any existing `cdx`, `db`, `csv` files will be **deleted**. This allows you to start the job from scratch without considering previously downloaded data.

- **`--keep`**:  
  If set, all files will be kept after the job is finished. This includes the `cdx` and `db` file. Without this argument, they will be deleted if the job finished successfully.

<br>
<br>

## Usage

### Handling Interrupted Jobs

`pywaybackup` resumes interrupted jobs. The tool automatically continues from where it left off.

- Detects existing `.cdx` and `.db` files in an `output dir` to resume downloading from the last successful point.
- Compares `URL`, `mode`, and `optional query parameters` to ensure automatic resumption.
- Skips previously downloaded files to save time.
  > **Note:** Changing URL, mode selection, query parameters or output prevents automatic resumption.

#### Resetting a Job (`--reset`)

- Deletes `.cdx` and `.db` files and restarts the process from scratch.
- Does **not** remove already downloaded files.
- `waybackup -u https://example.com -a --reset`

#### Keeping Job Data (`--keep`)

- Normally, `.cdx` and `.db` files are deleted after a successful job.
- `--keep` preserves them for future re-analysis or extending the query.
- `waybackup -u https://example.com -a --keep`

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

## Contributing

I'm always happy for some feature requests to improve the usability of this tool.
Feel free to give suggestions and report issues. Project is still far from being perfect.