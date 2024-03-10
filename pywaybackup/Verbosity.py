import tqdm
import json
import time
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
        if cls.mode == "json":
            print(json.dumps(cls.snapshots.SNAPSHOT_COLLECTION, indent=4, sort_keys=True))
        elif cls.mode == "standard":
            print("")

    @classmethod
    def write(cls, message: str = None, progress: int = None):
        if cls.mode == "progress":
            if progress == 0:
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