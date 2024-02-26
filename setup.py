
from setuptools import setup, find_packages
from pywaybackup.__version__ import __version__ as VERSION

DESCRIPTION = 'Download snapshots from the Wayback Machine'

import pkg_resources
def parse_requirements(filename):
    with open(filename, 'r') as f:
        requirements = [str(requirement) for requirement in pkg_resources.parse_requirements(f)]
    return requirements

from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='pywaybackup',
    version=VERSION,
    packages=find_packages(),
    install_requires=parse_requirements('./requirements.txt'),
    entry_points={
        'console_scripts': [
            'waybackup = pywaybackup.main:main',
        ],
    },
    author='bitdruid',
    author_email='bitdruid@outlook.com',
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='MIT',
    keywords='wayback machine internet archive',
    url='https://github.com/bitdruid/python-wayback-machine-downloader',
)
