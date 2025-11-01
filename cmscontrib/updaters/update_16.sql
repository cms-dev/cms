begin;

alter table contests add submissions_download_allowed boolean not null default 't';

rollback; -- change this to: commit;
