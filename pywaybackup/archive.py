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

from pywaybackup.helper import url_get_timestamp, move_index, sanitize_filename, check_nt

from pywaybackup.SnapshotCollection import SnapshotCollection as sc
from pywaybackup.Arguments import Configuration as config

from pywaybackup.__version__ import __version__

from pywaybackup.Converter import Converter as convert
from pywaybackup.Verbosity import Message
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
    vb.write(message="\nSaving page to the Wayback Machine...")
    connection = http.client.HTTPSConnection("web.archive.org")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    connection.request("GET", f"https://web.archive.org/save/{url}", headers=headers)
    vb.write(message="\n-----> Request sent")
    response = connection.getresponse()
    response_status = response.status

    if response_status == 302:
        location = response.getheader("Location")
        vb.write(message="\n-----> Response: 302 (redirect to snapshot)")
        snapshot_timestamp = datetime.strptime(url_get_timestamp(location), '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_difference = (datetime.strptime(current_timestamp, '%Y-%m-%d %H:%M:%S') - datetime.strptime(snapshot_timestamp, '%Y-%m-%d %H:%M:%S')).seconds / 60
        timestamp_difference = int(round(timestamp_difference, 0))

        if timestamp_difference < 1:
            vb.write(message="\n-----> New snapshot created")
        elif timestamp_difference > 1:
            vb.write(message=f"\n-----> Snapshot already exists. (1 hour limit) - wait for {60 - timestamp_difference} minutes")
            vb.write(message=f"TIMESTAMP SNAPSHOT: {snapshot_timestamp}")
            vb.write(message=f"TIMESTAMP REQUEST : {current_timestamp}")
            vb.write(message=f"\nLAST SNAPSHOT BACK: {timestamp_difference} minutes")

        vb.write(message=f"\nURL: {location}")

    elif response_status == 404:
        vb.write(message="\n-----> Response: 404 (not found)")
        vb.write(message=f"\nFAILED -> URL: {url}")
    else:
        vb.write(message="\n-----> Response: unexpected")
        vb.write(message=f"\nFAILED -> URL: {url}")

    connection.close()




def print_list():
    vb.write(message="")
    count = sc.count(collection=True)
    if count == 0:
        vb.write(message="\nNo snapshots found")
    else:
        __import__('pprint').pprint(sc.SNAPSHOT_COLLECTION)
        vb.write(message=f"\n-----> {count} snapshots listed")





# create filelist
# timestamp format yyyyMMddhhmmss
def query_list(range: int, start: int, end: int, explicit: bool, mode: str, cdxbackup: str, cdxinject: str):
    
    def inject(cdxinject):
        if os.path.isfile(cdxinject):
            vb.write(message="\nInjecting CDX data...")
            cdxResult = open(cdxinject, "r")
            cdxResult = cdxResult.read()
            linecount = cdxResult.count("\n") - 1
            vb.write(message=f"\n-----> {linecount} snapshots injected")
            return cdxResult
        else:
            vb.write(message="\nNo CDX file found to inject - querying snapshots...")
            return False

    def query(range, start, end, explicit):
        vb.write(message="\nQuerying snapshots...")
        query_range = ""
        if not range:
            if start: query_range = query_range + f"&from={start}"
            if end: query_range = query_range + f"&to={end}"
        else: 
            query_range = "&from=" + str(datetime.now().year - range)

        if config.domain and not config.subdir and not config.filename:
            cdx_url = f"{config.domain}"
        if config.domain and config.subdir and not config.filename:
            cdx_url = f"{config.domain}/{config.subdir}"
        if config.domain and config.subdir and config.filename:
            cdx_url = f"{config.domain}/{config.subdir}/{config.filename}"
        if config.domain and not config.subdir and config.filename:
            cdx_url = f"{config.domain}/{config.filename}"
        if not explicit:
            cdx_url = f"{cdx_url}/*"

        vb.write(message=f"---> {cdx_url}")
        cdxQuery = f"https://web.archive.org/cdx/search/cdx?output=json&url={cdx_url}{query_range}&fl=timestamp,digest,mimetype,statuscode,original&filter!=statuscode:200"

        try:
            cdxResult = requests.get(cdxQuery).text
        except requests.exceptions.ConnectionError as e:
            vb.write(message="\nCONNECTION REFUSED -> could not query cdx server (max retries exceeded)\n")
            os._exit(1)
        
        if cdxbackup:
            os.makedirs(cdxbackup, exist_ok=True)
            with open(os.path.join(cdxbackup, f"waybackup_{sanitize_filename(config.url)}.cdx"), "w") as file: 
                file.write(cdxResult)
                vb.write(message="\n-----> CDX backup generated")

        return cdxResult

    cdxResult = None
    if cdxinject:
        cdxResult = inject(cdxinject)
    if not cdxResult:
        cdxResult = query(range, start, end, explicit)
    cdxResult = json.loads(cdxResult)
    sc.create_list(cdxResult, mode)
    vb.write(message=f"\n-----> {sc.count(collection=True)} snapshots to utilize")






# example download: http://web.archive.org/web/20190815104545id_/https://www.google.com/
def download_list(output, retry, no_redirect, delay, workers, skipset: set = None):
    """
    Download a list of urls in format: [{"timestamp": "20190815104545", "url": "https://www.google.com/"}]
    """
    if sc.count(collection=True) == 0:
        vb.write(message="\nNothing to download");
        return
    vb.write(message="\nDownloading snapshots...",)
    vb.progress(0)
    if workers > 1:
        vb.write(message=f"\n-----> Simultaneous downloads: {workers}")

    sc.create_collection()
    vb.write(message="\n-----> Snapshots prepared")

    # create queue with snapshots and skip already downloaded urls
    snapshot_queue = queue.Queue()
    skip_count = 0
    for snapshot in sc.SNAPSHOT_COLLECTION:
        if skipset is not None and skip_read(skipset, snapshot["url_archive"]):
            skip_count += 1
            continue
        snapshot_queue.put(snapshot)
    vb.progress(skip_count)
    if skip_count > 0:
        vb.write(message=f"\n-----> Skipped snapshots: {skip_count}")

    threads = []
    worker = 0
    for worker in range(workers):
        worker += 1
        vb.write(message=f"\n-----> Starting worker: {worker}")
        thread = threading.Thread(target=download_loop, args=(snapshot_queue, output, worker, retry, no_redirect, delay, skipset))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    successed = sc.count(success=True)
    failed = sc.count(fail=True)
    vb.write(message=f"\nFiles downloaded: {successed}")
    vb.write(message=f"Not downloaded: {failed}\n")





def download_loop(snapshot_queue, output, worker, retry, no_redirect, delay, skipset=None, attempt=1, connection=None, failed_urls=[]):
    """
    Download a snapshot of the queue. If a download fails, the function will retry the download.
    The "snapshot_collection" dictionary will be updated with the download status and file information.
    Information for each entry is written by "create_entry" and "snapshot_dict_append" functions.
    """
    try:
        max_attempt = retry if retry > 0 else retry + 1
        connection = connection or http.client.HTTPSConnection("web.archive.org")
        if attempt > max_attempt:
            connection.close()
            return

        while not snapshot_queue.empty():
            snapshot = snapshot_queue.get()
            status_message = Message()
            status_message.store(message=f"\n-----> Attempt: [{attempt}/{max_attempt}] Snapshot [{sc.SNAPSHOT_COLLECTION.index(snapshot)+1}/{len(sc.SNAPSHOT_COLLECTION)}] - Worker: {worker}")
            download_status = download(output, snapshot, connection, status_message, no_redirect)
            if not download_status and snapshot not in failed_urls:
                failed_urls.append(snapshot)
            if download_status:
                if snapshot in failed_urls:
                    failed_urls.remove(snapshot)
                vb.progress(1)
                if delay > 0:
                    vb.write(message=f"\n-----> Worker: {worker} - Delay: {delay} seconds")
                    time.sleep(delay)

        if failed_urls:
            if not attempt > max_attempt: 
                attempt += 1
                vb.write(message=f"\n-----> Worker: {worker} - Retry Timeout: 15 seconds")
                time.sleep(15)
            download_loop(snapshot_queue, output, worker, retry, no_redirect, delay, skipset, attempt, connection, failed_urls)
    except Exception as e:
        ex.exception(f"Worker: {worker} - Exception", e)
        snapshot_queue.put(snapshot)  # requeue snapshot if worker crashes





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
    success = False
    for i in range(max_retries):
        try:
            response, response_data, response_status, response_status_message = download_response(connection, encoded_download_url, headers)
            sc.entry_modify(snapshot_entry, "response", response_status)
            if not no_redirect and response_status == 302:
                status_message.store(status="REDIRECT", type="HTTP", message=f"{response.status} - {response_status_message}")
                status_message.store(status="", type="FROM", message=download_url)
                for _ in range(5):                   
                    response, response_data, response_status, response_status_message = download_response(connection, encoded_download_url, headers) 
                    location = response.getheader("Location")
                    if location:
                        encoded_download_url = urllib.parse.quote(urljoin(download_url, location), safe=':/')
                        status_message.store(status="", type="TO", message=location)
                        sc.entry_modify(snapshot_entry, "redirect_timestamp", url_get_timestamp(location))
                        sc.entry_modify(snapshot_entry, "redirect_url", download_url)
                    else:
                        break
            if response_status == 200:
                output_file = sc.create_output(download_url, snapshot_entry["timestamp"], output)
                output_path = os.path.dirname(output_file)

                # if output_file is too long for windows, skip download
                if check_nt() and len(output_file) > 255:
                    status_message.store(status="PATH > 255", type="HTTP", message=f"{response.status} - {response_status_message}")
                    status_message.store(status="", type="URL", message=download_url)
                    sc.entry_modify(snapshot_entry, "file", "PATH TOO LONG TO SAVE FILE")
                    status_message.write()
                    continue
                # case if output_path is a file, move file to temporary name, create output_path and move file into output_path
                if os.path.isfile(output_path):
                    move_index(existpath=output_path)
                else: 
                    os.makedirs(output_path, exist_ok=True)
                # case if output_file is a directory, create file as index.html in this directory
                if os.path.isdir(output_file):
                    output_file = move_index(existfile=output_file, filebuffer=response_data)
                # download file if not existing
                if not os.path.isfile(output_file):
                    with open(output_file, 'wb') as file:
                        if response.getheader('Content-Encoding') == 'gzip':
                            response_data = gzip.decompress(response_data)
                        file.write(response_data)
                    # check if file is downloaded
                    if os.path.isfile(output_file):
                        status_message.store(status="SUCCESS", type="HTTP", message=f"{response.status} - {response_status_message}")
                else:
                    status_message.store(status="EXISTING", type="HTTP", message=f"{response.status} - {response_status_message}")
                status_message.store(status="", type="URL", message=download_url)
                status_message.store(status="", type="FILE", message=output_file)
                sc.entry_modify(snapshot_entry, "file", output_file)
                # if convert_links:
                #     convert.links(output_file, status_message)
                status_message.write()
                success = True
                break 
            else:
                status_message.store(status="UNEXPECTED", type="HTTP", message=f"{response.status} - {response_status_message}")
                status_message.store(status="", type="URL", message=download_url)
                status_message.write()
                continue
        # exception handling        
        except (http.client.HTTPException, timeout, ConnectionRefusedError, ConnectionResetError) as e:
            download_exception(type, e, i, max_retries, sleep_time, status_message)
            continue
    if not success:
        status_message.store(status="FAILED", type="", message=f"append to failed_urls: {download_url}")
        status_message.write()
    return success





def download_response(connection, encoded_download_url, headers):
    connection.request("GET", encoded_download_url, headers=headers)
    response = connection.getresponse()
    response_data = response.read()
    response_status = response.status
    response_status_message = parse_response_code(response_status)
    return response, response_data, response_status, response_status_message





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
    status_message.store(status=f"{type}", type=f"({i+1}/{max_retries})", message=f"reconnect in {sleep_time} seconds...")
    status_message.write()
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
            new_rows = [snapshot for snapshot in sc.SNAPSHOT_COLLECTION 
                        if ("response" in snapshot and snapshot["response"] is not False and "url_archive" in snapshot) or 
                           ("digest" in snapshot)]
            
            if os.path.exists(csv_path):  # append to existing file
                existing_rows = set(csv_read(open(csv_path, mode='r', newline='')))
                
                with open(csv_path, mode='a', newline='') as file:  # append new rows
                    row_writer = csv.DictWriter(file, sc.SNAPSHOT_COLLECTION[0].keys())
                    for snapshot in new_rows:
                        snapshot_tuple = tuple(snapshot.values())
                        if snapshot_tuple not in existing_rows:
                            row_writer.writerow(snapshot)
            else:  # create new file
                with open(csv_path, mode='w', newline='') as file:
                    row_writer = csv.DictWriter(file, sc.SNAPSHOT_COLLECTION[0].keys())
                    row_writer.writeheader()
                    row_writer.writerows(new_rows)
    except Exception as e:
        ex.exception("Could not save CSV file", e)

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
            vb.write(message="\nNo CSV-file or content found to load skipable URLs")
            return None
    except Exception as e:
        ex.exception("Could not open CSV-file", e)

def skip_read(skipset: set, archive_url: str) -> bool:
    """
    Check if the URL is already downloaded and contained in the set.
    """
    # print the whole set
    return archive_url in skipset
    
    
    
