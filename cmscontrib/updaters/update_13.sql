begin;

alter table submissions add comment varchar not null default '';

rollback; -- change this to: commit;
