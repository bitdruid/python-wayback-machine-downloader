# python wayback machine downloader

[![PyPI](https://img.shields.io/pypi/v/pywaybackup)](https://pypi.org/project/pywaybackup/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pywaybackup)](https://pypi.org/project/pywaybackup/)
![Python Version](https://img.shields.io/badge/Python-3.8-blue)
![Python_Sqlite3 Version](https://img.shields.io/badge/Python_Sqlite3-3.25-blue)
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

## Usage infos - important notes

- Linux recommended: On Windows machines, the path length is limited. This can only be overcome by editing the registry. Files that exceed the path length will not be downloaded.
- If you query an explicit file (e.g. a query-string `?query=this` or `login.html`), the `--explicit`-argument is recommended as a wildcard query may lead to an empty result.
- The tool uses a sqlite database to handle snapshots. The database will only persist while the download is running.

## Arguments

- `-h`, `--help`: Show the help message and exit.
- `-v`, `--version`: Show information about the tool and exit.

### Required

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

### Optional query parameters

- **`-e`**, **`--explicit`**:<br>
  Only download the explicit given URL. No wildcard subdomains or paths. Use e.g. to get root-only snapshots. This is recommended for explicit files like `login.html` or `?query=this`.

- **`--filetype`** `<filetype>`:<br>
  Specify filetypes to download. Default is all filetypes. Separate multiple filetypes with a comma. Example: `--filetype jpg,css,js`. A filter will result in a filtered cdx-file. So if you want to download all files later, you need to query again without the filter. Filetypes are filtered as they are in the snapshot. So if there is no explicit `html` file in the path (common practice) then you cant filter them.

- **`--limit`** `<count>`:<br>
Limits the amount of snapshots to query from the CDX server. If an existing CDX file is injected, the limit will have no effect. So you would need to set `--keep`.

- **Range Selection:**<br>
  Specify the range in years or a specific timestamp either start, end, or both. If you specify the `range` argument, the `start` and `end` arguments will be ignored. Format for timestamps: YYYYMMDDhhmmss. You can only give a year or increase specificity by going through the timestamp starting on the left.<br>
  (year 2019, year 2019, year+month+day 20190101, year+month+day+hour 2019010112)
   - **`-r`**, **`--range`**:<br>
     Specify the range in years for which to search and download snapshots.
   - **`--start`**:<br>
     Timestamp to start searching.
   - **`--end`**:<br>
     Timestamp to end searching.

### Behavior manipulation

- **`-o`**, **`--output`**:<br>
Defaults to `waybackup_snapshots` in the current directory. The folder where downloaded files will be saved.

<!-- - **`--verbosity`** `<level>`:<br>
Sets verbosity level. Options are `info`and `trace`. Default is `info`. -->

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

<!-- - **`--convert-links`**:<br>
If set, all links in the downloaded files will be converted to local links. This is useful for offline browsing. The links are converted to the local path structure. Show output with `--verbosity trace`. -->

### Special:

- **`--reset`**:  
  If set, the job will be reset, and any existing `cdx`, `db`, `csv` files will be **deleted**. This allows you to start the job from scratch without considering previously downloaded data.

- **`--keep`**:  
  If set, all files will be kept after the job is finished. This includes the `cdx` and `db` file. Without this argument, they will be deleted if the job finished successfully.

# Usage 

### Handling Interrupted Jobs
When a job is interrupted (by any reason), `pywaybackup` is designed to resume the job from where it left off. It automatically detects existing job data (based on the URL and <u>**optional query parameters**</u> - including output directory) and resumes the process without requiring manual intervention. Here's how the tool handles different scenarios:

- **Default Behavior:** 
  - On restarting the same job (same URL, <u>**optional query parameters**</u>, and output directory), the tool will:
    - Reuse the existing `.cdx` and `.db` files.
    - Resume downloading snapshots from the last successful point.
    - Skip previously downloaded files to save time and resources.

- **Manual Reset with `--reset`:** 
  - This command deletes any existing `.cdx` and `.db` files associated with the job and starts the process from scratch.
  - Useful if:
    - The previous data is corrupted.
    - You want to re-query the snapshots without considering previously downloaded data.

- **Preserving Job Data with `--keep`:** 
  - Normally, `.cdx` and `.db` files are deleted after the job finishes successfully.
  - Use `--keep` to retain these files for future use (e.g., re-analysis or extending the query later).

> **Note1:** The resumption process only works if the output directory remains the same as the one used during the initial job.
> 
> **Note2:** `--reset` will NOT delete the already downloaded files for now. You have to remove them 'by hand'.
  
### Example

1. Start downloading all available snapshots:<br>`waybackup -u https://example.com -a`
2. Interrupt the process `CTRL+C`<br>
3. The tool will detect the existing job data and resume downloading from the last completed point:<br>`waybackup -u https://example.com -a`
> **Important:** `waybackup -u https://example.com -c` -> The tool will NOT resume because a necessary identifier-changed
4. This deletes any existing .cdx and .db files associated with the job and starts the process from scratch:<br>`waybackup -u https://example.com -a --reset`
5. This ensures all job-related files are kept for future use, such as re-analysis or extending the query later:<br>`waybackup -u https://example.com -a --keep`

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

## CSV Output

Each snapshot is stored with the following keys/values. These are either stored in a sqlite database while the download is running or saved into a CSV file after the download is finished.

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

### Debugging

Exceptions will be written into `waybackup_error.log` (each run overwrites the file).

### Known ToDos

- [ ] currently there is no logic to handle if both a http and https version of a page is available

## Contributing

I'm always happy for some feature requests to improve the usability of this tool.
Feel free to give suggestions and report issues. Project is still far from being perfect.
