begin;

alter table contests add allowed_localizations not null default '';

rollback; -- change this to: commit;
