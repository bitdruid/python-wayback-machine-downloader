#import threading
import requests
import os
import gzip
import threading
import time
import http.client
from urllib.parse import urljoin
from datetime import datetime, timezone

import pywaybackup.SnapshotCollection as sc

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
        snapshot_timestamp = datetime.strptime(location.split('/web/')[1].split('/')[0], '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
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





def print_list(snapshots):
    v.write("")
    count = snapshots.count_list()
    if count == 0:
        v.write("\nNo snapshots found")
    else:
        __import__('pprint').pprint(snapshots.CDX_LIST)
        v.write(f"\n-----> {count} snapshots listed")





# create filelist
# timestamp format yyyyMMddhhmmss
def query_list(snapshots: sc.SnapshotCollection, url: str, range: int, start: int, end: int, explicit: bool, mode: str):
    try:
        v.write("\nQuerying snapshots...")
        range = ""
        if not range:
            if start: range = range + f"&from={start}"
            if end: range = range + f"&to={end}"
        else: range = "&from=" + str(datetime.now().year - range)
        cdx_url = f"*.{url}/*" if not explicit else f"{url}"
        cdxQuery = f"https://web.archive.org/cdx/search/xd?output=json&url={cdx_url}{range}&fl=timestamp,original,statuscode&filter!=statuscode:200"
        cdxResult = requests.get(cdxQuery)
        snapshots.create_full(cdxResult)
        if mode == "current": snapshots.create_current()
        v.write(f"\n-----> {snapshots.count_list()} snapshots found")
    except requests.exceptions.ConnectionError as e:
        v.write(f"\n-----> ERROR: could not query snapshots:\n{e}"); exit()





# example download: http://web.archive.org/web/20190815104545id_/https://www.google.com/
def download_list(snapshots, output, retry, redirect, worker):
    """
    Download a list of urls in format: [{"timestamp": "20190815104545", "url": "https://www.google.com/"}]
    """
    if snapshots.count_list() == 0: 
        v.write("\nNothing to download");
        return
    v.write("\nDownloading snapshots...", progress=0)
    download_list = snapshots.CDX_LIST
    if worker > 1:
        v.write(f"\n-----> Simultaneous downloads: {worker}")
        batch_size = snapshots.count_list() // worker + 1
    else:
        batch_size = snapshots.count_list()
    batch_list = [download_list[i:i + batch_size] for i in range(0, len(download_list), batch_size)]
    threads = []
    worker = 0
    for batch in batch_list:
        worker += 1
        thread = threading.Thread(target=download_loop, args=(snapshots, batch, output, worker, retry, redirect))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def download_loop(snapshots, cdx_list, output, worker, retry, redirect, attempt=1, connection=None):
    """
    Download a list of URLs in a recursive loop. If a download fails, the function will retry the download.
    The "snapshot_collection" dictionary will be updated with the download status and file information.
    Information for each entry is written by "create_entry" and "snapshot_collection_write" functions.
    """
    max_attempt = retry + 1
    failed_urls = []
    if not connection:
        connection = http.client.HTTPSConnection("web.archive.org")
    if attempt > max_attempt: 
        connection.close()
        v.write(f"\n-----> Worker: {worker} - Failed downloads: {len(cdx_list)}")
        return
    else:
        for cdx_entry in cdx_list:
            status = f"\n-----> Attempt: [{attempt}/{max_attempt}] Snapshot [{cdx_list.index(cdx_entry)+1}/{len(cdx_list)}] - Worker: {worker}"
            download_entry = snapshots.create_entry(cdx_entry, output)
            snapshots.snapshot_collection_write(download_entry)
            download_status=download(download_entry, connection, status, redirect)
            if not download_status:
                snapshots.snapshot_collection_update(download_entry["id"], "success", False)
                snapshots.snapshot_collection_update(download_entry["id"], "file", "")
                snapshots.snapshot_collection_update(download_entry["id"], "retry", attempt)
                failed_urls.append(cdx_entry);
            if download_status:
                snapshots.snapshot_collection_update(download_entry["id"], "success", True)
                snapshots.snapshot_collection_update(download_entry["id"], "file", download_entry["file"])
                # if harvest: harvest_resources(download_entry, connection, output, redirect)
                v.write(progress=1)
        attempt += 1
    if failed_urls: download_loop(snapshots, failed_urls, output, worker, retry, redirect, attempt, connection)

def download(download_entry, connection, status_message, redirect=False):
    """
    Download a single URL and save it to the specified filepath.
    If there is a redirect, the function will follow the redirect and update the download URL.
    gzip decompression is used if the response is encoded.
    According to the response status, the function will write a status message to the console and append a failed URL.
    """
    download_url = download_entry["url"]
    download_file = download_entry["file"]
    max_retries = 2
    sleep_time = 45
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
    for i in range(max_retries):
        try:
            connection.request("GET", download_url, headers=headers)
            response = connection.getresponse()
            response_data = response.read()
            response_status = response.status
            if redirect:
                if response_status == 302:
                    status_message = f"{status_message}\n" + \
                        f"REDIRECT   -> HTTP: {response.status}"
                    while response_status == 302:
                        connection.request("GET", download_url, headers=headers)
                        response = connection.getresponse()
                        response_data = response.read()
                        response_status = response.status
                        location = response.getheader("Location")
                        if location:
                            status_message = f"{status_message}\n" + \
                                f"           -> URL: {location}"
                            location = urljoin(download_url, location)
                            download_url = location
                        else:
                            break
            if response_status == 200:
                os.makedirs(os.path.dirname(download_file), exist_ok=True)
                with open(download_file, 'wb') as file:
                    if response.getheader('Content-Encoding') == 'gzip':
                        response_data = gzip.decompress(response_data)
                        file.write(response_data)
                    else:
                        file.write(response_data)
                if os.path.isfile(download_file):
                    status_message = f"{status_message}\n" + \
                        f"SUCCESS    -> HTTP: {response.status}\n" + \
                        f"           -> URL: {download_url}\n" + \
                        f"           -> FILE: {download_file}"
                v.write(status_message)
                return True
            elif response_status == 404:
                status_message = f"{status_message}\n" + \
                    f"NOT FOUND  -> HTTP: {response.status}\n" + \
                    f"           -> URL: {download_url}"
            else:
                status_message = f"{status_message}\n" + \
                    f"UNEXPECTED -> HTTP: {response.status}\n" + \
                    f"           -> URL: {download_url}\n"
            v.write(status_message)
            return False
        except ConnectionRefusedError as e:
            status_message = f"{status_message}\n" + \
                f"REFUSED  -> ({i+1}/{max_retries}), reconnect in {sleep_time} seconds...\n" + \
                f"         -> {e}"
            v.write(status_message)
            time.sleep(sleep_time)
        except http.client.HTTPException as e:
            status_message = f"{status_message}\n" + \
                f"EXCEPTION -> ({i+1}/{max_retries}), append to failed_urls: {download_url}\n" + \
                f"          -> {e}"
            v.write(status_message)
            return False
    v.write(f"FAILED  -> download, append to failed_urls: {download_url}")
    return False





# def harvest_resources(download_entry, connection, output, redirect):
#     """
#     Soup search the snapshot page for locations of the same domain and try to download a snapshot.
#     """
#     from bs4 import BeautifulSoup
#     snapshot_origin_domain = sc.SnapshotCollection.split_url(download_entry["origin_url"])[0]
#     snapshot_origin_url = download_entry["origin_url"]
#     snapshot_file = download_entry["file"]
#     snapshot_timestamp = download_entry["timestamp"]
#     if snapshot_file:
#         location_list = []
#         with open(snapshot_file, "rb") as file:
#             # find all href and src tags and if they are from the same domain add them to the list
#             soup = BeautifulSoup(file, "html.parser")
#             for tag in soup.find_all(["a", "link", "script", "img"]):
#                 if tag.has_attr("href"):
#                     if not tag["href"].startswith("http") and not tag["href"].startswith("//"):
#                         location_list.append(urljoin(snapshot_origin_url, tag["href"]))
#                 if tag.has_attr("src"):
#                     if not tag["src"].startswith("http") and not tag["src"].startswith("//"):
#                         location_list.append(urljoin(snapshot_origin_url, tag["src"]))
#             location_list = list(set(location_list))
#         for entry in location_list:
#             v.write("Harvesting resources...", progress=0)
#             domain, subdir, filename = sc.SnapshotCollection.split_url(entry)
#             if domain != snapshot_origin_domain: continue
#             filename = os.path.join(os.path.dirname(snapshot_file), subdir, filename)
#             download({ "url": sc.SnapshotCollection.create_archive_url(snapshot_timestamp, entry), "file": filename }, connection, "", redirect)
                



def remove_empty_folders(path, remove_root=True):
    count = 0
    if not os.path.isdir(path):
        return
    # remove empty subfolders
    for root, dirs, files in os.walk(path, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    v.write(f"-----> {dir_path}")
                    count += 1
                except OSError as e:
                    v.write(f"Error removing {dir_path}: {e}")
    # remove empty root folder
    if remove_root and not os.listdir(path):
        try:
            os.rmdir(path)
            v.write(f"-----> {path}")
            count += 1
        except OSError as e:
            v.write(f"Error removing {path}: {e}")
