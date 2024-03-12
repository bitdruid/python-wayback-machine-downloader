# archive wayback downloader

[![PyPI](https://img.shields.io/pypi/v/pywaybackup)](https://pypi.org/project/pywaybackup/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pywaybackup)](https://pypi.org/project/pywaybackup/)
![Release](https://img.shields.io/badge/Release-beta-orange)
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

- `-u URL`, `--url URL`: The URL of the web page to download. This argument is required.

#### Mode Selection (Choose One)

- `-c`, `--current`: Download the latest version of each file snapshot.
- `-f`, `--full`: Download snapshots of all timestamps.
- `-s`, `--save`: Save a page to the Wayback Machine. (beta)

#### Optional Arguments

- `-l`, `--list`: Only print the snapshots available within the specified range. Does not download the snapshots.
- `-e`, `--explicit`: Only download the explicit given url. No wildcard subdomains or paths.
- `-o OUTPUT`, `--output OUTPUT`: The folder where downloaded files will be saved.

- **Range Selection:**<br>
Specify the range in years or a specific timestamp either start, end or both. If you specify the `range` argument, the `start` and `end` arguments will be ignored. Format for timestamps: YYYYMMDDhhmmss. You can only give a year or increase specificity by going through the timestamp starting on the left.<br>
(year 2019, year+month 201901, year+month+day 20190101, year+month+day+hour 2019010112)
   - `-r RANGE`, `--range RANGE`: Specify the range in years for which to search and download snapshots.
   - `--start`: Timestamp to start searching.
   - `--end`: Timestamp to end searching.

#### Additional

- `--redirect`: Follow redirects of snapshots. Default is False. If a source has not statuscode 200, archive.org will redirect to the closest snapshot. So when setting this to `true`, parts of a timestamp-folder may not truly belong to the given timestamp.
<!-- - `--harvest`: The downloaded files are scanned for locations on the same domain. These locations (mostly resources) are then tried to be accessed within the same timestamp. Setting this to `true` may result in identical files in different timestamps but you may get a more complete snapshot of the website. -->
- `--verbosity [LEVEL]`: Set the verbosity: json (print json response), progress (show progress bar) or standard (default).
- `--retry [RETRY_FAILED]`: Retry failed downloads. You can specify the number of retry attempts as an integer.
- `--worker [AMOUNT]`: The number of worker to use for downloading (simultaneous downloads). Default is 1. Beware: Using too many worker will lead into refused connections from the Wayback Machine. Duration about 1.5 minutes.

### Examples

Download latest snapshot of all files:<br>
`waybackup -u http://example.com -c`

Download latest snapshot of all files with retries:<br>
`waybackup -u http://example.com -c --retry 3`

Download all snapshots sorted per timestamp with a specified range and follow redirects:<br>
`waybackup -u http://example.com -f -r 5 --redirect`

Download all snapshots sorted per timestamp with a specified range and save to a specified folder with 3 worker:<br>
`waybackup -u http://example.com -f -r 5 -o /home/user/Downloads/snapshots --worker 3`

List available snapshots per timestamp without downloading:<br>
`waybackup -u http://example.com -f -l`

## Contributing

I'm always happy for some feature requests to improve the usability of this script.
Feel free to give suggestions and report issues. Project is still far from being perfect.