import os
import errno
import magic
from pywaybackup.helper import url_split

from pywaybackup.Arguments import Configuration as config
from pywaybackup.Verbosity import Verbosity as vb
import re

class Converter:

    @classmethod
    def define_root_steps(cls, filepath) -> str:
        """
        Define the steps (../) to the root directory.
        """
        abs_path = os.path.abspath(filepath)
        webroot_path = os.path.abspath(f"{config.output}/{config.domain}/") # webroot is the domain folder in the output
        # common path between the two
        common_path = os.path.commonpath([abs_path, webroot_path])
        # steps up to the common path
        rel_path_from_common = os.path.relpath(abs_path, common_path)
        steps_up = rel_path_from_common.count(os.path.sep)
        if steps_up <= 1: # if the file is in the root of the domain
            return "./"
        return "../" * steps_up





    @classmethod
    def links(cls, filepath, status_message=None):
        """
        Convert all links in a HTML / CSS / JS file to local paths.
        """


        def extract_urls(content) -> list:
            """
            Extract all links from a file.
            """

            #content = re.sub(r'\s+', '', content)
            #content = re.sub(r'\n', '', content)

            html_types = ["src", "href", "poster", "data-src"]
            css_types = ["url"]
            links = []
            for html_type in html_types:
                # possible formatings of the value: "url", 'url', url
                matches = re.findall(f"{html_type}=[\"']?([^\"'>]+)", content)
                links += matches
            for css_type in css_types:
                # possible formatings of the value: url(url) url('url') url("url") // ends with )
                matches = re.findall(rf"{css_type}\((['\"]?)([^'\"\)]+)\1\)", content)
                links += [match[1] for match in matches]
            links = list(set(links))
            return links


        def local_url(original_url, domain, count) -> str:
            """
            Convert a given url to a local path.
            """
            original_url_domain = url_split(original_url)[0]

            # check if the url is external or internal (external is returned as is because no need to convert)
            external = False
            if original_url_domain != domain:
                if "://" in original_url:
                    external = True
            if original_url.startswith("//"):
                external = True
            if external:
                status_message.trace(status="", type=f"{count}/{len(links)}", message="External url")
                return original_url

            # convert the url to a relative path to the local root (download dir) if it's a valid path, else return the original url
            original_url_file = os.path.join(config.output, config.domain, normalize_url(original_url))
            if validate_path(original_url_file):
                if original_url.startswith("/"): # if only starts with /
                    original_url = f"{cls.define_root_steps(filepath)}{original_url.lstrip('/')}"
                if original_url.startswith(".//"):
                    original_url = f"{cls.define_root_steps(filepath)}{original_url.lstrip('./')}"
                if original_url_domain == domain: # if url is like https://domain.com/path/to/file
                    original_url = f"{cls.define_root_steps(filepath)}{original_url.split(domain)[1].lstrip('/')}"
                if original_url.startswith("../"): # if file is already ../ check if it's not too many steps up
                    original_url = f"{cls.define_root_steps(filepath)}{original_url.split('../')[-1].lstrip('/')}"
            else:
                status_message.trace(status="", type="", message=f"{count}/{len(links)}: URL is not a valid path")

            return original_url



        

        def normalize_url(url) -> str:
            """
            Normalize a given url by removing it's protocol, domain and parent directorie references.

            Example1:
                - Example input: https://domain.com/path/to/file
                - Example output: /path/to/file

            Example2
                - input: ../path/to/file
                - output: /path/to/file
            """
            try:
                url = "/" + url.split("../")[-1]
            except IndexError:
                pass
            if url.startswith("//"):
                url = "/" + url.split("//")[1]
            parsed_url = url_split(url)
            return f"{parsed_url[1]}/{parsed_url[2]}"


        def is_pathname_valid(pathname: str) -> bool:
            """
            Check if a given pathname is valid.
            """
            if not isinstance(pathname, str) or not pathname:
                return False

            try:
                os.lstat(pathname)
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    return True
                elif exc.errno in {errno.ENAMETOOLONG, errno.ERANGE}:
                    return False
            return True

        def is_path_creatable(pathname: str) -> bool:
            """
            Check if a given path is creatable.
            """
            dirname = os.path.dirname(pathname) or os.getcwd()
            return os.access(dirname, os.W_OK)

        def is_path_exists_or_creatable(pathname: str) -> bool:
            """
            Check if a given path exists or is creatable.
            """
            return is_pathname_valid(pathname) or is_path_creatable(pathname)

        def validate_path(filepath: str) -> bool:
            """
            Validate if a given path can exist.
            """
            return is_path_exists_or_creatable(filepath)





        if os.path.isfile(filepath):
            if magic.from_file(filepath, mime=True).split("/")[1] == "javascript":
                status_message.trace(status="Error", type="", message="JS-file is not supported")
                return
            try:
                with open(filepath, "r") as file:
                    domain = config.domain
                    content = file.read()
                    links = extract_urls(content)
                    status_message.store(message=f"\n-----> Convert: [{len(links)}] links in file")
                    count = 1
                    for original_link in links:
                        status_message.trace(status="ORIG", type=f"{count}/{len(links)}", message=original_link)
                        new_link = local_url(original_link, domain, count)
                        if new_link != original_link:
                            status_message.trace(status="CONV", type=f"{count}/{len(links)}", message=new_link)
                        content = content.replace(original_link, new_link)
                        count += 1
                    file = open(filepath, "w")
                    file.write(content)
                    file.close()
            except UnicodeDecodeError:
                status_message.trace(status="Error", type="", message="Could not decode file to convert links")
