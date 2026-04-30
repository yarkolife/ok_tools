from datetime import timedelta
from .models import RentalItem, RentalRequest
from .services import RentalService
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from inventory.models import InventoryItem
from registration.models import OKUser
import datetime
import json


def _parse_request_datetime(value):
    parsed = parse_datetime(value or '')
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _parse_edit_period_datetime(value):
    parsed = parse_datetime(value or '')
    if not parsed and value and 'T' in value and len(value) == 16:
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _item_location_label(item):
    location = getattr(item, 'location', None)
    if not location:
        return ''
    return getattr(location, 'full_path', None) or getattr(location, 'name', '') or str(location)


def _apply_inventory_access_filter(queryset, target):
    from rental.models import RentalConfig
    config = RentalConfig.get_config()
    if target.is_staff:
        orgs = config.employee_organizations.all()
    elif hasattr(target, 'profile') and target.profile and target.profile.member:
        orgs = config.member_organizations.all()
    else:
        orgs = config.user_organizations.all()

    if orgs.exists():
        return queryset.filter(owner__in=orgs)
    if target.is_staff:
        return queryset
    if hasattr(target, 'profile') and target.profile and target.profile.member:
        state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
        organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
        return queryset.filter(owner__isnull=False, owner__name__in=[state_institution, organization_owner])
    state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
    return queryset.filter(owner__isnull=False, owner__name=state_institution)


def _serialize_categories_for_queryset(queryset):
    category_rows = queryset.exclude(category__isnull=True).values(
        'category_id',
        'category__name',
    ).annotate(
        count=Count('id'),
    ).order_by('category__name')
    categories = [{
        'id': '',
        'label': str(_('All')),
        'icon': 'fa-th',
        'count': queryset.count(),
    }]
    categories.extend({
        'id': str(row['category_id']),
        'label': row['category__name'],
        'icon': 'fa-box',
        'count': row['count'],
    } for row in category_rows)
    return categories


def _serialize_inventory_item(item, start_at=None, end_at=None):
    total = item.quantity or 0
    if start_at and end_at:
        available = RentalService.get_available_quantity_for_period(item.pk, start_at, end_at)
    else:
        available = max(0, total - (item.reserved_quantity or 0) - (item.rented_quantity or 0))
    period_reserved = 0
    period_issued = 0
    if start_at and end_at:
        overlapping_items = RentalItem.objects.filter(
            inventory_item_id=item.pk,
            rental_request__requested_start_date__lt=end_at,
            rental_request__requested_end_date__gt=start_at,
            rental_request__status__in=['reserved', 'issued'],
        ).select_related('rental_request')
        for rental_item in overlapping_items:
            quantity = rental_item.quantity_issued or rental_item.quantity_requested or 0
            if rental_item.rental_request.status == 'issued':
                period_issued += quantity
            else:
                period_reserved += quantity
    reserved = max(0, total - available)
    status_label = ''
    if available <= 0:
        if period_issued:
            status_label = str(_('Issued'))
        elif period_reserved:
            status_label = str(_('Reserved'))
        else:
            status_label = str(_('Booked'))
    category = item.category.name if item.category else ''
    return {
        'id': item.pk,
        'name': item.description or '',
        'num': item.inventory_number or '',
        'cat': category,
        'category_id': item.category_id or '',
        'loc': _item_location_label(item),
        'qty': {
            'avail': available,
            'total': total,
            'reserved': reserved,
            'issued': period_issued,
        },
        'status_label': status_label,
        'conflict': available <= 0,
    }


