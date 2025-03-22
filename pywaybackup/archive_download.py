import gzip
import http.client
import os
import threading
import time
import urllib.parse
from datetime import datetime
from socket import timeout
from urllib.parse import urljoin

from importlib.metadata import version

import requests
from tqdm import tqdm

from pywaybackup.Arguments import Configuration as config
from pywaybackup.Exception import Exception as ex
from pywaybackup.SnapshotCollection import SnapshotCollection as sc
from pywaybackup.Verbosity import Message
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.db import Database
from pywaybackup.helper import check_nt, move_index, url_get_timestamp






def startup():
    try:
        vb.write(message=f"\n<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")
        
        if Database.QUERY_EXIST:
            vb.write(message=f"\nDOWNLOAD job exist - processed: {Database.QUERY_PROGRESS}\nResuming download... (to reset the job use '--reset')\n")

            for i in range(5, -1, -1):
                vb.write(message=f"\r{i}...")
                print("\033[F", end="")
                print("\033[K", end="")           

                time.sleep(1)

            #vb.write(message="\n")
    except KeyboardInterrupt:
        os._exit(1)





# create filelist
# timestamp format yyyyMMddhhmmss
def query_list(csvfile: str, cdxfile: str, queryrange: int, limit: int, start: int, end: int, explicit: bool, filter_filetype: list):
    
    def inject(cdxinject):
        if os.path.isfile(cdxinject):
            vb.write(message="\nCDX file found to inject...")
            return True
        else:
            vb.write(message="\nNo CDX file found to inject - querying snapshots...")
            return False
    
    def query(cdxfile, queryrange, limit, filter_filetype, start, end, explicit):
        vb.write(message="\nQuerying snapshots...")
        query_range = ""
        if not queryrange:
            if start: query_range = query_range + f"&from={start}"
            if end: query_range = query_range + f"&to={end}"
        else: 
            query_range = "&from=" + str(datetime.now().year - queryrange)
        
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
        
        limit = f"&limit={limit}" if limit else ""
        
        filter_filetype = f'&filter=original:.*\\.({"|".join(filter_filetype)})$' if filter_filetype else ''
        
        vb.write(message=f"-----> {cdx_url}")
        cdxQuery = f"https://web.archive.org/cdx/search/cdx?output=json&url={cdx_url}{query_range}&fl=timestamp,digest,mimetype,statuscode,original{limit}{filter_filetype}"
        
        try:
            cdxfile_IO = open(cdxfile, "w")
            with requests.get(cdxQuery, stream=True) as r:
                r.raise_for_status()
                with tqdm(unit='B', unit_scale=True, desc="download cdx".ljust(15)) as pbar:  # remove output: file=sys.stdout
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            pbar.update(len(chunk))
                            chunk = chunk.decode("utf-8")
                            cdxfile_IO.write(chunk)
            cdxfile_IO.close()
        except requests.exceptions.ConnectionError:
            vb.write(message="\nCONNECTION REFUSED -> could not query cdx server (max retries exceeded)\n")
            os.remove(cdxfile)
            os._exit(1)
        except Exception as e:
            ex.exception(message="\nUnexpected error while querying cdx server", e=e)
            os.remove(cdxfile)
            os._exit(1)
        
        return cdxfile
    
    cdxinject = inject(cdxfile)
    if not cdxinject:
        cdxfile = query(cdxfile, queryrange, limit, filter_filetype, start, end, explicit)
    
    sc.process_cdx(cdxfile, csvfile)
    
    vb.write(message="\nSnapshot calculation...")
    vb.write(message=f"-----> {'in CDX file'.ljust(18)}: {sc.CDX_TOTAL:,}")
    if sc.FILTER_DUPLICATES == 0 and sc.FILTER_MODE == 0:
        vb.write(message=f"-----> {'total removals'.ljust(18)}: {(sc.CDX_TOTAL - sc.SNAPSHOT_UNHANDLED - sc.FILTER_SKIP):,}")
    if sc.SNAPSHOT_FAULTY > 0: vb.write(message=f"-----> {'removed faulty'.ljust(18)}: {sc.SNAPSHOT_FAULTY}")
    if sc.FILTER_DUPLICATES > 0: vb.write(message=f"-----> {'removed duplicates'.ljust(18)}: {sc.FILTER_DUPLICATES:,}")
    if sc.FILTER_MODE > 0: vb.write(message=f"-----> {'removed versions'.ljust(18)}: {sc.FILTER_MODE:,}")
    if sc.FILTER_SKIP > 0: vb.write(message=f"-----> {'skipped existing'.ljust(18)}: {sc.FILTER_SKIP:,}")
    vb.write(message=f"\n-----> {'to utilize'.ljust(18)}: {sc.SNAPSHOT_UNHANDLED:,}")





