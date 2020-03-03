create type statement_type as enum ('pdf', 'md', 'html');
alter table statements add statement_type statement_type not null default 'pdf';
alter table statements drop constraint statements_task_id_language_key;
alter table statements add constraint statements_task_id_language_statement_type_key unique (task_id, language, statement_type);
create table statement_assets (
    id          serial primary key,
    task_id     integer not null references tasks(id) on update cascade on delete cascade,
    filename    filename not null,
    digest      digest not null,
    constraint  statement_assets_task_id_filename_key unique (task_id, filename),
    constraint  ix_statement_assets_task_id unique (task_id)
);
