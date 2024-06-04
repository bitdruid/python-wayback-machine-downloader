#!bin/bash

# path of the script
SCRIPT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
TARGET_PATH="$SCRIPT_PATH/.."

# install dependencies
pip install twine wheel setuptools

# build 
python $TARGET_PATH/setup.py sdist bdist_wheel --verbose
python -m twine upload dist/*
#pip install -e $TARGET_PATH

# clean up
rm -rf $TARGET_PATH/build $TARGET_PATH/dist # $TARGET_PATH/*.egg-info