def download_list(output, retry, no_redirect, delay, workers):
    #return
    if sc.SNAPSHOT_UNHANDLED == 0:
        vb.write(message="\nNothing to download")
        return
    vb.write(message="\nDownloading snapshots...",)
    vb.progress(progress=0, maxval=sc.SNAPSHOT_UNHANDLED)
    vb.progress(progress=sc.FILTER_SKIP)
    
    threads = []
    worker = 0
    for worker in range(workers):
        worker += 1
        vb.write(message=f"\n-----> Starting worker: {worker}")
        thread = threading.Thread(target=download_loop, args=(output, worker, retry, no_redirect, delay))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    successed = sc.count_totals(success=True)
    failed = sc.count_totals(fail=True)
    vb.write(message=f"\nFiles downloaded: {successed}")
    vb.write(message=f"Not downloaded: {failed}")





def download_loop(output, worker, retry, no_redirect, delay):
    try:
        db = Database()
        connection = http.client.HTTPSConnection("web.archive.org")
        
        while True:
            
            snapshot = sc.get_snapshot(db)
            if not snapshot: break
            SNAPSHOT_CURRENT = snapshot["rowid"]
            
            retry_attempt = 1
            retry_max_attempt = retry if retry > 0 else retry + 1
            status_message = Message()
            
            while retry_attempt <= retry_max_attempt: # retry as given by user
                status_message.store(message=f"\n-----> Worker: {worker} - Attempt: [{retry_attempt}/{retry_max_attempt}] Snapshot ID: [{SNAPSHOT_CURRENT}/{sc.SNAPSHOT_TOTAL}]")
                download_attempt = 1
                download_max_attempt = 3
                
                while download_attempt <= download_max_attempt: # reconnect as given by system
                    download_status = False
                    
                    try:
                        #status_message.store(message=f"attempt: {retry_attempt}, reconnect: {download_attempt}")
                        download_status = download(db, output, snapshot, connection, status_message, no_redirect)
                    
                    except (timeout, ConnectionRefusedError, ConnectionResetError, http.client.HTTPException, Exception) as e:
                        if isinstance(e, (timeout, ConnectionRefusedError, ConnectionResetError)):
                            if download_attempt < download_max_attempt:
                                download_attempt += 1  # try again 2x with same connection
                                vb.write(message=f"\n-----> Worker: {worker} - Attempt: [{retry_attempt}/{retry_max_attempt}] Snapshot ID: [{SNAPSHOT_CURRENT}/{sc.SNAPSHOT_TOTAL}] - {e.__class__.__name__} - requesting again in 50 seconds...")
                                time.sleep(50)
                                continue
                        elif isinstance(e, http.client.HTTPException):
                            if download_attempt < download_max_attempt:
                                download_attempt = download_max_attempt  # try again 1x with new connection
                                vb.write(message=f"\n-----> Worker: {worker} - Attempt: [{retry_attempt}/{retry_max_attempt}] Snapshot ID: [{SNAPSHOT_CURRENT}/{sc.SNAPSHOT_TOTAL}] - {e.__class__.__name__} - renewing connection in 15 seconds...")
                                time.sleep(15)
                                connection.close()
                                connection = http.client.HTTPSConnection("web.archive.org")
                                continue
                        else:
                            ex.exception(message=f"\n-----> Worker: {worker} - Attempt: [{retry_attempt}/{retry_max_attempt}] Snapshot ID: [{SNAPSHOT_CURRENT}/{sc.SNAPSHOT_TOTAL}] - EXCEPTION - {e}", e=e)
                            retry_attempt = retry_max_attempt
                            break

                    if download_status:
                        status_message.write()
                        vb.progress(1)
                        retry_attempt = retry_max_attempt
                        sc.SNAPSHOT_HANDLED += 1
                        break # break all loops because of successful download
                    
                    # depends on user - retries after timeout or proceed to next snapshot
                    if retry > 0:
                        status_message.store(status="FAILED", message="retry timeout: 15 seconds...")
                        status_message.write()
                        time.sleep(15)
                    else:
                        status_message.store(status="FAILED", message="no attempt left")
                        status_message.write()
                    sc.SNAPSHOT_HANDLED += 1
                    break # break all loops and do a user-defined retry
                
                retry_attempt += 1
                # if retry_attempt > retry_max_attempt:
                #     status_message.store(status="FAILED", message="Max retries exceeded")
                #     status_message.store(status="", type="URL", message=snapshot["url_archive"])
                #     status_message.write()
                #     vb.progress(1)
                #     sc.modify_snapshot(db, snapshot["rowid"], "response", "False")
                #     break
            
            if delay > 0:
                vb.write(message=f"\n-----> Worker: {worker} - Delay: {delay} seconds")
                time.sleep(delay)
    
    except Exception as e:
        ex.exception(f"\nWorker: {worker} - Exception", e)





