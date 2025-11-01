begin;

update contests set start = '946684800' where start is null;
update contests set stop = '4102444800' where stop is null;

alter table contests alter start set not null;
alter table contests alter stop set not null;

rollback; -- change this to: commit;
