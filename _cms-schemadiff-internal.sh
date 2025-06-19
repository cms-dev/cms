#!/usr/bin/env bash

# Create SQL dump of the old schema (with updates applied)
dropdb --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
psql --host=testdb --username=postgres cmsdbfortesting < .gh_action_data/1.5.sql
psql --host=testdb --username=postgres cmsdbfortesting < cmscontrib/updaters/update_from_1.5.sql
pg_dump --host=testdb --username=postgres --schema-only cmsdbfortesting > .gh_action_data/updated_schema.sql

# Create SQL dump of the new schema
dropdb --host=testdb --username=postgres cmsdbfortesting
createdb --host=testdb --username=postgres cmsdbfortesting
cmsInitDB
pg_dump --host=testdb --username=postgres --schema-only cmsdbfortesting > .gh_action_data/new_schema.sql

# Compare the two schema dumps
diff .gh_action_data/updated_schema.sql .gh_action_data/new_schema.sql | grep -v '^--' | grep -v -e '^[[:space:]]*$' > .gh_action_data/schema_diff.txt
if [ -s .gh_action_data/schema_diff.txt ]
then
    echo "Schema diff found:"
    cat .gh_action_data/schema_diff.txt
    exit 1
else
    echo "No schema diff found."
    exit 0
fi