def download(db, output, snapshot_entry, connection, status_message, no_redirect=False):
    download_url = snapshot_entry["url_archive"]
    encoded_download_url = urllib.parse.quote(download_url, safe=':/') # used for GET - otherwise always download_url
    headers = {"User-Agent": f"bitdruid-python-wayback-downloader/{version('pywaybackup')}"}
    response, response_data, response_status, response_status_message = download_response(connection, encoded_download_url, headers)
    sc.modify_snapshot(db, snapshot_entry["rowid"], "response", response_status)
    if not no_redirect and response_status == 302:
        status_message.store(status="REDIRECT", message=f"{response.status} - {response_status_message}")
        status_message.store(status="", type="FROM", message=download_url)
        for _ in range(5):                   
            response, response_data, response_status, response_status_message = download_response(connection, encoded_download_url, headers) 
            location = response.getheader("Location")
            if location:
                encoded_download_url = urllib.parse.quote(urljoin(download_url, location), safe=':/')
                status_message.store(status="", type="TO", message=location)
                sc.modify_snapshot(db, snapshot_entry["rowid"], "redirect_timestamp", url_get_timestamp(location))
                sc.modify_snapshot(db, snapshot_entry["rowid"], "redirect_url", download_url)
            else:
                break
    if response_status == 200:
        output_file = sc.create_output(download_url, snapshot_entry["timestamp"], output)
        output_path = os.path.dirname(output_file)
        
        # if output_file is too long for windows, skip download
        if check_nt() and len(output_file) > 255:
            status_message.store(status="PATH > 255", message=f"{response.status} - {response_status_message}")
            status_message.store(status="", type="URL", message=download_url)
            sc.entry_modify(snapshot_entry, "file", "PATH TOO LONG TO SAVE FILE")
            #status_message.write()
            raise Exception("Path too long to save file")
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
                status_message.store(status="SUCCESS", message=f"{response.status} - {response_status_message}")
        else:
            status_message.store(status="EXISTING", message=f"{response.status} - {response_status_message}")
        status_message.store(status="", type="URL", message=download_url)
        status_message.store(status="", type="FILE", message=output_file)
        sc.modify_snapshot(db, snapshot_entry["rowid"], "file", output_file)
        # if convert_links:
        #     convert.links(output_file, status_message)
        #status_message.write()
        return True
    else:
        status_message.store(status="UNEXPECTED", message=f"{response.status} - {response_status_message}")
        status_message.store(status="", type="URL", message=download_url)
        #status_message.write()
        return False

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
    302: "Redirect",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
    503: "Service Unavailable"
}

def parse_response_code(response_code: int):
    if response_code in RESPONSE_CODE_DICT:
        return RESPONSE_CODE_DICT[response_code]
    return "Unknown response code"
    
    
    
