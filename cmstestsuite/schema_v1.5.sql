--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13 (Debian 15.13-1.pgdg120+1)
-- Dumped by pg_dump version 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: codename; Type: DOMAIN; Schema: public; Owner: postgres
--

CREATE DOMAIN public.codename AS character varying
	CONSTRAINT codename_check CHECK (((VALUE)::text ~ '^[A-Za-z0-9_-]+$'::text));


ALTER DOMAIN public.codename OWNER TO postgres;

--
-- Name: compilation_outcome; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.compilation_outcome AS ENUM (
    'ok',
    'fail'
);


ALTER TYPE public.compilation_outcome OWNER TO postgres;

--
-- Name: digest; Type: DOMAIN; Schema: public; Owner: postgres
--

CREATE DOMAIN public.digest AS character varying
	CONSTRAINT digest_check CHECK (((VALUE)::text ~ '^([0-9a-f]{40}|x)$'::text));


ALTER DOMAIN public.digest OWNER TO postgres;

--
-- Name: evaluation_outcome; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.evaluation_outcome AS ENUM (
    'ok'
);


ALTER TYPE public.evaluation_outcome OWNER TO postgres;

--
-- Name: feedback_level; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.feedback_level AS ENUM (
    'full',
    'restricted'
);


ALTER TYPE public.feedback_level OWNER TO postgres;

--
-- Name: filename; Type: DOMAIN; Schema: public; Owner: postgres
--

CREATE DOMAIN public.filename AS character varying
	CONSTRAINT filename_check CHECK (((VALUE)::text ~ '^[A-Za-z0-9_.-]+$'::text))
	CONSTRAINT filename_check1 CHECK (((VALUE)::text <> '.'::text))
	CONSTRAINT filename_check2 CHECK (((VALUE)::text <> '..'::text));


ALTER DOMAIN public.filename OWNER TO postgres;

--
-- Name: filename_schema; Type: DOMAIN; Schema: public; Owner: postgres
--

CREATE DOMAIN public.filename_schema AS character varying
	CONSTRAINT filename_schema_check CHECK (((VALUE)::text ~ '^[A-Za-z0-9_.-]+(.%l)?$'::text))
	CONSTRAINT filename_schema_check1 CHECK (((VALUE)::text <> '.'::text))
	CONSTRAINT filename_schema_check2 CHECK (((VALUE)::text <> '..'::text));


ALTER DOMAIN public.filename_schema OWNER TO postgres;

--
-- Name: filename_schema_array; Type: DOMAIN; Schema: public; Owner: postgres
--

CREATE DOMAIN public.filename_schema_array AS character varying[]
	CONSTRAINT filename_schema_array_check CHECK ((array_to_string(VALUE, ''::text) ~ '^[A-Za-z0-9_.%-]*$'::text))
	CONSTRAINT filename_schema_array_check1 CHECK ((array_to_string(VALUE, ','::text) ~ '^([A-Za-z0-9_.-]+(.%l)?(,|$))*$'::text))
	CONSTRAINT filename_schema_array_check2 CHECK (('.'::text <> ALL ((VALUE)::text[])))
	CONSTRAINT filename_schema_array_check3 CHECK (('..'::text <> ALL ((VALUE)::text[])));


ALTER DOMAIN public.filename_schema_array OWNER TO postgres;

--
-- Name: score_mode; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.score_mode AS ENUM (
    'max_tokened_last',
    'max',
    'max_subtask'
);


ALTER TYPE public.score_mode OWNER TO postgres;

--
-- Name: token_mode; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.token_mode AS ENUM (
    'disabled',
    'finite',
    'infinite'
);


ALTER TYPE public.token_mode OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admins; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admins (
    id integer NOT NULL,
    name character varying NOT NULL,
    username public.codename NOT NULL,
    authentication character varying NOT NULL,
    enabled boolean NOT NULL,
    permission_all boolean NOT NULL,
    permission_messaging boolean NOT NULL
);


ALTER TABLE public.admins OWNER TO postgres;

--
-- Name: admins_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admins_id_seq OWNER TO postgres;

--
-- Name: admins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admins_id_seq OWNED BY public.admins.id;


--
-- Name: announcements; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.announcements (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    subject character varying NOT NULL,
    text character varying NOT NULL,
    contest_id integer NOT NULL,
    admin_id integer
);


ALTER TABLE public.announcements OWNER TO postgres;

--
-- Name: announcements_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.announcements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.announcements_id_seq OWNER TO postgres;

