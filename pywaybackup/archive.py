#import threading
import requests
import os
import magic
import threading
import time
import http.client
from urllib.parse import urljoin
from datetime import datetime, timezone

import pywaybackup.SnapshotCollection as sc




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
    print("\nSaving page to the Wayback Machine...")
    connection = http.client.HTTPSConnection("web.archive.org")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    connection.request("GET", f"https://web.archive.org/save/{url}", headers=headers)
    print("\n-----> Request sent")
    response = connection.getresponse()
    response_status = response.status

    if response_status == 302:
        location = response.getheader("Location")
        print("\n-----> Response: 302 (redirect to snapshot)")
        snapshot_timestamp = datetime.strptime(location.split('/web/')[1].split('/')[0], '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        timestamp_difference = (datetime.strptime(current_timestamp, '%Y-%m-%d %H:%M:%S') - datetime.strptime(snapshot_timestamp, '%Y-%m-%d %H:%M:%S')).seconds / 60
        timestamp_difference = int(round(timestamp_difference, 0))

        if timestamp_difference < 1:
            print("\n-----> New snapshot created")
        elif timestamp_difference > 1:
            print(f"\n-----> Snapshot already exists. (1 hour limit) - wait for {60 - timestamp_difference} minutes")
            print(f"TIMESTAMP SNAPSHOT: {snapshot_timestamp}")
            print(f"TIMESTAMP REQUEST : {current_timestamp}")
            print(f"\nLAST SNAPSHOT BACK: {timestamp_difference} minutes")

        print(f"\nURL: {location}")

    elif response_status == 404:
        print("\n-----> Response: 404 (not found)")
        print(f"\nFAILED -> URL: {url}")
    else:
        print("\n-----> Response: unexpected")
        print(f"\nFAILED -> URL: {url}")

    connection.close()





def print_result(snapshots):
    print("")
    if not snapshots:
        print("No snapshots found")
    else:
        __import__('pprint').pprint(snapshots.CDX_RESULT_LIST)
        print(f"\n-----> {snapshots.count_list()} snapshots listed")





# create filelist
def query_list(url: str, range: int, mode: str):
    try:
        print("\nQuerying snapshots...")
        if range:
            range = datetime.now().year - range
            range = "&from=" + str(range)
        else:
            range = ""
        cdxQuery = f"https://web.archive.org/cdx/search/xd?output=json&url=*.{url}/*{range}&fl=timestamp,original&filter=!statuscode:200"
        cdxResult = requests.get(cdxQuery)
        if cdxResult.status_code != 200: print(f"\n-----> ERROR: could not query snapshots, status code: {cdxResult.status_code}"); exit()
        snapshots = sc.SnapshotCollection(cdxResult)
        if mode == "current": snapshots.create_current()
        print(f"\n-----> {snapshots.count_list()} snapshots found")
        return snapshots
    except requests.exceptions.ConnectionError as e:
        print(f"\n-----> ERROR: could not query snapshots:\n{e}"); exit()






def remove_empty_folders(path, remove_root=True):
    print("")
    print("Removing empty output folders...")
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
                    print(f"-----> {dir_path}")
                    count += 1
                except OSError as e:
                    print(f"Error removing {dir_path}: {e}")
    # remove empty root folder
    if remove_root and not os.listdir(path):
        try:
            os.rmdir(path)
            print(f"-----> {path}")
            count += 1
        except OSError as e:
            print(f"Error removing {path}: {e}")
    if count == 0:
        print("No empty folders found")





# example download: http://web.archive.org/web/20190815104545id_/https://www.google.com/
def download_prepare_list(snapshots, output, retry, worker):
    """
    Download a list of urls in format: [{"timestamp": "20190815104545", "url": "https://www.google.com/"}]
    """
    print("\nDownloading latest snapshots of each file...")
    snapshots.create_collection(output)
    download_list = snapshots.CDX_RESULT_COLLECTION
    if worker > 1:
        print(f"\n-----> Simultaneous downloads: {worker}")
        batch_size = snapshots.count_collection() // worker + 1
    else:
        batch_size = snapshots.count_collection()
    batch_list = [download_list[i:i + batch_size] for i in range(0, len(download_list), batch_size)]
    threads = []
    worker = 0
    for batch in batch_list:
        worker += 1
        thread = threading.Thread(target=download_url_list, args=(snapshots, batch, worker, retry))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    failed_urls = len([url for url in snapshots.CDX_RESULT_COLLECTION if url["success"] == False])
    if failed_urls: print(f"\n-----> Failed downloads: {len(failed_urls)}")

def download_url_list(snapshots, url_list, worker, retry, attempt=1, connection=None):
    max_attempt = retry
    failed_urls = []
    if not connection:
        connection = http.client.HTTPSConnection("web.archive.org")
    if attempt > max_attempt: 
        connection.close()
        print(f"\n-----> Worker: {worker} - Failed downloads: {len(url_list)}")
        return
    else:
        for url_entry in url_list:
            status = f"\n-----> Attempt: [{attempt}/{max_attempt}] Snapshot [{url_list.index(url_entry) + 1}/{len(url_list)}] Worker: {worker}"
            download_status=download_url_entry(url_entry, connection, status)
            if download_status != True: failed_urls.append(url_entry); url_entry["retry"] += 1
            if download_status == True: snapshots.set_value(url_entry["index"], "success", True)
        attempt += 1
    if failed_urls: download_url_list(snapshots, failed_urls, worker, retry, attempt, connection)

def download_url_entry(download_entry, connection, status_message):
    """
    Download a single URL and save it to the specified filepath.

    Args:
        download_url (str): The URL to download.
        download_file (str): The name of the file to save.
        connection (http.client.HTTPConnection): The HTTP connection object.
        status_message (str): The current status message.

    Returns:
        bool: True if the download is successful, False otherwise.
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
            if response_status != 404:
                os.makedirs(os.path.dirname(download_file), exist_ok=True)
                with open(download_file, 'wb') as file:
                    file.write(response_data)
            if response_status == 200:
                status_message = f"{status_message}\n" + \
                    f"SUCCESS    -> HTTP: {response.status}\n" + \
                    f"           -> URL: {download_url}\n" + \
                    f"           -> FILE: {download_file}"
            elif response_status == 404:
                status_message = f"{status_message}\n" + \
                    f"NOT FOUND  -> HTTP: {response.status}\n" + \
                    f"           -> URL: {download_url}"
            else:
                status_message = f"{status_message}\n" + \
                    f"UNEXPECTED -> HTTP: {response.status}\n" + \
                    f"           -> URL: {download_url}\n" + \
                    f"           -> FILE: {download_file}"
            print(status_message)
            return True
        except ConnectionRefusedError as e:
            status_message = f"{status_message}\n" + \
                f"REFUSED  -> ({i+1}/{max_retries}), reconnect in {sleep_time} seconds...\n" + \
                f"         -> {e}"
            print(status_message)
            time.sleep(sleep_time)
        except http.client.HTTPException as e:
            status_message = f"{status_message}\n" + \
                f"EXCEPTION -> ({i+1}/{max_retries}), append to failed_urls: {download_url}\n" + \
                f"          -> {e}"
            print(status_message)
            return False
    print(f"FAILED  -> download, append to failed_urls: {download_url}")
    return False


# scan output folder and guess mimetype for each file
# if add file extension if not present
# def detect_filetype(filepath):
#     print("\nDetecting filetypes...")
#     path = Path(filepath)
#     if not path.is_dir():
#         print(f"\n-----> ERROR: {filepath} is not a directory"); return
#     for file_path in path.rglob("*"):
#         if file_path.is_file():
#             file_extension = file_path.suffix
#             if not file_extension:
#                 mime_type = magic.from_file(str(file_path), mime=True)
#                 file_extension = mime_type.split("/")[-1]
#                 new_file_path = file_path.with_suffix('.' + file_extension)
#                 file_path.rename(new_file_path)
#                 print(f"NO EXT -> {file_path}")
#                 print(f"   NEW -> {new_file_path}")