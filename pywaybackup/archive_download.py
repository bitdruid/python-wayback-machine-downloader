import gzip
import http.client
import os
import threading
import time
import urllib.parse
from http import HTTPStatus
from importlib.metadata import version
from socket import timeout
from urllib.parse import urljoin

from pywaybackup.Exception import Exception as ex
from pywaybackup.helper import check_nt, move_index, url_get_timestamp
from pywaybackup.SnapshotCollection import SnapshotCollection
from pywaybackup.Verbosity import Verbosity as vb
from pywaybackup.Worker import Worker


class DownloadContext:
    def __init__(self, snapshot_url: str):
        self.snapshot_url = snapshot_url
        self.headers = {"User-Agent": f"bitdruid-python-wayback-downloader/{version('pywaybackup')}"}
        self.encoded_download_url = self.encode_url(snapshot_url)
        self.output_file = None
        self.output_path = None
        self.response = None
        self.response_data = None
        self.response_status = None

    def encode_url(self, url: str) -> str:
        return urllib.parse.quote(url, safe=":/")

    @property
    def response_status_message(self):
        return HTTPStatus(self.response_status).phrase if self.response_status else "No Status"


class DownloadArchive:
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
        self._spawn_workers()

    def _spawn_workers(self):
        vb.write(
            content="\nDownloading snapshots...",
        )
        vb.progress(progress=0, maxval=self.sc._snapshot_total)
        vb.progress(progress=self.sc._filter_skip)

        threads = []
        for i in range(self.workers):
            worker = Worker(id=i + 1, output=self.output, mode=self.mode)
            vb.write(verbose=True, content=f"\n-----> Starting Worker: {worker.id}")
            thread = threading.Thread(target=self._download_loop, args=(worker,), daemon=True)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def _download_loop(self, worker: Worker):
        try:
            worker.init()

            while True:
                worker.assign_snapshot(total_amount=self.sc._snapshot_total)
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
                            download_status = self._download(worker=worker)

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

    def _download(self, worker: Worker):
        context = DownloadContext(snapshot_url=worker.snapshot.url_archive)

        self.__download_response(context=context, worker=worker)
        worker.snapshot.response_status = context.response_status

        if not self.no_redirect and context.response_status == 302:
            self.__handle_redirect(context=context, worker=worker)

        if context.response_status == 200:
            context.output_file = worker.snapshot.create_output()
            context.output_path = os.path.dirname(context.output_file)

            # if output_file is too long for windows, skip download
            try:
                self.__dl_nt_path_too_long(context, worker)
            except Exception:
                return False

            # create path or move file if path exists as file or file exists as directory
            self.__dl_move_path_or_file(context)

            # download file if not existing
            if not os.path.isfile(context.output_file):
                with open(context.output_file, "wb") as file:
                    if context.response.getheader("Content-Encoding") == "gzip":
                        context.response_data = gzip.decompress(context.response_data)
                    file.write(context.response_data)

                # check if file is downloaded
                if os.path.isfile(context.output_file):
                    return self.__dl_result(context, worker, "SUCCESS")
            else:
                return self.__dl_result(context, worker, "EXISTING")
        else:
            return self.__dl_fail(context, worker)

    def __handle_redirect(self, context: DownloadContext, worker: Worker) -> None:
        worker.message.store(verbose=True, result="REDIRECT", content=f"{context.response_status} {context.response_status_message}")
        worker.message.store(verbose=True, result="", info="FROM", content=context.snapshot_url)
        for _ in range(5):
            self.__download_response(context=context, worker=worker)
            location = context.response.getheader("Location")
            if location:
                context.encoded_download_url = context.encode_url(urljoin(context.snapshot_url, location))
                worker.message.store(verbose=True, result="", info="TO", content=location)
                worker.snapshot.redirect_timestamp = url_get_timestamp(location)
                worker.snapshot.redirect_url = context.snapshot_url
            else:
                break

    def __dl_nt_path_too_long(self, context: DownloadContext, worker: Worker) -> None:
        if check_nt() and len(context.output_file) > 255:
            worker.message.store(verbose=None, result="CANT SAVE", content="NT PATH TOO LONG")
            worker.message.store(verbose=True, result="", info="URL", content=context.snapshot_url)
            worker.file = "NT PATH TOO LONG TO SAVE FILE"
            raise Exception("NT Path too long to save file")

    def __dl_move_path_or_file(self, context: DownloadContext) -> None:
        # case if output_path is a file, move file to temporary name, create output_path and move file into output_path
        if os.path.isfile(context.output_path):
            move_index(existpath=context.output_path)
        else:
            os.makedirs(context.output_path, exist_ok=True)
        # case if output_file is a directory, create file as index.html in this directory
        if os.path.isdir(context.output_file):
            context.output_file = move_index(existfile=context.output_file, filebuffer=context.response_data)

    def __dl_result(self, context: DownloadContext, worker: Worker, result: str) -> bool:
        worker.message.store(verbose=True, result=result, content=f"{context.response_status} {context.response_status_message}")
        worker.message.store(verbose=False, result=result)
        worker.message.store(verbose=True, result="", info="URL", content=context.snapshot_url)
        worker.message.store(verbose=True, result="", info="FILE", content=context.output_file)
        worker.snapshot.file = context.output_file
        return True

    def __dl_fail(self, context: DownloadContext, worker: Worker) -> bool:
        worker.message.store(verbose=None, result="UNKNOWN", content=f"{context.response_status} {context.response_status_message}")
        worker.message.store(verbose=True, result="", info="URL", content=context.snapshot_url)
        return False

    def __download_response(self, context: DownloadContext, worker: Worker) -> None:
        worker.connection.request("GET", context.encoded_download_url, headers=context.headers)
        context.response = worker.connection.getresponse()
        context.response_data = context.response.read()
        context.response_status = context.response.status
