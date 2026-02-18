#!/usr/bin/env bash

sudo chown cmsuser:cmsuser ./codecov

dropdb --if-exists --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
cmsInitDB

pytest --cov . --cov-report xml:codecov/unittests.xml --junitxml=codecov/junit.xml -o junit_family=legacy
UNIT=$?

dropdb --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
cmsInitDB

if [ -n $TEST_QUOTAS ]; then
    sed -i 's/#fs_quota/fs_quota/' /home/cmsuser/cms/etc/cms-testdb.toml
    # Some platforms only support quotas on ext4, some only support them
    # on tmpfs. So pick the filesystem accordingly.
    case $TEST_QUOTAS in
      ext4)
        # 5 times the disk quota: the test runs up to 4 workers
        # concurrently; this makes sure they can't get spurious failures
        # from running out of disk space
        fallocate -l 320M ~/boxfs.img
        mkfs.ext4 -O quota ~/boxfs.img
        sudo mount -o loop,usrquota ~/boxfs.img /var/lib/isolate
        ;;
      tmpfs)
        sudo mount -o usrquota -t tmpfs tmpfs /var/lib/isolate
        ;;
      *)
        echo "Bad TEST_QUOTAS value (expected ext4 or tmpfs)" >&2
        exit 1
        ;;
    esac
fi

cmsRunFunctionalTests -v --coverage codecov/functionaltests.xml
FUNC=$?

# This check is needed because otherwise failing unit tests aren't reported in
# the CI as long as the functional tests are passing. Ideally we should get rid
# of `cmsRunFunctionalTests` and make those tests work with pytest so they can
# be auto-discovered and run in a single command.
if [ $UNIT -ne 0 ] || [ $FUNC -ne 0 ]
then
    exit 1
else
    exit 0
fi
