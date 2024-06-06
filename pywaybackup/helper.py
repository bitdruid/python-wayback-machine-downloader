
import os
import shutil

def sanitize_filename(input: str) -> str:
    """
    Sanitize a string to be used as (part of) a filename.
    """
    disallowed = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in disallowed:
        input = input.replace(char, ".")
    input = '.'.join(filter(None, input.split('.')))
    return input


def url_get_timestamp(url):
        """
        Extract the timestamp from a wayback machine URL.
        """
        timestamp = url.split("id_/")[0].split("/")[-1]
        return timestamp

def url_split(url, index=False):
    """
    Split a URL into domain, subdir, and filename.
    """
    if url.startswith("http"):
        url = url.split("://")[1]
    domain = url.split("/")[0]
    path = url[len(domain):]
    domain = domain.split("@")[-1].split(":")[0] # remove mailto and port
    path_parts = path.split("/")
    path_end = path_parts[-1]
    if not url.endswith("/") or "." in path_end:
        filename = path_parts.pop()
    else:
        filename = "index.html" if index else ""
    subdir = "/".join(path_parts).strip("/")
    # sanitize subdir and filename for windows
    if os.name == "nt":
        special_chars = [":", "*", "?", "&", "=", "<", ">", "\\", "|"]
        for char in special_chars:
            subdir = subdir.replace(char, f"%{ord(char):02x}")
            filename = filename.replace(char, f"%{ord(char):02x}")
    filename = filename.replace("%20", " ")
    return domain, subdir, filename

def move_index(existpath: str = None, existfile: str = None):
    """
    1. If output_path is given but can't be created because a file exists with the same name
        - moves the existing file to a temporary name
        - creates the output_path
        - moves the temporary file to the output_path

    2. If output_file is given but can't be created because a folder exists with the same name
        - sets output_file path to existing folder + index.html
    """
    if existpath:
        shutil.move(existpath, existpath + "_exist")
        os.makedirs(existpath, exist_ok=True)
        shutil.move(existpath + "_exist", os.path.join(existpath, "index.html"))
    elif existfile:
        return os.path.join(existfile, "index.html")

