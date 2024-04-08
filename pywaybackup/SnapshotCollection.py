from urllib.parse import urlparse
import os

class SnapshotCollection:

    SNAPSHOT_COLLECTION = []
    MODE_CURRENT = 0

    @classmethod
    def create_list(cls, cdxResult, mode):
        """
        Create the snapshot collection list from a cdx result.

        - mode `full`: All snapshots are included.
        - mode `current`: Only the latest snapshot of each file is included.
        """
        # creates a list of dictionaries for each snapshot entry
        cls.SNAPSHOT_COLLECTION = sorted([{"timestamp": snapshot[0], "digest": snapshot[1], "mimetype": snapshot[2], "status": snapshot[3], "url": snapshot[4]} for snapshot in cdxResult.json()[1:]], key=lambda k: k['timestamp'], reverse=True)
        if mode == "current": 
            cls.MODE_CURRENT = 1
            cdxResult_list_filtered = []
            url_set = set()
            # filters the list to only include the latest snapshot of each file
            for snapshot in cls.SNAPSHOT_COLLECTION:
                if snapshot["url"] not in url_set:
                    cdxResult_list_filtered.append(snapshot)
                    url_set.add(snapshot["url"])
            cls.SNAPSHOT_COLLECTION = cdxResult_list_filtered
        # writes the index for each snapshot entry
        cls.SNAPSHOT_COLLECTION = [{"id": idx, **entry} for idx, entry in enumerate(cls.SNAPSHOT_COLLECTION)]
    
    @classmethod
    def count_list(cls):
        return len(cls.SNAPSHOT_COLLECTION)

    @classmethod
    def create_collection(cls):
        new_collection = []
        for cdx_entry in cls.SNAPSHOT_COLLECTION:
            timestamp, url = cdx_entry["timestamp"], cdx_entry["url"]
            url_archive = f"http://web.archive.org/web/{timestamp}{cls._url_get_filetype(url)}/{url}"
            collection_entry = {
                "id": cls.SNAPSHOT_COLLECTION.index(cdx_entry),
                "timestamp": timestamp,
                "url_archive": url_archive,
                "url_origin": url,
                "redirect_url": False,
                "redirect_timestamp": False,
                "response": False,
                "file": False
            }
            new_collection.append(collection_entry)
        cls.SNAPSHOT_COLLECTION = new_collection
    
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
        download_file = os.path.abspath(os.path.join(download_dir, filename))
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