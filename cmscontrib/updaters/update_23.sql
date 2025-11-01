begin;

alter table participations add unrestricted boolean not null default 'f';

rollback; -- change this to: commit;
