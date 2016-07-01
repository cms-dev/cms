begin;

alter table contests add allow_questions boolean not null default 't';

rollback; -- change this to: commit;
