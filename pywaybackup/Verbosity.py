import tqdm
import json
import pywaybackup.SnapshotCollection as sc

class Verbosity:

    snapshots = None
    mode = None
    args = None
    pbar = None

    @classmethod
    def open(cls, args: list, snapshots: sc.SnapshotCollection):
        cls.snapshots = snapshots
        cls.args = args
        if cls.args == "progress":
            cls.mode = "progress"
        elif cls.args == "json":
            cls.mode = "json"
        else:
            cls.mode = "standard"

    @classmethod
    def close(cls):
        if cls.mode == "progress":
            cls.pbar.close()
        if cls.mode == "progress" or cls.mode == "standard":
            successed = len([snapshot for snapshot in cls.snapshots.SNAPSHOT_COLLECTION if snapshot["success"]])
            failed = len([snapshot for snapshot in cls.snapshots.SNAPSHOT_COLLECTION if not snapshot["success"]])
            print(f"\nSuccessed downloads: {successed}")
            print(f"Failed downloads: {failed}")
            print("")
        if cls.mode == "json":
            print(json.dumps(cls.snapshots.SNAPSHOT_COLLECTION, indent=4, sort_keys=True))

    @classmethod
    def write(cls, message: str = None, progress: int = None):
        if cls.mode == "progress":
            if progress == 0:
                print("")
                maxval = cls.snapshots.count_list()
                cls.pbar = tqdm.tqdm(total=maxval, desc="Downloading", unit=" snapshot", ascii="░▒█")
            elif progress == 1:
                cls.pbar.update(1)
                cls.pbar.refresh()
        elif cls.mode == "json":
            pass
        else:
            if message:
                print(message)