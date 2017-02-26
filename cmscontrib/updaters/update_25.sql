begin;

create function run_replace(tbl regclass, par varchar) returns void as $$
begin
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)c(,|$)'', ''\1C11 / gcc\2'')', tbl, par, par);
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)cpp(,|$)'', ''\1C++11 / g++\2'')', tbl, par, par);
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)pas(,|$)'', ''\1Pascal / fpc\2'')', tbl, par, par);
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)py(,|$)'', ''\1Python 2 / CPython\2'')', tbl, par, par);
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)php(,|$)'', ''\1PHP\2'')', tbl, par, par);
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)java(,|$)'', ''\1Java 1.4 / gcj\2'')', tbl, par, par);
    execute format('update %s set %s = regexp_replace(%s, ''(,|^)hs(,|$)'', ''\1Haskell / ghc\2'')', tbl, par, par);
end
$$ language plpgsql;

select run_replace('contests', 'languages');
select run_replace('submissions', 'language');
select run_replace('user_tests', 'language');

drop function run_replace(regclass, varchar);

rollback; -- change this to: commit;
