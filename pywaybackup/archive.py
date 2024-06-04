import requests
import os
import gzip
import threading
import time
import http.client
from urllib.parse import urljoin
from datetime import datetime, timezone

from pywaybackup.helper import url_get_timestamp, url_split, file_move_index

from pywaybackup.SnapshotCollection import SnapshotCollection as sc

from pywaybackup.Verbosity import Verbosity as v





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
    v.write("\nSaving page to the Wayback Machine...")
    connection = http.client.HTTPSConnection("web.archive.org")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    connection.request("GET", f"https://web.archive.org/save/{url}", headers=headers)
    v.write("\n-----> Request sent")
    response = connection.getresponse()
    response_status = response.status

    if response_status == 302:
        location = response.getheader("Location")
        v.write("\n-----> Response: 302 (redirect to snapshot)")
        snapshot_timestamp = datetime.strptime(url_get_timestamp(location), '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_difference = (datetime.strptime(current_timestamp, '%Y-%m-%d %H:%M:%S') - datetime.strptime(snapshot_timestamp, '%Y-%m-%d %H:%M:%S')).seconds / 60
        timestamp_difference = int(round(timestamp_difference, 0))

        if timestamp_difference < 1:
            v.write("\n-----> New snapshot created")
        elif timestamp_difference > 1:
            v.write(f"\n-----> Snapshot already exists. (1 hour limit) - wait for {60 - timestamp_difference} minutes")
            v.write(f"TIMESTAMP SNAPSHOT: {snapshot_timestamp}")
            v.write(f"TIMESTAMP REQUEST : {current_timestamp}")
            v.write(f"\nLAST SNAPSHOT BACK: {timestamp_difference} minutes")

        v.write(f"\nURL: {location}")

    elif response_status == 404:
        v.write("\n-----> Response: 404 (not found)")
        v.write(f"\nFAILED -> URL: {url}")
    else:
        v.write("\n-----> Response: unexpected")
        v.write(f"\nFAILED -> URL: {url}")

    connection.close()




def print_list(csv: str = None):
    v.write("")
    count = sc.count_list()
    if csv:
        csv_header(csv)
        for snapshot in sc.SNAPSHOT_COLLECTION:
            csv_write(csv, snapshot)
    if count == 0:
        v.write("\nNo snapshots found")
    else:
        __import__('pprint').pprint(sc.SNAPSHOT_COLLECTION)
        v.write(f"\n-----> {count} snapshots listed")





# create filelist
# timestamp format yyyyMMddhhmmss
def query_list(url: str, range: int, start: int, end: int, explicit: bool, mode: str):
    try:
        v.write("\nQuerying snapshots...")
        query_range = ""
        
        if not range:
            if start: query_range = query_range + f"&from={start}"
            if end: query_range = query_range + f"&to={end}"
        else: 
            query_range = "&from=" + str(datetime.now().year - range)

        # parse user input url and create according cdx url
        domain, subdir, filename = url_split(url)
        if domain and not subdir and not filename:
            cdx_url = f"*.{domain}/*" if not explicit else f"{domain}"
        if domain and subdir and not filename:
            cdx_url = f"{domain}/{subdir}/*"
        if domain and subdir and filename:
            cdx_url = f"{domain}/{subdir}/{filename}/*"
        if domain and not subdir and filename:
            cdx_url = f"{domain}/{filename}/*"

        v.write(f"---> {cdx_url}")
        cdxQuery = f"https://web.archive.org/cdx/search/xd?output=json&url={cdx_url}{query_range}&fl=timestamp,digest,mimetype,statuscode,original&filter!=statuscode:200"
        cdxResult = requests.get(cdxQuery)
        sc.create_list(cdxResult, mode)
        v.write(f"\n-----> {sc.count_list()} snapshots found")
    except requests.exceptions.ConnectionError as e:
        v.write(f"\n-----> ERROR: could not query snapshots:\n{e}"); exit()





# example download: http://web.archive.org/web/20190815104545id_/https://www.google.com/
def download_list(output, retry, no_redirect, workers, csv: str = None):
    """
    Download a list of urls in format: [{"timestamp": "20190815104545", "url": "https://www.google.com/"}]
    """
    if sc.count_list() == 0: 
        v.write("\nNothing to download");
        return
    v.write("\nDownloading snapshots...", progress=0)
    if workers > 1:
        v.write(f"\n-----> Simultaneous downloads: {workers}")
        batch_size = sc.count_list() // workers + 1
    else:
        batch_size = sc.count_list()
    sc.create_collection()
    v.write("\n-----> Snapshots prepared")
    if csv:
        csv_header(csv)
    batch_list = [sc.SNAPSHOT_COLLECTION[i:i + batch_size] for i in range(0, len(sc.SNAPSHOT_COLLECTION), batch_size)]    
    threads = []
    worker = 0
    for batch in batch_list:
        worker += 1
        thread = threading.Thread(target=download_loop, args=(batch, output, workers, retry, no_redirect, csv))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()





def download_loop(snapshot_batch, output, worker, retry, no_redirect, csv=None, attempt=1, connection=None):
    """
    Download a list of URLs in a recursive loop. If a download fails, the function will retry the download.
    The "snapshot_collection" dictionary will be updated with the download status and file information.
    Information for each entry is written by "create_entry" and "snapshot_dict_append" functions.
    """
    max_attempt = retry if retry > 0 else retry + 1
    failed_urls = []
    if not connection:
        connection = http.client.HTTPSConnection("web.archive.org")
    if attempt > max_attempt:
        connection.close()
        v.write(f"\n-----> Worker: {worker} - Failed downloads: {len(snapshot_batch)}")
        return
    for snapshot in snapshot_batch:
        status = f"\n-----> Attempt: [{attempt}/{max_attempt}] Snapshot [{snapshot_batch.index(snapshot)+1}/{len(snapshot_batch)}] - Worker: {worker}"
        download_status = download(output, snapshot, connection, status, no_redirect, csv)
        if not download_status:
            failed_urls.append(snapshot)
        if download_status:
            v.write(progress=1)
    attempt += 1
    if failed_urls:
        if not attempt > max_attempt: 
            v.write(f"\n-----> Worker: {worker} - Retry Timeout: 15 seconds")
            time.sleep(15)
        download_loop(failed_urls, output, worker, retry, no_redirect, csv, attempt, connection)





def download(output, snapshot_entry, connection, status_message, no_redirect=False, csv=None):
    """
    Download a single URL and save it to the specified filepath.
    If there is a redirect, the function will follow the redirect and update the download URL.
    gzip decompression is used if the response is encoded.
    According to the response status, the function will write a status message to the console and append a failed URL.
    """
    download_url = snapshot_entry["url_archive"]
    max_retries = 2
    sleep_time = 45
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
    for i in range(max_retries):
        try:
            connection.request("GET", download_url, headers=headers)
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
                    while response_status == 302:
                        connection.request("GET", download_url, headers=headers)
                        response = connection.getresponse()
                        response_data = response.read()
                        response_status = response.status
                        response_status_message = parse_response_code(response_status)
                        location = response.getheader("Location")
                        if location:
                            download_url = urljoin(download_url, location)
                            status_message = f"{status_message}\n" + \
                                f"           ->   TO: {download_url}"
                            sc.snapshot_entry_modify(snapshot_entry, "redirect_timestamp", url_get_timestamp(location))
                            sc.snapshot_entry_modify(snapshot_entry, "redirect_url", download_url)
                        else:
                            break
            if response_status == 200:
                output_file = sc.create_output(download_url, snapshot_entry["timestamp"], output)
                output_path = os.path.dirname(output_file)
                if os.path.isfile(output_path): 
                    file_move_index(output_path)
                else: 
                    os.makedirs(output_path, exist_ok=True)

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
                        sc.snapshot_entry_modify(snapshot_entry, "file", output_file)
                        csv_write(csv, snapshot_entry) if csv else None

                else:
                    status_message = f"{status_message}\n" + \
                        f"EXISTING   -> HTTP: {response_status} - {response_status_message}"
                status_message = f"{status_message}\n" + \
                    f"           -> URL: {download_url}\n" + \
                    f"           -> FILE: {output_file}"
                v.write(status_message)
                return True
            
            else:
                status_message = f"{status_message}\n" + \
                    f"UNEXPECTED -> HTTP: {response_status} - {response_status_message}\n" + \
                    f"           -> URL: {download_url}"
                v.write(status_message)
                return True
        # exception returns false and appends the url to the failed list
        except http.client.HTTPException as e:
            status_message = f"{status_message}\n" + \
                f"EXCEPTION -> ({i+1}/{max_retries}), append to failed_urls: {download_url}\n" + \
                f"          -> {e}"
            v.write(status_message)
            return False
        # connection refused waits and retries
        except ConnectionRefusedError as e:
            status_message = f"{status_message}\n" + \
                f"REFUSED  -> ({i+1}/{max_retries}), reconnect in {sleep_time} seconds...\n" + \
                f"         -> {e}"
            v.write(status_message)
            time.sleep(sleep_time)
    v.write(f"FAILED  -> download, append to failed_urls: {download_url}")
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

def parse_response_code(response_code: int):
    """
    Parse the response code of the Wayback Machine and return a human-readable message.
    """
    if response_code in RESPONSE_CODE_DICT:
        return RESPONSE_CODE_DICT[response_code]
    return "Unknown response code"





def csv_open(csv_path: str, url: str) -> object:
    """
    Open the CSV file with for writing snapshots and return the file object.
    """
    disallowed = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in disallowed:
        url = url.replace(char, '.')
    os.makedirs(os.path.abspath(csv_path), exist_ok=True)
    file = open(os.path.join(csv_path, f"waybackup_{url}.csv"), mode='w')
    return file

def csv_header(file: object):
    """
    Write the header of the CSV file.
    """
    import csv
    row = csv.DictWriter(file, sc.SNAPSHOT_COLLECTION[0].keys())
    row.writeheader()

def csv_write(file: object, snapshot: dict):
    """
    Write a snapshot to the CSV file.
    """
    import csv
    row = csv.DictWriter(file, snapshot.keys())
    row.writerow(snapshot)

def csv_close(file: object):
    """
    Close a CSV file and sort the entries by timestamp.
    """
    file.close()
    with open(file.name, 'r') as f:
        data = f.readlines()
    data[1:] = sorted(data[1:], key=lambda x: int(x.split(',')[0]))
    with open(file.name, 'w') as f:
        f.writelines(data)