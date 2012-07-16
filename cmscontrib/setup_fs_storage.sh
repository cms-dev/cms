#!/bin/bash

# Usage: setup_fs_storage.sh ORIG_DIR DEST_DIR
# For each regular file in ORIG_DIR (the directory is scanned
# recursively) create a symbolic link in DEST_DIR with basename the
# SHA1 sum of the file. You can use this script to set up a directory
# for the FileCacher file system backend.

ORIG_DIR="$1"
DEST_DIR="$2"
REL_ORIG_DIR="$(python -c "import os.path; print os.path.relpath('$ORIG_DIR', '$DEST_DIR')")"
echo $REL_ORIG_DIR

mkdir -p "$DEST_DIR"
(cd "$DEST_DIR" ; find "$REL_ORIG_DIR" -type f -print0 | xargs -0 sha1sum -b) | sed "s|^\([^ ]*\) \*\(.*\)$|ln -s \2 $DEST_DIR/\1|" | bash -v
