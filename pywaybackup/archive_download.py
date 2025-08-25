import gzip
import http.client
import os
import threading
import time
import urllib.parse
from socket import timeout
from urllib.parse import urljoin

from importlib.metadata import version

from pywaybackup.Exception import Exception as ex
from pywaybackup.SnapshotCollection import SnapshotCollection
from pywaybackup.Worker import Worker
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.helper import check_nt, move_index, url_get_timestamp


class Downloader:
    def __init__(self, mode: str, output: str, retry: int, no_redirect: bool, delay: int, workers: int):
        self.mode = mode
        self.output = output
        self.retry = retry
        self.no_redirect = no_redirect
        self.delay = delay
        self.workers = workers
        self.no_redirect = no_redirect
        self.sc = None

    def run(self, SnapshotCollection: SnapshotCollection):
        self.sc = SnapshotCollection
        if self.sc._snapshot_unhandled == 0:
            vb.write(content="\nNothing to download")
            return
        self.spawn_workers()

    def spawn_workers(self):
        vb.write(
            content="\nDownloading snapshots...",
        )
        vb.progress(progress=0, maxval=self.sc._snapshot_total)
        vb.progress(progress=self.sc._filter_skip)

        threads = []
        for i in range(self.workers):
            worker = Worker(id=i + 1, output=self.output, mode=self.mode)
            vb.write(verbose=True, content=f"\n-----> Starting Worker: {worker.id}")
            thread = threading.Thread(target=self.download_loop, args=(worker,), daemon=True)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def download_loop(self, worker: Worker):
        try:
            worker.init()

            while True:
                worker.assign_snapshot()
                if not worker.snapshot:
                    break

                retry_max_attempt = max(self.retry, 1)

                while worker.attempt <= retry_max_attempt:  # retry as given by user
                    worker.message.store(
                        verbose=True,
                        content=f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.snapshot.counter}/{self.sc._snapshot_total}]",
                    )
                    download_attempt = 1
                    download_max_attempt = 3

                    while download_attempt <= download_max_attempt:  # reconnect as given by system
                        download_status = False

                        try:
                            download_status = self.download(worker=worker)

                        except (timeout, ConnectionRefusedError, ConnectionResetError, http.client.HTTPException, Exception) as e:
                            if isinstance(e, (timeout, ConnectionRefusedError, ConnectionResetError)):
                                if download_attempt < download_max_attempt:
                                    download_attempt += 1  # try again 2x with same connection
                                    vb.write(
                                        verbose=True,
                                        content=f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.snapshot.counter}/{self.sc._snapshot_total}] - {e.__class__.__name__} - requesting again in 50 seconds...",
                                    )
                                    vb.write(
                                        verbose=False,
                                        content=f"Worker: {worker.id} - Snapshot {worker.snapshot.counter}/{self.sc._snapshot_total} - requesting again in 50 seconds...",
                                    )
                                    time.sleep(50)
                                    continue

                            elif isinstance(e, http.client.HTTPException):
                                if download_attempt < download_max_attempt:
                                    download_attempt = download_max_attempt  # try again 1x with new connection
                                    vb.write(
                                        verbose=True,
                                        content=f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.snapshot.counter}/{self.sc._snapshot_total}] - {e.__class__.__name__} - renewing connection in 15 seconds...",
                                    )
                                    vb.write(
                                        verbose=False,
                                        content=f"Worker: {worker.id} - Snapshot {worker.snapshot.counter}/{self.sc._snapshot_total} - renewing connection in 15 seconds...",
                                    )
                                    time.sleep(15)
                                    worker.refresh_connection()
                                    continue
                            else:
                                ex.exception(
                                    f"\n-----> Worker: {worker.id} - Attempt: [{worker.attempt}/{retry_max_attempt}] Snapshot ID: [{worker.snapshot.counter}/{self.sc._snapshot_total}] - EXCEPTION - {e}",
                                    e=e,
                                )
                                worker.attempt = retry_max_attempt
                                break

                        if download_status:
                            worker.message.write()
                            worker.attempt = retry_max_attempt
                            self.sc._snapshot_handled += 1
                            vb.progress(1)
                            break  # break all loops because of successful download

                        # depends on user - retries after timeout or proceed to next snapshot
                        if self.retry > 0:
                            worker.message.store(verbose=True, result="FAILED", content="retry timeout: 15 seconds...")
                            worker.message.write()
                            time.sleep(15)
                        else:
                            worker.message.store(verbose=None, result="FAILED", content="no attempt left")
                            worker.message.write()
                        self.sc._snapshot_handled += 1
                        break  # break all loops and do a user-defined retry

                    worker.attempt += 1

                if self.delay > 0:
                    vb.write(verbose=True, content=f"\n-----> Worker: {worker.id} - Delay: {self.delay} seconds")
                    time.sleep(self.delay)

        except Exception as e:
            ex.exception(f"\nWorker: {worker.id} - Exception", e)

    def download(self, worker: Worker):
        download_url = worker.snapshot.url_archive
        encoded_download_url = urllib.parse.quote(download_url, safe=":/")  # used for GET - otherwise always download_url
        headers = {"User-Agent": f"bitdruid-python-wayback-downloader/{version('pywaybackup')}"}
        response, response_data, response_status, response_status_message = self.download_response(
            worker.connection, encoded_download_url, headers
        )
        worker.snapshot.response = response_status

        if not self.no_redirect and response_status == 302:
            worker.message.store(verbose=True, result="REDIRECT", content=f"{response_status} {response_status_message}")
            worker.message.store(verbose=True, result="", info="FROM", content=download_url)
            for _ in range(5):
                response, response_data, response_status, response_status_message = self.download_response(
                    worker.connection, encoded_download_url, headers
                )
                location = response.getheader("Location")
                if location:
                    encoded_download_url = urllib.parse.quote(urljoin(download_url, location), safe=":/")
                    worker.message.store(verbose=True, result="", info="TO", content=location)
                    worker.snapshot.redirect_timestamp = url_get_timestamp(location)
                    worker.snapshot.redirect_url = download_url
                else:
                    break

        if response_status == 200:
            output_file = worker.snapshot.create_output()
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
                with open(output_file, "wb") as file:
                    if response.getheader("Content-Encoding") == "gzip":
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
            worker.snapshot.file = output_file
            # if convert_links:
            #     convert.links(output_file, worker.message)
            # worker.message.write()
            return True
        else:
            worker.message.store(verbose=None, result="UNKNOWN", content=f"{response_status} {response_status_message}")
            worker.message.store(verbose=True, result="", info="URL", content=download_url)
            return False

    def download_response(self, connection, encoded_download_url, headers):
        connection.request("GET", encoded_download_url, headers=headers)
        response = connection.getresponse()
        response_data = response.read()
        response_status = response.status
        response_status_message = self.parse_response_code(response_status)
        return response, response_data, response_status, response_status_message

    def parse_response_code(self, response_code: int):
        RESPONSE_CODE_DICT = {
            200: "OK",
            301: "Moved Permanently",
            302: "Redirect",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
            503: "Service Unavailable",
        }

        if response_code in RESPONSE_CODE_DICT:
            return RESPONSE_CODE_DICT[response_code]
        return "Unknown response code"
