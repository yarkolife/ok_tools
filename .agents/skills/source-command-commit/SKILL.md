---
name: "source-command-commit"
description: "Commit changes to git with English message, push, and update docs/version for significant changes"
---

# source-command-commit

Use this skill when the user asks to run the migrated source command `commit`.

## Command Template

# /commit — Smart Git Commit & Push

You are performing a structured git commit operation for the ok_tools project.
Target remote: https://github.com/yarkolife/ok_tools/tree/version_4

## Rules (NON-NEGOTIABLE)

- Commit message: **English only**, Conventional Commits style (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`)
- First line ≤ 72 characters
- Always push after committing
- Do NOT run `makemigrations` unless explicitly requested
- Do NOT commit secrets or `.env` files

---

## PHASE 0: Assess Changes

Run these in parallel:

```
git status --porcelain
git diff --stat HEAD
git diff HEAD
git log --oneline -5
```

Analyze:
1. What files changed?
2. What is the nature of the changes? (new feature / bug fix / refactor / docs / chore / test)
3. What is the **weight** of the change?
   - **patch** (x.x.X): Bug fixes, typos, minor tweaks, test updates
   - **minor** (x.X.0): New features, new views/models/endpoints, significant behavior changes
   - **major** (X.0.0): Breaking changes, architecture overhaul, major new modules

If the user passed arguments like `patch`, `minor`, or `major` — use that as the version bump level.
If no argument given — determine level from the diff.

---

## PHASE 1: Check if Docs Update Needed

Significant changes (minor or major) require updating these files:
- `/Users/pavlo/coding/ok_tools_v3/README.rst`
- `/Users/pavlo/coding/ok_tools_v3/overview.md`
- `/Users/pavlo/coding/ok_tools_v3/CHANGES.md`

**Significant** = new features, new apps, API changes, behavior changes, architectural decisions.
**Not significant** = bug fixes, test updates, refactors, chores → skip doc updates.

---

## PHASE 2: Update Version (if significant)

1. Read current version from `CHANGES.md` (format: `Version X.Y.Z`)
2. Bump according to weight:
   - patch: Z+1
   - minor: Y+1, Z=0
   - major: X+1, Y=0, Z=0
3. Update version in:
   - `CHANGES.md` — add new entry at top with date and version
   - `README.rst` — update `**Current Version**` line

---

## PHASE 3: Update CHANGES.md (if significant)

Add a new section at the top of `CHANGES.md` (after the `CHANGELOG` header):

```
YYYY-MM-DD (Version X.Y.Z)
==========================

* **[Module]: [Short title]**
  * [Concise bullet describing what changed]
  * [Another bullet if needed]
```

Date format: `YYYY-MM-DD` (today's date).
Keep bullets concise and technical. English only.

---

## PHASE 4: Compose Commit Message

Use Conventional Commits format:

```
<type>(<scope>): <short description>

[optional body: what and why, not how]
[list key changes if multiple files affected]
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`, `perf`
Scope: module name (e.g. `rental`, `registration`, `dashboard`, `licenses`, `inventory`)

If the user provided a custom message as argument, use it as the description (still apply the prefix).

Examples:
- `feat(rental): add room availability conflict detection`
- `fix(licenses): correct PDF generation for empty address field`
- `chore: update dependencies and pre-commit hooks`
- `docs: update CHANGES.md and README for v4.0.16`

---

## PHASE 5: Execute Git Operations

```bash
# Stage all changes (including doc updates)
git add -A

# Commit
git commit -m "<your commit message>"

# Push
git push
```

If push fails due to upstream divergence:
```bash
git pull --rebase
git push
```

---

## PHASE 6: Confirm

Report:
- ✅ Committed: `<commit hash> <message>`
- ✅ Pushed to remote
- 📦 Version bumped to X.Y.Z (if applicable)
- 📝 Docs updated (if applicable)

---

## CONSTRAINTS

- NEVER use `--no-verify`
- NEVER force push to `main` or `master`
- NEVER commit `venv/`, `*.pyc`, `__pycache__/`, `.env`
- NEVER run `makemigrations` as part of this command
- ALWAYS write commit messages in English
- ALWAYS push after committing
