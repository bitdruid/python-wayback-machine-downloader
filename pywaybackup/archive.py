#import threading
import requests
import os
import magic
import threading
import time
import http.client
from urllib.parse import urljoin
from datetime import datetime, timezone




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





def print_result(result_list):
    print("")
    if not result_list:
        print("No snapshots found")
    else:
        __import__('pprint').pprint(result_list)
        print(f"\n-----> {len(result_list)} snapshots listed")





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
        cdxResult_json = cdxResult.json()[1:] # first line is fieldlist, so remove it [timestamp, original
        cdxResult_list = [{"timestamp": snapshot[0], "url": snapshot[1]} for snapshot in cdxResult_json]
        if mode == "current":
            cdxResult_list = sorted(cdxResult_list, key=lambda k: k['timestamp'], reverse=True)
            cdxResult_list_filtered = []
            for snapshot in cdxResult_list:
                if snapshot["url"] not in [snapshot["url"] for snapshot in cdxResult_list_filtered]:
                    cdxResult_list_filtered.append(snapshot)
            cdxResult_list = cdxResult_list_filtered
        print(f"\n-----> {len(cdxResult_list)} snapshots found")
        return cdxResult_list
    except requests.exceptions.ConnectionError as e:
        print(f"\n-----> ERROR: could not query snapshots:\n{e}"); exit()






def split_url(url):
    """
    Split url into domain, subdir and file.
    If no file is present, the filename will be index.html
    """
    domain = url.split("//")[-1].split("/")[0]
    subdir = "/".join(url.split("//")[-1].split("/")[1:-1])
    filename = url.split("/")[-1] or "index.html"
    return domain, subdir, filename

def determine_url_filetype(url):
    """
    Determine filetype of the archive-url by looking at the file extension.
    """
    image = ["jpg", "jpeg", "png", "gif", "svg", "ico"]
    css = ["css"]
    js = ["js"]
    file_extension = url.split(".")[-1]
    if file_extension in image:
        urltype = "im_"
    elif file_extension in css:
        urltype = "cs_"
    elif file_extension in js:
        urltype = "js_"
    else:
        urltype = "id_"
    return urltype





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
# example url: https://www.google.com/
# example timestamp: 20190815104545
def download_prepare_list(cdxResult_list, output, retry, worker, mode):
    """
    Download a list of urls in format: [{"timestamp": "20190815104545", "url": "https://www.google.com/"}]
    """
    print("\nDownloading latest snapshots of each file...")
    download_list = []
    for snapshot in cdxResult_list:
        timestamp, url = snapshot["timestamp"], snapshot["url"]
        type = determine_url_filetype(url)
        download_url = f"http://web.archive.org/web/{timestamp}{type}/{url}"
        domain, subdir, filename = split_url(url)
        if mode == "current": download_dir = os.path.join(output, domain, subdir)
        if mode == "full": download_dir = os.path.join(output, domain, timestamp, subdir)
        download_list.append({"url": download_url, "filename": filename, "filepath": download_dir})
    if worker > 1:
        print(f"\n-----> Simultaneous downloads: {worker}")
        batch_size = len(download_list) // worker + 1
    else:
        batch_size = len(download_list)
    batch_list = [download_list[i:i + batch_size] for i in range(0, len(download_list), batch_size)]
    threads = []
    worker = 0
    for batch in batch_list:
        worker += 1
        thread = threading.Thread(target=download_url_list, args=(batch, worker, retry))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def download_url_list(url_list, worker, retry):
    failed_urls = []
    connection = http.client.HTTPSConnection("web.archive.org")
    for url_entry in url_list:
        status = f"\n-----> Snapshot [{url_list.index(url_entry) + 1}/{len(url_list)}] Worker: {worker}"
        download_url, download_filename, download_filepath = url_entry["url"], url_entry["filename"], url_entry["filepath"]
        download_status=download_url_entry(download_url, download_filename, download_filepath, connection, status)
        if download_status != True: failed_urls.append({"url": download_url, "filename": download_filename, "filepath": download_filepath})
    if retry:
        download_retry(failed_urls, retry, connection)
    connection.close()

