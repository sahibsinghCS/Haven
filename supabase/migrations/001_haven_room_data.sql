-- HAVEN / RoomOS cloud storage (run in Supabase SQL editor)
-- Backend uses SUPABASE_SERVICE_ROLE_KEY (server only — never expose in the browser).

create table if not exists public.haven_room_data (
  room_id text not null,
  kind text not null check (kind in ('integrations', 'preferences')),
  document jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (room_id, kind)
);

create index if not exists haven_room_data_updated_at_idx
  on public.haven_room_data (updated_at desc);

-- Optional: enable RLS for anon access later; service role bypasses RLS.
alter table public.haven_room_data enable row level security;

-- Demo policy: allow read/write for anon if you use the anon key on clients (not recommended for secrets).
-- For production, keep all reads/writes through the RoomOS API with the service role key.

comment on table public.haven_room_data is
  'Per-room Settings (integrations) and Preferences documents for HAVEN.';
