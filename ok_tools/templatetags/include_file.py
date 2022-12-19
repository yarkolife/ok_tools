from django import template
from django.conf import settings


register = template.Library()


@register.simple_tag
def include_file(filename):
    """Include the content of a file relative to the base directory."""
    with open(settings.BASE_DIR / filename, 'r') as file:
        return file.read()
