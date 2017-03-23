begin;

alter table contests add ip_autologin boolean not null default 'f';

rollback; -- change this to: commit;
