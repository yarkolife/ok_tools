# OK-Tools: development rules

Rules for everyone who changes the code, people and AI assistants alike.
`CLAUDE.md` repeats the per-commit rules for Claude Code; when the two
disagree, fix both.

## Branches and deployment

- Work on a feature branch (`feature/<topic>`), never directly on
  `version_4` or `main`.
- `version_4` is the deploy branch: production checks it out and is updated
  only with `deployment/scripts/update.sh` (backup of `.env` and database,
  `git pull`, `BUILD_COMMIT`, image build while the old containers keep
  serving, wait for idle Celery, restart; migrations and translations run
  when the web container starts).
  Bring a finished branch to `version_4` as a fast-forward; rebase first if
  `version_4` has moved.
- Deploy only tested commits, and only when the version and `CHANGES.md`
  are up to date (see below), so the version in the admin sidebar tells
  what is running.
- Data changes on production (settings rows, notification parameters,
  fixes in the database) are done through the admin or a reviewed
  `manage.py shell` snippet, read-only first, and mentioned in the commit
  or the change log when they belong to a change.
- One Docker image for the whole stack: in `deployment/docker-compose.production*.yml`
  only `web` has a `build:` block and names the image `oktools-app:latest`;
  `celery_beat` and the Celery workers run that image (`image:` +
  `pull_policy: never`) with their own `command`. A deploy builds and unpacks
  one image instead of seven (2026-11-27: seven identical builds kept the VM
  at 60 % iowait and filled 12 GB of disk). This holds only while every
  service needs the same Dockerfile and the same build args. A service that
  needs its own Dockerfile, build args or system packages gets its own
  `build:` block and its own image name back; `generate-override.sh` then
  has to add the UID/GID build args to it as well. A new Celery service uses
  `image: oktools-app:latest`, not `build:`.
- `update.sh` replaces a production `docker-compose.yml` that differs from
  the repository only with `FORCE_OVERWRITE=1`, which also overwrites
  `nginx.conf.template`; otherwise it leaves `docker-compose.yml.new` next to
  it. A compose change has to be put in place on both production servers.

## Commits

- Conventional Commits: `type(scope): summary`, in English, lower case,
  no full stop, at most about 72 characters.
  - `feat` new functionality, `fix` a correction, `docs` text only
    (CHANGES, README, overview, manual).
  - `scope` is the Django app (`rental`, `licenses`, `notifications`,
    `tools`, `planung`, `media_files`, `handbuch`, ...) or an area
    (`admin`, `deployment`, `celery`).
- The body says why, and what changed for users, not a list of files.
- One topic per commit. Code, tests, migrations, translations, manual and
  change log of that topic go into the same commit.
- Never commit secrets (`.env`, API keys, tokens), production dumps or
  personal data.

## Versions and change log

Versions are `MAJOR.MINOR.PATCH`, kept in `ok_tools/version.py`
(`VERSION`, shown in the admin with the commit) and at the top of
`README.rst`.

