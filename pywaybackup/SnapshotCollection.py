from urllib.parse import urlparse
import os

class SnapshotCollection:

    CDX_LIST = []
    SNAPSHOT_COLLECTION = []
    MODE_CURRENT = 0

    @classmethod
    def create_list_full(cls, cdxResult):
        cls.CDX_LIST = sorted([{"timestamp": snapshot[0], "url": snapshot[1], "status": snapshot[2], "mimetype": snapshot[3], "digest": snapshot[4]} for i, snapshot in enumerate(cdxResult.json()[1:])], key=lambda k: k['timestamp'], reverse=True)

    @classmethod
    def create_list_current(cls):
        cls.MODE_CURRENT = 1
        cdxResult_list_filtered = []
        url_set = set()
        for snapshot in cls.CDX_LIST:
            if snapshot["url"] not in url_set:
                cdxResult_list_filtered.append(snapshot)
                url_set.add(snapshot["url"])
        cls.CDX_LIST = cdxResult_list_filtered

    @classmethod
    def count_list(cls):
        return len(cls.CDX_LIST)

    @classmethod
    def create_collection(cls):
        for cdx_entry in cls.CDX_LIST:
            timestamp, url = cdx_entry["timestamp"], cdx_entry["url"]
            url_archive = f"http://web.archive.org/web/{timestamp}{cls._url_get_filetype(url)}/{url}"
            collection_entry = {
                "id": len(cls.SNAPSHOT_COLLECTION),
                "timestamp": timestamp,
                "url_archive": url_archive,
                "url_origin": url,
                "file": False,
                "redirect": False,
                "response": False
            }
            cls.SNAPSHOT_COLLECTION.append(collection_entry)
    
    @classmethod
    def snapshot_entry_create_output(cls, collection_entry: dict, output: str) -> str:
        """
        Create the output path for a snapshot entry of the collection according to the mode.

        Input:
        - collection_entry: A single snapshot entry of the collection (dict).
        - output: The output directory (str).

        Output:
        - download_file: The output path for the snapshot entry (str) with filename.
        """
        timestamp, url = collection_entry["timestamp"], collection_entry["url_origin"]
        domain, subdir, filename = cls._url_split(url)
        if cls.MODE_CURRENT:
            download_dir = os.path.join(output, domain, subdir)
        else:
            download_dir = os.path.join(output, domain, timestamp, subdir)
        download_file = os.path.join(download_dir, filename)
        return download_file

    @classmethod
    def snapshot_entry_modify(cls, collection_entry: dict, key: str, value: str):
        """
        Modify a key-value pair in a snapshot entry of the collection (dict).

        - Append a new key-value pair if the key does not exist.
        - Modify an existing key-value pair if the key exists.
        """
        collection_entry[key] = value

    @classmethod
    def url_get_timestamp(cls, url):
        """
        Extract the timestamp from a wayback machine URL.
        """
        timestamp = url.split("web.archive.org/web/")[1].split("/")[0]
        timestamp = ''.join([char for char in timestamp if char.isdigit()])
        return timestamp

    @classmethod
    def _url_get_filetype(cls, url):
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

    @classmethod
    def _url_split(cls, url):
        """
        Split a URL into domain, subdir and filename.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        subdir = parsed_url.path.strip("/").rsplit("/", 1)[0]
        filename = parsed_url.path.split("/")[-1] or "index.html"
        return domain, subdir, filename