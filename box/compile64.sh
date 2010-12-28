#!/bin/bash

echo > autoconf.h
echo '#define CONFIG_BOX_KERNEL_AMD64' >> autoconf.h
echo '#define CONFIG_BOX_USER_AMD64' >> autoconf.h
./mk-syscall-table > syscall-table.h
gcc -static -m64 -std=c99 -o mo-box box.c

