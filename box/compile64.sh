#!/bin/bash

# Common configuration
echo > autoconf.h
echo '#define CONFIG_BOX_KERNEL_AMD64' >> autoconf.h

# For 32-bit executables
./mk-syscall-table > syscall-table.h
gcc -static -m64 -std=c99 -o mo-box32 box.c

# For 64-bit executables
echo '#define CONFIG_BOX_USER_AMD64' >> autoconf.h
./mk-syscall-table > syscall-table.h
gcc -static -m64 -std=c99 -o mo-box box.c