| Change | Version | Text |
|---|---|---|
| New functionality (`feat`) | MINOR, PATCH back to 0: 4.79.1 → 4.80.0 | New `CHANGES.md` section; README feature list; `overview.md` "Recent Updates" (and the app's section if its structure changed); `python handbuch/aktualitaet.py --bump` |
| Fix that users or operators notice, deployed | PATCH: 4.79.0 → 4.79.1 | New `CHANGES.md` section with `* Fixed: ...` bullets; README/overview only if the described behaviour changes |
| Small internal fix (refactoring, tests, typos) | none | none |

- `CHANGES.md` section header: `YYYY-MM-DD (Version X.Y.Z)` underlined
  with `=`. Feature bullets: `* **<app>: <what is new>**` with indented
  details (what the user can do, settings, limits, file names). Fix
  bullets: `* Fixed: <the problem as users saw it>. <what happens now>.`
- Several features (or fixes) released together share one section. A
  commit with features and fixes is a feature release.
- README: `**Current Version**` and `**Last Updated**` on every version
  change.
- All texts in `CHANGES.md`, `README.rst`, `overview.md` are English.

## In-app manual (`handbuch`)

- When a commit changes a page the staff work with (fields, buttons,
  labels, steps), update its chapter in the same commit: text in
  `handbuch/inhalt/<slug>.md` (German, Markdown as described in
  `handbuch/render.py`), screenshots in `handbuch/static/handbuch/bilder/`,
  `version` and `stand` in `handbuch/kapitel.py`.
- Before committing changes to pages run
  `python handbuch/aktualitaet.py --staged`. If the chapter is still right,
  only raise its `stand`.
- Screenshots: light theme, demo data only ("Max Mustermann", "(Demo)"
  items), never real people. Check the page in the dark theme too and fix
  or list problems in `handbuch/design-aufgaben.md`.
- New chapters are registered in `handbuch/kapitel.py` with the modules
  they need and the files of their pages (`pfade`).
- The manual compares only MAJOR.MINOR with `VERSION`; patch versions do
  not make chapters outdated.

## Code style

Enforced by `.pre-commit-config.yaml` (install with `pre-commit install`):

- isort (`.isort.cfg`, Django profile): one import per line
  (`from typing import Dict`), `from` imports first, no sections, two
  blank lines after the imports.
- pydocstyle, PEP 257: every public class, method and function has a
  docstring; one-line summary ending with a full stop. Module docstrings
  are optional but used for anything non-trivial.
- No trailing whitespace, newline at end of file, no `# -*- coding` line,
  no debugger statements, no large files.

Conventions in the code base:

- Code, identifiers, comments and docstrings in English. Comments explain
  why something is done, not what the next line does.
- User-facing strings through `gettext` (`_()` / `gettext_lazy`), English
  msgid, German translation in `<app>/locale/de/LC_MESSAGES/django.po`.
  When a msgid changes, update its `.po` entry in the same commit;
  `.mo` files are not committed (compiled during installation and
  deployment).
- Business logic in services (`<app>/services/`), read queries in
  `selectors.py`, views and admin stay thin.
- Settings that staff edit are singleton models with `get_config()`; they
  appear on the configuration page automatically. Passwords, keys and
  tokens use `ok_tools/admin_secrets.py` (write-only fields).
- Optional modules are switched by settings flags (e.g.
  `MEDIA_FILES_ENABLED`); code that touches another module checks
  `apps.is_installed(...)` or the flag and degrades quietly.
- Model changes come with their migration; defaults for existing rows go
  into a data migration.
- Admin pages use the Unfold design and the theme tokens; everything must
  stay readable in the dark theme.

## Notifications

- An event type is declared once in `notifications/event_types.py`
  (`register(EventType(...))`: code, module, label, description, message,
  category, settings flag, parameters with defaults).
- Scan checks live in `notifications/checks.py` (`@scan_check(code)`),
  receive the effective parameters (`config.get_params`) and return
  `Finding`s with a stable `dedup_key`; one event per key.
- Whether a stored event is still open is decided in
  `notifications/process_state.py`; keep its conditions identical to the
  check's, or events close or stay open wrongly.
- Channel settings (enabled, parameters) are data on production, not code:
  change them on the notification settings page.

## Tests

- pytest with `pytest-django`; test files are `test_*.py`, `*_tests.py` or
  `tests.py` inside the app (see `pytest.ini`). Shared helpers are in
  `ok_tools/testing.py`; tests run with `test.cfg`.
- Run inside the web container: `docker compose exec web pytest`. The full
  run enforces 70 % coverage; for a subset use
  `pytest <paths> --no-cov`.
- Every feature and every fix gets a test that fails without the change.
- Run at least the tests of the touched apps before committing, and the
  full suite before a release.

## Data and privacy

- Production data (database dumps, exports, uploaded files) stays outside
  the repository and is never shared with external services.
- Examples, fixtures, screenshots and test data use invented names only.