@login_required
@require_GET
def api_inventory_search(request):
    category = request.GET.get('cat', '').strip()
    query = request.GET.get('q', '').strip()
    inventory_number = request.GET.get('num', '').strip()
    start_at = _parse_request_datetime(request.GET.get('from') or request.GET.get('start_date'))
    end_at = _parse_request_datetime(request.GET.get('to') or request.GET.get('end_date'))
    rental_id = request.GET.get('rental_id', '').strip()
    user_id = request.GET.get('user_id', '').strip()

    base_queryset = InventoryItem.objects.select_related(
        'category',
        'location',
        'owner',
    ).filter(
        available_for_rent=True,
    )

    filter_user = None
    if rental_id:
        try:
            rental = RentalRequest.objects.select_related('user', 'user__profile').get(id=rental_id)
        except (RentalRequest.DoesNotExist, ValueError):
            return JsonResponse({'error': _('Rental not found.')}, status=404)
        if request.user.is_staff or rental.user_id == request.user.id:
            filter_user = rental.user
        else:
            return JsonResponse({'error': _('Permission denied.')}, status=403)
    elif user_id and request.user.is_staff:
        try:
            filter_user = OKUser.objects.select_related('profile').get(id=user_id)
        except OKUser.DoesNotExist:
            filter_user = None

    target = filter_user or request.user
    base_queryset = _apply_inventory_access_filter(base_queryset, target)
    categories = _serialize_categories_for_queryset(base_queryset)

    queryset = base_queryset
    if category:
        queryset = queryset.filter(category_id=category)
    if query:
        queryset = queryset.filter(
            Q(description__icontains=query)
            | Q(inventory_number__icontains=query)
            | Q(manufacturer__name__icontains=query)
        )
    if inventory_number:
        queryset = queryset.filter(inventory_number__iexact=inventory_number)

    items = [_serialize_inventory_item(item, start_at, end_at) for item in queryset.order_by('inventory_number')[:80]]
    return JsonResponse({'items': items, 'categories': categories})


@login_required
@staff_member_required
@require_GET
def api_users_search(request):
    query = request.GET.get('q', '').strip()
    queryset = OKUser.objects.select_related('profile', 'profile__media_authority').filter(is_active=True)
    if query:
        queryset = queryset.filter(
            Q(email__icontains=query)
            | Q(profile__first_name__icontains=query)
            | Q(profile__last_name__icontains=query)
        )
    queryset = queryset.distinct().order_by('email')[:30]

    from .views import serialize_user
    return JsonResponse({'users': [serialize_user(user) for user in queryset]})


@login_required
@staff_member_required
@require_POST
def api_availability_check(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': _('Invalid JSON.')}, status=400)

    selected_from = _parse_request_datetime(data.get('from'))
    selected_to = _parse_request_datetime(data.get('to'))
    item_ids = data.get('items') or []
    if not selected_from or not selected_to or selected_to <= selected_from:
        return JsonResponse({'error': _('A valid rental period is required.')}, status=400)

    window_start = selected_from - timedelta(days=2)
    window_end = window_start + timedelta(days=14)
    window_seconds = max((window_end - window_start).total_seconds(), 1)

    def pct(moment):
        return max(0, min(100, (moment - window_start).total_seconds() / window_seconds * 100))

    selection_left = pct(selected_from)
    selection_width = max(0, pct(selected_to) - selection_left)
    items = InventoryItem.objects.filter(pk__in=item_ids).select_related('category')
    items_by_id = {item.pk: item for item in items}

    rows = []
    for raw_id in item_ids:
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        item = items_by_id.get(item_id)
        if not item:
            continue
        overlapping = RentalItem.objects.filter(
            inventory_item_id=item_id,
            rental_request__requested_start_date__lt=window_end,
            rental_request__requested_end_date__gt=window_start,
            rental_request__status__in=['reserved', 'issued'],
        ).select_related('rental_request', 'rental_request__user')
        ranges = []
        for rental_item in overlapping:
            rental = rental_item.rental_request
            start_at = rental.requested_start_date
            end_at = rental.requested_end_date
            conflict = start_at < selected_to and end_at > selected_from
            user_label = rental.user.get_full_name() or rental.user.email
            ranges.append({
                'left': pct(start_at),
                'width': max(0, pct(end_at) - pct(start_at)),
                'label': f'R-{rental.created_at:%y%m}-{rental.pk:04d} · {user_label}',
                'conflict': conflict,
            })
        rows.append({
            'item': item.description or item.inventory_number,
            'selection': {
                'left': selection_left,
                'width': selection_width,
            },
            'ranges': ranges,
        })
    return JsonResponse({'rows': rows})


@login_required
@staff_member_required
@require_POST
def api_change_rental_user(request, rental_id):
    """Change the user assigned to a rental request."""
    try:
        rental = RentalRequest.objects.get(pk=rental_id)
    except RentalRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Rental request not found.')}, status=404)

    if rental.has_any_signature():
        return JsonResponse({'success': False, 'error': _('Cannot modify rental after it is signed')}, status=400)

    if rental.status not in ('draft', 'reserved'):
        return JsonResponse({'success': False, 'error': _('Cannot modify rental in current status')}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': _('Invalid JSON.')}, status=400)

    user_id = data.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'error': _('User ID is required.')}, status=400)

    try:
        new_user = OKUser.objects.get(pk=user_id, is_active=True)
    except OKUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('User not found.')}, status=404)

    rental.user = new_user
    rental.save(update_fields=['user', 'updated_at'])

    from .views import serialize_user
    return JsonResponse({
        'success': True,
        'user': serialize_user(new_user),
    })


