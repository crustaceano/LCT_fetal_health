-- Расширения (uuid и т.п.)
create extension if not exists "uuid-ossp";

-- Таблица sessions
create table if not exists sessions (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid        not null,
  dataset       varchar(16) not null check (dataset in ('hypoxia','regular')),
  study_number  integer     not null,
  started_at    timestamptz not null default now(),
  stopped_at    timestamptz,
  status        varchar(16) not null default 'starting' check (status in ('starting','running','stopped','error')),
  meta          jsonb       not null default '{}'::jsonb,
  pipeline      jsonb       not null default '{"bpm": [], "uterus": [], "window_seconds": 180}'::jsonb
);
