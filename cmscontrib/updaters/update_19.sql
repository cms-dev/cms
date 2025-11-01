begin;

alter table contests add block_hidden_participations boolean not null default 'f';
alter table contests add ip_restriction boolean not null default 't';

rollback; -- change this to: commit;
