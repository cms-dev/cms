#!/bin/bash

# Check whether files present if fs/objects and fs-cache/objects have their
# filename matching their SHA1 sum
for file in fs/objects/* fs-cache/objects/* ; do
	REAL_SUM=`sha1sum $file | cut -d' ' -f1`
	PRESUMED_SUM=`basename $file`
	if diff <(echo $REAL_SUM) <(echo $PRESUMED_SUM) >/dev/null ; then
		true
	else
		echo "File $file has wrong checksum $REAL_SUM"

		# If requested, delete wrong files
		if [ "z$1" == "zdelete" ] ; then
			echo "Deleting file $file"
			rm -f $file
		fi
	fi
done

