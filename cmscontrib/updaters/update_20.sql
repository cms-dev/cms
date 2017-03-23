begin;

alter table contests add allow_user_tests boolean not null default 't';

rollback; -- change this to: commit;
