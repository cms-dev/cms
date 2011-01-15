#!/bin/bash

# Check whether files present in both fs/objects and fs-cache/objects actually
# have the same content.
for file in `cat <(ls fs/objects/) <(ls fs-cache/objects/) | sort | uniq -d` ; do
	diff fs/objects/$file fs-cache/objects/$file
done

# Check whether files present if fs/objects and fs-cache/objects have their
# filename matching their SHA1 sum
for file in fs/objects/* fs-cache/objects/* ; do
	diff <(sha1sum $file | cut -d' ' -f1) <(echo `basename $file`)
done

