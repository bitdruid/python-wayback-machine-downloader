import os
import shutil
import magic

# one instance for the run to keep resource usage low
_mime = magic.Magic(mime=True)

# only keep the header for libmagic
_MIME_SNIFF_BYTES = 2048


def check_nt():
    """
    Check if the OS is Windows.
    """
    return os.name == "nt"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be used as (part of) a filename.
    """
    disallowed = ["<", ">", ":", '"', "/", "\\", "|", "?", "*", "=", "#", "!", "~"]
    for char in disallowed:
        filename = filename.replace(char, ".")
    filename = ".".join(filter(None, filename.split(".")))
    return filename


def sanitize_url(url: str) -> str:
    """
    Sanitize a url by encoding special characters.
    """
    special_chars = [":", "*", "?", "&", "=", "<", ">", "\\", "|"]
    for char in special_chars:
        url = url.replace(char, f"%{ord(char):02x}")
    return url


def url_get_timestamp(url):
    """
    Extract the timestamp from a wayback machine URL.

    Returns an empty string if the URL does not contain a `web/<timestamp>` segment
    (e.g. relative or external redirect targets).
    """
    parts = url.split("web/")
    if len(parts) < 2:
        return ""
    timestamp = parts[1].split("/")[0]
    if "id_" in url:
        timestamp = timestamp.split("id_")[0]
    return timestamp


def move_index(existpath: str = None, existfile: str = None, filebuffer: bytes = None):
    """
    1. If existpath is given but can't be created because a file exists with the same name
        - moves the existing file to a temporary name
        - creates the existpath
        - moves the temporary file to the existpath
        - if existing file is text/html, renames it to index.html, else to basename

    2. If existfile is given but can't be created because a folder exists with the same name
        - sets existfile path to existing folder + index.html
        - if the new file is text/html, stores it as index.html, else as basename of target folder
    """
    if existpath:
        shutil.move(existpath, existpath + "_exist")
        os.makedirs(existpath, exist_ok=True)
        if not check_index_mime(existpath):
            new_file = os.path.join(existpath, os.path.basename(os.path.normpath(existpath)))
        else:
            new_file = os.path.join(existpath, "index.html")
        shutil.move(existpath + "_exist", new_file)
    elif existfile:
        if filebuffer:
            if not check_index_mime(filebuffer):
                return os.path.join(existfile, os.path.basename(os.path.normpath(existfile)))
            else:
                return os.path.join(existfile, "index.html")


def check_index_mime(filebuffer: bytes) -> bool:
    mime_type = _mime.from_buffer(filebuffer[:_MIME_SNIFF_BYTES])
    if mime_type != "text/html":
        return False
    return True


def add_html_extension(filepath: str, filebuffer: bytes) -> str:
    """
    Append `.html` to a file without extension if its content is html.

    Urls like `/about` or `/docs/guide` carry no extension, so the snapshot is
    written as an extensionless file that no browser or file manager opens.
    The content type is sniffed from the buffer instead of the cdx mimetype
    column, which is often `warc/revisit` or `unk` rather than a real type.
    """
    if os.path.splitext(filepath)[1]:
        return filepath
    if not check_index_mime(filebuffer):
        return filepath
    return filepath + ".html"
