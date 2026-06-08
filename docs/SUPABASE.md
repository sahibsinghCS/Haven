# Supabase: Auth + cloud save

Each **signed-in user** gets their own:

- **Settings** — smart plug, lights, thermostat connections  
- **Preferences** — mood presets (fan, light, temperature)

Data is stored in `haven_user_data` keyed by `auth.users.id`.

## 1. Supabase project setup

1. Create a project at [supabase.com](https://supabase.com).
2. **Authentication → Providers → Email**: enable Email provider (confirm email optional for dev).
3. **SQL Editor** — run in order:
   - `supabase/migrations/001_haven_room_data.sql` (legacy shared room id; optional)
   - `supabase/migrations/002_haven_user_data.sql` (**required for auth**)

## 2. API keys

| Key | Where |
|-----|--------|
| Project URL | `SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL` |
| **anon** (public) | `SUPABASE_ANON_KEY` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| **service_role** (secret) | `SUPABASE_SERVICE_ROLE_KEY` in **backend/.env only** |

Never put the service role key in the Next.js app or git.

## 3. Backend `backend/.env`

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...anon...
SUPABASE_SERVICE_ROLE_KEY=eyJ...service_role...
HAVEN_REQUIRE_AUTH=true
```

## 4. Frontend `web/.env.local`

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...anon...
NEXT_PUBLIC_ROOMOS_API_BASE=http://127.0.0.1:8000
```

## 5. Run

```bash
npm run demo
```

Open the app → you are redirected to **Sign in** → create an account → **Connections** and **Preferences** save to your user.

Auth pages: `/login`, `/login/sign-up`, `/login/forgot-password`, `/auth/reset-password`.

## 6. Auth redirect URLs

In Supabase **Authentication → URL configuration**, add:

- Site URL: `http://localhost:3000`
- Redirect URLs:
  - `http://localhost:3000/auth/callback`
  - `http://localhost:3000/auth/reset-password`

## Local dev without auth

Leave Supabase env vars empty — the app skips the login gate and uses local JSON files only.
