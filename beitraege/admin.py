"""Admin of posts, topics and the post configuration."""

from . import workflow
from .models import Beitrag
from .models import BeitragFoto
from .models import BeitragZiel
from .models import BeitragsConfig
from .models import Thema
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import path
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from ok_tools.admin_base import ModelAdmin
from ok_tools.admin_base import TabularInline
from ok_tools.admin_secrets import SecretFieldsMixin


@admin.register(BeitragsConfig)
class BeitragsConfigAdmin(SecretFieldsMixin, ModelAdmin):
    """Channels for posts; Instagram and Facebook use the Tools credentials."""

    secret_fields = ('wordpress_app_password',)
    fieldsets = (
        (_('Platforms'), {
            'fields': ('instagram_enabled', 'facebook_enabled', 'website_enabled', 'approval_mail'),
            'description': _('Instagram and Facebook use the account, page and token entered '
                             'in the Tools configuration (section Instagram).'),
        }),
        (_('Website (WordPress)'), {
            'fields': ('wordpress_url', 'wordpress_user', 'wordpress_app_password', 'connection'),
        }),
    )
    readonly_fields = ('connection',)

    def has_add_permission(self, request):
        return not BeitragsConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Connection'))
    def connection(self, obj):
        if not obj or not obj.pk:
            return '-'
        return format_html('<a class="button" href="{}">{}</a>',
                           reverse('admin:beitraege_beitragsconfig_test'), _('Test connections'))

    def get_urls(self):
        return [
            path('test/', self.admin_site.admin_view(self.test_view), name='beitraege_beitragsconfig_test'),
        ] + super().get_urls()

    def test_view(self, request):
        from .services import wordpress

        if not request.user.is_superuser:
            raise PermissionDenied
        config = BeitragsConfig.get_config()
        if config.is_website_configured():
            try:
                user = wordpress.check(config)
            except wordpress.WordPressError as exc:
                messages.error(request, _('Website: %(error)s') % {'error': exc})
            else:
                messages.success(request, _('Website: connected as %(name)s (%(roles)s).') % {
                    'name': user['name'], 'roles': ', '.join(user['roles']) or '-'})
        meta = config.meta_config()
        if config.is_instagram_configured():
            from tools.services import instagram
            try:
                info = instagram.account_info(meta)
            except instagram.InstagramError as exc:
                messages.error(request, _('Instagram: %(error)s') % {'error': exc})
            else:
                messages.success(request, _('Instagram: @%(name)s.') % {'name': info.get('username') or '?'})
        if config.is_facebook_configured():
            from tools.services import facebook
            try:
                page = facebook.page_info(meta)
            except facebook.FacebookError as exc:
                messages.error(request, _('Facebook: %(error)s') % {'error': exc})
            else:
                messages.success(request, _('Facebook: page "%(name)s".') % {'name': page.get('name')})
        for flag, ready, label in (
                (config.instagram_enabled, config.is_instagram_configured(), 'Instagram'),
                (config.facebook_enabled, config.is_facebook_configured(), 'Facebook'),
                (config.website_enabled, config.is_website_configured(), _('Website'))):
            if flag and not ready:
                messages.warning(request, _('%(platform)s is switched on but not set up completely.') % {
                    'platform': label})
        return redirect('admin:beitraege_beitragsconfig_change', config.pk)


@admin.register(Thema)
class ThemaAdmin(ModelAdmin):
    list_display = ['name', 'hashtags', 'instagram', 'facebook', 'website', 'is_active', 'position']
    list_editable = ['position', 'is_active']
    search_fields = ['name', 'hashtags']
    filter_horizontal = ['freigeber']
    fieldsets = (
        (None, {'fields': ('name', 'is_active', 'position')}),
        (_('Texts'), {'fields': ('hashtags', 'signatur_instagram', 'signatur_facebook', 'signatur_website')}),
        (_('Website'), {'fields': ('wordpress_categories', 'wordpress_tags')}),
        (_('Platforms by default'), {'fields': ('instagram', 'facebook', 'website')}),
        (_('Approval'), {'fields': ('freigeber',)}),
    )


class BeitragFotoInline(TabularInline):
    model = BeitragFoto
    extra = 0
    fields = ('preview', 'bild', 'position', 'fokus_y')
    readonly_fields = ('preview',)

    @admin.display(description=_('Preview'))
    def preview(self, obj):
        if not obj or not obj.pk:
            return '-'
        url = reverse('beitraege:foto', args=[obj.token, 'instagram'])
        return format_html('<img src="{}" style="height:90px;border-radius:4px" alt="">', url)


