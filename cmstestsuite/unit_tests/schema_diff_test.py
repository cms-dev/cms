import os
import unittest
import subprocess
import difflib

from cms.conf import config
from cms.db.drop import drop_db
from cms.db.init import init_db
from cms.db.session import custom_psycopg2_connection

"""
Compare the DB schema obtained from upgrading an older version's database using
an SQL updater, with the schema of a fresh install. These should be as close as
possible, but there are a few quirks which means it's not possible for the
updater to be perfect: columns can't be reordered, and enum values can't be
removed. We thus sort columns in CREATE TABLE statements, and have special
handing of enums that allows extra values in the updated form.

To make the diff output nicer in cases of mismatches, we first pair up
statements by the first line (which, for most statements, just contains the
affected object's name) and then diff the paired up statements. (One exception
to the first line thing is ALTER TABLE ADD CONSTRAINT, in which the constraint
name is on the second line. So we move the constraint name up to the first
line.)

To update the files after a new release:

    cmsInitDB
    pg_dump --schema-only >schema_vX.Y.sql

and replace update_from_vX.Y.sql with a blank file.
"""

def split_schema(schema: str) -> list[list[str]]:
    statements: list[list[str]] = []
    cur_statement: list[str] = []
    for line in schema.splitlines():
        if (
            line == ""
            or line.startswith("--")
            or line.startswith("\\restrict")
            or line.startswith("\\unrestrict")
        ):
            continue
        cur_statement.append(line)
        if line.endswith(";"):
            statements.append(cur_statement)
            cur_statement = []
    assert cur_statement == []
    return statements


def normalize_stmt(statement: list[str]) -> list[str]:
    if statement[0].startswith("CREATE TABLE "):
        # normalize order of columns by sorting the arguments to CREATE TABLE.

        assert statement[-1] == ");"
        # add missing trailing comma on the last column.
        assert not statement[-2].endswith(",")
        statement[-2] += ","
        columns = statement[1:-1]
        columns.sort()
        return [statement[0]] + columns + [");"]
    elif (
        statement[0].startswith("ALTER TABLE ")
        and len(statement) > 1
        and statement[1].startswith("    ADD CONSTRAINT ")
    ):
        # move the constraint name to the first line.
        name, rest = statement[1].removeprefix("    ADD CONSTRAINT ").split(" ", 1)
        return [statement[0] + " ADD CONSTRAINT " + name, rest] + statement[2:]
    else:
        return statement


def is_create_enum(line: str) -> bool:
    return line.startswith("CREATE TYPE ") and line.endswith(" AS ENUM (")


def compare_schemas(updated_schema: list[list[str]], fresh_schema: list[list[str]]) -> str:
    errors: list[str] = []

    updated_map: dict[str, list[str]] = {}
    for stmt in map(normalize_stmt, updated_schema):
        assert stmt[0] not in updated_map
        updated_map[stmt[0]] = stmt

    fresh_map: dict[str, list[str]] = {}
    for stmt in map(normalize_stmt, fresh_schema):
        assert stmt[0] not in fresh_map
        fresh_map[stmt[0]] = stmt

    for updated_stmt in updated_map.values():
        if updated_stmt[0] not in fresh_map:
            errors += ["Updated schema contains extra statement:", *updated_stmt]
        else:
            fresh_stmt = fresh_map[updated_stmt[0]]
            if is_create_enum(updated_stmt[0]):
                # for enums, updated's values must be a superset of fresh.
                updated_values = {
                    x.removesuffix(",").strip() for x in updated_stmt[1:-1]
                }
                fresh_values = {x.removesuffix(",").strip() for x in fresh_stmt[1:-1]}
                if not fresh_values.issubset(updated_values):
                    errors += ["Updated schema is missing enum value(s):"]
                    errors += ["Updated:"] + ["    " + x for x in updated_stmt]
                    errors += ["Fresh:"] + ["    " + x for x in fresh_stmt]
            else:
                # Other statements must match exactly (in normalized form)
                if updated_stmt != fresh_stmt:
                    differ = difflib.Differ()
                    cmp = differ.compare(
                        [x + "\n" for x in updated_stmt], [x + "\n" for x in fresh_stmt]
                    )
                    errors += ["Statement differs between updated and fresh schema:"]
                    errors += ["".join(cmp).strip()]

    for fresh_stmt in fresh_map.values():
        if fresh_stmt[0] not in updated_map:
            errors += ["Fresh schema contains extra statement:", *fresh_stmt]
        # if it exists, then it was already checked earlier
    # print('\n'.join(updated_map.keys()))
    return '\n'.join(errors)

def run_pg_dump() -> str:
    db_url = config.database.url
    db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
    result = subprocess.run(
        ["pg_dump", "--schema-only", "--dbname", db_url],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout

def get_updated_schema(schema_file: str, updater_file: str) -> str:
    drop_db()
    schema_sql = open(schema_file).read()
    # The schema sets the owner of every object explicitly. We actually want
    # these objects to be owned by whichever user CMS uses, so we skip the
    # OWNER TO commands and let the owners be defaulted to the current user.
    schema_sql = '\n'.join(
        line
        for line in schema_sql.splitlines()
        if not (line.startswith('ALTER ') and ' OWNER TO ' in line)
    )
    updater_sql = open(updater_file).read()
    # We need to do this in two separate connections, since the schema_sql sets
    # some connection properties which we don't want.
    for sql in [schema_sql, updater_sql]:
        conn = custom_psycopg2_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()

    return run_pg_dump()

def get_fresh_schema():
    drop_db()
    init_db()
    return run_pg_dump()

class TestSchemaDiff(unittest.TestCase):
    def test_schema_diff(self):
        dirname = os.path.dirname(__file__)
        schema_file = os.path.join(dirname, "schema_v1.5.sql")
        updater_file = os.path.join(dirname, "../../cmscontrib/updaters/update_from_1.5.sql")
        updated_schema = split_schema(get_updated_schema(schema_file, updater_file))
        fresh_schema = split_schema(get_fresh_schema())
        errors = compare_schemas(updated_schema, fresh_schema)
        self.longMessage = False
        self.assertTrue(errors == "", errors)
