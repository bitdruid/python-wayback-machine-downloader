import gzip
import http.client
import os
import sys
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
from pywaybackup.Worker import Worker
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.db import Database
from pywaybackup.helper import check_nt, move_index, url_get_timestamp





def startup():
    try:
        vb.write(content=f"\n<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")
        
        if Database.QUERY_EXIST:
            vb.write(content=f"\nDOWNLOAD job exist - processed: {Database.QUERY_PROGRESS}\nResuming download... (to reset the job use '--reset')")

            for i in range(5, -1, -1):
                vb.write(content=f"\r{i}...")
                print("\033[F", end="")
                print("\033[K", end="")           

                time.sleep(1)

    except KeyboardInterrupt:
        os._exit(1)





def query_list(csvfile: str, cdxfile: str,queryrange: int,limit: int,start: int,end: int,explicit: bool,filter_filetype: list,filter_statuscode: list):
    
    def inject(cdxinject: str) -> bool:
        if os.path.isfile(cdxinject):
            vb.write(content="\nExisting CDX file found")
            return True
        else:
            vb.write(
                verbose=None,
                content="\nQuerying snapshots...",
            )
            return False
        
    def create_query(queryrange: int, limit: int, filter_filetype: list, filter_statuscode: list, start: int, end: int, explicit: bool) -> str:
        if queryrange:
            query_range = f"&from={datetime.now().year - queryrange}"
        else:
            query_range = ""
            if start:
                query_range += f"&from={start}"
            if end:
                query_range += f"&to={end}"

        cdx_url = config.domain or ""

        if config.subdir:
            cdx_url += f"/{config.subdir}"
        if config.filename:
            cdx_url += f"/{config.filename}"
        if not explicit:
            cdx_url += "/*"

        limit = f"&limit={limit}" if limit else ""

        filter_statuscode = (f"&filter=statuscode:({'|'.join(filter_statuscode)})$" if filter_statuscode else "")
        filter_filetype = (f"&filter=original:.*\\.({'|'.join(filter_filetype)})$" if filter_filetype else "")

        cdxquery = f"https://web.archive.org/cdx/search/cdx?output=json&url={cdx_url}{query_range}&fl=timestamp,digest,mimetype,statuscode,original{limit}{filter_filetype}{filter_statuscode}"

        return cdxquery
    
    def run_query(cdxfile: str, cdxquery: str) -> None:
        try:
            with open(cdxfile, "w", encoding="utf-8") as cdxfile_io:
                with requests.get(cdxquery, stream=True) as r:
                    r.raise_for_status()
                    with tqdm(unit="B", unit_scale=True, desc="download cdx".ljust(15)) as pbar:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                pbar.update(len(chunk))
                                cdxfile_io.write(chunk.decode("utf-8"))

        except requests.exceptions.ConnectionError:
            vb.write(content="\nCONNECTION REFUSED -> could not query cdx server (max retries exceeded)")
            os.remove(cdxfile)
            sys.exit(1)
        except Exception as e:
            ex.exception(message="\nUnknown error while querying cdx server", e=e)
            os.remove(cdxfile)
            sys.exit(1)

        return cdxfile

    cdxinject = inject(cdxfile)
    if not cdxinject:
        cdxquery = create_query(queryrange, limit, filter_filetype, filter_statuscode, start, end, explicit)
        cdxfile =  run_query(cdxfile, cdxquery)
    sc.process_cdx(cdxfile, csvfile)





def download_list(output, retry, no_redirect, delay, workers):
    if sc.SNAPSHOT_UNHANDLED == 0:
        vb.write(content="\nNothing to download")
        return
    
    vb.write(content="\nDownloading snapshots...",)
    vb.progress(progress=0, maxval=sc.SNAPSHOT_TOTAL)
    vb.progress(progress=sc.FILTER_SKIP)
    
    threads = []
    for i in range(workers):
        worker = Worker(id=i + 1)
        vb.write(verbose=True, content=f"\n-----> Starting Worker: {worker.id}")
        thread = threading.Thread(target=download_loop, args=(worker, output, retry, no_redirect, delay))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    successed = sc.count_totals(success=True)
    failed = sc.count_totals(fail=True)
    vb.write(content=f"\nFiles downloaded: {successed}")
    vb.write(content=f"Not downloaded: {failed}")





