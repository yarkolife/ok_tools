"""Module flags in settings.py pull in the modules they depend on."""

from pathlib import Path
import json
import os
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]


def _settings_with(**env):
    """Import ok_tools.settings in a fresh interpreter with these flags."""
    code = (
        'import json, ok_tools.settings as s; '
        'print(json.dumps({"apps": s.INSTALLED_APPS, "tools": s.TOOLS_ENABLED}))'
    )
    full_env = {**os.environ, **env}
    out = subprocess.run(
        [sys.executable, '-c', code], cwd=REPO, env=full_env,
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test__settings__media_files_enables_tools():
    result = _settings_with(
        LICENSES_ENABLED='true', MEDIA_FILES_ENABLED='true', TOOLS_ENABLED='false')
    assert 'media_files' in result['apps']
    assert 'tools' in result['apps']
    assert result['tools'] is True


def test__settings__tools_stays_off_without_media_files():
    result = _settings_with(
        LICENSES_ENABLED='true', MEDIA_FILES_ENABLED='false', TOOLS_ENABLED='false')
    assert 'tools' not in result['apps']
