begin;

alter table participations add team_id integer references teams(id);

rollback; -- change this to: commit;
