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

cmsRunFunctionalTests -v --coverage codecov/functionaltests.xml
FUNC=$?

python cmstestsuite/check_schema_diff.py --user=postgres --host=testdb --name=cmsdbfortesting --schema_sql=cmstestsuite/schema_v1.5.sql --updater_sql=cmscontrib/updaters/update_from_1.5.sql
SCHEMA=$?

# This check is needed because otherwise failing unit tests aren't reported in
# the CI as long as the functional tests are passing. Ideally we should get rid
# of `cmsRunFunctionalTests` and make those tests work with pytest so they can
# be auto-discovered and run in a single command.
if [ $UNIT -ne 0 ] || [ $FUNC -ne 0 ] || [ $SCHEMA -ne 0 ]
then
    exit 1
else
    exit 0
fi
