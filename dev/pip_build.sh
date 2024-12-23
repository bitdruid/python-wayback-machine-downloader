#!bin/bash

# path of the script
SCRIPT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
TARGET_PATH="$SCRIPT_PATH/.."

pip install build twine

python -m build
twine upload dist/*

rm -rf $TARGET_PATH/build $TARGET_PATH/dist $TARGET_PATH/*.egg-info