"""Client for the external OKMQ reel renderer.

Wraps the HTTP calls to the reel renderer (okmq-pretix:8011):
  /api/hook  -> AI hook variants (per hook_type)
  /api/cta   -> curated CTA closing texts (dropdown)
  /api/reel  -> render a reel (ASYNC: job_id, then poll)
  /api/reel/{job_id} -> poll job status

IMPORTANT:
- Always async: ``start_reel()`` returns a job_id immediately, then poll with
  ``wait_for_job()``. Never call synchronously (``?wait=1``) -- the gunicorn worker
  timeout would kill the request (502) even though the render keeps running.
- ``wait_for_job()`` / ``render_reel_blocking()`` block for minutes -> only call
  them inside a Celery task / thread / management command, never in a web request.
- HTTP is 200 even on render errors -> always check the ``status`` field.

Configuration comes from :class:`tools.models.ToolsConfig` (singleton), not settings.
"""

import time

import requests

HOOK_TYPES = {"frage", "intrige", "kontrast", "naehe", "emotion"}
REEL_SECONDS = 15  # fixed reel length (engine)

_session = requests.Session()


# ---- Errors ---------------------------------------------------------------
class OkmqError(Exception):
    """Transport / HTTP error (unreachable, 401, 400 ...)."""


class OkmqJobError(OkmqError):
    """Render job finished with status=error."""


class OkmqTimeout(OkmqError):
    """Job did not finish within the time limit."""


# ---- Config / HTTP helpers ------------------------------------------------
def _config():
    """Return the ToolsConfig singleton."""
    from tools.models import ToolsConfig
    return ToolsConfig.get_config()


def _base_url() -> str:
    return (_config().reel_render_url or "").rstrip("/")


def _headers() -> dict:
    key = _config().reel_render_api_key or ""
    return {"X-API-Key": key} if key else {}


def _timeout() -> int:
    return int(_config().reel_render_timeout or 30)


def _require_configured() -> str:
    base = _base_url()
    if not base:
        raise OkmqError("Reel renderer is not configured (missing URL).")
    return base


def _post(path: str, payload: dict, read_timeout: float) -> dict:
    base = _require_configured()
    try:
        r = _session.post(
            base + path, json=payload, headers=_headers(),
            timeout=(10, read_timeout),
        )
    except requests.RequestException as e:
        raise OkmqError(f"OKMQ unreachable ({path}): {e}") from e
    if r.status_code == 401:
        raise OkmqError("OKMQ: invalid/missing API key")
    if not r.ok:
        raise OkmqError(f"OKMQ {path} HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def _get(path: str, params: dict | None = None, read_timeout: float = 30) -> dict:
    base = _require_configured()
    try:
        r = _session.get(
            base + path, params=params, headers=_headers(),
            timeout=(10, read_timeout),
        )
    except requests.RequestException as e:
        raise OkmqError(f"OKMQ unreachable ({path}): {e}") from e
    if r.status_code == 401:
        raise OkmqError("OKMQ: invalid/missing API key")
    if not r.ok:
        raise OkmqError(f"OKMQ {path} HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


# ---- 1. Hooks -------------------------------------------------------------
def generate_hooks(
    title: str,
    *,
    hook_type: str,
    description: str | None = None,
    category: str | None = None,
    location: str | None = None,
    date: str | None = None,
    n: int = 5,
    read_timeout: float = 200,
) -> list[dict]:
    """Return n hook variants [{zeile1, zeile2, short_title}, ...] for hook_type.

    Slow (cold 7B model up to ~180 s) -> call in the background.
    """
    payload: dict = {"title": title, "n": n, "hook_type": hook_type}
    for k, v in (
        ("description", description),
        ("category", category),
        ("location", location),
        ("date", date),
    ):
        if v:
            payload[k] = v
    return _post("/api/hook", payload, read_timeout).get("candidates", [])


# ---- 2. CTA selection (dropdown) ------------------------------------------
def list_cta(hook_type: str | None = None) -> dict:
    """Curated CTA closing texts.

    Without hook_type -> {footer, by_type:{...}}; with hook_type ->
    {hook_type, footer, options:[{zeile1,zeile2}, ...]}.
    """
    params = {"hook_type": hook_type} if hook_type else None
    return _get("/api/cta", params)


# ---- 3. Start reel (async) + poll -----------------------------------------
def auto_start_seconds(duration_seconds: float, reel_seconds: int = REEL_SECONDS) -> float:
    """Auto mode: take a clip from the middle of the source video.

    Manual mode: pass the user-selected second instead.
    """
    return max(0.0, float(duration_seconds) / 2 - reel_seconds / 2)


def start_reel(
    *,
    video: str,
    hook: dict,            # {"zeile1": "...", "zeile2": "..."} -- chosen hook variant
    hook_type: str,        # frage|intrige|kontrast|naehe|emotion
    output_name: str,
    autor: str | None = None,
    start_from_seconds: float | None = None,   # auto_start_seconds(...) OR manual second
    cta: dict | None = None,                    # omit -> server default per hook_type
    mediathek: dict | None = None,              # {"zeile1","zeile2"} optional
    sendetermin: dict | None = None,            # {"tag":"Montag","uhrzeit":"18:00"} optional
    read_timeout: float | None = None,
) -> str:
    """Enqueue a reel into the render queue and return the job_id immediately (async)."""
    beitrag: dict = {"video": video}
    if autor:
        beitrag["autor"] = autor
    if start_from_seconds is not None:
        beitrag["startFromSeconds"] = round(float(start_from_seconds), 2)

    payload: dict = {
        "beitrag": beitrag,
        "hook": hook,
        "hookType": hook_type,   # camelCase! (mind the snake_case in /api/hook)
        "output_name": output_name,
    }
    if cta:
        payload["cta"] = cta
    if mediathek:
        payload["mediathek"] = mediathek
    if sendetermin:
        payload["sendetermin"] = sendetermin

    timeout = read_timeout if read_timeout is not None else _timeout()
    return _post("/api/reel", payload, timeout)["job_id"]  # no ?wait -> async


def get_job(job_id: str) -> dict:
    """Status of a render job: {status: queued|rendering|done|error, file, output, error}."""
    return _get(f"/api/reel/{job_id}")


def wait_for_job(job_id: str, *, overall_timeout: float = 900, interval: float = 4) -> dict:
    """Poll until done (-> status dict) / error (-> OkmqJobError) / timeout (-> OkmqTimeout).

    Only call inside Celery/thread/command, never in a web request (blocks minutes).
    """
    deadline = time.monotonic() + overall_timeout
    while True:
        st = get_job(job_id)
        status = st.get("status")
        if status == "done":
            return st
        if status == "error":
            raise OkmqJobError(st.get("error") or "Render failed")
        if time.monotonic() > deadline:
            raise OkmqTimeout(
                f"Job {job_id} not finished after {overall_timeout}s (status={status})"
            )
        time.sleep(interval)


def render_reel_blocking(**kwargs) -> dict:
    """Convenience for Celery/command: start_reel(...) + wait_for_job(...)."""
    return wait_for_job(start_reel(**kwargs))
