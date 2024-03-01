from urllib.parse import urlparse
import os

class SnapshotCollection:

    CDX_RESULT_JSON = []
    CDX_RESULT_LIST = []
    CDX_RESULT_COLLECTION = []

    MODE_CURRENT = 0

    def __init__(self, cdxResult=None, cdxCollection=None):
        if cdxResult:
            self.CDX_RESULT_JSON = cdxResult.json()[1:]
            self.CDX_RESULT_LIST = [{"timestamp": snapshot[0], "url": snapshot[1]} for snapshot in self.CDX_RESULT_JSON]
            self.CDX_RESULT_LIST = sorted(self.CDX_RESULT_LIST, key=lambda k: k['timestamp'], reverse=True)
        if cdxCollection:
            self.CDX_RESULT_COLLECTION = cdxCollection

    def create_current(self):
        self.MODE_CURRENT = 1
        self.CDX_RESULT_LIST = sorted(self.CDX_RESULT_LIST, key=lambda k: k['timestamp'], reverse=True)
        cdxResult_list_filtered = []
        for snapshot in self.CDX_RESULT_LIST:
            if snapshot["url"] not in [snapshot["url"] for snapshot in cdxResult_list_filtered]:
                cdxResult_list_filtered.append(snapshot)
        self.CDX_RESULT_LIST = cdxResult_list_filtered

    def create_collection(self, output):
        for snapshot in self.CDX_RESULT_LIST:
            timestamp, url = snapshot["timestamp"], snapshot["url"]
            url_type = self.__get_url_filetype(url)
            download_url = f"http://web.archive.org/web/{timestamp}{url_type}/{url}"
            domain, subdir, filename = self.__split_url(url)
            if self.MODE_CURRENT: download_dir = os.path.join(output, domain, subdir)
            else: download_dir = os.path.join(output, domain, timestamp, subdir)
            download_file = os.path.join(download_dir, filename)
            self.CDX_RESULT_COLLECTION.append(
                {
                    "index": self.CDX_RESULT_LIST.index(snapshot),
                    "url": download_url, 
                    "file": str(download_file),
                    "success": False,
                    "retry": 0
                }
            )

    def count_list(self):
        return len(self.CDX_RESULT_LIST)
    
    def count_collection(self):
        return len(self.CDX_RESULT_COLLECTION)
    
    def set_value(self, index: int, key: str, value: str):
        """
        Set a value in the collection

        Args:
            index (int): Index of the snapshot
            key (str): Key of the value
            value (str): Value to set
        """
        self.CDX_RESULT_COLLECTION[index][key] = value
    
    def __get_url_filetype(self, url):
        file_extension = url.split(".")[-1]
        urltype_mapping = {
            "jpg": "im_",
            "jpeg": "im_",
            "png": "im_",
            "gif": "im_",
            "svg": "im_",
            "ico": "im_",
            "css": "cs_",
            "js": "js_"
        }
        urltype = urltype_mapping.get(file_extension, "id_")
        return urltype
    
    def __split_url(self, url):
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        subdir = parsed_url.path.strip("/")
        filename = parsed_url.path.split("/")[-1] or "index.html"
        return domain, subdir, filename