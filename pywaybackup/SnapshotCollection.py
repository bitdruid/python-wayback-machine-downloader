from pywaybackup.helper import url_split
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
        cls.SNAPSHOT_COLLECTION = sorted([{"timestamp": snapshot[0], "digest": snapshot[1], "mimetype": snapshot[2], "status": snapshot[3], "url": snapshot[4]} for snapshot in cdxResult[1:]], key=lambda k: k['timestamp'], reverse=True)
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
    def count(cls, collection=False, success=False, fail=False):
        if collection:
            return len(cls.SNAPSHOT_COLLECTION)
        if success:
            return len([entry for entry in cls.SNAPSHOT_COLLECTION if entry["file"]])
        if fail:
            return len([entry for entry in cls.SNAPSHOT_COLLECTION if not entry["file"]])
        return len(cls.SNAPSHOT_COLLECTION)


    @classmethod
    def create_collection(cls):
        new_collection = []
        for idx, cdx_entry in enumerate(cls.SNAPSHOT_COLLECTION):
            timestamp, url_origin = cdx_entry["timestamp"], cdx_entry["url"]
            url_archive = f"https://web.archive.org/web/{timestamp}id_/{url_origin}"
            collection_entry = {
                "id": idx,
                "timestamp": timestamp,
                "url_archive": url_archive,
                "url_origin": url_origin,
                "redirect_url": False,
                "redirect_timestamp": False,
                "response": False,
                "file": False
            }
            new_collection.append(collection_entry)
        cls.SNAPSHOT_COLLECTION = new_collection
    

    @classmethod
    def create_output(cls, url: str, timestamp: str, output: str):
        domain, subdir, filename = url_split(url.split("id_/")[1], index=True)
        if cls.MODE_CURRENT:
            download_dir = os.path.join(output, domain, subdir)
        else:
            download_dir = os.path.join(output, domain, timestamp, subdir)
        download_file = os.path.abspath(os.path.join(download_dir, filename))
        return download_file
    

    @classmethod
    def entry_modify(cls, collection_entry: dict, key: str, value: str):
        """
        Modify a key-value pair in a snapshot entry of the collection (dict).

        - Append a new key-value pair if the key does not exist.
        - Modify an existing key-value pair if the key exists.
        """
        collection_entry[key] = value
