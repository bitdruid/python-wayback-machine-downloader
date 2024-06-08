import tqdm
import json
from pywaybackup.SnapshotCollection import SnapshotCollection as sc


class Verbosity:

    mode = None
    args = None
    pbar = None

    new_debug = True
    debug = False
    output = None
    command = None

    @classmethod
    def init(cls, v_args: list, debug=False, output=None, command=None):
        cls.args = v_args
        cls.output = output
        cls.command = command
        if cls.args == "progress":
            cls.mode = "progress"
        elif cls.args == "json":
            cls.mode = "json"
        else:
            cls.mode = "standard"
        cls.debug = True if debug else False

    @classmethod
    def fini(cls):
        if cls.mode == "progress":
            if cls.pbar is not None: cls.pbar.close()
        if cls.mode == "json":
            print(json.dumps(sc.SNAPSHOT_COLLECTION, indent=4, sort_keys=True))

    @classmethod
    def write(cls, message: str = None, progress: int = None):
        if cls.mode == "progress":
            if cls.pbar is None and progress == 0:
                maxval = sc.count_list()
                cls.pbar = tqdm.tqdm(total=maxval, desc="Downloading", unit=" snapshot", ascii="░▒█")
            if cls.pbar is not None and progress is not None and progress > 0 :
                cls.pbar.update(progress)
                cls.pbar.refresh()
        elif cls.mode == "json":
            pass
        else:
            if message:
                print(message)