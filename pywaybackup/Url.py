import os


class Url:
    """
    A url parsed once into the parts waybackup needs.

    Every view is derived from the same parse, so the dedup key and the output
    path can not drift apart. `key` is not a parallel normalization of the path,
    it *is* the path relative to the output directory (without the timestamp
    folder), which is what makes two urls "the same file".

    Immutable by convention - build one, read from it, drop it. `__slots__`
    keeps it cheap enough to run per cdx row on six-figure jobs.
    """

    __slots__ = ("domain_raw", "subdir", "filename_raw", "_merge_www")

    # problematic in file- and foldernames
    SPECIAL_CHARS = [":", "*", "?", "&", "=", "<", ">", "\\", "|", "#", "!", "~"]

    # path segments that would climb out of the output directory
    TRAVERSAL = (".", "..")

    @classmethod
    def _contain(cls, path: str) -> str:
        """
        Neutralize `.` and `..` path segments by encoding their dots.

        Archived urls carry traversal payloads in their query strings
        (`?file=../../../../etc/passwd`). The query is folded into the path, so
        without this the segments survive into the output path and `abspath`
        happily resolves them to somewhere outside the output directory.

        Encoded rather than dropped, so the snapshot keeps a distinct filename
        instead of silently colliding with another url.
        """
        return "/".join(
            segment.replace(".", "%2e") if segment in cls.TRAVERSAL else segment for segment in path.split("/")
        )

    def __init__(self, url: str, merge_www: bool = True):
        """
        Split a url into domain, subdir and filename.

        Args:
            url (str): The url to parse.
            merge_www (bool): Strip a leading `www.` from the domain (see `domain`).
        """
        self._merge_www = merge_www

        if "://" in url:
            url = url.split("://")[1]
        domain = url.split("/")[0]
        path = url[len(domain):]  # fmt: skip
        self.domain_raw = domain.split("@")[-1].split(":")[0]  # remove mailto and port

        path_parts = path.split("/")
        path_end = path_parts[-1]
        if not url.endswith("/") or "." in path_end:
            filename = path_parts.pop()
        else:
            filename = ""
        subdir = "/".join(path_parts).strip("/")

        for char in self.SPECIAL_CHARS:
            subdir = subdir.replace(char, f"%{ord(char):02x}")
            filename = filename.replace(char, f"%{ord(char):02x}")
        self.subdir = self._contain(subdir)
        self.filename_raw = self._contain(filename.replace("%20", " "))

    @classmethod
    def from_archive(cls, url_archive: str, merge_www: bool = True) -> "Url":
        """
        Build from a wayback `.../<timestamp>id_/<origin>` url by taking the origin.
        """
        return cls(url_archive.split("id_/")[1], merge_www)

    @property
    def domain(self) -> str:
        """
        str: The domain as a folder name.

        The cdx api canonicalizes hosts, so a single query returns `example.com`,
        `www.example.com`, `www.example.com.` and `www.EXAMPLE.com` mixed together.
        Without normalizing these all become separate folders for the same site.

        The `www.` prefix is only stripped if a dot remains, so `www.com` stays
        intact. Real subdomains (`blog.example.com`) are left alone.
        """
        domain = self.domain_raw.lower().rstrip(".")
        if self._merge_www and domain.startswith("www.") and "." in domain[4:]:
            domain = domain[4:]
        return domain

    @property
    def filename(self) -> str:
        """
        str: The filename, defaulting to `index.html` for urls without one.
        """
        return self.filename_raw or "index.html"

    @property
    def key(self) -> str:
        """
        str: Identity of the file this url maps to, relative to the output directory.

        Two urls sharing a key are the same file on disk and must not be
        downloaded twice - this is what the mode filter (last/first) groups by.
        """
        return "/".join(part for part in (self.domain, self.subdir, self.filename) if part)

    def to_path(self, output: str, timestamp: str = None) -> str:
        """
        Build the absolute output path for this url.

        Args:
            output (str): Output directory for downloaded files.
            timestamp (str, optional): Inserted as a folder below the domain (mode `all`).
        """
        return self.path_from_key(self.key, output, timestamp)

    @staticmethod
    def path_from_key(key: str, output: str, timestamp: str = None) -> str:
        """
        Rebuild an output path from a stored `key` without parsing the url again.

        Args:
            key (str): A key as produced by `Url.key`.
            output (str): Output directory for downloaded files.
            timestamp (str, optional): Inserted as a folder below the domain (mode `all`).
        """
        key = Url._contain(key)  # keys stored before _contain existed may still traverse
        if timestamp:
            domain, _, rest = key.partition("/")
            return os.path.abspath(os.path.join(output, domain, timestamp, rest))
        return os.path.abspath(os.path.join(output, key))
