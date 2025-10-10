from django import template
from django.conf import settings
from django.template import Context, Template


register = template.Library()


@register.simple_tag(takes_context=True)
def include_file(context, filename):
    """Include the content of a file relative to the base directory and render it as a template."""
    with open(settings.BASE_DIR / filename, 'r') as file:
        content = file.read()
    
    # Render the content as a Django template with the current context
    template_obj = Template(content)
    return template_obj.render(Context(context.flatten()))
