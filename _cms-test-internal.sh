#!/usr/bin/env bash

sudo chown cmsuser:cmsuser ./codecov

dropdb --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
cmsInitDB

pytest --cov . --cov-report xml:codecov/unittests.xml --junitxml=codecov/junit.xml -o junit_family=legacy
UNIT=$?

dropdb --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
cmsInitDB

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
