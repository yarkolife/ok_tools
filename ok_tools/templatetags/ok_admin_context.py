"""``{% ensure_admin_context %}``: admin context for non-admin views.

Used by ok_tools/unfold_templates/admin/base_site.html. Pages outside the
admin site that extend the admin templates get ``admin.site.each_context()``
(sidebar, header, permissions) added to the lowest context layer, so
anything the view passed itself still wins.
"""

from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def ensure_admin_context(context):
    request = context.get('request')
    if request is None or 'available_apps' in context:
        return ''
    from django.contrib import admin
    context.dicts[0].update(admin.site.each_context(request))
    return ''
