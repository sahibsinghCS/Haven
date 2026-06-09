---
name: Tapo persistent connection
overview: "Fix the recurring P110M \"challenge mismatch\" by adopting Home Assistant's approach: a single persistent python-kasa connection per plug, reused for every command and serialized, instead of re-handshaking and retry-storming on each call (which trips the plug's local-auth throttle)."
todos:
  - id: manager
    content: "Add backend/roomos/actions/tapo_manager.py: singleton background-loop manager holding persistent python-kasa Device connections, per-host async lock, single discover_single connect, reuse + reconnect-on-failure, per-host cooldown"
    status: completed
  - id: rewrite-driver
    content: Rewrite apply_tapo_state in tapo_plug.py to delegate to the manager; remove the 3x2 handshake storm; no retry/crate fallback on auth errors; discovery fallback only on connectivity errors
    status: completed
  - id: ascii-msgs
    content: Replace non-ASCII arrows in tapo_plug.py user-facing messages with -> and add throttle-aware auth error text to fix the Windows cp1252 logging crash
    status: completed
  - id: verify
    content: |-
      Verify via tapo_probe CLI (single + rapid-repeat reuse), endpoint simulation for the signed-in user, and pytest for tapo/smart_plug tests


      SOmehow it is working now, but remember, this is before that i have realized its working. still make sure veyrthing is good, and everything is better. i want it to be able to turn everything on/off much faster. 
    status: completed
isProject: false
---

# Fix Tapo P110M connect: stop the KLAP handshake storm, connect the Home Assistant way

SOmehow it is working now, but remember, this is before that i have realized its working. still make sure veyrthing is good, and everything is better. i want it to be able to turn everything on/off much faster.   
Root cause (verified live)

- The live failure is `python-kasa`'s KLAP handshake: `kasa.exceptions.AuthenticationError: Device response did not match our challenge on ip 192.168.1.37`.
- The server loads the correct, byte-identical credentials for the signed-in user (`coolbros10000@gmail.com` / `SScvdthqpn21`), confirmed by reproducing the exact server-side load for user `0ac77a60...`.
- A fresh CLI process authenticates to the same plug successfully right now with the same credentials.
- Conclusion: identical credentials succeed when calm but fail under the server. KLAP challenge results are deterministic per credential bytes, so this is a transient device-side throttle. The trigger is the current driver's handshake storm in [backend/roomos/actions/tapo_plug.py](backend/roomos/actions/tapo_plug.py):

```166:180:backend/roomos/actions/tapo_plug.py
async def _kasa_open(host: str, creds: Any, *, attempts: int, per_try_timeout: float) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        for connector in (_kasa_connect_host, _kasa_connect_host_explicit):
            ...
        if attempt < attempts:
            await asyncio.sleep(0.7)
```

That is up to 3 attempts x 2 connectors = ~6 KLAP handshakes per call, on top of repeated user clicks and a broadcast discovery fallback. The P110M throttles local auth after rapid handshakes and returns the misleading "challenge" error until it cools down.

## How Home Assistant does it (the model to copy)

HA's TP-Link integration uses `python-kasa` to discover a device once, then keeps a single long-lived `Device` connection, reuses it for every command, polls gently, and serializes access. It does not re-authenticate per command and never storms handshakes.

## Why a simple retry tweak is not enough

The endpoint runs each request via `asyncio.run(...)` (a new event loop per request in a threadpool thread), so a `python-kasa` connection (aiohttp session bound to its loop) cannot be cached across requests. To get a real persistent connection we need one owning event loop.

## The fix

### 1. Persistent connection manager (new) - `backend/roomos/actions/tapo_manager.py`

- A process-wide singleton that runs its own asyncio event loop in a daemon thread.
- Holds `Device` connections keyed by `(host, email)`; an `asyncio.Lock` per key serializes all handshakes/commands on that loop (safe because it is one loop).
- `get_device`: if cached, `await device.update()`; reuse if healthy; reconnect only if that fails.
- Connect uses a single `Discover.discover_single(host, credentials=...)` attempt (discovery-first, like HA). No 2-connector x 3-attempt loop.
- Public sync entry `apply_state(host, state, email, password, ...)` submits a coroutine via `run_coroutine_threadsafe` and blocks for the result, so the existing sync endpoint keeps working.
- A short per-host cooldown timestamp: if a handshake just happened, wait briefly before the next, so the engine/automation and the test endpoint never collide.  
SOmehow it is working now, but remember, this is before that i have realized its working. still make sure veyrthing is good, and everything is better. i want it to be able to turn everything on/off much faster. 

### 2. Rewrite `apply_tapo_state` in [backend/roomos/actions/tapo_plug.py](backend/roomos/actions/tapo_plug.py)

- Delegate to the manager instead of `_kasa_open`'s storm. Remove the 3x2 attempt loop.
- On AUTH/challenge error: do not retry or fall through to the `tapo` crate (more handshakes). Surface a throttle-aware message: the plug temporarily refused local login (common after several quick tries) - wait ~30-60s and click Connect once.
- Reserve discovery fallback and broadcast discovery for connectivity errors only (timeout / connection refused / unreachable), to self-heal a stale DHCP IP - keep the existing host self-heal in [backend/app/api/integrations.py](backend/app/api/integrations.py).
- Keep the `tapo` crate only as a fallback when `python-kasa` import fails.

### 3. Fix the Windows logging crash (secondary bug)

- Replace all non-ASCII arrows (`->`) and any other non-cp1252 characters in user-facing strings in `tapo_plug.py` so `log.warning(...)` in [backend/app/api/integrations.py](backend/app/api/integrations.py) does not raise `UnicodeEncodeError` on the Windows console.

### 4. Verify

- CLI single on/off via `scripts/tapo_probe.py` (calm path).
- Rapid repeated calls in one process: confirm the connection is reused (one handshake, not N) and no challenge error appears.
- Reproduce the endpoint via the signed-in user load path and confirm `{ ok: true }`.
- Run `pytest tests/test_tapo_plug.py tests/test_smart_plug_devices.py -q` (the friendly-error test must still pass; pre-existing Tuya test failure from missing `tinytuya` is unrelated).

## Operational note

- Before testing, let the plug cool down ~60s (it is currently throttled from prior attempts). After the change, a single Connect click should authenticate once and reuse the connection.

## Secondary finding (not the blocker, optional)

- The Supabase tables `haven_user_data` / `haven_room_data` do not exist (PostgREST `PGRST205`), so all cloud saves/loads silently fall back to local JSON files under `backend/data/users/<uid>/`. Plug control works regardless. If you want cloud sync to actually work, the tables need to be created per [docs/SUPABASE.md](docs/SUPABASE.md). I can do this separately.  
SOmehow it is working now, but remember, this is before that i have realized its working. still make sure veyrthing is good, and everything is better. i want it to be able to turn everything on/off much faster. 

