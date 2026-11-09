"""``{% static_v 'path' %}``: static URL with the file's mtime appended.

Browsers keep CSS/JS from the development server for a while; the
version parameter makes them load a changed file at once. In production
the hashed file names of the static storage do the same job.
"""

from django import template
from ok_tools.admin_nav import _versioned


register = template.Library()


@register.simple_tag
def static_v(path):
    return _versioned(path)
