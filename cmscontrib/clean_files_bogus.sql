BEGIN;
    UPDATE executables SET digest = 'x' WHERE digest != 'x';
    SELECT pg_size_pretty(pg_table_size('pg_largeobject')) AS "Large objects size";
    CREATE TEMPORARY TABLE digests_to_delete (digest VARCHAR) ON COMMIT DROP;
    INSERT INTO digests_to_delete 
        SELECT digest FROM fsobjects EXCEPT (
            SELECT digest FROM attachments UNION
            SELECT digest FROM executables UNION
            SELECT digest FROM files UNION
            SELECT digest FROM managers UNION
            SELECT digest FROM printjobs UNION
            SELECT digest FROM statements UNION
            SELECT input AS digest FROM testcases UNION
            SELECT output AS digest FROM testcases UNION
            SELECT input AS digest FROM user_tests UNION
            SELECT digest FROM user_test_executables UNION
            SELECT digest FROM user_test_files UNION
            SELECT digest FROM user_test_managers UNION
            select output AS digest FROM user_test_results);
    SELECT SUM(rm.success) AS "Files deleted" FROM (
        SELECT lo_unlink(loid) AS success FROM fsobjects WHERE digest IN (
            SELECT digest FROM digests_to_delete
        )) AS rm;
    DELETE FROM fsobjects WHERE digest in (
        SELECT digest FROM digests_to_delete
    );
    SELECT pg_size_pretty(pg_table_size('pg_largeobject')) AS "Large objects new size";
COMMIT;
