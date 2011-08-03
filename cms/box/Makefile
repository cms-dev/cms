# Makefile for MO-Eval sandbox
# (c) 2008--2010 Martin Mares <mj@ucw.cz>

DIRS+=box
PROGS+=$(o)/box/box

BOX_CFLAGS=
ifdef CONFIG_BOX_KERNEL_AMD64
BOX_CFLAGS += -m64
endif

$(o)/box/box: $(o)/box/box.o
$(o)/box/box.o: $(o)/box/syscall-table.h

$(o)/box/box: LDFLAGS+=$(BOX_CFLAGS)
$(o)/box/box.o: CFLAGS+=$(BOX_CFLAGS)

$(o)/box/syscall-table.h: $(s)/box/mk-syscall-table
	sh $^ >$@ $(CFLAGS) $(BOX_CFLAGS)

box-tests: $(addprefix $(o)/box/test-sys,32-int80 64-int80 32-syscall 64-syscall 32-sysenter 64-sysenter)

.PHONY: box-tests

$(o)/box/test-sys32-int80: $(s)/box/test-syscalls.c
	$(CC) -m32 $^ -o $@ -DTEST_INT80

$(o)/box/test-sys64-int80: $(s)/box/test-syscalls.c
	$(CC) -m64 $^ -o $@ -DTEST_INT80

$(o)/box/test-sys32-syscall: $(s)/box/test-syscalls.c
	$(CC) -m32 $^ -o $@ -DTEST_SYSCALL_32

$(o)/box/test-sys64-syscall: $(s)/box/test-syscalls.c
	$(CC) -m64 $^ -o $@ -DTEST_SYSCALL_64

$(o)/box/test-sys32-sysenter: $(s)/box/test-syscalls.c
	$(CC) -m32 $^ -o $@ -DTEST_SYSENTER_32

$(o)/box/test-sys64-sysenter: $(s)/box/test-syscalls.c
	$(CC) -m64 $^ -o $@ -DTEST_SYSENTER_32 #sic
