-- 애프터 MVP 스키마
-- 모든 테이블은 RLS 를 켜고 정책을 만들지 않는다. 서버(service role)만 접근하고
-- 브라우저는 절대 DB 에 직접 접근하지 않는다. 익명 세션은 auth.users 의 anonymous user 다.

create extension if not exists pgcrypto;

-- 세션: auth.users(익명 로그인) 와 1:1
create table if not exists public.sessions (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  age_confirmed_at timestamptz,
  consent_at timestamptz,
  face_credits int not null default 0,
  photo_credits int not null default 0,
  current_upload_id uuid,
  current_face_generation_id uuid,
  current_photo_generation_id uuid,
  selection jsonb
);

create table if not exists public.uploads (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  kind text not null check (kind in ('front','side')),
  path text not null,
  width int not null default 0,
  height int not null default 0,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists uploads_session_idx on public.uploads(session_id);
create index if not exists uploads_expires_idx on public.uploads(expires_at);

create table if not exists public.generations (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  kind text not null check (kind in ('face','photo')),
  provider_id text not null,
  external_job_id text,
  status text not null check (status in ('queued','running','processing','done','failed')),
  prompt text not null,
  params jsonb not null default '{}'::jsonb,
  input_upload_ids uuid[] not null default '{}',
  input_generation_id uuid,
  output_paths text[] not null default '{}',
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists generations_session_idx on public.generations(session_id);
create index if not exists generations_expires_idx on public.generations(expires_at);

create table if not exists public.shares (
  id text primary key,
  session_id uuid not null references public.sessions(id) on delete cascade,
  face_generation_id uuid not null,
  photo_generation_id uuid not null,
  after_path text not null,
  photo_paths text[] not null default '{}',
  og_path text not null,
  story_paths text[] not null default '{}',
  caption text not null default '',
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists shares_session_idx on public.shares(session_id);
create index if not exists shares_expires_idx on public.shares(expires_at);

create table if not exists public.waitlist (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  session_id uuid,
  created_at timestamptz not null default now()
);

create table if not exists public.rate_limits (
  session_id uuid not null,
  key text not null,
  window_start timestamptz not null,
  count int not null default 0,
  primary key (session_id, key)
);

alter table public.sessions enable row level security;
alter table public.uploads enable row level security;
alter table public.generations enable row level security;
alter table public.shares enable row level security;
alter table public.waitlist enable row level security;
alter table public.rate_limits enable row level security;

-- 크레딧 차감 (원자적). 부족하면 false.
create or replace function public.consume_credits(p_session uuid, p_kind text, p_amount int)
returns boolean language plpgsql security definer set search_path = public as $$
declare ok boolean := false;
begin
  if p_kind = 'face' then
    update sessions set face_credits = face_credits - p_amount
      where id = p_session and face_credits >= p_amount returning true into ok;
  elsif p_kind = 'photo' then
    update sessions set photo_credits = photo_credits - p_amount
      where id = p_session and photo_credits >= p_amount returning true into ok;
  end if;
  return coalesce(ok, false);
end $$;

create or replace function public.refund_credits(p_session uuid, p_kind text, p_amount int)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_kind = 'face' then
    update sessions set face_credits = face_credits + p_amount where id = p_session;
  elsif p_kind = 'photo' then
    update sessions set photo_credits = photo_credits + p_amount where id = p_session;
  end if;
end $$;

-- 고정 윈도우 분당 제한 (원자적). allowed=false 면 retry_after 초 뒤에 다시.
create or replace function public.check_rate_limit(p_session uuid, p_key text, p_limit int, p_window_seconds int)
returns table(allowed boolean, retry_after int) language plpgsql security definer set search_path = public as $$
declare r rate_limits%rowtype;
begin
  insert into rate_limits(session_id, key, window_start, count)
    values (p_session, p_key, now(), 1)
    on conflict (session_id, key) do update
      set count = case when rate_limits.window_start + make_interval(secs => p_window_seconds) < now() then 1 else rate_limits.count + 1 end,
          window_start = case when rate_limits.window_start + make_interval(secs => p_window_seconds) < now() then now() else rate_limits.window_start end
    returning * into r;
  if r.count > p_limit then
    return query select false, greatest(1, ceil(extract(epoch from (r.window_start + make_interval(secs => p_window_seconds) - now())))::int);
  else
    return query select true, 0;
  end if;
end $$;

-- 스토리지 버킷: private(원본, 스토리 슬라이드), public(워터마크 생성물, OG)
insert into storage.buckets (id, name, public, file_size_limit)
  values ('private', 'private', false, 20971520)
  on conflict (id) do nothing;
insert into storage.buckets (id, name, public, file_size_limit)
  values ('public', 'public', true, 20971520)
  on conflict (id) do nothing;