def download_retry(failed_urls, retry, connection):
    """
    Retry failed downloads.
    failed_urls: [{"url": download_url, "filename": download_filename, "filepath": download_filepath}]
    retry: int or None
    """
    attempt = 1
    max_attempt = retry if retry is not True else "no-limit"
    while failed_urls and (attempt <= retry or retry is True):
        print("\n-----> Retrying...")
        retry_urls = []
        for failed_entry in failed_urls:
            status = f"\n-----> RETRY attempt: [{attempt}/{max_attempt}] Snapshot [{failed_urls.index(failed_entry) + 1}/{len(failed_urls)}]"
            download_url, download_filename, download_filepath = failed_entry["url"], failed_entry["filename"], failed_entry["filepath"]
            retry_status=download_url_entry(download_url, download_filename, download_filepath, connection, status)
            if retry_status != bool(1):
                retry_urls.append({"url": download_url, "filename": download_filename, "filepath": download_filepath})
        failed_urls = retry_urls
        print(f"\n-----> Fail downloads: {len(failed_urls)}")
        if retry: attempt += 1

def download_url_entry(url, filename, filepath, connection, status_message):
    """
    Download a single URL and save it to the specified filepath.

    Args:
        url (str): The URL to download.
        filename (str): The name of the file to save.
        filepath (str): The path where the file will be saved.
        connection (http.client.HTTPConnection): The HTTP connection object.
        status (str): The current status message.

    Returns:
        bool: True if the download is successful, False otherwise.
    """
    output = os.path.join(filepath, filename)
    max_retries = 2
    sleep_time = 45
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
    for i in range(max_retries):
        try:
            connection.request("GET", url, headers=headers)
            response = connection.getresponse()
            response_data = response.read()
            response_status = response.status
            if response_status == 302:
                status_message = f"{status_message}\n" + \
                    f"REDIRECT   -> HTTP: {response.status}"
                while response_status == 302:
                    connection.request("GET", url, headers=headers)
                    response = connection.getresponse()
                    response_data = response.read()
                    response_status = response.status
                    location = response.getheader("Location")
                    if location:
                        status_message = f"{status_message}\n" + \
                            f"           -> URL: {location}"
                        location = urljoin(url, location)
                        url = location
                    else:
                        break
            if response_status != 404:
                os.makedirs(filepath, exist_ok=True)
                with open(output, 'wb') as file:
                    file.write(response_data)
            if response_status == 200:
                status_message = f"{status_message}\n" + \
                    f"SUCCESS    -> HTTP: {response.status}\n" + \
                    f"           -> URL: {url}\n" + \
                    f"           -> FILE: {output}"
                print(status_message)
            elif response_status == 404:
                status_message = f"{status_message}\n" + \
                    f"NOT FOUND  -> HTTP: {response.status}\n" + \
                    f"           -> URL: {url}"
            else:
                status_message = f"{status_message}\n" + \
                    f"UNEXPECTED -> HTTP: {response.status}\n" + \
                    f"           -> URL: {url}\n" + \
                    f"           -> FILE: {output}"
            return True
        except ConnectionRefusedError as e:
            status_message = f"{status_message}\n" + \
                f"REFUSED  -> ({i+1}/{max_retries}), reconnect in {sleep_time} seconds...\n" + \
                f"         -> {e}"
            print(status_message)
            time.sleep(sleep_time)
        except http.client.HTTPException as e:
            status_message = f"{status_message}\n" + \
                f"EXCEPTION -> ({i+1}/{max_retries}), append to failed_urls: {url}\n" + \
                f"          -> {e}"
            print(status_message)
            return False
    print(f"FAILED  -> download, append to failed_urls: {url}")
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