class BeitragZielInline(TabularInline):
    model = BeitragZiel
    extra = 0
    can_delete = False
    fields = ('plattform', 'aktiv', 'text', 'status', 'link_display', 'error')
    readonly_fields = ('plattform', 'status', 'link_display', 'error')

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Link'))
    def link_display(self, obj):
        if not obj.permalink:
            return '-'
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.permalink, _('Open'))


@admin.register(Beitrag)
class BeitragAdmin(ModelAdmin):
    """Posts: write, check, approve, follow up."""

    list_display = ['titel', 'thema', 'status_badge', 'publish_at', 'created_by', 'created_at', 'links']
    list_filter = ['status', 'thema']
    search_fields = ['titel', 'text']
    date_hierarchy = 'created_at'
    inlines = [BeitragFotoInline, BeitragZielInline]
    change_list_template = 'admin/beitraege/beitrag/change_list.html'
    actions = ['submit_action', 'approve_action', 'retry_action']
    readonly_fields = ['status', 'created_by', 'approved_by', 'approved_at', 'rejection_note',
                       'created_at', 'updated_at', 'check_link']
    fieldsets = (
        (None, {'fields': ('status', 'check_link', 'thema', 'titel', 'text', 'link', 'einwilligung',
                           'publish_at')}),
        (_('Approval'), {'fields': ('created_by', 'approved_by', 'approved_at', 'rejection_note',
                                    'created_at', 'updated_at')}),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in (Beitrag.STATUS_PUBLISHING, Beitrag.STATUS_PUBLISHED):
            fields += ['thema', 'titel', 'text', 'link', 'einwilligung', 'publish_at']
        return fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        if change and obj.status == Beitrag.STATUS_APPROVED and form.changed_data:
            obj.status = Beitrag.STATUS_SUBMITTED
            obj.approved_by = None
            obj.approved_at = None
            messages.warning(request, _('The post was changed and needs a new approval.'))
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, BeitragZiel):
                workflow.mark_edited(instance)
            instance.save()
        for deleted in formset.deleted_objects:
            deleted.delete()
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # New posts and changed posts get their platform texts (re)built.
        workflow.ensure_ziele(form.instance)

    @admin.display(description=_('Status'), ordering='status')
    def status_badge(self, obj):
        colours = {
            Beitrag.STATUS_SUBMITTED: 'var(--ok-warning, #8a5a00)',
            Beitrag.STATUS_APPROVED: 'var(--ok-brand, #417690)',
            Beitrag.STATUS_PUBLISHED: 'var(--ok-success, #0a6b2d)',
            Beitrag.STATUS_PARTIAL: 'var(--ok-warning, #8a5a00)',
            Beitrag.STATUS_FAILED: 'var(--ok-danger, #c62828)',
            Beitrag.STATUS_REJECTED: 'var(--ok-danger, #c62828)',
        }
        return format_html('<strong style="color:{}">{}</strong>',
                           colours.get(obj.status, 'inherit'), obj.get_status_display())

    @admin.display(description=_('Links'))
    def links(self, obj):
        parts = [format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', z.permalink,
                             z.get_plattform_display())
                 for z in obj.ziele.all() if z.permalink]
        return format_html(' · '.join(['{}'] * len(parts)), *parts) if parts else '-'

    @admin.display(description=_('Check and approve'))
    def check_link(self, obj):
        if not obj or not obj.pk:
            return '-'
        return format_html('<a class="button" href="{}">{}</a>',
                           reverse('beitraege:pruefen', args=[obj.pk]), _('Open the check page'))

    @admin.action(description=_('Submit for approval'))
    def submit_action(self, request, queryset):
        count = 0
        for beitrag in queryset.filter(status__in=[Beitrag.STATUS_DRAFT, Beitrag.STATUS_REJECTED]):
            workflow.submit(beitrag)
            count += 1
        self.message_user(request, _('%(count)s post(s) submitted; the approvers have been told.') % {
            'count': count})

    @admin.action(description=_('Approve'))
    def approve_action(self, request, queryset):
        done = 0
        for beitrag in queryset:
            try:
                workflow.approve(beitrag, request.user)
            except (PermissionDenied, ValidationError) as exc:
                text = '; '.join(getattr(exc, 'messages', [str(exc)]))
                self.message_user(request, f'{beitrag}: {text}', level=messages.ERROR)
                continue
            done += 1
        if done:
            self.message_user(request, _('%(count)s post(s) approved.') % {'count': done})

    @admin.action(description=_('Publish failed platforms again'))
    def retry_action(self, request, queryset):
        count = 0
        for beitrag in queryset:
            if not beitrag.may_approve(request.user):
                continue
            if workflow.retry(beitrag):
                count += 1
        self.message_user(request, _('%(count)s post(s) are being published again.') % {'count': count})