def download_loop(worker, output, retry, no_redirect, delay):
    try:
        
        worker.init()

        while True:
            
            worker.assign_snapshot()
            if not worker.snapshot:
                break
            
            retry_max_attempt = max(retry, 1)
            
            while worker.attempt <= retry_max_attempt: # retry as given by user

                worker.message.store(verbose=True, content=f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.counter}/{sc.SNAPSHOT_TOTAL}]")
                download_attempt = 1
                download_max_attempt = 3
                
                while download_attempt <= download_max_attempt: # reconnect as given by system
                    download_status = False
                    
                    try:
                        download_status = download(output, no_redirect, worker=worker)
                    
                    except (timeout, ConnectionRefusedError, ConnectionResetError, http.client.HTTPException, Exception) as e:

                        if isinstance(e, (timeout, ConnectionRefusedError, ConnectionResetError)):
                            if download_attempt < download_max_attempt:
                                download_attempt += 1  # try again 2x with same connection
                                vb.write(
                                    verbose=True,
                                    content=f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.counter}/{sc.SNAPSHOT_TOTAL}] - {e.__class__.__name__} - requesting again in 50 seconds...",
                                )
                                vb.write(
                                    verbose=False,
                                    content=f"Worker: {worker.id} - Snapshot {worker.counter}/{sc.SNAPSHOT_TOTAL} - requesting again in 50 seconds...",
                                )
                                time.sleep(50)
                                continue

                        elif isinstance(e, http.client.HTTPException):

                            if download_attempt < download_max_attempt:
                                download_attempt = download_max_attempt  # try again 1x with new connection
                                vb.write(
                                    verbose=True,
                                    content=f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.counter}/{sc.SNAPSHOT_TOTAL}] - {e.__class__.__name__} - renewing connection in 15 seconds...",
                                )
                                vb.write(
                                    verbose=False,
                                    content=f"Worker: {worker.id} - Snapshot {worker.counter}/{sc.SNAPSHOT_TOTAL} - renewing connection in 15 seconds...",
                                )
                                time.sleep(15)
                                worker.refresh_connection()
                                continue
                        else:
                            ex.exception(f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.counter}/{sc.SNAPSHOT_TOTAL}] - EXCEPTION - {e}", e=e)
                            worker.attempt = retry_max_attempt
                            break

                    if download_status:
                        worker.message.write()
                        worker.attempt = retry_max_attempt
                        sc.SNAPSHOT_HANDLED += 1
                        vb.progress(1)
                        break # break all loops because of successful download
                    
                    # depends on user - retries after timeout or proceed to next snapshot
                    if retry > 0:
                        worker.message.store(verbose=True, result="FAILED", content="retry timeout: 15 seconds...")
                        worker.message.write()
                        time.sleep(15)
                    else:
                        worker.message.store(verbose=None, result="FAILED", content="no attempt left")
                        worker.message.write()
                    sc.SNAPSHOT_HANDLED += 1
                    break # break all loops and do a user-defined retry
                
                worker.attempt += 1
            
            if delay > 0:
                vb.write(verbose=True, content=f"\n-----> Worker: {worker.id} - Delay: {delay} seconds")
                time.sleep(delay)
    
    except Exception as e:
        ex.exception(f"\nWorker: {worker.id} - Exception", e)





def download(output, no_redirect=False, worker=None):
    download_url = worker.url_archive
    encoded_download_url = urllib.parse.quote(download_url, safe=':/') # used for GET - otherwise always download_url
    headers = {"User-Agent": f"bitdruid-python-wayback-downloader/{version('pywaybackup')}"}
    response, response_data, response_status, response_status_message = download_response(worker.connection, encoded_download_url, headers)
    worker.response = response_status

    if not no_redirect and response_status == 302:
        worker.message.store(verbose=True, result="REDIRECT", content=f"{response_status} {response_status_message}")
        worker.message.store(verbose=True, result="", info="FROM", content=download_url)
        for _ in range(5):                   
            response, response_data, response_status, response_status_message = download_response(worker.connection, encoded_download_url, headers) 
            location = response.getheader("Location")
            if location:
                encoded_download_url = urllib.parse.quote(urljoin(download_url, location), safe=':/')
                worker.message.store(verbose=True, result="", info="TO", content=location)
                worker.redirect_timestamp = url_get_timestamp(location)
                worker.redirect_url = download_url
            else:
                break

    if response_status == 200:
        output_file = sc.create_output(download_url, worker.timestamp, output)
        output_path = os.path.dirname(output_file)
        
        # if output_file is too long for windows, skip download
        if check_nt() and len(output_file) > 255:
            worker.message.store(verbose=None, result="CANT SAVE", content="NT PATH TOO LONG")
            worker.message.store(verbose=True, result="", info="URL", content=download_url)
            worker.file = "NT PATH TOO LONG TO SAVE FILE"
            raise Exception("NT Path too long to save file")
        
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
                worker.message.store(verbose=True, result="SUCCESS", content=f"{response_status} {response_status_message}")
                worker.message.store(verbose=False, result="SUCCESS")
        else:
            worker.message.store(verbose=True, result="EXISTING", content=f"{response_status} {response_status_message}")
            worker.message.store(verbose=False, result="EXISTING")
        worker.message.store(verbose=True, result="", info="URL", content=download_url)
        worker.message.store(verbose=True, result="", info="FILE", content=output_file)
        worker.file = output_file
        # if convert_links:
        #     convert.links(output_file, worker.message)
        #worker.message.write()
        return True
    else:
        worker.message.store(verbose=None, result="UNKNOWN", content=f"{response_status} {response_status_message}")
        worker.message.store(verbose=True, result="", info="URL", content=download_url)
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
    
    
    
