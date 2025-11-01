begin;

create type score_mode as enum('max', 'max_tokened_last');
alter table tasks add score_mode score_mode not null default 'max';

rollback; -- change this to: commit;
