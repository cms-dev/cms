begin;

alter table contests add allow_password_authentication boolean not null default 't';

rollback; -- change this to: commit;
