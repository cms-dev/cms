begin;

alter table users add delay_time interval not null default '00:00:00'::interval;

rollback; -- change this to: commit;
