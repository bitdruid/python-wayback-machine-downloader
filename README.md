# python wayback machine downloader

[![PyPI](https://img.shields.io/pypi/v/pywaybackup)](https://pypi.org/project/pywaybackup/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pywaybackup)](https://pypi.org/project/pywaybackup/)
![Python Version](https://img.shields.io/badge/Python-3.6-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Downloading archived web pages from the [Wayback Machine](https://archive.org/web/).

Internet-archive is a nice source for several OSINT-information. This tool is a work in progress to query and fetch archived web pages.

This tool allows you to download content from the Wayback Machine (archive.org). You can use it to download either the latest version or all versions of web page snapshots within a specified range.

## Installation

### Pip

1. Install the package <br>
   ```pip install pywaybackup```
2. Run the tool <br>
   ```waybackup -h```

### Manual

1. Clone the repository <br>
   ```git clone https://github.com/bitdruid/python-wayback-machine-downloader.git```
2. Install <br>
   ```pip install .```
   - in a virtual env or use `--break-system-package`

## Arguments

- `-h`, `--help`: Show the help message and exit.
- `-a`, `--about`: Show information about the tool and exit.

### Required

- `-u`, `--url`: The URL of the web page to download. This argument is required.

#### Mode Selection (Choose One)
- `-c`, `--current`: Download the latest version of each file snapshot. You will get a rebuild of the current website with all available files (but not any original state because new and old versions are mixed).
- `-f`, `--full`: Download snapshots of all timestamps. You will get a folder per timestamp with the files available at that time.
- `-s`, `--save`: Save a page to the Wayback Machine. (beta)

### Optional query parameters

- `-l`, `--list`: Only print the snapshots available within the specified range. Does not download the snapshots.
- `-e`, `--explicit`: Only download the explicit given url. No wildcard subdomains or paths. Use e.g. to get root-only snapshots.
- `-o`, `--output`: Defaults to `waybackup_snapshots` in the current directory. The folder where downloaded files will be saved.

- **Range Selection:**<br>
Specify the range in years or a specific timestamp either start, end or both. If you specify the `range` argument, the `start` and `end` arguments will be ignored. Format for timestamps: YYYYMMDDhhmmss. You can only give a year or increase specificity by going through the timestamp starting on the left.<br>
(year 2019, year+month 201901, year+month+day 20190101, year+month+day+hour 2019010112)
   - `-r`, `--range`: Specify the range in years for which to search and download snapshots.
   - `--start`: Timestamp to start searching.
   - `--end`: Timestamp to end searching.

### Additional behavior manipulation
  
- **`--csv`** `<path>`:<br>
Path defaults to output-dir. Saves a CSV file with the json-response for successfull downloads. If `--list` is set, the CSV contains the CDX list of snapshots. If `--current` or `--full` is set, CSV contains downloaded files. Named as `waybackup_<sanitized_url>.csv`.

- **`--skip`** `<path>`:<br>
Path defaults to output-dir. Checks for an existing `waybackup_<domain>.csv` for URLs to skip downloading. Useful for interrupted downloads. Files are checked by their root-domain, ensuring consistency across queries. This means that if you download `http://example.com/subdir1/` and later `http://example.com`, the second query will skip the first path.
  
- **`--no-redirect`**:<br>
Disables following redirects of snapshots. Useful for preventing timestamp-folder mismatches caused by Archive.org redirects.
  
- **`--verbosity`** `<level>`:<br>
Sets verbosity level. Options are `json` (prints JSON response) or `progress` (shows progress bar).
  
- **`--retry`** `<attempts>`:<br>
Specifies number of retry attempts for failed downloads.
  
- **`--workers`** `<count>`:<br>
Sets the number of simultaneous download workers. Default is 1, safe range is about 10. Be cautious as too many workers may lead to refused connections from the Wayback Machine.

**CDX Query Handling:**
- **`--cdxbackup`** `<path>`:<br>
Path defaults to output-dir. Saves the result of CDX query as a file. Useful for later downloading snapshots and overcoming refused connections by CDX server due to too many queries. Named as `waybackup_<sanitized_url>.cdx`.
  
- **`--cdxinject`** `<filepath>`:<br>
Injects a CDX query file to download snapshots. Ensure the query matches the previous `--url` for correct folder structure.

### Debug

- `--debug`: If set, full traceback will be printed in case of an error. The full exception will be written into `waybackup_error.log`.

### Examples

Download latest snapshot of all files:<br>
`waybackup -u http://example.com -c`

Download latest snapshot of a specific file:<br>
`waybackup -u http://example.com/subdir/file.html -c`

Download all snapshots sorted per timestamp with a specified range and do not follow redirects:<br>
`waybackup -u http://example.com -f -r 5 --no-redirect`

Download all snapshots sorted per timestamp with a specified range and save to a specified folder with 3 workers:<br>
`waybackup -u http://example.com -f -r 5 -o /home/user/Downloads/snapshots --workers 3`

Download all snapshots from 2020 to 12th of December 2022 with 4 workers, save a csv and show a progress bar:
`waybackup -u http://example.com -f --start 2020 --end 20221212 --workers 4 --csv --verbosity progress`

Download all snapshots and output a json response:<br>
`waybackup -u http://example.com -f --verbosity json`

List available snapshots per timestamp without downloading and save a csv file to home folder:<br>
`waybackup -u http://example.com -f -l --csv /home/user/Downloads`

## Output path structure

The output path is currently structured as follows by an example for the query:<br>
`http://example.com/subdir1/subdir2/assets/`:
<br><br>
For the current version (`-c`):
- The requested path will only include all files/folders starting from your query-path.
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
For all versions (`-f`):
- Will currently create a folder named as the root of your query. Inside this folder, you will find all timestamps and per timestamp the path you requested.
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


### Json Response

For download queries:

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

For list queries:

```
[
   {
      "digest": "DIGESTOFSNAPSHOT",
      "id": 1,
      "mimetype": "text/html",
      "status": "200",
      "timestamp": "yyyymmddhhmmss",
      "url": "http://example.com/"
   },
   ...
]
```

## CSV Output

The csv contains the json response in a table format.

## Contributing

I'm always happy for some feature requests to improve the usability of this tool.
Feel free to give suggestions and report issues. Project is still far from being perfect.
