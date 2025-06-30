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


COMMIT;
