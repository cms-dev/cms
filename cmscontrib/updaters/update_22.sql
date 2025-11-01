begin;

update datasets set task_type_parameters = '[1]' where task_type = 'Communication' and task_type_parameters = '[]';

rollback; -- change this to: commit;
