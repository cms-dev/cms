begin;

create or replace function createParticipations() returns void as $$
declare
    u users%rowtype;
    pid participations.id%type;
begin
    for u in select * from users
    loop
        insert into participations(ip, starting_time, delay_time, extra_time, hidden, contest_id, user_id) values (u.ip, u.starting_time, u.delay_time, u.extra_time, u.hidden, u.contest_id, u.id) returning id into pid;
        update messages set participation_id = pid where user_id = u.id;
        update printjobs set participation_id = pid where user_id = u.id;
        update submissions set participation_id = pid where user_id = u.id;
        update questions set participation_id = pid where user_id = u.id;
        update user_tests set participation_id = pid where user_id = u.id;
    end loop;
end
$$
language 'plpgsql';

select * from users limit 10;
select * from participations limit 10;

alter table messages add participation_id integer;
alter table printjobs add participation_id integer;
alter table submissions add participation_id integer;
alter table questions add participation_id integer;
alter table user_tests add participation_id integer;

select createParticipations();

alter table messages add foreign key (participation_id) references participations(id) on update cascade on delete cascade;
alter table messages alter participation_id set not null;
create index on messages using btree (participation_id);
alter table printjobs add foreign key (participation_id) references participations(id) on update cascade on delete cascade;
alter table printjobs alter participation_id set not null;
create index on printjobs using btree (participation_id);
alter table submissions add foreign key (participation_id) references participations(id) on update cascade on delete cascade;
alter table submissions alter participation_id set not null;
create index on submissions using btree (participation_id);
alter table questions add foreign key (participation_id) references participations(id) on update cascade on delete cascade;
alter table questions alter participation_id set not null;
create index on questions using btree (participation_id);
alter table user_tests add foreign key (participation_id) references participations(id) on update cascade on delete cascade;
alter table user_tests alter participation_id set not null;
create index on user_tests using btree (participation_id);

alter table messages drop user_id;
alter table printjobs drop user_id;
alter table submissions drop user_id;
alter table questions drop user_id;
alter table user_tests drop user_id;

alter table users drop ip;
alter table users drop starting_time;
alter table users drop delay_time;
alter table users drop extra_time;
alter table users drop hidden;
alter table users drop contest_id;

select * from users limit 10;
select * from participations limit 10;
select * from questions limit 10;

rollback; -- change this to: commit;
