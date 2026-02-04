"""Utility helpers for tools module."""

from pathlib import Path

from django.conf import settings

from .models import ToolsConfig


def _media_root_abs() -> Path:
    media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
    if media_root.is_absolute():
        return media_root.resolve()
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return (base_dir / media_root).resolve()


def resolve_tools_file_path(file_field, config: ToolsConfig | None = None) -> Path:
    """Resolve a FileField path using ToolsConfig storage or MEDIA_ROOT fallback."""
    if file_field is None or not getattr(file_field, "name", ""):
        raise ValueError("File field is empty.")

    config = config or ToolsConfig.get_config()
    rel_path = str(file_field.name).lstrip("/\\")

    storage_path = (config.get_effective_storage_path() or "").strip()
    if storage_path:
        storage_base = Path(storage_path).resolve()
        candidate = (storage_base / rel_path).resolve()
        try:
            candidate.relative_to(storage_base)
            if candidate.exists() and candidate.is_file():
                return candidate
        except (ValueError, OSError):
            pass

    try:
        return Path(file_field.path)
    except (ValueError, AttributeError):
        pass

    media_root = _media_root_abs()
    return (media_root / rel_path).resolve()


def resolve_tools_output_path(file_field, config: ToolsConfig | None = None) -> Path:
    """Resolve output FileField path using ToolsConfig output path or fallback."""
    if file_field is None or not getattr(file_field, "name", ""):
        raise ValueError("File field is empty.")

    config = config or ToolsConfig.get_config()
    rel_path = str(file_field.name).lstrip("/\\")

    output_path = (config.get_effective_output_path() or "").strip()
    if output_path:
        output_base = Path(output_path).resolve()
        candidate = (output_base / rel_path).resolve()
        try:
            candidate.relative_to(output_base)
            if candidate.exists() and candidate.is_file():
                return candidate
        except (ValueError, OSError):
            pass

    return resolve_tools_file_path(file_field, config=config)