--
-- Name: announcements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.announcements_id_seq OWNED BY public.announcements.id;


--
-- Name: attachments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.attachments (
    id integer NOT NULL,
    task_id integer NOT NULL,
    filename public.filename NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.attachments OWNER TO postgres;

--
-- Name: attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attachments_id_seq OWNER TO postgres;

--
-- Name: attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.attachments_id_seq OWNED BY public.attachments.id;


--
-- Name: contests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.contests (
    id integer NOT NULL,
    name public.codename NOT NULL,
    description character varying NOT NULL,
    allowed_localizations character varying[] NOT NULL,
    languages character varying[] NOT NULL,
    submissions_download_allowed boolean NOT NULL,
    allow_questions boolean NOT NULL,
    allow_user_tests boolean NOT NULL,
    block_hidden_participations boolean NOT NULL,
    allow_password_authentication boolean NOT NULL,
    allow_registration boolean NOT NULL,
    ip_restriction boolean NOT NULL,
    ip_autologin boolean NOT NULL,
    token_mode public.token_mode NOT NULL,
    token_max_number integer,
    token_min_interval interval NOT NULL,
    token_gen_initial integer NOT NULL,
    token_gen_number integer NOT NULL,
    token_gen_interval interval NOT NULL,
    token_gen_max integer,
    start timestamp without time zone NOT NULL,
    stop timestamp without time zone NOT NULL,
    analysis_enabled boolean NOT NULL,
    analysis_start timestamp without time zone NOT NULL,
    analysis_stop timestamp without time zone NOT NULL,
    timezone character varying,
    per_user_time interval,
    max_submission_number integer,
    max_user_test_number integer,
    min_submission_interval interval,
    min_user_test_interval interval,
    score_precision integer NOT NULL,
    CONSTRAINT contests_check CHECK ((start <= stop)),
    CONSTRAINT contests_check1 CHECK ((stop <= analysis_start)),
    CONSTRAINT contests_check2 CHECK ((analysis_start <= analysis_stop)),
    CONSTRAINT contests_check3 CHECK ((token_gen_initial <= token_gen_max)),
    CONSTRAINT contests_max_submission_number_check CHECK ((max_submission_number > 0)),
    CONSTRAINT contests_max_user_test_number_check CHECK ((max_user_test_number > 0)),
    CONSTRAINT contests_min_submission_interval_check CHECK ((min_submission_interval > '00:00:00'::interval)),
    CONSTRAINT contests_min_user_test_interval_check CHECK ((min_user_test_interval > '00:00:00'::interval)),
    CONSTRAINT contests_per_user_time_check CHECK ((per_user_time >= '00:00:00'::interval)),
    CONSTRAINT contests_score_precision_check CHECK ((score_precision >= 0)),
    CONSTRAINT contests_token_gen_initial_check CHECK ((token_gen_initial >= 0)),
    CONSTRAINT contests_token_gen_interval_check CHECK ((token_gen_interval > '00:00:00'::interval)),
    CONSTRAINT contests_token_gen_max_check CHECK ((token_gen_max > 0)),
    CONSTRAINT contests_token_gen_number_check CHECK ((token_gen_number >= 0)),
    CONSTRAINT contests_token_max_number_check CHECK ((token_max_number > 0)),
    CONSTRAINT contests_token_min_interval_check CHECK ((token_min_interval >= '00:00:00'::interval))
);


ALTER TABLE public.contests OWNER TO postgres;

--
-- Name: contests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.contests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.contests_id_seq OWNER TO postgres;

--
-- Name: contests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.contests_id_seq OWNED BY public.contests.id;


--
-- Name: datasets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.datasets (
    id integer NOT NULL,
    task_id integer NOT NULL,
    description character varying NOT NULL,
    autojudge boolean NOT NULL,
    time_limit double precision,
    memory_limit bigint,
    task_type character varying NOT NULL,
    task_type_parameters jsonb NOT NULL,
    score_type character varying NOT NULL,
    score_type_parameters jsonb NOT NULL,
    CONSTRAINT datasets_memory_limit_check CHECK ((memory_limit > 0)),
    CONSTRAINT datasets_memory_limit_check1 CHECK ((mod(memory_limit, (1048576)::bigint) = 0)),
    CONSTRAINT datasets_time_limit_check CHECK ((time_limit > (0)::double precision))
);


ALTER TABLE public.datasets OWNER TO postgres;

--
-- Name: datasets_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.datasets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.datasets_id_seq OWNER TO postgres;

--
-- Name: datasets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.datasets_id_seq OWNED BY public.datasets.id;


--
-- Name: evaluations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.evaluations (
    id integer NOT NULL,
    submission_id integer NOT NULL,
    dataset_id integer NOT NULL,
    testcase_id integer NOT NULL,
    outcome character varying,
    text character varying[] NOT NULL,
    execution_time double precision,
    execution_wall_clock_time double precision,
    execution_memory bigint,
    evaluation_shard integer,
    evaluation_sandbox character varying
);


ALTER TABLE public.evaluations OWNER TO postgres;

--
-- Name: evaluations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.evaluations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.evaluations_id_seq OWNER TO postgres;

--
-- Name: evaluations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.evaluations_id_seq OWNED BY public.evaluations.id;


--
-- Name: executables; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.executables (
    id integer NOT NULL,
    submission_id integer NOT NULL,
    dataset_id integer NOT NULL,
    filename public.filename NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.executables OWNER TO postgres;

--
-- Name: executables_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.executables_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.executables_id_seq OWNER TO postgres;

--
-- Name: executables_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.executables_id_seq OWNED BY public.executables.id;


--
-- Name: files; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.files (
    id integer NOT NULL,
    submission_id integer NOT NULL,
    filename public.filename_schema NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.files OWNER TO postgres;

--
-- Name: files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.files_id_seq OWNER TO postgres;

--
-- Name: files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.files_id_seq OWNED BY public.files.id;


--
-- Name: fsobjects; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fsobjects (
    digest character varying NOT NULL,
    loid oid NOT NULL,
    description character varying
);


ALTER TABLE public.fsobjects OWNER TO postgres;

--
-- Name: managers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.managers (
    id integer NOT NULL,
    dataset_id integer NOT NULL,
    filename public.filename NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.managers OWNER TO postgres;

--
-- Name: managers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.managers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.managers_id_seq OWNER TO postgres;

--
-- Name: managers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.managers_id_seq OWNED BY public.managers.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    subject character varying NOT NULL,
    text character varying NOT NULL,
    participation_id integer NOT NULL,
    admin_id integer
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.messages_id_seq OWNER TO postgres;

--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: participations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.participations (
    id integer NOT NULL,
    ip cidr[],
    starting_time timestamp without time zone,
    delay_time interval NOT NULL,
    extra_time interval NOT NULL,
    password character varying,
    hidden boolean NOT NULL,
    unrestricted boolean NOT NULL,
    contest_id integer NOT NULL,
    user_id integer NOT NULL,
    team_id integer,
    CONSTRAINT participations_delay_time_check CHECK ((delay_time >= '00:00:00'::interval)),
    CONSTRAINT participations_extra_time_check CHECK ((extra_time >= '00:00:00'::interval))
);


ALTER TABLE public.participations OWNER TO postgres;

--
-- Name: participations_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.participations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.participations_id_seq OWNER TO postgres;

--
-- Name: participations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.participations_id_seq OWNED BY public.participations.id;


--
-- Name: printjobs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.printjobs (
    id integer NOT NULL,
    participation_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    filename public.filename NOT NULL,
    digest public.digest NOT NULL,
    done boolean NOT NULL,
    status character varying[] NOT NULL
);


ALTER TABLE public.printjobs OWNER TO postgres;

--
-- Name: printjobs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.printjobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.printjobs_id_seq OWNER TO postgres;

--
-- Name: printjobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.printjobs_id_seq OWNED BY public.printjobs.id;


--
-- Name: questions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.questions (
    id integer NOT NULL,
    question_timestamp timestamp without time zone NOT NULL,
    subject character varying NOT NULL,
    text character varying NOT NULL,
    reply_timestamp timestamp without time zone,
    ignored boolean NOT NULL,
    reply_subject character varying,
    reply_text character varying,
    participation_id integer NOT NULL,
    admin_id integer
);


ALTER TABLE public.questions OWNER TO postgres;

--
-- Name: questions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.questions_id_seq OWNER TO postgres;

--
-- Name: questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.questions_id_seq OWNED BY public.questions.id;


--
-- Name: statements; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.statements (
    id integer NOT NULL,
    task_id integer NOT NULL,
    language character varying NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.statements OWNER TO postgres;

--
-- Name: statements_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.statements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.statements_id_seq OWNER TO postgres;

--
-- Name: statements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.statements_id_seq OWNED BY public.statements.id;


--
-- Name: submission_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.submission_results (
    submission_id integer NOT NULL,
    dataset_id integer NOT NULL,
    compilation_outcome public.compilation_outcome,
    compilation_text character varying[] NOT NULL,
    compilation_tries integer NOT NULL,
    compilation_stdout character varying,
    compilation_stderr character varying,
    compilation_time double precision,
    compilation_wall_clock_time double precision,
    compilation_memory bigint,
    compilation_shard integer,
    compilation_sandbox character varying,
    evaluation_outcome public.evaluation_outcome,
    evaluation_tries integer NOT NULL,
    score double precision,
    score_details jsonb,
    public_score double precision,
    public_score_details jsonb,
    ranking_score_details character varying[]
);


ALTER TABLE public.submission_results OWNER TO postgres;

--
-- Name: submissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.submissions (
    id integer NOT NULL,
    participation_id integer NOT NULL,
    task_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    language character varying,
    comment character varying NOT NULL,
    official boolean NOT NULL
);


ALTER TABLE public.submissions OWNER TO postgres;

--
-- Name: submissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.submissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.submissions_id_seq OWNER TO postgres;

--
-- Name: submissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.submissions_id_seq OWNED BY public.submissions.id;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tasks (
    id integer NOT NULL,
    num integer,
    contest_id integer,
    name public.codename NOT NULL,
    title character varying NOT NULL,
    submission_format public.filename_schema_array NOT NULL,
    primary_statements character varying[] NOT NULL,
    token_mode public.token_mode NOT NULL,
    token_max_number integer,
    token_min_interval interval NOT NULL,
    token_gen_initial integer NOT NULL,
    token_gen_number integer NOT NULL,
    token_gen_interval interval NOT NULL,
    token_gen_max integer,
    max_submission_number integer,
    max_user_test_number integer,
    min_submission_interval interval,
    min_user_test_interval interval,
    feedback_level public.feedback_level NOT NULL,
    score_precision integer NOT NULL,
    score_mode public.score_mode NOT NULL,
    active_dataset_id integer,
    CONSTRAINT tasks_check CHECK ((token_gen_initial <= token_gen_max)),
    CONSTRAINT tasks_max_submission_number_check CHECK ((max_submission_number > 0)),
    CONSTRAINT tasks_max_user_test_number_check CHECK ((max_user_test_number > 0)),
    CONSTRAINT tasks_min_submission_interval_check CHECK ((min_submission_interval > '00:00:00'::interval)),
    CONSTRAINT tasks_min_user_test_interval_check CHECK ((min_user_test_interval > '00:00:00'::interval)),
    CONSTRAINT tasks_score_precision_check CHECK ((score_precision >= 0)),
    CONSTRAINT tasks_token_gen_initial_check CHECK ((token_gen_initial >= 0)),
    CONSTRAINT tasks_token_gen_interval_check CHECK ((token_gen_interval > '00:00:00'::interval)),
    CONSTRAINT tasks_token_gen_max_check CHECK ((token_gen_max > 0)),
    CONSTRAINT tasks_token_gen_number_check CHECK ((token_gen_number >= 0)),
    CONSTRAINT tasks_token_max_number_check CHECK ((token_max_number > 0)),
    CONSTRAINT tasks_token_min_interval_check CHECK ((token_min_interval >= '00:00:00'::interval))
);


ALTER TABLE public.tasks OWNER TO postgres;

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tasks_id_seq OWNER TO postgres;

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tasks_id_seq OWNED BY public.tasks.id;


--
-- Name: teams; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.teams (
    id integer NOT NULL,
    code public.codename NOT NULL,
    name character varying NOT NULL
);


ALTER TABLE public.teams OWNER TO postgres;

--
-- Name: teams_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.teams_id_seq OWNER TO postgres;

--
-- Name: teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.teams_id_seq OWNED BY public.teams.id;


--
-- Name: testcases; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.testcases (
    id integer NOT NULL,
    dataset_id integer NOT NULL,
    codename public.codename NOT NULL,
    public boolean NOT NULL,
    input public.digest NOT NULL,
    output public.digest NOT NULL
);


ALTER TABLE public.testcases OWNER TO postgres;

--
-- Name: testcases_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.testcases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.testcases_id_seq OWNER TO postgres;

--
-- Name: testcases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.testcases_id_seq OWNED BY public.testcases.id;


--
-- Name: tokens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tokens (
    id integer NOT NULL,
    submission_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL
);


ALTER TABLE public.tokens OWNER TO postgres;

--
-- Name: tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tokens_id_seq OWNER TO postgres;

--
-- Name: tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tokens_id_seq OWNED BY public.tokens.id;


--
-- Name: user_test_executables; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_test_executables (
    id integer NOT NULL,
    user_test_id integer NOT NULL,
    dataset_id integer NOT NULL,
    filename public.filename NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.user_test_executables OWNER TO postgres;

--
-- Name: user_test_executables_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_test_executables_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_test_executables_id_seq OWNER TO postgres;

--
-- Name: user_test_executables_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_test_executables_id_seq OWNED BY public.user_test_executables.id;


--
-- Name: user_test_files; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_test_files (
    id integer NOT NULL,
    user_test_id integer NOT NULL,
    filename public.filename_schema NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.user_test_files OWNER TO postgres;

--
-- Name: user_test_files_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_test_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_test_files_id_seq OWNER TO postgres;

--
-- Name: user_test_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_test_files_id_seq OWNED BY public.user_test_files.id;


--
-- Name: user_test_managers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_test_managers (
    id integer NOT NULL,
    user_test_id integer NOT NULL,
    filename public.filename NOT NULL,
    digest public.digest NOT NULL
);


ALTER TABLE public.user_test_managers OWNER TO postgres;

--
-- Name: user_test_managers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_test_managers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_test_managers_id_seq OWNER TO postgres;

--
-- Name: user_test_managers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_test_managers_id_seq OWNED BY public.user_test_managers.id;


--
-- Name: user_test_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_test_results (
    user_test_id integer NOT NULL,
    dataset_id integer NOT NULL,
    output public.digest,
    compilation_outcome character varying,
    compilation_text character varying[] NOT NULL,
    compilation_tries integer NOT NULL,
    compilation_stdout character varying,
    compilation_stderr character varying,
    compilation_time double precision,
    compilation_wall_clock_time double precision,
    compilation_memory bigint,
    compilation_shard integer,
    compilation_sandbox character varying,
    evaluation_outcome character varying,
    evaluation_text character varying[] NOT NULL,
    evaluation_tries integer NOT NULL,
    execution_time double precision,
    execution_wall_clock_time double precision,
    execution_memory bigint,
    evaluation_shard integer,
    evaluation_sandbox character varying
);


ALTER TABLE public.user_test_results OWNER TO postgres;

--
-- Name: user_tests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_tests (
    id integer NOT NULL,
    participation_id integer NOT NULL,
    task_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    language character varying,
    input public.digest NOT NULL
);


ALTER TABLE public.user_tests OWNER TO postgres;

--
-- Name: user_tests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_tests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_tests_id_seq OWNER TO postgres;

--
-- Name: user_tests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_tests_id_seq OWNED BY public.user_tests.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    first_name character varying NOT NULL,
    last_name character varying NOT NULL,
    username public.codename NOT NULL,
    password character varying NOT NULL,
    email character varying,
    timezone character varying,
    preferred_languages character varying[] NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: admins id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins ALTER COLUMN id SET DEFAULT nextval('public.admins_id_seq'::regclass);


--
-- Name: announcements id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements ALTER COLUMN id SET DEFAULT nextval('public.announcements_id_seq'::regclass);


--
-- Name: attachments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments ALTER COLUMN id SET DEFAULT nextval('public.attachments_id_seq'::regclass);


--
-- Name: contests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contests ALTER COLUMN id SET DEFAULT nextval('public.contests_id_seq'::regclass);


--
-- Name: datasets id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.datasets ALTER COLUMN id SET DEFAULT nextval('public.datasets_id_seq'::regclass);


--
-- Name: evaluations id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations ALTER COLUMN id SET DEFAULT nextval('public.evaluations_id_seq'::regclass);


--
-- Name: executables id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.executables ALTER COLUMN id SET DEFAULT nextval('public.executables_id_seq'::regclass);


--
-- Name: files id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files ALTER COLUMN id SET DEFAULT nextval('public.files_id_seq'::regclass);


--
-- Name: managers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.managers ALTER COLUMN id SET DEFAULT nextval('public.managers_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: participations id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participations ALTER COLUMN id SET DEFAULT nextval('public.participations_id_seq'::regclass);


--
-- Name: printjobs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.printjobs ALTER COLUMN id SET DEFAULT nextval('public.printjobs_id_seq'::regclass);


--
-- Name: questions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.questions ALTER COLUMN id SET DEFAULT nextval('public.questions_id_seq'::regclass);


--
-- Name: statements id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.statements ALTER COLUMN id SET DEFAULT nextval('public.statements_id_seq'::regclass);


--
-- Name: submissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions ALTER COLUMN id SET DEFAULT nextval('public.submissions_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks ALTER COLUMN id SET DEFAULT nextval('public.tasks_id_seq'::regclass);


--
-- Name: teams id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams ALTER COLUMN id SET DEFAULT nextval('public.teams_id_seq'::regclass);


--
-- Name: testcases id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.testcases ALTER COLUMN id SET DEFAULT nextval('public.testcases_id_seq'::regclass);


--
-- Name: tokens id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tokens ALTER COLUMN id SET DEFAULT nextval('public.tokens_id_seq'::regclass);


--
-- Name: user_test_executables id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_executables ALTER COLUMN id SET DEFAULT nextval('public.user_test_executables_id_seq'::regclass);


--
-- Name: user_test_files id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_files ALTER COLUMN id SET DEFAULT nextval('public.user_test_files_id_seq'::regclass);


--
-- Name: user_test_managers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_managers ALTER COLUMN id SET DEFAULT nextval('public.user_test_managers_id_seq'::regclass);


--
-- Name: user_tests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_tests ALTER COLUMN id SET DEFAULT nextval('public.user_tests_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (id);


--
-- Name: admins admins_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_username_key UNIQUE (username);


--
-- Name: announcements announcements_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (id);


--
-- Name: attachments attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_pkey PRIMARY KEY (id);


--
-- Name: attachments attachments_task_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_task_id_filename_key UNIQUE (task_id, filename);


--
-- Name: contests contests_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contests
    ADD CONSTRAINT contests_name_key UNIQUE (name);


--
-- Name: contests contests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contests
    ADD CONSTRAINT contests_pkey PRIMARY KEY (id);


--
-- Name: datasets datasets_id_task_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.datasets
    ADD CONSTRAINT datasets_id_task_id_key UNIQUE (id, task_id);


--
-- Name: datasets datasets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.datasets
    ADD CONSTRAINT datasets_pkey PRIMARY KEY (id);


--
-- Name: datasets datasets_task_id_description_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.datasets
    ADD CONSTRAINT datasets_task_id_description_key UNIQUE (task_id, description);


--
-- Name: evaluations evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_pkey PRIMARY KEY (id);


--
-- Name: evaluations evaluations_submission_id_dataset_id_testcase_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_submission_id_dataset_id_testcase_id_key UNIQUE (submission_id, dataset_id, testcase_id);


--
-- Name: executables executables_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.executables
    ADD CONSTRAINT executables_pkey PRIMARY KEY (id);


--
-- Name: executables executables_submission_id_dataset_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.executables
    ADD CONSTRAINT executables_submission_id_dataset_id_filename_key UNIQUE (submission_id, dataset_id, filename);


--
-- Name: files files_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- Name: files files_submission_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_submission_id_filename_key UNIQUE (submission_id, filename);


--
-- Name: fsobjects fsobjects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fsobjects
    ADD CONSTRAINT fsobjects_pkey PRIMARY KEY (digest);


--
-- Name: managers managers_dataset_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.managers
    ADD CONSTRAINT managers_dataset_id_filename_key UNIQUE (dataset_id, filename);


--
-- Name: managers managers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.managers
    ADD CONSTRAINT managers_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: participations participations_contest_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participations
    ADD CONSTRAINT participations_contest_id_user_id_key UNIQUE (contest_id, user_id);


--
-- Name: participations participations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participations
    ADD CONSTRAINT participations_pkey PRIMARY KEY (id);


--
-- Name: printjobs printjobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.printjobs
    ADD CONSTRAINT printjobs_pkey PRIMARY KEY (id);


--
-- Name: questions questions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_pkey PRIMARY KEY (id);


--
-- Name: statements statements_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.statements
    ADD CONSTRAINT statements_pkey PRIMARY KEY (id);


--
-- Name: statements statements_task_id_language_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.statements
    ADD CONSTRAINT statements_task_id_language_key UNIQUE (task_id, language);


--
-- Name: submission_results submission_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_pkey PRIMARY KEY (submission_id, dataset_id);


--
-- Name: submissions submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_contest_id_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_contest_id_name_key UNIQUE (contest_id, name);


--
-- Name: tasks tasks_contest_id_num_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_contest_id_num_key UNIQUE (contest_id, num);


--
-- Name: tasks tasks_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_name_key UNIQUE (name);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: teams teams_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_code_key UNIQUE (code);


--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (id);


--
-- Name: testcases testcases_dataset_id_codename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.testcases
    ADD CONSTRAINT testcases_dataset_id_codename_key UNIQUE (dataset_id, codename);


--
-- Name: testcases testcases_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.testcases
    ADD CONSTRAINT testcases_pkey PRIMARY KEY (id);


--
-- Name: tokens tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tokens
    ADD CONSTRAINT tokens_pkey PRIMARY KEY (id);


--
-- Name: tokens tokens_submission_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tokens
    ADD CONSTRAINT tokens_submission_id_key UNIQUE (submission_id);


--
-- Name: user_test_executables user_test_executables_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_executables
    ADD CONSTRAINT user_test_executables_pkey PRIMARY KEY (id);


--
-- Name: user_test_executables user_test_executables_user_test_id_dataset_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_executables
    ADD CONSTRAINT user_test_executables_user_test_id_dataset_id_filename_key UNIQUE (user_test_id, dataset_id, filename);


--
-- Name: user_test_files user_test_files_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_files
    ADD CONSTRAINT user_test_files_pkey PRIMARY KEY (id);


--
-- Name: user_test_files user_test_files_user_test_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_files
    ADD CONSTRAINT user_test_files_user_test_id_filename_key UNIQUE (user_test_id, filename);


--
-- Name: user_test_managers user_test_managers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_managers
    ADD CONSTRAINT user_test_managers_pkey PRIMARY KEY (id);


--
-- Name: user_test_managers user_test_managers_user_test_id_filename_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_managers
    ADD CONSTRAINT user_test_managers_user_test_id_filename_key UNIQUE (user_test_id, filename);


--
-- Name: user_test_results user_test_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_results
    ADD CONSTRAINT user_test_results_pkey PRIMARY KEY (user_test_id, dataset_id);


--
-- Name: user_tests user_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_tests
    ADD CONSTRAINT user_tests_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: ix_announcements_admin_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_announcements_admin_id ON public.announcements USING btree (admin_id);


--
-- Name: ix_announcements_contest_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_announcements_contest_id ON public.announcements USING btree (contest_id);


--
-- Name: ix_attachments_task_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_attachments_task_id ON public.attachments USING btree (task_id);


--
-- Name: ix_evaluations_dataset_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_evaluations_dataset_id ON public.evaluations USING btree (dataset_id);


--
-- Name: ix_evaluations_submission_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_evaluations_submission_id ON public.evaluations USING btree (submission_id);


--
-- Name: ix_evaluations_testcase_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_evaluations_testcase_id ON public.evaluations USING btree (testcase_id);


--
-- Name: ix_executables_dataset_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_executables_dataset_id ON public.executables USING btree (dataset_id);


--
-- Name: ix_executables_submission_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_executables_submission_id ON public.executables USING btree (submission_id);


--
-- Name: ix_files_submission_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_files_submission_id ON public.files USING btree (submission_id);


--
-- Name: ix_managers_dataset_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_managers_dataset_id ON public.managers USING btree (dataset_id);


--
-- Name: ix_messages_admin_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_messages_admin_id ON public.messages USING btree (admin_id);


--
-- Name: ix_messages_participation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_messages_participation_id ON public.messages USING btree (participation_id);


--
-- Name: ix_participations_contest_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_participations_contest_id ON public.participations USING btree (contest_id);


--
-- Name: ix_participations_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_participations_user_id ON public.participations USING btree (user_id);


--
-- Name: ix_printjobs_participation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_printjobs_participation_id ON public.printjobs USING btree (participation_id);


--
-- Name: ix_questions_admin_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_questions_admin_id ON public.questions USING btree (admin_id);


--
-- Name: ix_questions_participation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_questions_participation_id ON public.questions USING btree (participation_id);


--
-- Name: ix_statements_task_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_statements_task_id ON public.statements USING btree (task_id);


--
-- Name: ix_submissions_participation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_submissions_participation_id ON public.submissions USING btree (participation_id);


--
-- Name: ix_submissions_task_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_submissions_task_id ON public.submissions USING btree (task_id);


--
-- Name: ix_tasks_contest_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tasks_contest_id ON public.tasks USING btree (contest_id);


--
-- Name: ix_testcases_dataset_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_testcases_dataset_id ON public.testcases USING btree (dataset_id);


--
-- Name: ix_tokens_submission_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tokens_submission_id ON public.tokens USING btree (submission_id);


--
-- Name: ix_user_test_executables_dataset_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_test_executables_dataset_id ON public.user_test_executables USING btree (dataset_id);


--
-- Name: ix_user_test_executables_user_test_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_test_executables_user_test_id ON public.user_test_executables USING btree (user_test_id);


--
-- Name: ix_user_test_files_user_test_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_test_files_user_test_id ON public.user_test_files USING btree (user_test_id);


--
-- Name: ix_user_test_managers_user_test_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_test_managers_user_test_id ON public.user_test_managers USING btree (user_test_id);


--
-- Name: ix_user_tests_participation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_tests_participation_id ON public.user_tests USING btree (participation_id);


--
-- Name: ix_user_tests_task_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_user_tests_task_id ON public.user_tests USING btree (task_id);


--
-- Name: announcements announcements_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: announcements announcements_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: attachments attachments_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: datasets datasets_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.datasets
    ADD CONSTRAINT datasets_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: evaluations evaluations_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: evaluations evaluations_submission_id_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_submission_id_dataset_id_fkey FOREIGN KEY (submission_id, dataset_id) REFERENCES public.submission_results(submission_id, dataset_id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: evaluations evaluations_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: evaluations evaluations_testcase_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evaluations
    ADD CONSTRAINT evaluations_testcase_id_fkey FOREIGN KEY (testcase_id) REFERENCES public.testcases(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: executables executables_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.executables
    ADD CONSTRAINT executables_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: executables executables_submission_id_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.executables
    ADD CONSTRAINT executables_submission_id_dataset_id_fkey FOREIGN KEY (submission_id, dataset_id) REFERENCES public.submission_results(submission_id, dataset_id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: executables executables_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.executables
    ADD CONSTRAINT executables_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: files files_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: tasks fk_active_dataset_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT fk_active_dataset_id FOREIGN KEY (id, active_dataset_id) REFERENCES public.datasets(task_id, id) ON UPDATE SET NULL ON DELETE SET NULL;


--
-- Name: managers managers_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.managers
    ADD CONSTRAINT managers_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: messages messages_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: messages messages_participation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_participation_id_fkey FOREIGN KEY (participation_id) REFERENCES public.participations(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: participations participations_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participations
    ADD CONSTRAINT participations_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: participations participations_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participations
    ADD CONSTRAINT participations_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: participations participations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participations
    ADD CONSTRAINT participations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: printjobs printjobs_participation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.printjobs
    ADD CONSTRAINT printjobs_participation_id_fkey FOREIGN KEY (participation_id) REFERENCES public.participations(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: questions questions_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: questions questions_participation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.questions
    ADD CONSTRAINT questions_participation_id_fkey FOREIGN KEY (participation_id) REFERENCES public.participations(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: statements statements_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.statements
    ADD CONSTRAINT statements_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: submission_results submission_results_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: submission_results submission_results_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: submissions submissions_participation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_participation_id_fkey FOREIGN KEY (participation_id) REFERENCES public.participations(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: submissions submissions_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: tasks tasks_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: testcases testcases_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.testcases
    ADD CONSTRAINT testcases_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: tokens tokens_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tokens
    ADD CONSTRAINT tokens_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_executables user_test_executables_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_executables
    ADD CONSTRAINT user_test_executables_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_executables user_test_executables_user_test_id_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_executables
    ADD CONSTRAINT user_test_executables_user_test_id_dataset_id_fkey FOREIGN KEY (user_test_id, dataset_id) REFERENCES public.user_test_results(user_test_id, dataset_id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_executables user_test_executables_user_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_executables
    ADD CONSTRAINT user_test_executables_user_test_id_fkey FOREIGN KEY (user_test_id) REFERENCES public.user_tests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_files user_test_files_user_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_files
    ADD CONSTRAINT user_test_files_user_test_id_fkey FOREIGN KEY (user_test_id) REFERENCES public.user_tests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_managers user_test_managers_user_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_managers
    ADD CONSTRAINT user_test_managers_user_test_id_fkey FOREIGN KEY (user_test_id) REFERENCES public.user_tests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_results user_test_results_dataset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_results
    ADD CONSTRAINT user_test_results_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES public.datasets(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_test_results user_test_results_user_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_test_results
    ADD CONSTRAINT user_test_results_user_test_id_fkey FOREIGN KEY (user_test_id) REFERENCES public.user_tests(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_tests user_tests_participation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_tests
    ADD CONSTRAINT user_tests_participation_id_fkey FOREIGN KEY (participation_id) REFERENCES public.participations(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_tests user_tests_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_tests
    ADD CONSTRAINT user_tests_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

