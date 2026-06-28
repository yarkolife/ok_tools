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

HOOK_TYPES = {"frage", "intrige", "kontrast", "naehe", "emotion", "sachlich"}
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
    read_timeout: float | None = None,
) -> list[dict]:
    """Return n hook variants [{zeile1, zeile2, short_title}, ...] for hook_type.

    Slow (cold 7B model up to ~180 s) -> call in the background. Uses the
    configured reel timeout (should be generous, e.g. 360 s) unless overridden.
    """
    timeout = read_timeout if read_timeout is not None else _timeout()
    payload: dict = {"title": title, "n": n, "hook_type": hook_type}
    for k, v in (
        ("description", description),
        ("category", category),
        ("location", location),
        ("date", date),
    ):
        if v:
            payload[k] = v
    return _post("/api/hook", payload, timeout).get("candidates", [])


def warmup(read_timeout: float = 5) -> bool:
    """Best-effort: trigger model warm-up so the first hook call is warm.

    Errors are swallowed (the renderer may be unreachable or lack the endpoint).
    """
    base = _base_url()
    if not base:
        return False
    try:
        _session.post(
            base + "/api/hook/warmup", headers=_headers(), timeout=(3, read_timeout))
        return True
    except requests.RequestException:
        return False


def share_prefix_for(storage_location) -> str:
    """Pick the renderer share prefix for a StorageLocation.

    Rule: ``playout/`` = //192.168.88.2/Sendedaten, ``archive/`` = FilmArchiv.
    Detection order: share name in unc_path/path (most reliable), then
    storage_type, then default ``playout``.
    """
    if storage_location is None:
        return "playout"
    hay = "{} {}".format(
        getattr(storage_location, "unc_path", "") or "",
        getattr(storage_location, "path", "") or "",
    ).lower()
    if "filmarchiv" in hay or "archiv" in hay:
        return "archive"
    if "sendedaten" in hay or "playout" in hay:
        return "playout"
    storage_type = (getattr(storage_location, "storage_type", "") or "").upper()
    return {"PLAYOUT": "playout", "ARCHIVE": "archive"}.get(storage_type, "playout")


def _storage_in_share_subpath(storage_location) -> str:
    """Return the StorageLocation path *inside* its CIFS share, e.g. for
    ``\\\\192.168.88.2\\Sendedaten\\000_Sendungen`` -> ``000_Sendungen``.

    The share root is ``\\\\host\\Share``; everything after it is the subpath.
    Derived from the UNC path (the only reliable source of the share layout).
    """
    if storage_location is None:
        return ""
    unc = (getattr(storage_location, "unc_path", "") or "").strip()
    if not unc:
        return ""
    parts = [p for p in unc.replace("\\", "/").split("/") if p]
    # parts = [host, share, <subpath...>]
    if len(parts) <= 2:
        return ""
    return "/".join(parts[2:])


def share_relative_path(file_path, storage_location=None) -> str:
    """Build a path relative to the renderer's CIFS share root.

    ``playout/`` = //192.168.88.2/Sendedaten, ``archive/`` = FilmArchiv. The
    result is ``<prefix>/<storage subpath inside the share>/<file_path>`` so
    that folders carried by the StorageLocation itself (e.g. 000_Sendungen) are
    not dropped. http(s) URLs and already-prefixed paths are returned unchanged.
    """
    if not file_path:
        return ""
    fp = str(file_path)
    if fp.startswith(("http://", "https://")):
        return fp
    fp = fp.replace("\\", "/").lstrip("/")
    if fp.split("/", 1)[0] in ("playout", "archive"):
        return fp
    prefix = share_prefix_for(storage_location)
    subpath = _storage_in_share_subpath(storage_location)
    if subpath:
        return f"{prefix}/{subpath}/{fp}"
    return f"{prefix}/{fp}"


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
    hook_type: str,        # frage|intrige|kontrast|naehe|emotion|sachlich
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
