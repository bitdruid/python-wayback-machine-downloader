# archive wayback downloader

[![PyPI](https://img.shields.io/pypi/v/pywaybackup)](https://pypi.org/project/pywaybackup/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pywaybackup)](https://pypi.org/project/pywaybackup/)
![Python Version](https://img.shields.io/badge/Python-3.6-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Downloading archived web pages from the [Wayback Machine](https://archive.org/web/).

Internet-archive is a nice source for several OSINT-information. This script is a work in progress to query and fetch archived web pages.

## Installation

### Pip

1. Install the package <br>
   ```pip install pywaybackup```
2. Run the script <br>
   ```waybackup -h```

### Manual

1. Clone the repository <br>
   ```git clone https://github.com/bitdruid/python-wayback-machine-downloader.git```
2. Install <br>
   ```pip install .```
   - in a virtual env or use `--break-system-package`

## Usage

This script allows you to download content from the Wayback Machine (archive.org). You can use it to download either the latest version or all versions of web page snapshots within a specified range.

### Arguments

- `-h`, `--help`: Show the help message and exit.
- `-a`, `--about`: Show information about the script and exit.

#### Required Arguments

- `-u`, `--url`: The URL of the web page to download. This argument is required.

#### Mode Selection (Choose One)

- `-c`, `--current`: Download the latest version of each file snapshot. You will get a rebuild of the current website with all available files (but not any original state because new and old versions are mixed).
- `-f`, `--full`: Download snapshots of all timestamps. You will get a folder per timestamp with the files available at that time.
- `-s`, `--save`: Save a page to the Wayback Machine. (beta)

#### Optional Arguments

- `-l`, `--list`: Only print the snapshots available within the specified range. Does not download the snapshots.
- `-e`, `--explicit`: Only download the explicit given url. No wildcard subdomains or paths. Use e.g. to get root-only snapshots.
- `-o`, `--output`: The folder where downloaded files will be saved.

- **Range Selection:**<br>
Specify the range in years or a specific timestamp either start, end or both. If you specify the `range` argument, the `start` and `end` arguments will be ignored. Format for timestamps: YYYYMMDDhhmmss. You can only give a year or increase specificity by going through the timestamp starting on the left.<br>
(year 2019, year+month 201901, year+month+day 20190101, year+month+day+hour 2019010112)
   - `-r`, `--range`: Specify the range in years for which to search and download snapshots.
   - `--start`: Timestamp to start searching.
   - `--end`: Timestamp to end searching.

#### Additional

- `--csv`: Save a csv file with the list of snapshots inside the output folder or a specified folder. If you set `--list` the csv will contain the cdx list of snapshots. If you set either `--current` or `--full` the csv will contain the downloaded files.
- `--no-redirect`: Do not follow redirects of snapshots. Archive.org sometimes redirects to a different snapshot for several reasons. Downloading redirects may lead to timestamp-folders which contain some files with a different timestamp. This does not matter if you only want to download the latest version (`-c`).
- `--verbosity`: Set the verbosity: json (print json response), progress (show progress bar).
- `--retry`: Retry failed downloads. You can specify the number of retry attempts as an integer.
- `--workers`: The number of workers to use for downloading (simultaneous downloads). Default is 1. A safe spot is about 10 workers. Beware: Using too many workers will lead into refused connections from the Wayback Machine. Duration about 1.5 minutes.

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

I'm always happy for some feature requests to improve the usability of this script.
Feel free to give suggestions and report issues. Project is still far from being perfect.