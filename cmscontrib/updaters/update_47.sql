begin;

alter table tasks add allowed_languages varchar[] not null default '{}';

rollback; -- change this to: commit;
