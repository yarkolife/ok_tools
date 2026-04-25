from datetime import timedelta
from .models import RentalItem
from .services import RentalService
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from inventory.models import InventoryItem
from registration.models import OKUser
import json


def _parse_request_datetime(value):
    parsed = parse_datetime(value or '')
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


def _serialize_inventory_item(item, start_at=None, end_at=None):
    total = item.quantity or 0
    if start_at and end_at:
        available = RentalService.get_available_quantity_for_period(item.pk, start_at, end_at)
    else:
        available = max(0, total - (item.reserved_quantity or 0) - (item.rented_quantity or 0))
    reserved = max(0, total - available)
    category = item.category.name if item.category else ''
    return {
        'id': item.pk,
        'name': item.description or '',
        'num': item.inventory_number or '',
        'cat': category,
        'loc': _item_location_label(item),
        'qty': {
            'avail': available,
            'total': total,
            'reserved': reserved,
        },
        'conflict': available <= 0,
    }


@login_required
@staff_member_required
@require_GET
def api_inventory_search(request):
    category = request.GET.get('cat', '').strip()
    query = request.GET.get('q', '').strip()
    inventory_number = request.GET.get('num', '').strip()
    start_at = _parse_request_datetime(request.GET.get('from') or request.GET.get('start_date'))
    end_at = _parse_request_datetime(request.GET.get('to') or request.GET.get('end_date'))

    queryset = InventoryItem.objects.select_related(
        'category',
        'location',
        'owner',
    ).filter(
        available_for_rent=True,
    )
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
    return JsonResponse({'items': items})


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
