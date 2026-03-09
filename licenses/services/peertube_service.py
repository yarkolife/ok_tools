from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
import logging
from typing import Any
from urllib.parse import quote
from urllib.parse import urljoin

import requests
from django.utils import timezone


logger = logging.getLogger('django')


DEFAULT_PEERTUBE_BASE_URL = 'https://lokalmedial.de'


@dataclass
class PeerTubeEndpointConfig:
    base_url: str
    channel_handle: str


def parse_target_channel(target_channel: str | None) -> tuple[str | None, str | None]:
    """Parse @handle@domain and return (handle, domain)."""
    value = (target_channel or '').strip()
    if not value:
        return None, None

    if value.startswith('@'):
        value = value[1:]

    if '@' not in value:
        return None, None

    handle, domain = value.split('@', 1)
    handle = handle.strip()
    domain = domain.strip()
    if not handle or not domain:
        return None, None
    return handle, domain


def resolve_peertube_endpoint(*, target_channel: str | None, organization_channel: str | None) -> PeerTubeEndpointConfig:
    """Resolve PeerTube base URL and channel handle."""
    parsed_handle, parsed_domain = parse_target_channel(target_channel)

    channel_handle = (organization_channel or '').strip() or (parsed_handle or '')
    if not channel_handle:
        raise ValueError('PeerTube channel handle is not configured')

    base_url = DEFAULT_PEERTUBE_BASE_URL
    if parsed_domain:
        base_url = f'https://{parsed_domain}'

    return PeerTubeEndpointConfig(base_url=base_url.rstrip('/'), channel_handle=channel_handle)


def peertube_get_json(base_url: str, path: str, params: dict | None = None, timeout: int = 15) -> dict:
    """GET JSON from PeerTube public API."""
    base_url = base_url.rstrip('/') + '/'
    url = urljoin(base_url, path.lstrip('/'))
    response = requests.get(
        url,
        params=params,
        headers={'Accept': 'application/json'},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    raise ValueError('Unexpected PeerTube response payload')


def find_video_by_number_in_channel(
    base_url: str,
    channel_handle: str,
    video_number: str | int,
    *,
    page_size: int = 100,
    max_pages: int = 50,
) -> dict | None:
    """Find full PeerTube video object by pluginData.videoNumber in channel."""

    def _channel_candidates(value: str) -> list[str]:
        raw = (value or '').strip()
        if not raw:
            return []

        candidates: list[str] = []

        def _add(candidate: str) -> None:
            candidate = candidate.strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        _add(raw)

        no_leading_at = raw[1:] if raw.startswith('@') else raw
        _add(no_leading_at)

        if '@' in no_leading_at:
            _add(no_leading_at.split('@', 1)[0])

        return candidates

    def _fetch_for_channel(channel_identifier: str) -> dict[str, Any] | None:
        start = 0
        video_number_str = str(video_number)

        for _ in range(max_pages):
            path = f'/api/v1/video-channels/{quote(channel_identifier, safe="")}/videos'
            data = peertube_get_json(
                base_url,
                path,
                params={'count': page_size, 'start': start, 'sort': '-publishedAt'},
            )

            items = data.get('data') or []
            if not items:
                return None

            for item in items:
                plugin_data = item.get('pluginData') or {}
                if str(plugin_data.get('videoNumber', '')) == video_number_str:
                    uuid = item.get('uuid')
                    if not uuid:
                        continue
                    return peertube_get_json(base_url, f'/api/v1/videos/{quote(uuid, safe="")}')

                uuid = item.get('uuid')
                if not uuid:
                    continue

                full = peertube_get_json(base_url, f'/api/v1/videos/{quote(uuid, safe="")}')
                full_plugin_data = full.get('pluginData') or {}
                if str(full_plugin_data.get('videoNumber', '')) == video_number_str:
                    return full

            if len(items) < page_size:
                return None
            start += page_size

        return None

    last_http_error: requests.HTTPError | None = None
    for candidate in _channel_candidates(channel_handle):
        try:
            return _fetch_for_channel(candidate)
        except requests.HTTPError as exc:
            status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status_code == 404:
                logger.warning(
                    'PeerTube channel identifier not found: %s (base_url=%s)',
                    candidate,
                    base_url,
                )
                last_http_error = exc
                continue
            raise

    if last_http_error:
        raise last_http_error

    return None


def peertube_watch_url(base_url: str, video: dict) -> str:
    """Build watch URL /w/{shortUUID|uuid}."""
    base_url = base_url.rstrip('/')
    video_id = video.get('shortUUID') or video.get('uuid')
    if not video_id:
        raise ValueError('No shortUUID/uuid in video data')
    return f'{base_url}/w/{video_id}'


def compute_publish_time_for_license(license_obj) -> datetime | None:
    """Resolve publish time using Contribution first, then planned TagesPlan entry."""
    try:
        from contributions.models import Contribution

        contribution = (
            Contribution.objects
            .filter(license=license_obj)
            .only('broadcast_date')
            .order_by('broadcast_date')
            .first()
        )
        if contribution and contribution.broadcast_date:
            return contribution.broadcast_date
    except (ImportError, RuntimeError, ModuleNotFoundError):
        pass

    try:
        from planung.models import TagesPlan

        plans = TagesPlan.objects.filter(datum__isnull=False).order_by('datum')
        for plan in plans:
            plan_json = plan.json_plan or {}
            if plan_json.get('draft') is True or plan_json.get('planned') is False:
                continue

            for item in plan_json.get('items', []):
                if item.get('number') != license_obj.number:
                    continue

                start_raw = (item.get('start') or '').strip()
                if not start_raw:
                    continue

                try:
                    parts = start_raw.split(':')
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    second = int(parts[2]) if len(parts) > 2 else 0
                    naive_dt = datetime.combine(
                        plan.datum,
                        datetime.min.time().replace(hour=hour, minute=minute, second=second),
                    )
                    return timezone.make_aware(naive_dt)
                except (ValueError, TypeError, IndexError):
                    continue
    except (ImportError, RuntimeError, ModuleNotFoundError):
        pass

    return None


def compute_lookup_eta(publish_time: datetime | None) -> datetime:
    """Compute first lookup ETA: publish_time + 5 minutes, else now."""
    if publish_time is None:
        return timezone.now()
    return publish_time + timedelta(minutes=5)
