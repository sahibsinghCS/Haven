-- Per-user Settings + Preferences (requires Supabase Auth)
-- Run after 001_haven_room_data.sql

create table if not exists public.haven_user_data (
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('integrations', 'preferences')),
  document jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, kind)
);

create index if not exists haven_user_data_updated_at_idx
  on public.haven_user_data (updated_at desc);

alter table public.haven_user_data enable row level security;

-- Users can read/write only their own rows when using the anon key + JWT from the client.
create policy "haven_user_data_select_own"
  on public.haven_user_data for select
  using (auth.uid() = user_id);

create policy "haven_user_data_insert_own"
  on public.haven_user_data for insert
  with check (auth.uid() = user_id);

create policy "haven_user_data_update_own"
  on public.haven_user_data for update
  using (auth.uid() = user_id);

create policy "haven_user_data_delete_own"
  on public.haven_user_data for delete
  using (auth.uid() = user_id);

comment on table public.haven_user_data is
  'Per-user device connections (integrations) and mood presets (preferences).';
