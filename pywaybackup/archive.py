import requests
import os
import gzip
import csv
import threading
import queue
import time
import json
import urllib.parse
import http.client
from urllib.parse import urljoin
from datetime import datetime, timezone

from socket import timeout

from pywaybackup.helper import url_get_timestamp, url_split, move_index, sanitize_filename, check_nt

from pywaybackup.SnapshotCollection import SnapshotCollection as sc

from pywaybackup.__version__ import __version__

from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Exception import Exception as ex





# GET: store page to wayback machine and response with redirect to snapshot
# POST: store page to wayback machine and response with wayback machine status-page
# tag_jobid = '<script>spn.watchJob("spn2-%s", "/_static/",6000);</script>'
# tag_result_timeout = '<p>The same snapshot had been made %s minutes ago. You can make new capture of this URL after 1 hour.</p>'
# tag_result_success = ' A snapshot was captured. Visit page: <a href="%s">%s</a>'
def save_page(url: str):
    """
    Saves a webpage to the Wayback Machine. 

    Args:
        url (str): The URL of the webpage to be saved.

    Returns:
        None: The function does not return any value. It only prints messages to the console.
    """
    vb.write("\nSaving page to the Wayback Machine...")
    connection = http.client.HTTPSConnection("web.archive.org")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    connection.request("GET", f"https://web.archive.org/save/{url}", headers=headers)
    vb.write("\n-----> Request sent")
    response = connection.getresponse()
    response_status = response.status

    if response_status == 302:
        location = response.getheader("Location")
        vb.write("\n-----> Response: 302 (redirect to snapshot)")
        snapshot_timestamp = datetime.strptime(url_get_timestamp(location), '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_difference = (datetime.strptime(current_timestamp, '%Y-%m-%d %H:%M:%S') - datetime.strptime(snapshot_timestamp, '%Y-%m-%d %H:%M:%S')).seconds / 60
        timestamp_difference = int(round(timestamp_difference, 0))

        if timestamp_difference < 1:
            vb.write("\n-----> New snapshot created")
        elif timestamp_difference > 1:
            vb.write(f"\n-----> Snapshot already exists. (1 hour limit) - wait for {60 - timestamp_difference} minutes")
            vb.write(f"TIMESTAMP SNAPSHOT: {snapshot_timestamp}")
            vb.write(f"TIMESTAMP REQUEST : {current_timestamp}")
            vb.write(f"\nLAST SNAPSHOT BACK: {timestamp_difference} minutes")

        vb.write(f"\nURL: {location}")

    elif response_status == 404:
        vb.write("\n-----> Response: 404 (not found)")
        vb.write(f"\nFAILED -> URL: {url}")
    else:
        vb.write("\n-----> Response: unexpected")
        vb.write(f"\nFAILED -> URL: {url}")

    connection.close()




def print_list():
    vb.write("")
    count = sc.count(collection=True)
    if count == 0:
        vb.write("\nNo snapshots found")
    else:
        __import__('pprint').pprint(sc.SNAPSHOT_COLLECTION)
        vb.write(f"\n-----> {count} snapshots listed")





# create filelist
# timestamp format yyyyMMddhhmmss
def query_list(url: str, range: int, start: int, end: int, explicit: bool, mode: str, cdxbackup: str, cdxinject: str):
    
    def inject(cdxinject):
        if os.path.isfile(cdxinject):
            vb.write("\nInjecting CDX data...")
            cdxResult = open(cdxinject, "r")
            cdxResult = cdxResult.read()
            linecount = cdxResult.count("\n") - 1
            vb.write(f"\n-----> {linecount} snapshots injected")
            return cdxResult
        else:
            vb.write("\nNo CDX file found to inject - querying snapshots...")
            return False

    def query(url, range, start, end, explicit):
        vb.write("\nQuerying snapshots...")
        query_range = ""
        if not range:
            if start: query_range = query_range + f"&from={start}"
            if end: query_range = query_range + f"&to={end}"
        else: 
            query_range = "&from=" + str(datetime.now().year - range)

        domain, subdir, filename = url_split(url)
        if domain and not subdir and not filename:
            cdx_url = f"*.{domain}/*" if not explicit else f"{domain}"
        if domain and subdir and not filename:
            cdx_url = f"{domain}/{subdir}/*"
        if domain and subdir and filename:
            cdx_url = f"{domain}/{subdir}/{filename}/*"
        if domain and not subdir and filename:
            cdx_url = f"{domain}/{filename}/*"

        vb.write(f"---> {cdx_url}")
        cdxQuery = f"https://web.archive.org/cdx/search/cdx?output=json&url={cdx_url}{query_range}&fl=timestamp,digest,mimetype,statuscode,original&filter!=statuscode:200"

        try:
            cdxResult = requests.get(cdxQuery).text
        except requests.exceptions.ConnectionError as e:
            vb.write("\nCONNECTION REFUSED -> could not query cdx server (max retries exceeded)\n")
            os._exit(1)
        
        if cdxbackup:
            os.makedirs(cdxbackup, exist_ok=True)
            with open(os.path.join(cdxbackup, f"waybackup_{sanitize_filename(url)}.cdx"), "w") as file: 
                file.write(cdxResult)
                vb.write("\n-----> CDX backup generated")

        return cdxResult

    cdxResult = None
    if cdxinject:
        cdxResult = inject(cdxinject)
    if not cdxResult:
        cdxResult = query(url, range, start, end, explicit)
    cdxResult = json.loads(cdxResult)
    sc.create_list(cdxResult, mode)
    vb.write(f"\n-----> {sc.count(collection=True)} snapshots to utilize")






# example download: http://web.archive.org/web/20190815104545id_/https://www.google.com/
def download_list(output, retry, no_redirect, workers, skipset: set = None):
    """
    Download a list of urls in format: [{"timestamp": "20190815104545", "url": "https://www.google.com/"}]
    """
    if sc.count(collection=True) == 0:
        vb.write("\nNothing to download");
        return
    vb.write("\nDownloading snapshots...", progress=0)
    if workers > 1:
        vb.write(f"\n-----> Simultaneous downloads: {workers}")

    sc.create_collection()
    vb.write("\n-----> Snapshots prepared")

    # create queue with snapshots and skip already downloaded urls
    snapshot_queue = queue.Queue()
    skip_count = 0
    for snapshot in sc.SNAPSHOT_COLLECTION:
        if skipset is not None and skip_read(skipset, snapshot["url_archive"]):
            skip_count += 1
            continue
        snapshot_queue.put(snapshot)
    vb.write(progress=skip_count)
    if skip_count > 0:
        vb.write(f"\n-----> Skipped snapshots: {skip_count}")

    threads = []
    worker = 0
    for worker in range(workers):
        worker += 1
        vb.write(f"\n-----> Starting worker: {worker}")
        thread = threading.Thread(target=download_loop, args=(snapshot_queue, output, worker, retry, no_redirect, skipset))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    successed = sc.count(success=True)
    failed = sc.count(fail=True)
    vb.write(f"\nFiles downloaded: {successed}")
    vb.write(f"Not downloaded: {failed}\n")





def download_loop(snapshot_queue, output, worker, retry, no_redirect, skipset=None, attempt=1, connection=None, failed_urls=[]):
    """
    Download a snapshot of the queue. If a download fails, the function will retry the download.
    The "snapshot_collection" dictionary will be updated with the download status and file information.
    Information for each entry is written by "create_entry" and "snapshot_dict_append" functions.
    """
    try:
        max_attempt = retry if retry > 0 else retry + 1
        if not connection:
            connection = http.client.HTTPSConnection("web.archive.org")
        if attempt > max_attempt:
            connection.close()
            vb.write(f"\n-----> Worker: {worker} - Failed downloads: {len(failed_urls)}")
            return
        while not snapshot_queue.empty():
            snapshot = snapshot_queue.get()
            status = f"\n-----> Attempt: [{attempt}/{max_attempt}] Snapshot [{sc.SNAPSHOT_COLLECTION.index(snapshot)+1}/{len(sc.SNAPSHOT_COLLECTION)}] - Worker: {worker}"
            download_status = download(output, snapshot, connection, status, no_redirect)
            if not download_status:
                if snapshot not in failed_urls:
                    failed_urls.append(snapshot)
            if download_status:
                if snapshot in failed_urls:
                    failed_urls.remove(snapshot)
                vb.write(progress=1)
        if failed_urls:
            if not attempt > max_attempt: 
                attempt += 1
                vb.write(f"\n-----> Worker: {worker} - Retry Timeout: 15 seconds")
                time.sleep(15)
            download_loop(snapshot_queue, output, worker, retry, no_redirect, skipset, attempt, connection, failed_urls)
    except Exception as e:
        ex.exception(f"Worker: {worker} - Exception", e)
        snapshot_queue.put(snapshot) # requeue snapshot if worker crashes





def download(output, snapshot_entry, connection, status_message, no_redirect=False):
    """
    Download a single URL and save it to the specified filepath.
    If there is a redirect, the function will follow the redirect and update the download URL.
    gzip decompression is used if the response is encoded.
    According to the response status, the function will write a status message to the console and append a failed URL.
    """
    download_url = snapshot_entry["url_archive"]
    encoded_download_url = urllib.parse.quote(download_url, safe=':/') # used for GET - otherwise always download_url
    max_retries = 2
    sleep_time = 45
    headers = {'User-Agent': f'bitdruid-python-wayback-downloader/{__version__}'}
    for i in range(max_retries):
        try:
            connection.request("GET", encoded_download_url, headers=headers)
            response = connection.getresponse()
            response_data = response.read()
            response_status = response.status
            response_status_message = parse_response_code(response_status)
            sc.snapshot_entry_modify(snapshot_entry, "response", response_status)
            if not no_redirect:
                if response_status == 302:
                    status_message = f"{status_message}\n" + \
                        f"REDIRECT   -> HTTP: {response.status} - {response_status_message}\n" + \
                        f"           -> FROM: {download_url}"
                    redirect_count = 0
                    while response_status == 302:
                        redirect_count += 1
                        if redirect_count > 5:
                            break
                        connection.request("GET", encoded_download_url, headers=headers)
                        response = connection.getresponse()
                        response_data = response.read()
                        response_status = response.status
                        response_status_message = parse_response_code(response_status)
                        location = response.getheader("Location")
                        if location:
                            encoded_download_url = urllib.parse.quote(urljoin(download_url, location), safe=':/')
                            status_message = f"{status_message}\n" + \
                                f"           ->   TO: {download_url}"
                            sc.snapshot_entry_modify(snapshot_entry, "redirect_timestamp", url_get_timestamp(location))
                            sc.snapshot_entry_modify(snapshot_entry, "redirect_url", download_url)
                        else:
                            break
            if response_status == 200:
                output_file = sc.create_output(download_url, snapshot_entry["timestamp"], output)
                output_path = os.path.dirname(output_file)

                # if output_file is too long for windows, skip download
                if check_nt() and len(output_file) > 255:
                    status_message = f"{status_message}\n" + \
                        f"PATH TOO LONG TO SAVE FILE -> HTTP: {response_status} - {response_status_message}\n" + \
                        f"                           -> URL: {download_url}"
                    sc.snapshot_entry_modify(snapshot_entry, "file", "PATH TOO LONG TO SAVE FILE")
                    vb.write(status_message)
                    return True

                # case if output_path is a file, move file to temporary name, create output_path and move file into output_path
                if os.path.isfile(output_path):
                    move_index(existpath=output_path)
                else: 
                    os.makedirs(output_path, exist_ok=True)
                # case if output_file is a directory, create file as index.html in this directory
                if os.path.isdir(output_file):
                    output_file = move_index(existfile=output_file, filebuffer=response_data)

                if not os.path.isfile(output_file):
                    with open(output_file, 'wb') as file:
                        if response.getheader('Content-Encoding') == 'gzip':
                            response_data = gzip.decompress(response_data)
                            file.write(response_data)
                        else:
                            file.write(response_data)
                    if os.path.isfile(output_file):
                        status_message = f"{status_message}\n" + \
                            f"SUCCESS    -> HTTP: {response_status} - {response_status_message}"
                else:
                    status_message = f"{status_message}\n" + \
                        f"EXISTING   -> HTTP: {response_status} - {response_status_message}"
                status_message = f"{status_message}\n" + \
                    f"           -> URL: {download_url}\n" + \
                    f"           -> FILE: {output_file}"
                vb.write(status_message)
                sc.snapshot_entry_modify(snapshot_entry, "file", output_file)
                return True
            
            else:
                status_message = f"{status_message}\n" + \
                    f"UNEXPECTED -> HTTP: {response_status} - {response_status_message}\n" + \
                    f"           -> URL: {download_url}"
                vb.write(status_message)
                return True
        # exception returns false and appends the url to the failed list
        except http.client.HTTPException as e:
            status_message = f"{status_message}\n" + \
                f"EXCEPTION -> ({i+1}/{max_retries}), append to failed_urls: {download_url}\n" + \
                f"          -> {e}"
            vb.write(status_message)
            return False
        except (timeout, ConnectionRefusedError, ConnectionResetError) as e:
            download_exception(type, e, i, max_retries, sleep_time, status_message)
    vb.write(f"FAILED  -> download, append to failed_urls: {download_url}")
    return False

RESPONSE_CODE_DICT = {
    200: "OK",
    301: "Moved Permanently",
    302: "Found (redirect)",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
    503: "Service Unavailable"
}

def download_exception(type, e, i, max_retries, sleep_time, status_message):
    """
    Handle exceptions during the download process.
    """
    type = e.__class__.__name__.upper()
    status_message = f"{status_message}\n" + \
        f"{type} -> ({i+1}/{max_retries}), reconnect in {sleep_time} seconds...\n"
    vb.write(status_message)
    time.sleep(sleep_time)

def parse_response_code(response_code: int):
    """
    Parse the response code of the Wayback Machine and return a human-readable message.
    """
    if response_code in RESPONSE_CODE_DICT:
        return RESPONSE_CODE_DICT[response_code]
    return "Unknown response code"





def csv_close(csv_path: str, url: str):
    """
    Write a CSV file with the list of snapshots. Append new snapshots to the existing file.
    """
    try:
        csv_path = csv_filepath(csv_path, url)
        if sc.count(collection=True) > 0:
            if os.path.exists(csv_path): # append to existing file
                existing_rows = set()
                with open(csv_path, mode='r', newline='') as file: # read existing rows
                    existing_rows = set(csv_read(file))
                with open(csv_path, mode='a', newline='') as file: # append new rows
                    row = csv.DictWriter(file, sc.SNAPSHOT_COLLECTION[0].keys())
                    for snapshot in sc.SNAPSHOT_COLLECTION:
                        if snapshot["response"] is not False and snapshot["url_archive"] not in existing_rows: # only append handled snapshots
                            row.writerow(snapshot)
            else: # create new file
                with open(csv_path, mode='w', newline='') as file:
                    row = csv.DictWriter(file, sc.SNAPSHOT_COLLECTION[0].keys())
                    row.writeheader()
                    for snapshot in sc.SNAPSHOT_COLLECTION:
                        if snapshot["response"] is not False: # only append handled snapshots
                            row.writerow(snapshot)
    except Exception as e:
        ex.exception("Could not save CSV-file", e)

def csv_read(csv_file: object) -> list:
    """
    Read the CSV file and return a list of existing snapshot urls with a status (any status means file was handled)
    """
    try:
        csv_reader = csv.reader(csv_file)
        next(csv_reader)  # Skip the header row
        return [row[2] for row in csv_reader]
    except Exception as e:
        ex.exception("Could not read CSV-file", e)

def csv_filepath(csv_path: str, url: str) -> str:
    """
    Return the path to the CSV file.
    """
    return os.path.join(csv_path, f"waybackup_{sanitize_filename(url)}.csv")





def skip_open(csv_path: str, url: str) -> tuple:
    """
    Open the CSV file and return a set of existing snapshot urls.
    """
    try:
        csv_path = csv_filepath(csv_path, url)
        if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0:
            csv_file = open(csv_path, mode='r')
            skipset = set(csv_read(csv_file))
            csv_file.close()
            return skipset
        else:
            vb.write("\nNo CSV-file or content found to load skipable URLs")
            return None
    except Exception as e:
        ex.exception("Could not open CSV-file", e)

def skip_read(skipset: set, archive_url: str) -> bool:
    """
    Check if the URL is already downloaded and contained in the set.
    """
    # print the whole set
    return archive_url in skipset
    
    
    
