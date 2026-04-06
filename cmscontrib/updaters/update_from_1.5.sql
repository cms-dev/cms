BEGIN;

-- https://github.com/cms-dev/cms/pull/1378
ALTER TYPE public.feedback_level ADD VALUE 'oi_restricted';

-- https://github.com/cms-dev/cms/pull/1391
ALTER TABLE public.contests ADD COLUMN min_submission_interval_grace_period interval;
ALTER TABLE public.contests ADD CONSTRAINT contests_min_submission_interval_grace_period_check CHECK ((min_submission_interval_grace_period > '00:00:00'::interval));

-- https://github.com/cms-dev/cms/pull/1392
ALTER TABLE public.contests ADD COLUMN allow_unofficial_submission_before_analysis_mode boolean NOT NULL DEFAULT false;
ALTER TABLE public.contests ALTER COLUMN allow_unofficial_submission_before_analysis_mode DROP DEFAULT;

-- https://github.com/cms-dev/cms/pull/1393
ALTER TABLE public.submission_results ADD COLUMN scored_at timestamp without time zone;

-- https://github.com/cms-dev/cms/pull/1416
ALTER TABLE ONLY public.participations DROP CONSTRAINT participations_team_id_fkey;
ALTER TABLE ONLY public.participations ADD CONSTRAINT participations_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON UPDATE CASCADE ON DELETE SET NULL;

-- https://github.com/cms-dev/cms/pull/1419
ALTER TABLE submissions ADD COLUMN opaque_id BIGINT;
UPDATE submissions SET opaque_id = id WHERE opaque_id IS NULL;
ALTER TABLE submissions ADD CONSTRAINT participation_opaque_unique UNIQUE (participation_id, opaque_id);
ALTER TABLE submissions ALTER COLUMN opaque_id SET NOT NULL;

-- https://github.com/cms-dev/cms/pull/1456
ALTER TABLE submission_results ADD COLUMN compilation_sandbox_paths VARCHAR[];
ALTER TABLE submission_results ADD COLUMN compilation_sandbox_digests VARCHAR[];
UPDATE submission_results SET compilation_sandbox_paths = string_to_array(compilation_sandbox, ':');
ALTER TABLE submission_results DROP COLUMN compilation_sandbox;
ALTER TABLE evaluations ADD COLUMN evaluation_sandbox_paths VARCHAR[];
ALTER TABLE evaluations ADD COLUMN evaluation_sandbox_digests VARCHAR[];
UPDATE evaluations SET evaluation_sandbox_paths = string_to_array(evaluation_sandbox, ':');
ALTER TABLE evaluations DROP COLUMN evaluation_sandbox;
ALTER TABLE user_test_results ADD COLUMN compilation_sandbox_paths VARCHAR[];
ALTER TABLE user_test_results ADD COLUMN compilation_sandbox_digests VARCHAR[];
UPDATE user_test_results SET compilation_sandbox_paths = string_to_array(compilation_sandbox, ':');
ALTER TABLE user_test_results DROP COLUMN compilation_sandbox;
ALTER TABLE user_test_results ADD COLUMN evaluation_sandbox_paths VARCHAR[];
ALTER TABLE user_test_results ADD COLUMN evaluation_sandbox_digests VARCHAR[];
UPDATE user_test_results SET evaluation_sandbox_paths = string_to_array(evaluation_sandbox, ':');
ALTER TABLE user_test_results DROP COLUMN evaluation_sandbox;

-- https://github.com/cms-dev/cms/pull/1476
ALTER TABLE contests ADD COLUMN show_task_scores_in_overview boolean NOT NULL DEFAULT true;
ALTER TABLE contests ADD COLUMN show_task_scores_in_sidebar boolean NOT NULL DEFAULT true;
ALTER TABLE contests ALTER COLUMN show_task_scores_in_overview DROP DEFAULT;
ALTER TABLE contests ALTER COLUMN show_task_scores_in_sidebar DROP DEFAULT;

-- https://github.com/cms-dev/cms/pull/1486
ALTER TABLE public.tasks ADD COLUMN allowed_languages varchar[];

-- https://github.com/cms-dev/cms/pull/1583
DROP TABLE public.printjobs;

-- https://github.com/cms-dev/cms/pull/1642
ALTER TABLE evaluations ADD COLUMN admin_text VARCHAR;

-- https://github.com/cms-dev/cms/pull/1621
CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    name varchar NOT NULL,
    start timestamp without time zone NOT NULL,
    stop timestamp without time zone NOT NULL,
    analysis_enabled boolean NOT NULL,
    analysis_start timestamp without time zone NOT NULL,
    analysis_stop timestamp without time zone NOT NULL,
    per_user_time interval,
    contest_id integer NOT NULL,
    CONSTRAINT groups_check CHECK ((start <= stop)),
    CONSTRAINT groups_check1 CHECK ((stop <= analysis_start)),
    CONSTRAINT groups_check2 CHECK ((analysis_start <= analysis_stop)),
    CONSTRAINT groups_per_user_time_check CHECK ((per_user_time >= '00:00:00'::interval)),
    UNIQUE (contest_id, name),
    UNIQUE (id, contest_id)
);
-- create one group for each contest, make it the main group, and move all participants into it.
INSERT INTO groups (contest_id, name, start, stop, analysis_enabled, analysis_start, analysis_stop, per_user_time)
    SELECT id, 'default', start, stop, analysis_enabled, analysis_start, analysis_stop, per_user_time FROM contests;
ALTER TABLE contests ADD COLUMN main_group_id INTEGER;
UPDATE contests SET main_group_id = (SELECT id FROM groups WHERE groups.contest_id = contests.id);
ALTER TABLE participations ADD COLUMN group_id INTEGER;
UPDATE participations SET group_id = (SELECT id FROM groups WHERE groups.contest_id = participations.contest_id);
ALTER TABLE participations ALTER COLUMN group_id SET NOT NULL;

CREATE INDEX ix_contests_main_group_id ON contests USING btree (main_group_id);
CREATE INDEX ix_groups_contest_id ON groups USING btree (contest_id);
CREATE INDEX ix_participations_group_id ON participations USING btree (group_id);

ALTER TABLE contests ADD CONSTRAINT fk_contest_main_group_id
    FOREIGN KEY (main_group_id) REFERENCES groups(id) ON UPDATE CASCADE ON DELETE SET NULL;
ALTER TABLE groups ADD CONSTRAINT groups_contest_id_fkey
    FOREIGN KEY (contest_id) REFERENCES contests(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE participations ADD CONSTRAINT participations_group_id_contest_id_fkey
    FOREIGN KEY (group_id, contest_id) REFERENCES groups(id, contest_id);
ALTER TABLE participations ADD CONSTRAINT participations_group_id_fkey
    FOREIGN KEY (group_id) REFERENCES groups(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE contests DROP CONSTRAINT contests_check;
ALTER TABLE contests DROP CONSTRAINT contests_check1;
ALTER TABLE contests DROP CONSTRAINT contests_check2;
ALTER TABLE contests RENAME CONSTRAINT contests_check3 TO contests_check;

ALTER TABLE contests DROP COLUMN start;
ALTER TABLE contests DROP COLUMN stop;
ALTER TABLE contests DROP COLUMN analysis_enabled;
ALTER TABLE contests DROP COLUMN analysis_start;
ALTER TABLE contests DROP COLUMN analysis_stop;

COMMIT;
