# TODO

## Upgrade SQLite to ≥3.51.3 to close the WAL-reset corruption bug

On 2026-04-19 the production database corrupted with `database disk image is
malformed` (recovered via `sqlite3 .recover` on 2026-04-26). Root cause was a
two-part interaction:

1. **SQLite WAL-reset bug** (introduced 3.7.0, fixed in **3.51.3** released
   2026-03-13). Triggered when two or more connections on the same file
   write/checkpoint simultaneously. The scheduler runs 4 worker threads with
   their own Django connections, plus gunicorn — exactly the trigger pattern.
2. **`PRAGMA mmap_size=128MB`** amplified a transient WAL inconsistency into
   structural corruption (`Child page depth differs`, `2nd reference to page X`
   — classic mmap-spread signatures). SQLite docs explicitly warn against mmap
   with multi-process writers.

Mitigations already applied (commit `dca4328`): dropped `mmap_size`, reduced
gunicorn to 1 worker. mmap removal is the meaningful fix — it eliminates the
amplifier so a transient WAL race is self-correcting. **The bug itself is
still latent** because we're stuck on SQLite 3.48.0 (Alpine 3.21).

### Path forward, by preference

- **Wait for Alpine 3.23** to ship SQLite ≥3.51.3 (likely May–June 2026), then
  bump `FROM alpine:3.21` in the Dockerfile. Zero code change.
- If it recurs before Alpine 3.23 lands: build SQLite from source in the
  Dockerfile and `LD_PRELOAD` it, or switch the DB to Postgres (analytics
  already runs on it).

### Versions checked 2026-04-26

- Alpine 3.21: sqlite-libs 3.48.0 (vulnerable, currently in use)
- Alpine 3.22: sqlite-libs 3.49.2 (vulnerable)
- Alpine edge: sqlite-libs 3.53.0 (fixed, but edge isn't appropriate for prod)
- `pysqlite3-binary` 0.5.4.post2: bundles 3.51.1 (vulnerable; package's last
  release predates the SQLite fix)
