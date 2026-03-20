from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'n', 'off'}:
            return False
    return default


def normalize_exchange_metadata(payload: Any) -> dict[str, Any]:
    data = _as_dict(payload).copy()
    organization = _as_dict(data.get('organization'))
    license_data = _as_dict(data.get('license'))

    normalized = data.copy()
    normalized['bundesland'] = _first_value(
        data.get('bundesland'),
        organization.get('bundesland'),
    )
    normalized['bundesland_code'] = _first_value(
        data.get('bundesland_code'),
        organization.get('bundesland_code'),
    )
    normalized['allowExchange'] = _first_value(
        data.get('allowExchange'),
        license_data.get('allowExchange'),
        data.get('media_authority_exchange_allowed'),
    )
    normalized['allowExchangeOtherStates'] = _first_value(
        data.get('allowExchangeOtherStates'),
        license_data.get('allowExchangeOtherStates'),
        data.get('media_authority_exchange_allowed_other_states'),
    )
    normalized['targetChannel'] = _first_value(
        data.get('targetChannel'),
        license_data.get('targetChannel'),
        organization.get('targetChannel'),
    )
    return normalized


def is_exchange_allowed_for_viewer(payload: Any, viewer_bundesland_code: str | None) -> bool:
    normalized = normalize_exchange_metadata(payload)
    viewer_code = (viewer_bundesland_code or '').strip().upper()
    origin_code = str(normalized.get('bundesland_code') or '').strip().upper()

    if viewer_code and origin_code and viewer_code == origin_code:
        return _coerce_bool(normalized.get('allowExchange'))
    return _coerce_bool(normalized.get('allowExchangeOtherStates'))
