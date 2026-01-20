"""
Compatibility wrapper.

Preset loading moved to `tools.rendering.presets`. Keep this module to avoid
breaking imports from `media_files.*`.
"""

from tools.rendering.presets import *  # noqa: F403


