#!/bin/bash
# Simple and hacky  one-liner to check if files present in both fs/objects and
# fs-cache/objects actually have the same content.

for file in `cat <(ls fs/objects/) <(ls fs-cache/objects/) | sort | uniq -d` ; do
	diff fs/objects/$file fs-cache/objects/$file
done

