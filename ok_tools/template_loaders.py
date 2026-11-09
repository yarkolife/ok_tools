"""Template loader for ok_tools/templates when the Unfold admin is on.

ok_tools/templates holds the public site's templates (base.html,
dashboard.html, ...) and the classic admin's overrides (admin/base_site.html,
admin/index.html, admin/nav_sidebar.html). With Unfold the admin overrides
must not win over Unfold's templates, while the public templates must keep
their place before registration/templates (both have a base.html).
"""

from django.template.loaders.filesystem import Loader as FilesystemLoader


class NonAdminLoader(FilesystemLoader):
    """Filesystem loader that skips templates under ``admin/``."""

    def get_template_sources(self, template_name):
        if template_name.startswith('admin/'):
            return
        yield from super().get_template_sources(template_name)
