begin;

alter table tasks add languages character varying[];

rollback; -- change this to: commit;
