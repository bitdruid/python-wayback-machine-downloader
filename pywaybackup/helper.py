
import os
import shutil

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

def file_move_index(output_path: str):
    shutil.move(output_path, output_path + "_exist")
    os.makedirs(output_path, exist_ok=True)
    shutil.move(output_path + "_exist", os.path.join(output_path, "index.html"))

