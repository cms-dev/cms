import argparse
import subprocess
import difflib
import sys

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
"""


def split_schemma(schema: str):
    statements: list[list[str]] = []
    cur_statement: list[str] = []
    for line in schema.splitlines():
        if line == "" or line.startswith("--"):
            continue
        cur_statement.append(line)
        if line.endswith(";"):
            statements.append(cur_statement)
            cur_statement = []
    assert cur_statement == []
    return statements


def normalize_stmt(statement: list[str]):
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


def is_create_enum(line: str):
    return line.startswith("CREATE TYPE ") and line.endswith(" AS ENUM (")


def compare_schemas(updated_schema: list[list[str]], fresh_schema: list[list[str]]):
    ok = True

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
            print("Updated schema contains extra statement:", *updated_stmt, sep="\n")
            ok = False
        else:
            fresh_stmt = fresh_map[updated_stmt[0]]
            if is_create_enum(updated_stmt[0]):
                # for enums, updated's values must be a superset of fresh.
                updated_values = {
                    x.removesuffix(",").strip() for x in updated_stmt[1:-1]
                }
                fresh_values = {x.removesuffix(",").strip() for x in fresh_stmt[1:-1]}
                if not fresh_values.issubset(updated_values):
                    print("Updated schema is missing enum value(s):")
                    print("Updated:\n    " + "\n    ".join(updated_stmt))
                    print("Fresh:\n    " + "\n    ".join(fresh_stmt))
            else:
                # Other statements must match exactly (in normalized form)
                if updated_stmt != fresh_stmt:
                    ok = False
                    differ = difflib.Differ()
                    cmp = differ.compare(
                        [x + "\n" for x in updated_stmt], [x + "\n" for x in fresh_stmt]
                    )
                    print("Statement differs between updated and fresh schema:")
                    print("".join(cmp))

    for fresh_stmt in fresh_map.values():
        if fresh_stmt[0] not in updated_map:
            print("Fresh schema contains extra statement:", *fresh_stmt, sep="\n")
            ok = False
        # if it exists, then it was already checked earlier
    # print('\n'.join(updated_map.keys()))
    return ok


def get_updated_schema(user, host, name, schema_sql, updater_sql):
    args = [f"--username={user}", f"--host={host}", name]
    psql_flags = ["--quiet", "--set=ON_ERROR_STOP=1"]
    subprocess.run(["dropdb", "--if-exists", *args], check=True)
    subprocess.run(["createdb", *args], check=True)
    subprocess.run(
        ["psql", *args, *psql_flags, f"--file={schema_sql}"],
        check=True,
        stdout=subprocess.PIPE,
    )
    subprocess.run(
        ["psql", *args, *psql_flags, f"--file={updater_sql}"],
        check=True,
    )
    result = subprocess.run(
        ["pg_dump", "--schema-only", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def get_fresh_schema(user, host, name):
    args = [f"--username={user}", f"--host={host}", name]
    subprocess.run(["dropdb", "--if-exists", *args], check=True)
    subprocess.run(["createdb", *args], check=True)
    subprocess.run(["cmsInitDB"], check=True)
    result = subprocess.run(
        ["pg_dump", "--schema-only", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--schema_sql", required=True)
    parser.add_argument("--updater_sql", required=True)
    args = parser.parse_args()
    print("Checking schema updater...")
    updated_schema = split_schemma(
        get_updated_schema(
            args.user, args.host, args.name, args.schema_sql, args.updater_sql
        )
    )
    fresh_schema = split_schemma(get_fresh_schema(args.user, args.host, args.name))
    if compare_schemas(updated_schema, fresh_schema):
        print("All good, updater works")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
