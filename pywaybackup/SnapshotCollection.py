from urllib.parse import urlparse
import os

class SnapshotCollection:

    CDX_JSON = []
    CDX_LIST = []

    SNAPSHOT_COLLECTION = []

    MODE_CURRENT = 0

    def __init__(self):
        pass

    def create_full(self, cdxResult):
        self.CDX_JSON = cdxResult.json()[1:]
        self.CDX_LIST = [{"timestamp": snapshot[0], "url": snapshot[1]} for i, snapshot in enumerate(self.CDX_JSON)]
        self.CDX_LIST = sorted(self.CDX_LIST, key=lambda k: k['timestamp'], reverse=True)

    def create_current(self):
        self.MODE_CURRENT = 1
        self.CDX_LIST = sorted(self.CDX_LIST, key=lambda k: k['timestamp'], reverse=True)
        cdxResult_list_filtered = []
        url_set = set()
        for snapshot in self.CDX_LIST:
            if snapshot["url"] not in url_set:
                cdxResult_list_filtered.append(snapshot)
                url_set.add(snapshot["url"])
        self.CDX_LIST = cdxResult_list_filtered

    def create_entry(self, cdx_entry: dict, output: str) -> dict:
        timestamp, url = cdx_entry["timestamp"], cdx_entry["url"]
        domain, subdir, filename = self.split_url(url)
        if self.MODE_CURRENT: download_dir = os.path.join(output, domain, subdir)
        else: download_dir = os.path.join(output, domain, timestamp, subdir)
        download_file = os.path.join(download_dir, filename)
        cdx_entry = {
                "id": len(self.SNAPSHOT_COLLECTION),
                "url": self.create_archive_url(timestamp, url),
                "file": download_file,
                "timestamp": timestamp,
                "origin_url": url,
                "success": False,
                "retry": 0
            }
        return cdx_entry

    @classmethod    
    def create_archive_url(cls, timestamp: str, url: str) -> str:
        url_type = cls.__get_url_filetype(url)
        return f"http://web.archive.org/web/{timestamp}{url_type}/{url}"

    def count_list(self):
        return len(self.CDX_LIST)
    
    def snapshot_collection_write(self, query_entry: dict):
        if query_entry["id"] not in self.SNAPSHOT_COLLECTION:
            self.SNAPSHOT_COLLECTION.append(query_entry)
    
    def snapshot_collection_update(self, id: int, key: str, value: str):
        index = next((index for (index, d) in enumerate(self.SNAPSHOT_COLLECTION) if d["id"] == id), None)
        if index is not None:
            self.SNAPSHOT_COLLECTION[index][key] = value

    @classmethod
    def get_url_filetype(cls, url):
        file_extension = os.path.splitext(url)[1][1:]
        urltype_mapping = {
            "jpg": "im_",
            "jpeg": "im_",
            "png": "im_",
            "gif": "im_",
            "svg": "im_",
            "ico": "im_",
            "css": "cs_"
            #"js": "js_"
        }
        urltype = urltype_mapping.get(file_extension, "id_")
        return urltype

    @staticmethod    
    def split_url(url):
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        subdir = parsed_url.path.strip("/").rsplit("/", 1)[0]
        filename = parsed_url.path.split("/")[-1] or "index.html"
        return domain, subdir, filename