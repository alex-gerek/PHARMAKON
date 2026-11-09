# Security notes

## Local server (`gui/server.py`, `gui/security.py`)
- Listens on `127.0.0.1:7860` only. No CORS headers are emitted.
- Every `/api/*` call needs a per-run secret token (HttpOnly, SameSite=Strict cookie set when the UI
  loads; `X-Pharmakon-Token` header for tools; the launcher reads `~/.pharmakon/session_token`).
  Only `/api/ping` is public.
- `Host` must be the local server (blocks DNS rebinding); foreign `Origin` and `Sec-Fetch-Site: cross-site` are rejected.
- File endpoints serve only audio files (`/api/stream`, `/api/download-delta`) or PHARMAKON report
  HTML (`/api/report`, `/api/open-report`); uploads accept audio only. `/api/open-report` can no longer launch arbitrary files.
- Known remaining limit: an authenticated UI session can read any audio file the user can read.

## Updates (`auto_updater.py`, `tools/release_tool.py`)
- Updates are Ed25519-signed (`release_manifest.json` + `.sig`) with per-file SHA-256, fetched from a pinned git tag, never from `master`.
- Launch only *checks*; installing needs an explicit click. Installed patches are re-verified on every load.
- Until `UPDATE_PUBLIC_KEY_B64` is set, updates are notify-only (fail closed).

### One-time setup / release
1. `python tools/release_tool.py keygen --out <path outside the repo>` and paste the printed public key into `auto_updater.py`.
2. Release: `build --version X.Y.Z` → `sign --key <private key>` → commit manifest+sig → tag `vX.Y.Z` on the same commit → push.
3. Keep the private key offline; never commit it.