@login_required
@staff_member_required
@require_POST
def api_change_rental_period(request, rental_id):
    """Change the start/end date of a rental request."""
    try:
        rental = RentalRequest.objects.get(pk=rental_id)
    except RentalRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': _('Rental request not found.')}, status=404)

    if rental.has_any_signature():
        return JsonResponse({'success': False, 'error': _('Cannot modify rental after it is signed')}, status=400)

    if rental.status not in ('draft', 'reserved'):
        return JsonResponse({'success': False, 'error': _('Cannot modify rental in current status')}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': _('Invalid JSON.')}, status=400)

    new_start = data.get('from')
    new_end = data.get('to')

    if not new_start or not new_end:
        return JsonResponse({'success': False, 'error': _('Both start and end dates are required.')}, status=400)

    start_dt = _parse_edit_period_datetime(new_start)
    end_dt = _parse_edit_period_datetime(new_end)

    if not start_dt or not end_dt:
        return JsonResponse({'success': False, 'error': _('Invalid date format.')}, status=400)

    if end_dt <= start_dt:
        return JsonResponse({'success': False, 'error': _('End date must be after start date.')}, status=400)

    rental.requested_start_date = start_dt
    rental.requested_end_date = end_dt
    rental.save(update_fields=['requested_start_date', 'requested_end_date', 'updated_at'])

    return JsonResponse({
        'success': True,
        'from_at': start_dt.isoformat(),
        'to_at': end_dt.isoformat(),
    })


@login_required
@staff_member_required
@require_POST
def api_add_rental_items(request, rental_id):
    """Add inventory items to an editable rental request."""
    try:
        rental = RentalRequest.objects.get(pk=rental_id)
    except RentalRequest.DoesNotExist:
        return JsonResponse({'error': _('Rental request not found.')}, status=404)

    if rental.has_any_signature():
        return JsonResponse({'error': _('Cannot modify items after rental is signed')}, status=400)

    if rental.status not in ('draft', 'reserved'):
        return JsonResponse({'error': _('Cannot add items in the current rental status')}, status=400)

    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': _('Invalid JSON.')}, status=400)

    items_data = []
    existing_inventory_ids = set(
        rental.items.values_list('inventory_item_id', flat=True)
    )
    for raw_item in data.get('items', []):
        try:
            inventory_item_id = int(raw_item.get('id') or raw_item.get('inventory_item_id'))
            quantity = int(raw_item.get('qty') or raw_item.get('quantity_requested') or 1)
        except (TypeError, ValueError):
            continue
        if not inventory_item_id or quantity <= 0:
            continue
        if inventory_item_id in existing_inventory_ids:
            continue
        items_data.append({
            'inventory_item_id': inventory_item_id,
            'quantity_requested': quantity,
            'notes': raw_item.get('notes', ''),
        })

    if not items_data:
        return JsonResponse({'error': _('No new items were selected.')}, status=400)

    created_items = RentalService.add_items_to_rental_request(rental, items_data)
    if not created_items:
        return JsonResponse({'error': _('Selected items are no longer available for this period.')}, status=400)

    from .views import serialize_item
    return JsonResponse({
        'success': True,
        'items': [serialize_item(item) for item in created_items],
    })
