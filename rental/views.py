from .models import EquipmentSet
from .models import EquipmentSetItem
from .models import RentalIssue
from .models import RentalItem
from .models import RentalRequest
from .models import RentalTransaction
from .models import Room
from .models import RoomRental
from .permissions import CanCreateRentalRequest
from .permissions import IsAuthenticatedAndMemberOrReadOnly
from .permissions import StaffCanIssuePermission
from .serializers import EquipmentSetItemSerializer
from .serializers import EquipmentSetSerializer
from .serializers import InventoryItemSerializer
from .serializers import RentalIssueSerializer
from .serializers import RentalItemSerializer
from .serializers import RentalRequestSerializer
from .serializers import RentalTransactionSerializer
from .services import RentalService
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from rental.services.inventory_service_interface import inventory_service
from registration.models import OKUser
from registration.models import Profile
from rest_framework import filters
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
import json


class DefaultPagination(PageNumberPagination):
    """
    Default pagination configuration for rental API views.

    Provides consistent pagination across all rental-related endpoints
    with configurable page size and reasonable limits.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class InventoryItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for inventory items available for rental.

    Provides filtered access to inventory items based on user permissions.
    Members can see MSA and OKMQ items, non-members only see MSA items.
    """

    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'owner', 'available_for_rent']
    search_fields = ['inventory_number', 'description', 'manufacturer__name']
    ordering_fields = ['inventory_number', 'description']

    def get_queryset(self):
        """
        Filter queryset based on user permissions and availability.

        Returns:
            Filtered queryset of available inventory items
        """
        # Use the inventory service to get available items
        user_id = self.request.user.id if self.request.user.is_authenticated else None
        available_items = inventory_service.get_available_items(user_id=user_id)
        
        # Extract IDs from the service response
        item_ids = [item['id'] for item in available_items]
        
        # Get the actual model instances
        # This viewset is now backed by the inventory service, but the serializer
        # still expects model instances. This is a temporary state until the
        # serializer is also updated.
        from inventory.models import InventoryItem
        return InventoryItem.objects.filter(id__in=item_ids)


class RentalRequestViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing rental requests.

    Provides full CRUD operations for rental requests with filtering,
    search, and ordering capabilities.
    """

    queryset = RentalRequest.objects.select_related('user', 'created_by').all()
    serializer_class = RentalRequestSerializer
    permission_classes = [CanCreateRentalRequest]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'user', 'created_by']
    search_fields = ['project_name', 'purpose']
    ordering_fields = ['created_at', 'requested_start_date']


class RentalItemViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing rental items within rental requests.

    Handles individual items that are part of rental requests
    with search and filtering capabilities.
    """

    queryset = RentalItem.objects.select_related('rental_request', 'inventory_item').all()
    serializer_class = RentalItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['rental_request', 'inventory_item']
    search_fields = ['rental_request__project_name', 'inventory_item__inventory_number']


class RentalTransactionViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing rental transactions.

    Handles all rental-related transactions (reserve, issue, return, cancel)
    with staff-only access for security.
    """

    queryset = RentalTransaction.objects.select_related('rental_item', 'performed_by').all()
    serializer_class = RentalTransactionSerializer
    permission_classes = [StaffCanIssuePermission]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['transaction_type', 'performed_by']


class RentalIssueViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing rental issues and problems.

    Handles reporting and tracking of issues with rental items
    including severity levels and resolution status.
    """

    queryset = RentalIssue.objects.select_related('rental_item', 'reported_by').all()
    serializer_class = RentalIssueSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['issue_type', 'severity', 'resolved']


class EquipmentSetViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing equipment sets.

    Handles predefined sets of equipment that can be rented together
    with member-only access for creation and editing.
    """

    queryset = EquipmentSet.objects.prefetch_related('items').all()
    serializer_class = EquipmentSetSerializer
    permission_classes = [IsAuthenticatedAndMemberOrReadOnly]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_template', 'is_active']
    search_fields = ['name', 'description']


class EquipmentSetItemViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing items within equipment sets.

    Handles individual items that make up equipment sets
    with member-only access for management.
    """

    queryset = EquipmentSetItem.objects.select_related('equipment_set', 'inventory_item').all()
    serializer_class = EquipmentSetItemSerializer
    permission_classes = [IsAuthenticatedAndMemberOrReadOnly]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['equipment_set', 'inventory_item']


class AccessDeniedView(TemplateView):
    """
    View for access denied page.

    Displays a user-friendly message when access is denied
    due to insufficient permissions.
    """

    template_name = 'rental/access_denied.html'


class StaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to require staff access with better error handling.

    Provides custom error messages and redirects for unauthorized access,
    distinguishing between unauthenticated users and insufficient permissions.
    """

    def test_func(self):
        """
        Check if user has staff permissions.

        Returns:
            bool: True if user is authenticated and staff, False otherwise
        """
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        """
        Handle unauthorized access with appropriate messages and redirects.

        Returns:
            HttpResponse: Redirect to login or access denied page
        """
        if not self.request.user.is_authenticated:
            messages.warning(
                self.request,
                _('You must log in to access this page.')
            )
            return redirect('login')
        else:
            messages.error(
                self.request,
                _('You do not have permission to access this page. Only staff have access.')
            )
            return redirect('rental:access_denied')


class RentalProcessView(StaffRequiredMixin, TemplateView):
    """
    Custom admin page for rental process management.

    Provides staff interface for creating and managing rental requests,
    including user selection, inventory browsing, and equipment set management.
    """

    template_name = 'rental/admin_rental_process.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data for rental process page.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context with users, inventory, organizations, and equipment sets
        """
        context = super().get_context_data(**kwargs)
        users = OKUser.objects.select_related('profile').filter(is_active=True)
        
        # Use the inventory service to get available items
        inventory_data = inventory_service.get_available_items()
        inventory_ids = [item['id'] for item in inventory_data]
        inventory = inventory_service.get_items_by_ids(inventory_ids)
        
        organizations = inventory_service.get_item_organizations()
        equipment_sets = EquipmentSet.objects.filter(is_active=True)
        context.update({
            'users': users,
            'inventory_items': inventory,
            'organizations': organizations,
            'equipment_sets': equipment_sets,
        })
        return context


@login_required
@staff_member_required
def api_search_users(request):
    """
    Search users by name or email.

    Searches for users based on profile information and returns
    user details including member status and permissions.
    Also handles users without profiles (staff members).

    Args:
        request: HTTP request object with query parameter 'q'

    Returns:
        JsonResponse: List of matching users with their details
    """
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'users': []})
    
    # Search by email first (works for all users, including those without profile)
    # Then search by profile fields using LEFT JOIN to include users without profile
    users = OKUser.objects.select_related('profile').filter(
        Q(email__icontains=query) |
        Q(profile__first_name__icontains=query) |
        Q(profile__last_name__icontains=query)
    ).distinct()[:10]
    
    result = []
    from django.conf import settings
    state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
    organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
    
    for user in users:
        profile = getattr(user, 'profile', None)
        
        # Determine role: Staff has highest priority, then Member, then User
        if user.is_staff:
            member_status = _('Staff')
            # Staff have access to all items
            permissions_text = _('All items')
        elif profile and profile.member:
            member_status = _('Member')
            permissions_text = f"{state_institution}, {organization_owner}"
        else:
            member_status = _('User')
            permissions_text = state_institution
        
        # Get user name
        if profile:
            name = f"{profile.first_name} {profile.last_name}".strip()
            if not name:
                name = user.email  # Fallback to email if name is empty
        else:
            # User without profile (e.g., staff members with only email/password)
            name = user.email
                
        result.append({
            'id': user.id,
            'name': name,
            'email': user.email,
            'member_status': member_status,
            'permissions': permissions_text,
            'is_member': profile.member if profile else False,
            'is_staff': user.is_staff,
        })
    
    return JsonResponse({'users': result})


@login_required
@staff_member_required
def api_get_user_inventory(request, user_id):
    """
    Get available inventory for a specific user.

    Returns filtered inventory items based on user permissions and
    availability during specified time period.

    Args:
        request: HTTP request object with filter parameters
        user_id: ID of the user to get inventory for

    Returns:
        JsonResponse: List of available inventory items
    """
    user = get_object_or_404(OKUser, id=user_id)
    # For staff users, don't require profile
    profile = getattr(user, 'profile', None)
    if not profile and not getattr(user, 'is_staff', False):
        return JsonResponse({'error': _('User profile not found')}, status=400)

    # Get filter parameters
    owner_filter = request.GET.get('owner', '')
    location_filter = request.GET.get('location', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('search', '')

    # Get date parameters for availability calculation
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    # Parse dates
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = parse_datetime(start_date_str)
            if start_date:
                # Make sure date is timezone-aware
                if timezone.is_naive(start_date):
                    start_date = timezone.make_aware(start_date)
            else:
                # Try parsing as date only
                from django.utils.dateparse import parse_date
                date_only = parse_date(start_date_str)
                if date_only:
                    start_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.min.time()))
        except:
            pass

    if end_date_str:
        try:
            end_date = parse_datetime(end_date_str)
            if end_date:
                # Make sure date is timezone-aware
                if timezone.is_naive(end_date):
                    end_date = timezone.make_aware(end_date)
            else:
                # Try parsing as date only
                from django.utils.dateparse import parse_date
                date_only = parse_date(end_date_str)
                if date_only:
                    end_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.max.time()))
        except:
            pass

    # Get available inventory through the service interface
    inventory_data = inventory_service.get_available_items(user_id=user.id)
    
    # Check if user is staff (Mitarbeiter) - staff can see all items even if quantity is 0
    is_staff = getattr(user, 'is_staff', False)
    
    # Apply additional filters
    filtered_inventory = []
    for item in inventory_data:
        if not item:
            continue
            
        # Apply owner filter
        owner_data = item.get('owner') or {}
        owner_name = owner_data.get('name') if isinstance(owner_data, dict) else (owner_data or '')
        if owner_filter and owner_filter != 'all':
            if owner_name != owner_filter:
                continue
        
        # Apply category filter
        category_data = item.get('category') or {}
        category_name = category_data.get('name') if isinstance(category_data, dict) else (category_data or '')
        if category_filter and category_filter != 'all':
            # Normalize both strings: strip whitespace and compare case-insensitively
            category_name_normalized = category_name.strip().lower() if category_name else ''
            category_filter_normalized = category_filter.strip().lower()
            if category_name_normalized != category_filter_normalized:
                continue
        
        # Apply location filter
        location_data = item.get('location') or {}
        if isinstance(location_data, dict):
            location_path = location_data.get('full_path', '')
            location_name = location_data.get('name', '')
        else:
            location_path = ''
            location_name = ''
        
        if location_filter and location_filter != 'all':
            # Compare with full_path (as stored in filter)
            if location_path != location_filter:
                continue
        
        # Apply search query
        manufacturer = item.get('manufacturer', '') or ''
        if isinstance(manufacturer, dict):
            manufacturer = manufacturer.get('name', '')
        if search_query:
            search_text = f"{item.get('description', '')} {item.get('inventory_number', '')} {manufacturer} {category_name}"
            if search_query.lower() not in search_text.lower():
                continue
        
        # Check availability for the period
        if start_date and end_date:
            # Use period-specific availability calculation
            try:
                available_qty = RentalService.get_available_quantity_for_period(
                    item.get('id'),
                    start_date,
                    end_date
                )
            except Exception:
                # Fallback to general availability if period calculation fails
                available_qty = inventory_service.get_available_quantity(item.get('id'))
        else:
            # No dates specified, use general availability
            available_qty = inventory_service.get_available_quantity(item.get('id'))
        
        # For staff users, show all items even if available_qty is 0
        # For regular users, only show items with available_qty > 0
        if available_qty > 0 or is_staff:
            
            filtered_inventory.append({
                'id': item.get('id'),
                'inventory_number': item.get('inventory_number', ''),
                'description': item.get('description', ''),
                'location_path': location_path,
                'location_name': location_name,
                'owner': owner_name,
                'manufacturer': manufacturer,
                'category': category_name,
                'available_quantity': available_qty,
                'total_quantity': item.get('quantity', 0),
            })
    
    return JsonResponse({'inventory': filtered_inventory})


@login_required
def api_create_rental_user(request):
    """
    Create a new rental request (user version).
    This version is accessible to regular users but only for their own rentals.

    Args:
        request: HTTP request object with rental data

    Returns:
        JsonResponse: Success status and rental ID or error message
    """
    # Security check: users can only create rentals for themselves
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        
        rental_service = RentalService()
        result = rental_service.create_rental_request(data, request.user, request.user, is_user_request=True)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({'error': result['error']}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@staff_member_required
def api_create_rental(request):
    """
    Create a new rental request.

    Creates rental requests for equipment and rooms with validation
    of dates, availability, and user permissions.

    Args:
        request: HTTP request object with rental data

    Returns:
        JsonResponse: Success status and rental ID or error message
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)
    
    try:
        data = json.loads(request.body)
        
        rental_service = RentalService()
        user = get_object_or_404(OKUser, id=data['user_id'])
        result = rental_service.create_rental_request(data, user, request.user, is_user_request=False)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({'error': result['error']}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def get_available_quantity_for_period(item, start_date, end_date):
    """
    Calculate available quantity for a specific time period.

    Determines how many items are available for rental during a given
    time period by considering existing reservations and rentals.

    Args:
        item: InventoryItem instance to check availability for
        start_date: Start datetime of the requested period
        end_date: End datetime of the requested period

    Returns:
        int: Available quantity for the specified period
    """
    rental_service = RentalService()
    return rental_service.get_available_quantity_for_period(item, start_date, end_date)


@login_required
@staff_member_required
def api_get_user_stats(request, user_id):
    """
    Get rental statistics for a specific user.

    Returns counts of active, completed, and overdue rentals
    along with recent rental activities.

    Args:
        request: HTTP request object
        user_id: ID of the user to get stats for

    Returns:
        JsonResponse: User rental statistics and recent activities
    """
    from django.utils import timezone
    user = get_object_or_404(OKUser, id=user_id)
    active_rentals = RentalRequest.objects.filter(user=user, status__in=['draft', 'reserved', 'issued']).count()
    completed_rentals = RentalRequest.objects.filter(user=user, status='returned').count()
    overdue_rentals = RentalRequest.objects.filter(user=user, status='issued', requested_end_date__lt=timezone.now()).count()
    recent_activities = RentalRequest.objects.filter(user=user).order_by('-created_at')[:5]
    activities = [{
        'project_name': r.project_name,
        'date': r.created_at.strftime('%d.%m.%Y'),
        'status': r.get_status_display(),
    } for r in recent_activities]
    return JsonResponse({
        'active_rentals': active_rentals,
        'completed_rentals': completed_rentals,
        'overdue_rentals': overdue_rentals,
        'recent_activities': activities,
    })


@login_required
@staff_member_required
def api_user_active_items(request, user_id):
    """
    Get list of active issued items for a user to return.

    Returns items that are currently issued to the user and have
    outstanding quantities that need to be returned.

    Args:
        request: HTTP request object
        user_id: ID of the user to get active items for

    Returns:
        JsonResponse: List of active rental items with outstanding quantities
    """
    user = get_object_or_404(OKUser, id=user_id)
    items = RentalItem.objects.select_related('inventory_item', 'rental_request').filter(
        rental_request__user=user,
        rental_request__status='issued',
    )
    result = []
    for it in items:
        outstanding = max(0, (it.quantity_issued or 0) - (it.quantity_returned or 0))
        if outstanding > 0:
            inv = it.inventory_item
            result.append({
                'rental_item_id': it.id,
                'rental_request_id': it.rental_request.id,
                'inventory_number': inv.inventory_number,
                'description': inv.description,
                'outstanding': outstanding,
            })
    return JsonResponse({'items': result})


@login_required
@staff_member_required
def api_return_items(request):
    """
    Return selected items (creates RentalTransaction 'return').

    Processes item returns and updates rental status when all items
    in a rental request are fully returned.

    Args:
        request: HTTP request object with items to return

    Returns:
        JsonResponse: Success status or error message
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        
        rental_service = RentalService()
        result = rental_service.return_items(items, request.user)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({'error': result['error']}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@staff_member_required
def api_get_filter_options(request):
    """
    Get filter options for inventory.

    Returns available filter options for organizations (owners),
    locations, and categories to help with inventory filtering.
    If user_id is provided, filters owners based on user access rights.

    Args:
        request: HTTP request object with optional user_id parameter

    Returns:
        JsonResponse: Available filter options for inventory
    """
    from django.conf import settings
    
    # Get user_id if provided
    user_id = request.GET.get('user_id', None)
    
    # Get organizations (owners)
    all_organizations = inventory_service.get_item_organizations()
    
    # Filter owners based on user access if user_id provided
    if user_id:
        try:
            user = OKUser.objects.get(id=user_id)
            state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
            organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
            
            if user.is_staff:
                # Staff can see all owners
                organizations = all_organizations
            elif hasattr(user, 'profile') and user.profile and user.profile.member:
                # Members can see state institution + organization
                organizations = [
                    org for org in all_organizations 
                    if org.get('name') in [state_institution, organization_owner]
                ]
            else:
                # Regular users can only see state institution
                organizations = [
                    org for org in all_organizations 
                    if org.get('name') == state_institution
                ]
        except OKUser.DoesNotExist:
            organizations = all_organizations
    else:
        organizations = all_organizations

    # Get locations with hierarchical structure
    locations = inventory_service.get_item_locations()

    # Get categories
    categories = inventory_service.get_item_categories()

    return JsonResponse({
        'owners': organizations,
        'locations': locations,
        'categories': categories,
    })


@login_required
@staff_member_required
def api_get_equipment_sets(request):
    """
    Get available equipment sets.

    Returns equipment sets that are active and have all items
    available for rental.

    Args:
        request: HTTP request object

    Returns:
        JsonResponse: List of available equipment sets
    """

    try:
        from .models import EquipmentSet
        equipment_sets = EquipmentSet.objects.filter(is_active=True)

        result = []
        for equipment_set in equipment_sets:
            # Check availability of all items in the set
            all_items_available = True
            total_items = 0

            for set_item in equipment_set.items.all():
                inventory_item = set_item.inventory_item
                if inventory_item:
                    total_items += 1
                    # Simple availability check
                    if not inventory_item.available_for_rent or inventory_item.status != 'in_stock':
                        all_items_available = False
                        break

            if all_items_available and total_items > 0:
                result.append({
                    'id': equipment_set.id,
                    'name': equipment_set.name,
                    'description': equipment_set.description,
                    'items_count': total_items,
                })

        return JsonResponse({'success': True, 'equipment_sets': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def api_get_equipment_set_details(request, set_id):
    """
    Get detailed information about a specific equipment set.

    Returns comprehensive details about an equipment set including
    all items, their availability, and metadata.

    Args:
        request: HTTP request object
        set_id: ID of the equipment set to get details for

    Returns:
        JsonResponse: Detailed equipment set information
    """
    try:
        from .models import EquipmentSet
        equipment_set = get_object_or_404(EquipmentSet, id=set_id, is_active=True)

        items_data = []
        for set_item in equipment_set.items.all():
            inventory_item = set_item.inventory_item
            if inventory_item:
                # Check item availability
                is_available = inventory_item.available_for_rent and inventory_item.status == 'in_stock'

                items_data.append({
                    'id': set_item.id,
                    'inventory_item_id': inventory_item.id,
                    'inventory_number': inventory_item.inventory_number,
                    'description': inventory_item.description,
                    'quantity_needed': set_item.quantity,
                    'quantity_available': inventory_item.quantity if is_available else 0,
                    'is_available': is_available,
                    'location': inventory_item.location.full_path if inventory_item.location else _('Location not specified'),
                    'category': inventory_item.category.name if inventory_item.category else _('No category')
                })

        result = {
            'id': equipment_set.id,
            'name': equipment_set.name,
            'description': equipment_set.description,
            'items': items_data,
            'total_items': len(items_data)
        }

        return JsonResponse({'success': True, 'equipment_set': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_get_rooms(request):
    """
    Get available rooms.

    Returns rooms with availability information for specified time periods,
    including conflict details for unavailable rooms.

    Args:
        request: HTTP request object with optional date parameters

    Returns:
        JsonResponse: List of rooms with availability status
    """

    try:
        from .models import Room
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime

        # Get time parameters for availability checking
        start_date_str = request.GET.get('start_date', '')
        end_date_str = request.GET.get('end_date', '')

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = parse_datetime(start_date_str)
                if not start_date:
                    from django.utils.dateparse import parse_date
                    date_only = parse_date(start_date_str)
                    if date_only:
                        start_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.min.time()))
            except:
                pass

        if end_date_str:
            try:
                end_date = parse_datetime(end_date_str)
                if not end_date:
                    from django.utils.dateparse import parse_date
                    date_only = parse_date(end_date_str)
                    if date_only:
                        end_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.max.time()))
            except:
                pass

        rooms = Room.objects.filter(is_active=True)

        result = []
        for room in rooms:
            # Check room availability
            is_available = True
            availability_info = _("Available")

            if start_date and end_date:
                if not room.is_available_for_time(start_date, end_date):
                    is_available = False
                    # Get conflict information
                    conflicts = room.get_conflicting_rentals(start_date, end_date)
                    if conflicts:
                        conflict_details = []
                        for conflict in conflicts[:3]:  # Show maximum 3 conflicts
                            user = conflict.rental_request.user
                            user_name = _("Unknown user")

                            # Try to get name from profile
                            try:
                                if hasattr(user, 'profile') and user.profile:
                                    profile = user.profile
                                    if hasattr(profile, 'first_name') and profile.first_name and hasattr(profile, 'last_name') and profile.last_name:
                                        user_name = f"{profile.first_name} {profile.last_name}"
                                    elif hasattr(profile, 'first_name') and profile.first_name:
                                        user_name = profile.first_name
                                    elif hasattr(profile, 'last_name') and profile.last_name:
                                        user_name = profile.last_name
                                elif hasattr(user, 'first_name') and user.first_name and hasattr(user, 'last_name') and user.last_name:
                                    user_name = f"{user.first_name} {user.last_name}"
                                elif hasattr(user, 'username') and user.username:
                                    user_name = user.username
                                elif hasattr(user, 'email') and user.email:
                                    user_name = user.email.split('@')[0]
                                else:
                                    user_name = _("User #{user_id}").format(user_id=user.id)
                            except:
                                user_name = _("User #{user_id}").format(user_id=user.id)

                            project = conflict.rental_request.project_name
                            status = conflict.rental_request.get_status_display()
                            conflict_details.append(f"{user_name} ({project})")

                        availability_info = _("Not available - Conflicts: {conflicts}").format(
                            conflicts=", ".join(conflict_details)
                        )
                        if len(conflicts) > 3:
                            availability_info += _(" and {count} more").format(count=len(conflicts) - 3)

            result.append({
                'id': room.id,
                'name': room.name,
                'description': room.description,
                'capacity': room.capacity,
                'location': room.location,
                'is_available': is_available,
                'availability_info': availability_info,
            })

        return JsonResponse({'success': True, 'rooms': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_get_user_rental_details_by_id(request, user_id=None):
    """
    Get detailed rental information for a user.

    Returns comprehensive rental details including items, rooms,
    and status information filtered by rental type.

    Args:
        request: HTTP request object with filter parameters
        user_id: ID of the user to get rental details for

    Returns:
        JsonResponse: Detailed rental information for the user
    """

    user = get_object_or_404(OKUser, id=user_id)
    rental_type = request.GET.get('type', 'active')  # active, returned, overdue
    rental_id = request.GET.get('rental_id')  # specific rental ID

    from .models import RentalRequest
    from django.utils import timezone

    base_query = RentalRequest.objects.select_related('user', 'created_by').prefetch_related(
        'items__inventory_item__category',
        'items__inventory_item__location',
        'items__transactions',
        'items__issues',
        'room_rentals__room'
    ).filter(user=user)

    # Filter by specific rental if provided
    if rental_id:
        rentals = base_query.filter(id=rental_id)
    elif rental_type == 'active':
        rentals = base_query.filter(status__in=['draft', 'reserved', 'issued'])
    elif rental_type == 'returned':
        rentals = base_query.filter(status='returned')
    elif rental_type == 'overdue':
        # Find rentals that are past their end date and not returned
        rentals = base_query.filter(
            status__in=['reserved', 'issued'],
            requested_end_date__lt=timezone.now()
        )
    else:
        rentals = base_query.none()

    result = []
    for rental in rentals:
        items_data = []
        for item in rental.items.all():
            items_data.append({
                'id': item.id,
                'inventory_item': {
                    'inventory_number': item.inventory_item.inventory_number,
                    'description': item.inventory_item.description,
                    'category': item.inventory_item.category.name if item.inventory_item.category else '',
                    'location': item.inventory_item.location.full_path if item.inventory_item.location else '',
                },
                'quantity_requested': item.quantity_requested,
                'quantity_issued': item.quantity_issued,
                'quantity_returned': item.quantity_returned,
                'actual_return_date': item.actual_return_date.isoformat() if item.actual_return_date else None,
                'is_overdue': item.is_overdue,
                'days_overdue': item.days_overdue,
                'outstanding': max(0, (item.quantity_issued or 0) - (item.quantity_returned or 0)),
            })

        # Calculate days overdue for overdue rentals
        days_overdue = 0
        if rental_type == 'overdue' and rental.requested_end_date:
            days_overdue = (timezone.now().date() - rental.requested_end_date.date()).days

        # Get rooms data
        rooms_data = []
        for room_rental in rental.room_rentals.all():
            rooms_data.append({
                'id': room_rental.id,
                'room': {
                    'id': room_rental.room.id,
                    'name': room_rental.room.name,
                    'description': room_rental.room.description,
                    'capacity': room_rental.room.capacity,
                    'location': room_rental.room.location,
                },
                'people_count': room_rental.people_count,
                'notes': room_rental.notes,
                'requested_start_date': room_rental.requested_start_date.isoformat() if room_rental.requested_start_date else None,
                'requested_end_date': room_rental.requested_end_date.isoformat() if room_rental.requested_end_date else None,
            })

        result.append({
            'id': rental.id,
            'project_name': rental.project_name,
            'purpose': rental.purpose,
            'status': rental.status,
            'status_display': rental.get_status_display(),
            'requested_start_date': rental.requested_start_date.isoformat() if rental.requested_start_date else None,
            'requested_end_date': rental.requested_end_date.isoformat() if rental.requested_end_date else None,
            'actual_start_date': rental.actual_start_date.isoformat() if rental.actual_start_date else None,
            'actual_end_date': rental.actual_end_date.isoformat() if rental.actual_end_date else None,
            'created_by': f"{rental.created_by.profile.first_name} {rental.created_by.profile.last_name} ({rental.created_by.email})" if rental.created_by and hasattr(rental.created_by, 'profile') and rental.created_by.profile else (rental.created_by.email if rental.created_by else ''),
            'created_at': rental.created_at.isoformat() if rental.created_at else None,
            'days_overdue': days_overdue,
            'items': items_data,
            'total_items': len(items_data),
            'room_rentals': rooms_data,
            'total_rooms': len(rooms_data),
        })

    return JsonResponse({
        'rentals': result,
        'type': rental_type,
        'user': {
            'id': user.id,
            'name': f"{user.profile.first_name} {user.profile.last_name}" if hasattr(user, 'profile') and user.profile else user.email,
            'email': user.email,
        }
    })


@login_required
@staff_member_required
def api_cancel_rental(request):
    """
    Cancel a rental request.

    Cancels active rentals by creating appropriate transactions
    and updating the rental status to cancelled.

    Args:
        request: HTTP request object with rental ID

    Returns:
        JsonResponse: Success status and confirmation message
    """

    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        rental_id = data.get('rental_id')

        if not rental_id:
            return JsonResponse({'error': _('Rental ID is required')}, status=400)

        rental_service = RentalService()
        result = rental_service.cancel_rental(rental_id, request.user)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({'error': result['error']}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_confirm_rental(request):
    """
    Confirm a draft rental request (status -> reserved).

    Args:
        request: HTTP request object with rental ID

    Returns:
        JsonResponse: Success status and updated rental status
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        rental_id = data.get('rental_id')

        if not rental_id:
            return JsonResponse({'error': _('Rental ID is required')}, status=400)

        rental = get_object_or_404(RentalRequest, id=rental_id)
        if rental.status != 'draft':
            return JsonResponse({'error': _('Only draft requests can be confirmed')}, status=400)

        rental.status = 'reserved'
        rental.save(update_fields=['status'])

        return JsonResponse({
            'success': True,
            'rental_id': rental.id,
            'status': rental.status,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_return_rental_items(request):
    """
    Return rental items with condition and issues tracking.

    Processes item returns with condition assessment and issue reporting,
    updating rental status when all items are returned.

    Args:
        request: HTTP request object with return data

    Returns:
        JsonResponse: Success status and completion information
    """

    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        rental_id = data.get('rental_id')
        items = data.get('items', [])

        if not rental_id or not items:
            return JsonResponse({'error': _('Rental ID and items are required')}, status=400)

        from .models import RentalIssue
        from .models import RentalRequest
        from .models import RentalTransaction

        rental_request = get_object_or_404(RentalRequest, id=rental_id)

        # Check if rental can have returns
        if rental_request.status not in ['reserved', 'issued']:
            return JsonResponse({'error': _('Only active rentals can have returns')}, status=400)

        for item_data in items:
            rental_item_id = item_data.get('rental_item_id')
            quantity = int(item_data.get('quantity', 0))
            condition = item_data.get('condition', 'good')
            notes = item_data.get('notes', '')
            issues = item_data.get('issues', [])

            if quantity <= 0:
                continue

            rental_item = rental_request.items.get(id=rental_item_id)

            # Create return transaction
            from django.utils import timezone

            transaction = RentalTransaction.objects.create(
                rental_item=rental_item,
                transaction_type='return',
                quantity=quantity,
                performed_by=request.user,
                condition=condition,
                notes=notes
            )

            # Update actual return date when item is fully returned
            rental_item.refresh_from_db()
            if (rental_item.quantity_issued or 0) <= (rental_item.quantity_returned or 0):
                # Item is fully returned - set actual return date
                rental_item.actual_return_date = timezone.now()
                rental_item.save(update_fields=['actual_return_date'])

            # Create issues if any
            for issue_data in issues:
                if issue_data.get('issue_type') and issue_data.get('description'):
                    RentalIssue.objects.create(
                        rental_item=rental_item,
                        issue_type=issue_data['issue_type'],
                        description=issue_data['description'],
                        severity=issue_data.get('severity', 'minor'),
                        reported_by=request.user
                    )

        # Check if all equipment items are returned
        # Note: Rooms are handled separately via automatic expiration
        # For mixed rentals, we only check equipment items for 'returned' status
        rental_request.refresh_from_db()
        all_equipment_returned = True
        has_equipment = rental_request.items.exists()
        
        if has_equipment:
            for item in rental_request.items.all():
                if (item.quantity_issued or 0) > (item.quantity_returned or 0):
                    all_equipment_returned = False
                    break
        else:
            # No equipment items, so technically "returned" (rooms handled separately)
            all_equipment_returned = True

        # Update rental status if all equipment items returned
        # Rooms will be automatically returned by the expiration task
        if all_equipment_returned and has_equipment:
            from django.utils import timezone
            rental_request.status = 'returned'
            rental_request.actual_end_date = timezone.now()
            rental_request.save(update_fields=['status', 'actual_end_date'])

        return JsonResponse({
            'success': True,
            'message': _('Items returned successfully'),
            'rental_completed': all_equipment_returned
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class RentalDetailView(StaffRequiredMixin, TemplateView):
    """
    Detail view for a specific rental request with return/extend options.

    Displays comprehensive rental information including items,
    transactions, and available actions for staff members.
    """

    template_name = 'rental/rental_detail.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data for rental detail page.

        Args:
            **kwargs: Additional context data including rental_id

        Returns:
            dict: Context with rental details and action permissions
        """
        context = super().get_context_data(**kwargs)
        rental_id = kwargs.get('rental_id')

        try:
            from .models import RentalRequest
            rental = RentalRequest.objects.select_related('user', 'created_by').prefetch_related(
                'items__inventory_item__owner',
                'items__inventory_item__location',
                'items__inventory_item__category',
                'items__transactions',
                'items__issues'
            ).get(id=rental_id)

            context['rental'] = rental
            context['can_confirm'] = rental.status == 'draft'
            context['can_return'] = rental.status in ['reserved', 'issued']
            context['can_extend'] = rental.status in ['reserved', 'issued']

        except Exception as e:
            context['error'] = str(e)

        return context


class UserRentalDetailView(LoginRequiredMixin, TemplateView):
    """
    User-facing detail view for a specific rental request.

    Shows summary details for the owning user without staff actions.
    """

    template_name = 'rental/user_rental_detail.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data for user rental detail page.

        Args:
            **kwargs: Additional context data including rental_id

        Returns:
            dict: Context with rental details
        """
        context = super().get_context_data(**kwargs)
        rental_id = kwargs.get('rental_id')

        try:
            from .models import RentalRequest
            rental = RentalRequest.objects.select_related('user', 'created_by').prefetch_related(
                'items__inventory_item__owner',
                'items__inventory_item__location',
                'items__inventory_item__category',
                'items__issues',
                'room_rentals__room'
            ).get(id=rental_id, user=self.request.user)

            context['rental'] = rental
        except Exception as e:
            context['error'] = str(e)

        return context


@login_required
@staff_member_required
def api_extend_rental(request):
    """
    Extend a rental request.

    Extends the end date of an active rental request with
    validation of the new date format and business rules.

    Args:
        request: HTTP request object with new end date

    Returns:
        JsonResponse: Success status and confirmation message
    """

    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        rental_id = data.get('rental_id')
        new_end_date = data.get('new_end_date')

        if not rental_id or not new_end_date:
            return JsonResponse({'error': _('Rental ID and new end date are required')}, status=400)

        from .models import RentalRequest
        from django.utils.dateparse import parse_datetime

        rental_request = get_object_or_404(RentalRequest, id=rental_id)

        # Check if rental can be extended
        if rental_request.status not in ['reserved', 'issued']:
            return JsonResponse({'error': _('Only active rentals can be extended')}, status=400)

        # Parse and validate new end date
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        import datetime

        try:
            new_end_datetime = parse_datetime(new_end_date)

            # If parse_datetime fails, try to parse as datetime-local format
            if not new_end_datetime:
                # Try parsing datetime-local format (YYYY-MM-DDTHH:MM)
                if 'T' in new_end_date and len(new_end_date) == 16:
                    try:
                        # Parse as naive datetime and make it timezone-aware
                        naive_datetime = datetime.datetime.fromisoformat(new_end_date)
                        new_end_datetime = timezone.make_aware(naive_datetime)
                    except:
                        pass

                # If still not parsed, try other formats
                if not new_end_datetime:
                    # Try parsing date only and add default time
                    date_part = new_end_date.split('T')[0] if 'T' in new_end_date else new_end_date
                    date_only = parse_date(date_part)
                    if date_only:
                        # Add default time (23:59) if only date is provided
                        default_time = datetime.time(hour=23, minute=59)
                        new_end_datetime = timezone.make_aware(datetime.datetime.combine(date_only, default_time))

            if not new_end_datetime:
                return JsonResponse({'error': _('Invalid date format. Please use YYYY-MM-DDTHH:MM or ISO format')}, status=400)

            # Ensure both dates are timezone-aware for comparison
            current_end_date = rental_request.requested_end_date
            if timezone.is_naive(current_end_date):
                current_end_date = timezone.make_aware(current_end_date)
            if timezone.is_naive(new_end_datetime):
                new_end_datetime = timezone.make_aware(new_end_datetime)

            if new_end_datetime <= current_end_date:
                return JsonResponse({'error': _('New end date must be after current end date')}, status=400)

        except Exception as e:
            return JsonResponse({'error': _('Invalid date format: {error}').format(error=str(e))}, status=400)

        # Update rental request
        rental_request.requested_end_date = new_end_datetime
        rental_request.save(update_fields=['requested_end_date'])

        return JsonResponse({
            'success': True,
            'message': _('Rental request {rental_id} has been extended until {end_date}').format(
                rental_id=rental_id,
                end_date=new_end_datetime.strftime("%d.%m.%Y %H:%M")
            )
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



class RentalStatsView(StaffRequiredMixin, TemplateView):
    """
    Statistics and administration page for rental system.

    Provides overview statistics and administrative functions
    for managing the rental system.
    """

    template_name = 'rental/rental_stats.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data for rental statistics page.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context with rental system statistics
        """
        context = super().get_context_data(**kwargs)

        try:
            from .models import RentalItem
            from .models import RentalRequest
            from django.db.models import Count
            from django.db.models import Q
            from django.db.models import Sum

            # Overall statistics
            total_rentals = RentalRequest.objects.count()
            active_rentals = RentalRequest.objects.filter(status__in=['reserved', 'issued']).count()
            total_users = OKUser.objects.filter(rentalrequest__isnull=False).distinct().count()
            total_items = len(inventory_service.get_available_items())

            context.update({
                'total_rentals': total_rentals,
                'active_rentals': active_rentals,
                'total_users': total_users,
                'total_items': total_items,
            })

        except Exception as e:
            context['error'] = str(e)

        return context


class InventoryCalendarDayView(StaffRequiredMixin, TemplateView):
    template_name = 'rental/inventory_calendar_day.html'

    def get_context_data(self, **kwargs):
        from django.utils import timezone
        from datetime import timedelta
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date')
        try:
            from django.utils.dateparse import parse_date
            day = parse_date(date_str) if date_str else timezone.now().date()
        except Exception:
            day = timezone.now().date()
        context['day'] = day
        context['prev_day'] = day - timedelta(days=1)
        context['next_day'] = day + timedelta(days=1)
        context['hours'] = list(range(10, 19))
        return context


class InventoryCalendarWeekView(StaffRequiredMixin, TemplateView):
    template_name = 'rental/inventory_calendar_week.html'

    def get_context_data(self, **kwargs):
        from django.utils import timezone
        from datetime import timedelta
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date')
        try:
            from django.utils.dateparse import parse_date
            ref = parse_date(date_str) if date_str else timezone.now().date()
        except Exception:
            ref = timezone.now().date()
        context['ref_day'] = ref
        context['prev_week'] = ref - timedelta(days=7)
        context['next_week'] = ref + timedelta(days=7)
        # Also expose the actual week day labels (dates) for header rendering
        context['week_days'] = [ref + timedelta(days=i) for i in range(7)]
        return context


@login_required
@staff_member_required
def api_reset_rental_system(request):
    """
    Reset rental system (DANGER: This will clear all rental data).

    Provides administrative functions to reset rental data, inventory quantities,
    or cancel active rentals. Requires special confirmation code for security.

    Args:
        request: HTTP request object with action and confirmation code

    Returns:
        JsonResponse: Success status and operation result
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        action = data.get('action')
        confirm_code = data.get('confirm_code')

        # Security check
        if confirm_code != 'RESET_ALL_DATA':
            return JsonResponse({'error': _('Invalid confirmation code')}, status=400)

        from .models import RentalIssue
        from .models import RentalItem
        from .models import RentalRequest
        from .models import RentalTransaction

        if action == 'reset_all':
            # Delete all rental data
            RentalIssue.objects.all().delete()
            RentalTransaction.objects.all().delete()
            RentalItem.objects.all().delete()
            RentalRequest.objects.all().delete()

            # Reset inventory quantities through the service
            # This action is only possible through direct model access, which we're trying to avoid
            # So we'll skip this part or implement a special endpoint for it
            message = _('All rental data has been reset (inventory quantities reset not supported through API)')

        elif action == 'reset_inventory_quantities':
            # Only reset inventory quantities through the service
            # This action is only possible through direct model access, which we're trying to avoid
            message = _('Inventory quantities reset not supported through API')

        elif action == 'cancel_active_rentals':
            # Cancel all active rentals
            from django.utils import timezone

            active_rentals = RentalRequest.objects.filter(status__in=['reserved', 'issued'])
            count = active_rentals.count()

            active_rentals.update(
                status='cancelled',
                actual_end_date=timezone.now()
            )

            # Reset inventory quantities through the service
            # This action is only possible through direct model access, which we're trying to avoid
            message = _('{count} active rentals have been cancelled (inventory quantities reset not supported through API)').format(count=count)

        else:
            return JsonResponse({'error': _('Invalid action')}, status=400)

        return JsonResponse({
            'success': True,
            'message': message
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_get_all_rentals(request):
    """
    Get all rentals with filtering options.

    Returns paginated list of all rentals with optional filtering
    by status and user search, including summary information.

    Args:
        request: HTTP request object with filter and pagination parameters

    Returns:
        JsonResponse: Paginated list of rentals with metadata
    """
    try:
        from .models import RentalRequest
        from django.core.paginator import Paginator

        # Get filter parameters
        status = request.GET.get('status', 'all')
        type_filter = request.GET.get('type', 'all')
        user_query = request.GET.get('user', '')
        page = int(request.GET.get('page', 1))

        # Base queryset
        rentals = RentalRequest.objects.select_related(
            'user', 'created_by'
        ).prefetch_related(
            'items__inventory_item',
            'room_rentals__room'
        ).order_by('-created_at')

        # Apply filters
        if status != 'all':
            rentals = rentals.filter(status=status)

        if type_filter != 'all':
            if type_filter == 'equipment':
                # Only equipment rentals (have items, no rooms)
                rentals = rentals.filter(items__isnull=False).exclude(room_rentals__isnull=False)
            elif type_filter == 'room':
                # Only room rentals (have rooms, no items)
                rentals = rentals.filter(room_rentals__isnull=False).exclude(items__isnull=False)
            elif type_filter == 'mixed':
                # Mixed rentals (have both items and rooms)
                rentals = rentals.filter(items__isnull=False, room_rentals__isnull=False)

        if user_query:
            # Safe filtering - only include profile filters if profile exists
            q_filters = Q(user__email__icontains=user_query)
            try:
                q_filters |= Q(user__profile__first_name__icontains=user_query) | Q(user__profile__last_name__icontains=user_query)
            except:
                pass  # Skip profile filtering if it causes issues
            rentals = rentals.filter(q_filters)

        # Paginate
        paginator = Paginator(rentals.distinct(), 20)
        page_obj = paginator.get_page(page)

        # PERFORMANCE OPTIMIZATION: Re-fetch with prefetch after pagination
        # Paginator breaks prefetch_related, so we need to re-apply it
        rental_ids = [r.id for r in page_obj]
        optimized_rentals = RentalRequest.objects.filter(
            id__in=rental_ids
        ).select_related(
            'user', 'created_by', 'user__profile', 'created_by__profile'
        ).prefetch_related(
            'items__inventory_item', 
            'room_rentals__room'
        )
        
        # Create dict for quick lookup maintaining page order
        rentals_dict = {r.id: r for r in optimized_rentals}
        ordered_rentals = [rentals_dict[rid] for rid in rental_ids if rid in rentals_dict]

        # Serialize data
        result = []
        for rental in ordered_rentals:
            # Safely get user name
            try:
                user_name = f"{rental.user.profile.first_name} {rental.user.profile.last_name}" if hasattr(rental.user, 'profile') and rental.user.profile else rental.user.email
            except:
                user_name = rental.user.email

            # Safely get created_by name
            try:
                created_by_name = f"{rental.created_by.profile.first_name} {rental.created_by.profile.last_name}" if rental.created_by and hasattr(rental.created_by, 'profile') and rental.created_by.profile else (rental.created_by.email if rental.created_by else 'N/A')
            except:
                created_by_name = rental.created_by.email if rental.created_by else 'N/A'

            items_summary = []
            for item in rental.items.all()[:3]:  # Show first 3 items
                items_summary.append({
                    'description': item.inventory_item.description or item.inventory_item.inventory_number,
                    'quantity': item.quantity_requested
                })

            # Get rooms summary
            rooms_summary = []
            for room_rental in rental.room_rentals.all()[:3]:  # Show first 3 rooms
                rooms_summary.append({
                    'name': room_rental.room.name,
                    'people_count': room_rental.people_count
                })

            result.append({
                'id': rental.id if rental else 0,
                'project_name': rental.project_name or '',
                'user_name': user_name or '',
                'user_email': rental.user.email if rental.user else '',
                'created_by_name': created_by_name or '',
                'status': rental.status or '',
                'rental_type': rental.rental_type or '',
                'created_at': rental.created_at.strftime('%d.%m.%Y %H:%M') if rental.created_at else '',
                'requested_start_date': rental.requested_start_date.isoformat() if rental.requested_start_date else '',
                'requested_end_date': rental.requested_end_date.isoformat() if rental.requested_end_date else '',
                'actual_end_date': rental.actual_end_date.isoformat() if rental.actual_end_date else '',
                'items_count': rental.items.count() if hasattr(rental, 'items') else 0,
                'rooms_count': rental.room_rentals.count() if hasattr(rental, 'room_rentals') else 0,
                'items_summary': items_summary or [],
                'rooms_summary': rooms_summary or []
            })

        return JsonResponse({
            'rentals': result or [],
            'has_next': page_obj.has_next() if page_obj else False,
            'has_previous': page_obj.has_previous() if page_obj else False,
            'current_page': page or 1,
            'total_pages': paginator.num_pages if paginator else 1,
            'total_count': paginator.count if paginator else 0
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_get_all_inventory_status(request):
    """
    Get inventory status overview.

    Returns comprehensive inventory status information including
    quantities, locations, and categories with optional filtering.

    Args:
        request: HTTP request object with filter parameters

    Returns:
        JsonResponse: List of inventory items with status information
    """
    try:
        # Get filter parameters
        owner_filter = request.GET.get('owner', 'all')
        status_filter = request.GET.get('status', 'all')

        # Get all available items through the service
        items = inventory_service.get_available_items()

        # Apply filters
        filtered_items = []
        for item in items:
            if not item:
                continue
                
            # Safely get owner data
            owner_data = item.get('owner')
            if owner_data is None:
                owner_name = 'N/A'
            elif isinstance(owner_data, dict):
                owner_name = owner_data.get('name', 'N/A')
            else:
                owner_name = str(owner_data) if owner_data else 'N/A'
            
            # Apply owner filter
            if owner_filter != 'all':
                if owner_name != owner_filter:
                    continue

            # Apply status filter
            if status_filter == 'rented':
                if (item.get('rented_quantity') or 0) <= 0:
                    continue
            elif status_filter == 'reserved':
                if (item.get('reserved_quantity') or 0) <= 0:
                    continue
            elif status_filter == 'available':
                if (item.get('reserved_quantity') or 0) > 0 or (item.get('rented_quantity') or 0) > 0:
                    continue

            # Safely get location data
            location_data = item.get('location')
            if location_data is None:
                location_path = 'N/A'
            elif isinstance(location_data, dict):
                location_path = location_data.get('full_path') or location_data.get('name', 'N/A')
            else:
                location_path = str(location_data) if location_data else 'N/A'
            
            # Safely get category data
            category_data = item.get('category')
            if category_data is None:
                category_name = 'N/A'
            elif isinstance(category_data, dict):
                category_name = category_data.get('name', 'N/A')
            else:
                category_name = str(category_data) if category_data else 'N/A'

            filtered_items.append({
                'id': item.get('id'),
                'inventory_number': item.get('inventory_number', ''),
                'description': item.get('description') or item.get('inventory_number', ''),
                'owner': owner_name,
                'location': location_path,
                'category': category_name,
                'reserved_quantity': item.get('reserved_quantity') or 0,
                'rented_quantity': item.get('rented_quantity') or 0,
                'status': item.get('status') or ''
            })

        return JsonResponse({
            'items': filtered_items or [],
            'total_count': len(filtered_items) if filtered_items else 0
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_inventory_calendar(request):
    """
    Aggregate availability for inventory over a period.

    Query params:
      - mode: 'day' | 'week' (default: day)
      - date: ISO date (YYYY-MM-DD), default: today

    For day mode: returns hours 10..18 per item with occupied/available.
    For week mode: returns 7 days per item with occupied/available (any overlap in day).
    """
    try:
        from datetime import datetime, timedelta
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        from .models import RentalItem

        mode = request.GET.get('mode', 'day')
        day = parse_date(request.GET.get('date') or '') or timezone.now().date()

        # Get inventory items through the service
        items_list = inventory_service.get_available_items()
        item_ids = [it['id'] for it in items_list]

        if mode == 'week':
            start_date = day
            end_date = day + timedelta(days=6)
        else:
            start_date = day
            end_date = day

        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

        rentals = (
            RentalItem.objects.select_related('rental_request')  # avoid selecting inventory_item to prevent model init side effects
            .filter(
                rental_request__status__in=['reserved', 'issued'],
                rental_request__requested_start_date__lte=end_dt,
                rental_request__requested_end_date__gte=start_dt,
                inventory_item_id__in=item_ids
            )
        )

        item_id_to_rentals = {}
        for ri in rentals:
            item_id_to_rentals.setdefault(ri.inventory_item_id, []).append(ri)

        result = []

        if mode == 'week':
            days = [start_date + timedelta(days=i) for i in range(7)]
            for it in items_list:
                day_statuses = []
                conflicts = item_id_to_rentals.get(it['id'], [])
                for d in days:
                    # Business day window 10:00..19:00
                    d_start = timezone.make_aware(datetime.combine(d, datetime.min.time()).replace(hour=10, minute=0))
                    d_end = timezone.make_aware(datetime.combine(d, datetime.min.time()).replace(hour=19, minute=0))
                    status = 'available'
                    has_reserved = False
                    selected_user = None
                    selected_req = None
                    for ri in conflicts:
                        rs = timezone.localtime(ri.rental_request.requested_start_date)
                        re = timezone.localtime(ri.rental_request.requested_end_date)
                        if rs <= d_end and re >= d_start:
                            # Prefer issued
                            if ri.rental_request.status == 'issued':
                                status = 'issued'
                                selected_req = ri
                                break
                            elif ri.rental_request.status == 'reserved':
                                has_reserved = True
                                if not selected_req:
                                    selected_req = ri
                    if status != 'issued' and has_reserved:
                        status = 'reserved'
                    info = None
                    if selected_req:
                        user = selected_req.rental_request.user
                        try:
                            profile = user.profile
                            full = f"{getattr(profile,'first_name','') or ''} {getattr(profile,'last_name','') or ''}".strip()
                            selected_user = full or (user.email.split('@')[0] if getattr(user,'email','') else str(user.id))
                        except Exception:
                            selected_user = user.email.split('@')[0] if getattr(user,'email','') else str(user.id)
                        
                        # Add info object for clickable slots
                        # Include start/end datetimes for display in modals
                        from django.utils import timezone as _tz
                        _rs = _tz.localtime(selected_req.rental_request.requested_start_date)
                        _re = _tz.localtime(selected_req.rental_request.requested_end_date)

                        info = {
                            'user_name': selected_user,
                            'status': selected_req.rental_request.status,
                            'rental_request_id': selected_req.rental_request_id,
                            'project': selected_req.rental_request.project_name or '',
                            'user_email': user.email if hasattr(user, 'email') and user.email else '',
                            'start': _rs.strftime('%d.%m.%Y %H:%M'),
                            'end': _re.strftime('%d.%m.%Y %H:%M'),
                        }
                    day_statuses.append({
                        'date': d.isoformat(),
                        'status': status,
                        'user_name': selected_user if selected_req else None,
                        'info': info
                    })

                result.append({
                    'id': it['id'],
                    'inventory_number': it['inventory_number'],
                    'description': it.get('description') or it['inventory_number'],
                    'week': day_statuses,
                })
        else:
            # Business hours view 10:00..18:00
            hours = list(range(10, 20))  # 10..19 inclusive
            for it in items_list:
                hour_slots = []
                conflicts = item_id_to_rentals.get(it['id'], [])
                for h in hours:
                    slot_start = timezone.make_aware(datetime.combine(day, datetime.min.time().replace(hour=h, minute=0)))
                    slot_end = slot_start + timedelta(hours=1)
                    status = 'available'
                    info = None
                    for ri in conflicts:
                        rs = timezone.localtime(ri.rental_request.requested_start_date)
                        re = timezone.localtime(ri.rental_request.requested_end_date)
                        if slot_start < re and slot_end > rs:
                            status = ri.rental_request.status  # reserved or issued
                            user = ri.rental_request.user
                            try:
                                profile = user.profile
                                full = f"{getattr(profile,'first_name','') or ''} {getattr(profile,'last_name','') or ''}".strip()
                                user_name = full or (user.email.split('@')[0] if getattr(user,'email','') else str(user.id))
                            except Exception:
                                user_name = user.email.split('@')[0] if getattr(user,'email','') else str(user.id)
                            info = {
                                'user_name': user_name,
                                'status': ri.rental_request.status,
                                'start': rs.strftime('%d.%m.%Y %H:%M'),
                                'end': re.strftime('%d.%m.%Y %H:%M'),
                                'id': ri.rental_request_id,
                                'rental_request_id': ri.rental_request_id,
                                'project': ri.rental_request.project_name or '',
                                'user_email': user.email if hasattr(user, 'email') and user.email else '',
                                'start_time': rs.strftime('%H:%M'),
                                'end_time': re.strftime('%H:%M'),
                            }
                            break
                    hour_slots.append({'time': f"{h:02d}:00", 'status': status, 'info': info})

                result.append({
                    'id': it['id'],
                    'inventory_number': it['inventory_number'],
                    'description': it.get('description') or it['inventory_number'],
                    'day': day.isoformat(),
                    'hours': hour_slots,
                })

        return JsonResponse({'success': True, 'mode': mode, 'date': day.isoformat(), 'items': result})
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        try:
            # Best-effort logging to console
            print('Error in api_inventory_calendar:', e)
            print(trace)
        except Exception:
            pass
        return JsonResponse({'success': False, 'error': str(e), 'trace': trace}, status=500)
def api_get_all_equipment_sets(request):
    """
    Get all equipment sets for admin management.

    Returns all equipment sets with their items and metadata
    for administrative management purposes.

    Args:
        request: HTTP request object

    Returns:
        JsonResponse: List of all equipment sets with details
    """
    try:
        from .models import EquipmentSet

        sets = EquipmentSet.objects.prefetch_related('items__inventory_item').order_by('-created_at')

        result = []
        for equipment_set in sets:
            result.append({
                'id': equipment_set.id,
                'name': equipment_set.name,
                'description': equipment_set.description or '',
                'is_active': equipment_set.is_active,
                'items_count': equipment_set.items.count(),
                'created_at': equipment_set.created_at.strftime('%d.%m.%Y %H:%M'),
                'created_by': f"{equipment_set.created_by.profile.first_name} {equipment_set.created_by.profile.last_name}" if equipment_set.created_by and hasattr(equipment_set.created_by, 'profile') and equipment_set.created_by.profile else (equipment_set.created_by.email if equipment_set.created_by else 'N/A'),
                'items': [
                    {
                        'id': item.id,
                        'inventory_item': {
                            'id': item.inventory_item.id,
                            'inventory_number': item.inventory_item.inventory_number,
                            'description': item.inventory_item.description or item.inventory_item.inventory_number,
                        },
                        'quantity': item.quantity,
                    }
                    for item in equipment_set.items.all()
                ]
            })

        return JsonResponse({
            'sets': result or [],
            'total_count': len(result) if result else 0
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_create_equipment_set(request):
    """
    Create a new equipment set.

    Creates a new equipment set with specified items and quantities,
    allowing staff to define reusable equipment combinations.

    Args:
        request: HTTP request object with equipment set data

    Returns:
        JsonResponse: Success status and created set information
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)

        from .models import EquipmentSet
        from .models import EquipmentSetItem

        # Create the set
        equipment_set = EquipmentSet.objects.create(
            name=data['name'],
            description=data.get('description', ''),
            is_active=data.get('is_active', True),
            created_by=request.user
        )

        # Add items to the set
        for item_data in data.get('items', []):
            inventory_item = InventoryItem.objects.get(id=item_data['inventory_item_id'])
            EquipmentSetItem.objects.create(
                equipment_set=equipment_set,
                inventory_item=inventory_item,
                quantity=item_data['quantity']
            )

        return JsonResponse({
            'success': True,
            'message': _('Equipment Set "{name}" was successfully created.').format(name=equipment_set.name),
            'set_id': equipment_set.id
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_delete_equipment_set(request, pk):
    """
    Delete an equipment set.

    Removes an equipment set and all its associated items
    from the system.

    Args:
        request: HTTP request object
        pk: Primary key of the equipment set to delete

    Returns:
        JsonResponse: Success status and confirmation message
    """
    if request.method != 'DELETE':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        from .models import EquipmentSet

        equipment_set = get_object_or_404(EquipmentSet, pk=pk)
        set_name = equipment_set.name
        equipment_set.delete()

        return JsonResponse({
            'success': True,
            'message': _('Equipment Set "{name}" was successfully deleted.').format(name=set_name)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_search_inventory_items(request):
    """
    Search inventory items for set creation.

    Searches for available inventory items that can be added
    to equipment sets with filtering and search capabilities.

    Args:
        request: HTTP request object with search query

    Returns:
        JsonResponse: List of matching inventory items
    """
    try:
        query = request.GET.get('q', '').strip()
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        from django.utils import timezone
        from django.utils.dateparse import parse_datetime
        from .services import RentalService
        from inventory.models import InventoryItem

        # Start with all items available for rent (don't filter by status for search)
        # This allows searching for all items, even if currently unavailable
        items = InventoryItem.objects.filter(
            available_for_rent=True
        ).select_related('category', 'location', 'owner', 'manufacturer')

        if query:
            # First, filter by database fields
            items = items.filter(
                Q(inventory_number__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(manufacturer__name__icontains=query) |
                Q(location__name__icontains=query) |
                Q(owner__name__icontains=query)
            )

        items = list(items[:150])  # Get more items to filter by full_path in Python
        
        # Additional filtering by full_path (computed property) in Python
        if query:
            query_lower = query.lower()
            filtered_items = []
            for item in items:
                # Check if already matched by database query
                matched = (
                    query_lower in (item.inventory_number or '').lower() or
                    query_lower in (item.description or '').lower() or
                    (item.category and query_lower in item.category.name.lower()) or
                    (item.manufacturer and query_lower in item.manufacturer.name.lower()) or
                    (item.location and query_lower in item.location.name.lower()) or
                    (item.owner and query_lower in item.owner.name.lower())
                )
                
                # Also check full_path (computed property)
                if not matched and item.location:
                    full_path_lower = item.location.full_path.lower()
                    if query_lower in full_path_lower:
                        matched = True
                
                if matched:
                    filtered_items.append(item)
            
            items = filtered_items[:100]  # Limit final results
        else:
            items = items[:100]

        result = []
        for item in items:
            # Check availability if dates are provided
            available_quantity = item.quantity or 0
            if start_date and end_date:
                try:
                    start_datetime = parse_datetime(start_date)
                    end_datetime = parse_datetime(end_date)

                    if start_datetime and end_datetime:
                        if timezone.is_naive(start_datetime):
                            start_datetime = timezone.make_aware(start_datetime)
                        if timezone.is_naive(end_datetime):
                            end_datetime = timezone.make_aware(end_datetime)

                        # Use RentalService method which takes item_id
                        available_quantity = RentalService.get_available_quantity_for_period(
                            item.id, start_datetime, end_datetime
                        )
                except Exception as e:
                    # If date parsing fails, use original quantity
                    pass

            # Include all items in search results (not just available ones)
            # This allows staff to see all items and their availability status
            manufacturer_name = item.manufacturer.name if item.manufacturer else ''
            
            result.append({
                'id': item.id,
                'inventory_number': item.inventory_number or '',
                'description': item.description or item.inventory_number or '',
                'category': item.category.name if item.category else 'Other',
                'location': item.location.full_path if item.location else 'N/A',
                'owner': item.owner.name if item.owner else 'N/A',
                'manufacturer': manufacturer_name,
                'available_quantity': available_quantity,
                'total_quantity': item.quantity or 0,
                'status': item.status or 'unknown'
            })

        return JsonResponse({
            'items': result or [],
            'total_count': len(result) if result else 0
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


class PrintFormMSAView(StaffRequiredMixin, TemplateView):
    """
    View for printing MSA rental forms.

    Displays MSA-specific rental information for printing,
    filtering items to show only MSA-owned equipment.
    """

    template_name = 'rental/print_form_msa.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data for MSA rental form printing.

        Args:
            **kwargs: Additional context data including rental_id

        Returns:
            dict: Context with MSA rental items and request details
        """
        context = super().get_context_data(**kwargs)
        rental_id = kwargs.get('rental_id')

        try:
            rental_request = get_object_or_404(RentalRequest, id=rental_id)

            # Get only MSA items for this rental
            msa_items = rental_request.items.filter(
                inventory_item__owner__name='MSA'
            ).select_related('inventory_item', 'inventory_item__owner')

            context.update({
                'rental_request': rental_request,
                'msa_items': msa_items,
            })

        except Exception as e:
            context['error'] = _('Error loading rental: {error}').format(error=str(e))

        return context


class PrintFormOKMQView(StaffRequiredMixin, TemplateView):
    """
    View for printing OKMQ rental forms.

    Displays OKMQ-specific rental information for printing,
    filtering items to show only OKMQ-owned equipment.
    """

    template_name = 'rental/print_form_okmq.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data for OKMQ rental form printing.

        Args:
            **kwargs: Additional context data including rental_id

        Returns:
            dict: Context with OKMQ rental items and request details
        """
        context = super().get_context_data(**kwargs)
        rental_id = kwargs.get('rental_id')

        try:
            rental_request = get_object_or_404(RentalRequest, id=rental_id)

            # Get only OKMQ items for this rental
            okmq_items = rental_request.items.filter(
                inventory_item__owner__name='OKMQ'
            ).select_related('inventory_item', 'inventory_item__owner', 'inventory_item__location')

            context.update({
                'rental_request': rental_request,
                'okmq_items': okmq_items,
            })

        except Exception as e:
            context['error'] = _('Error loading rental: {error}').format(error=str(e))

        return context


@login_required
@staff_member_required
def api_get_rental_print_info(request, rental_id):
    """
    Get rental print information.

    Returns information needed for printing rental forms,
    including item counts by owner organization.

    Args:
        request: HTTP request object
        rental_id: ID of the rental to get print info for

    Returns:
        JsonResponse: Rental print information and item counts
    """
    try:
        rental_request = get_object_or_404(RentalRequest, id=rental_id)

        # Count items by owner
        msa_count = rental_request.items.filter(inventory_item__owner__name='MSA').count()
        okmq_count = rental_request.items.filter(inventory_item__owner__name='OKMQ').count()

        try:
            user_name = f"{rental_request.user.profile.first_name} {rental_request.user.profile.last_name}" if hasattr(rental_request.user, 'profile') and rental_request.user.profile else rental_request.user.email
        except:
            user_name = rental_request.user.email

        return JsonResponse({
            'success': True,
            'rental_id': rental_request.id,
            'project_name': rental_request.project_name,
            'user_name': user_name,
            'msa_items_count': msa_count,
            'okmq_items_count': okmq_count,
            'has_msa_items': msa_count > 0,
            'has_okmq_items': okmq_count > 0,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_expire_room_rentals(request):
    """
    Manually trigger expiration of room rentals.

    Executes the management command to expire overdue room rentals
    and returns statistics about the operation.

    Args:
        request: HTTP request object

    Returns:
        JsonResponse: Operation results and statistics
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Only POST method allowed')}, status=405)

    try:
        from django.core.management import call_command
        from io import StringIO
        import json

        # Capture command output
        out = StringIO()

        # Run the command
        call_command('expire_room_rentals', stdout=out, verbosity=2)

        # Get the output
        output = out.getvalue()
        out.close()

        # Parse output to extract statistics
        lines = output.split('\n')
        expired_count = 0
        reserved_expired = 0
        issued_expired = 0

        for line in lines:
            if 'Found' in line and 'expired room rentals' in line:
                try:
                    expired_count = int(line.split()[1])
                except:
                    pass
            elif 'expired room reservations' in line:
                try:
                    reserved_expired = int(line.split()[0])
                except:
                    pass
            elif 'expired room issues' in line:
                try:
                    issued_expired = int(line.split()[0])
                except:
                    pass

        return JsonResponse({
            'success': True,
            'message': _('Automatic expiration of room rentals completed'),
            'output': output,
            'statistics': {
                'total_expired': expired_count,
                'reserved_expired': reserved_expired,
                'issued_expired': issued_expired
            }
        })

    except Exception as e:
        return JsonResponse({
            'error': _('Error executing command: {error}').format(error=str(e) if e else 'Unknown error')
        }, status=500)


@login_required
@staff_member_required
def api_get_room_schedule(request):
    """
    Get room schedule with detailed occupancy information.

    Returns comprehensive room scheduling information including
    time slots, availability status, and conflict details.

    Args:
        request: HTTP request object with date parameters

    Returns:
        JsonResponse: Room schedule with availability information
    """
    try:
        from .models import Room
        from .models import RoomRental
        from datetime import datetime
        from datetime import timedelta
        from django.utils import timezone
        from django.utils.dateparse import parse_date

        # Get parameters
        room_id = request.GET.get('room_id')
        start_date_str = request.GET.get('start_date', '')
        end_date_str = request.GET.get('end_date', '')

        # Parse dates
        start_date = None
        end_date = None

        if start_date_str:
            start_date = parse_date(start_date_str)
        if end_date_str:
            end_date = parse_date(end_date_str)

        # If dates are not specified, use current week
        if not start_date:
            start_date = timezone.now().date()
        if not end_date:
            end_date = start_date + timedelta(days=6)

        # Get rooms
        if room_id:
            rooms = Room.objects.filter(id=room_id, is_active=True)
        else:
            rooms = Room.objects.filter(is_active=True)

        result = []
        for room in rooms:
            # Get all room rentals in the specified period
            # Use __date for date-only comparison, avoiding timezone issues
            room_rentals = RoomRental.objects.filter(
                room=room,
                rental_request__status__in=['reserved', 'issued'],
                rental_request__requested_start_date__date__lte=end_date,
                rental_request__requested_end_date__date__gte=start_date
            ).select_related('rental_request__user')

            # Build schedule by days
            schedule = []
            current_date = start_date
            while current_date <= end_date:
                # German day names mapping
                german_days = {
                    0: 'MO',  # Monday
                    1: 'DI',  # Tuesday
                    2: 'MI',  # Wednesday
                    3: 'DO',  # Thursday
                    4: 'FR',  # Friday
                    5: 'SA',  # Saturday
                    6: 'SO'   # Sunday
                }

                day_schedule = {
                    'date': current_date.isoformat(),
                    'day_name': current_date.strftime('%A'),  # Monday, Tuesday, etc.
                    'day_short': german_days[current_date.weekday()],  # German abbreviations
                    'day_number': current_date.day,
                    'is_today': current_date == timezone.now().date(),
                    'is_weekend': current_date.weekday() >= 5,  # Saturday and Sunday
                    'slots': []
                }

                # Split day into 30-minute slots (10:00-18:00)
                for hour in range(10, 18):
                    for minute in [0, 30]:
                        # Create datetime objects for current day
                        slot_start = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))
                        slot_end = slot_start + timedelta(minutes=30)

                        # Check for overlaps with rentals
                        slot_status = 'available'
                        slot_info = None

                        for rental in room_rentals:
                            # Get rental dates - use room-specific dates if available, otherwise use rental request dates
                            rental_start = rental.get_start_date()
                            rental_end = rental.get_end_date()

                            # Check overlap using only time (without timezones)
                            if rental_start and rental_end:
                                # Convert to local time for comparison
                                rental_start_local = timezone.localtime(rental_start)
                                rental_end_local = timezone.localtime(rental_end)

                                # Create datetime objects for comparison
                                rental_start_time = datetime.combine(
                                    current_date,
                                    rental_start_local.time()
                                )
                                rental_end_time = datetime.combine(
                                    current_date,
                                    rental_end_local.time()
                                )

                                # Only consider rentals that actually cover this date
                                rental_covers_day = (
                                    rental_start_local.date() <= current_date <= rental_end_local.date()
                                )
                                if not rental_covers_day:
                                    continue

                                # Check overlap
                                if (slot_start < rental_end_time and slot_end > rental_start_time):
                                    slot_status = 'occupied'

                                    # Safely get user name
                                    user = rental.rental_request.user
                                    user_name = _("Unknown user")

                                    # Try to get name from profile (first_name + last_name)
                                    try:
                                        if hasattr(user, 'profile') and user.profile:
                                            profile = user.profile
                                            if hasattr(profile, 'first_name') and profile.first_name and hasattr(profile, 'last_name') and profile.last_name:
                                                user_name = f"{profile.first_name} {profile.last_name}"
                                            elif hasattr(profile, 'first_name') and profile.first_name:
                                                user_name = profile.first_name
                                            elif hasattr(profile, 'last_name') and profile.last_name:
                                                user_name = profile.last_name
                                        # If profile not found or empty, try other options
                                        elif hasattr(user, 'first_name') and user.first_name and hasattr(user, 'last_name') and user.last_name:
                                            user_name = f"{user.first_name} {user.last_name}"
                                        elif hasattr(user, 'username') and user.username:
                                            user_name = user.username
                                        elif hasattr(user, 'email') and user.email:
                                            user_name = user.email.split('@')[0]  # Take part before @
                                        else:
                                            user_name = _("User #{user_id}").format(user_id=user.id)
                                    except Exception as e:
                                        # In case of error, use fallback
                                        if hasattr(user, 'email') and user.email:
                                            user_name = user.email.split('@')[0]
                                        else:
                                            user_name = _("User #{user_id}").format(user_id=user.id)

                                    slot_info = {
                                        'user_name': user_name,
                                        'project': rental.rental_request.project_name or _("No project"),
                                        'status': rental.rental_request.status,
                                        'people_count': rental.people_count or 1,
                                        'start_time': rental_start_local.strftime('%H:%M'),
                                        'end_time': rental_end_local.strftime('%H:%M'),
                                        'rental_request_id': rental.rental_request.id,
                                        'user_email': user.email if hasattr(user, 'email') and user.email else ''
                                    }
                                    break

                        day_schedule['slots'].append({
                            'time': f"{hour:02d}:{minute:02d}",
                            'status': slot_status,
                            'info': slot_info
                        })

                schedule.append(day_schedule)
                current_date += timedelta(days=1)

            result.append({
                'id': room.id,
                'name': room.name,
                'description': room.description,
                'capacity': room.capacity,
                'location': room.location,
                'schedule': schedule
            })

        return JsonResponse({
            'success': True,
            'rooms': result,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        })

    except Exception as e:
        import traceback
        print(f"Error in api_get_room_schedule: {e}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_get_inventory_schedule(request):
    """Return schedule for a specific inventory item for a date range."""
    print(f"🔍 api_get_inventory_schedule called with params: {request.GET}")
    try:
        from .models import RentalItem
        from datetime import datetime
        from datetime import timedelta
        from django.utils import timezone
        from django.utils.dateparse import parse_date

        inv = request.GET.get('inv')
        print(f"🔍 Looking for inventory item: {inv}")
        if not inv:
            return JsonResponse({'error': 'inv is required'}, status=400)

        # Get inventory item through the service
        item = inventory_service.get_item_by_inventory_number(inv)
        print(f"🔍 Found item: {item}")
        if not item:
            return JsonResponse({'error': 'Item not found'}, status=404)

        start_date = parse_date(request.GET.get('start_date') or '')
        end_date = parse_date(request.GET.get('end_date') or '')
        if not start_date:
            start_date = timezone.now().date()
        if not end_date:
            end_date = start_date + timedelta(days=6)

        print(f"🔍 Querying rental items for date range: {start_date} to {end_date}")
        # PERFORMANCE OPTIMIZATION: Add select_related for all FK accessed in loop
        rental_items = RentalItem.objects.filter(
            inventory_item_id=item['id'],
            rental_request__status__in=['reserved', 'issued'],
            rental_request__requested_start_date__date__lte=end_date,
            rental_request__requested_end_date__date__gte=start_date,
        ).select_related(
            'rental_request', 
            'rental_request__user', 
            'inventory_item'
        )

        print(f"🔍 Found {rental_items.count()} rental items")
        if rental_items.count() > 0:
            for ri in rental_items:
                print(f"🔍 Rental item {ri.id}: {ri.rental_request.requested_start_date} to {ri.rental_request.requested_end_date}, status: {ri.rental_request.status}")
        else:
            print("🔍 No rental items found!")

        print(f"🔍 Building schedule for {len(range((end_date - start_date).days + 1))} days")
        schedule = []
        current = start_date
        day_count = 0

        while current <= end_date:
            day_count += 1
            print(f"🔍 Processing day {day_count}: {current}")

            day = {
                'date': current.isoformat(),
                'day_name': current.strftime('%A'),
                'day_short': current.strftime('%a'),
                'day_number': current.day,
                'is_today': current == timezone.now().date(),
                'is_weekend': current.weekday() >= 5,
                'slots': []
            }

            slot_count = 0
            for hour in range(0, 24):  # 24 hours with 1-hour steps
                slot_count += 1
                if slot_count % 6 == 0:  # Log every 6th slot to avoid spam
                    print(f"🔍 Processing slot {slot_count}/24 for day {current}")

                slot_start = timezone.make_aware(datetime.combine(current, datetime.min.time().replace(hour=hour, minute=0)))
                slot_end = slot_start + timedelta(hours=1)
                status = 'available'
                info = None

                for ri in rental_items:
                    rs = timezone.localtime(ri.rental_request.requested_start_date)
                    re = timezone.localtime(ri.rental_request.requested_end_date)

                    # Debug: print rental item details for first slot of each day
                    if slot_count == 1:  # Only for first slot to avoid spam
                        print(f"🔍 Checking rental item: {ri.id}, start: {rs}, end: {re}, current date: {current}")

                    # Check if current day is within rental period
                    # Fix: Convert current to timezone-aware datetime for comparison
                    current_start_of_day = timezone.make_aware(datetime.combine(current, datetime.min.time().replace(hour=0, minute=0)))
                    current_end_of_day = timezone.make_aware(datetime.combine(current, datetime.min.time().replace(hour=23, minute=59)))

                    if rs <= current_end_of_day and re >= current_start_of_day:
                        # Define working hours (10:00-19:00)
                        working_start = timezone.make_aware(datetime.combine(current, datetime.min.time().replace(hour=10, minute=0)))
                        working_end = timezone.make_aware(datetime.combine(current, datetime.min.time().replace(hour=19, minute=0)))

                        # For the current day, adjust rental times to working hours
                        if current == rs.date():
                            # First day of rental
                            if rs.hour >= 19:
                                # If rental starts after 19:00, move to next day's 10:00
                                continue
                            elif rs.hour < 10:
                                # If rental starts before 10:00, use 10:00
                                rental_start = working_start
                            else:
                                # Use actual rental start time
                                rental_start = rs
                        else:
                            # Middle days - use working start
                            rental_start = working_start

                        if current == re.date():
                            # Last day of rental
                            if re.hour < 10:
                                # If rental ends before 10:00, skip this day
                                continue
                            elif re.hour > 19:
                                # If rental ends after 19:00, use 19:00
                                rental_end = working_end
                            else:
                                # Use actual rental end time
                                rental_end = re
                        else:
                            # Middle days - use working end
                            rental_end = working_end

                        # Check overlap with current slot
                        if hour >= 10 and hour < 20:
                            print(f"🔍 Checking slot {hour}:00 ({slot_start.strftime('%H:%M')}-{slot_end.strftime('%H:%M')}) vs rental ({rental_start.strftime('%H:%M')}-{rental_end.strftime('%H:%M')})")
                        
                        if slot_start < rental_end and slot_end > rental_start:
                            status = 'occupied'
                            user = ri.rental_request.user

                            # Get full name from Profile model (First Name + Last Name) instead of email
                            try:
                                profile = user.profile
                                if profile and profile.first_name and profile.last_name:
                                    user_name = f"{profile.first_name} {profile.last_name}"
                                elif profile and profile.first_name:
                                    user_name = profile.first_name
                                elif profile and profile.last_name:
                                    user_name = profile.last_name
                                else:
                                    user_name = user.email.split('@')[0] if getattr(user, 'email', '') else str(user.id)
                            except:
                                # Fallback to email if profile doesn't exist
                                user_name = user.email.split('@')[0] if getattr(user, 'email', '') else str(user.id)

                            info = {
                                'user_name': user_name,
                                'project': ri.rental_request.project_name or '',
                                'status': ri.rental_request.status,
                                'start_time': rs.strftime('%H:%M'),
                                'end_time': re.strftime('%H:%M')
                            }

                            # Log occupied slots for working hours (10-19)
                            if hour >= 10 and hour < 20:
                                print(f"🔍 Slot {hour}:00 occupied! Status: {status}, User: {user_name}")

                            break
                        else:
                            if slot_count == 1:  # Only for first slot to avoid spam
                                print(f"🔍 No overlap: Slot {slot_start.strftime('%H:%M')}-{slot_end.strftime('%H:%M')} vs Rental {rental_start.strftime('%H:%M')}-{rental_end.strftime('%H:%M')}")

                day['slots'].append({'time': f"{hour:02d}:00", 'status': status, 'info': info})

            schedule.append(day)
            current += timedelta(days=1)
        print(f"🔍 Schedule built successfully with {len(schedule)} days")

        return JsonResponse({
            'success': True,
            'item': {
                'inventory_number': item['inventory_number'],
                'description': item.get('description'),
            },
            'schedule': schedule,
            'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}
        })
    except Exception as e:
        import traceback
        print('Error in api_get_inventory_schedule:', e)
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


# User-accessible API endpoints (without staff_member_required)

@login_required
def api_get_filter_options_user(request):
    """
    Get filter options for inventory (user version).
    This version is accessible to regular users.
    """
    # Get organizations (owners)
    organizations = inventory_service.get_item_organizations()

    # Get locations with hierarchical structure
    locations = inventory_service.get_item_locations()

    # Get categories
    categories = inventory_service.get_item_categories()

    return JsonResponse({
        'owners': organizations,
        'locations': locations,
        'categories': categories,
    })


@login_required
def api_get_user_inventory_simple(request, user_id):
    """
    Get available inventory for a specific user (simplified version).
    This version is accessible to regular users but only for their own inventory.
    """
    # Security check: users can only access their own inventory
    if request.user.id != user_id and not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)

    user = get_object_or_404(OKUser, id=user_id)
    profile = getattr(user, 'profile', None)
    if not profile:
        return JsonResponse({'error': _('User profile not found')}, status=400)

    # Get filter parameters
    owner_filter = request.GET.get('owner', '')
    location_filter = request.GET.get('location', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('search', '')

    # Get date parameters for availability calculation
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    # Parse dates
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = parse_datetime(start_date_str)
            if start_date:
                # Make sure date is timezone-aware
                if timezone.is_naive(start_date):
                    start_date = timezone.make_aware(start_date)
            else:
                # Try parsing as date only
                from django.utils.dateparse import parse_date
                date_only = parse_date(start_date_str)
                if date_only:
                    start_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.min.time()))
        except:
            pass

    if end_date_str:
        try:
            end_date = parse_datetime(end_date_str)
            if end_date:
                # Make sure date is timezone-aware
                if timezone.is_naive(end_date):
                    end_date = timezone.make_aware(end_date)
            else:
                # Try parsing as date only
                from django.utils.dateparse import parse_date
                date_only = parse_date(end_date_str)
                if date_only:
                    end_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.max.time()))
        except:
            pass

    # Get available inventory through the service interface
    inventory_data = inventory_service.get_available_items(user_id=user.id)
    
    # Apply additional filters
    filtered_inventory = []
    for item in inventory_data:
        # Apply owner filter
        owner_data = item.get('owner') or {}
        owner_name = owner_data.get('name') if isinstance(owner_data, dict) else (owner_data or '')
        if owner_filter and owner_filter != 'all':
            if owner_name != owner_filter:
                continue
        
        # Apply category filter
        category_data = item.get('category') or {}
        category_name = category_data.get('name') if isinstance(category_data, dict) else (category_data or '')
        if category_filter and category_filter != 'all':
            # Normalize both strings: strip whitespace and compare case-insensitively
            category_name_normalized = category_name.strip().lower() if category_name else ''
            category_filter_normalized = category_filter.strip().lower()
            if category_name_normalized != category_filter_normalized:
                continue
        
        # Apply search query
        manufacturer = item.get('manufacturer', '') or ''
        if isinstance(manufacturer, dict):
            manufacturer = manufacturer.get('name', '')
        if search_query:
            search_text = f"{item.get('description', '')} {item.get('inventory_number', '')} {manufacturer} {category_name}"
            if search_query.lower() not in search_text.lower():
                continue
        
        # Check availability for the period
        if start_date and end_date:
            # Use period-specific availability calculation
            try:
                available_qty = RentalService.get_available_quantity_for_period(
                    item['id'],
                    start_date,
                    end_date
                )
            except Exception:
                # Fallback to general availability if period calculation fails
                available_qty = inventory_service.get_available_quantity(item['id'])
        else:
            # No dates specified, use general availability
            available_qty = inventory_service.get_available_quantity(item['id'])
        
        if available_qty > 0:
            location_data = item.get('location') or {}
            owner_data = item.get('owner') or {}
            category_data = item.get('category') or {}
            
            # Handle location - can be dict or None
            if isinstance(location_data, dict):
                location_path = location_data.get('full_path', '')
                location_name = location_data.get('name', '')
            else:
                location_path = ''
                location_name = ''
            
            # Handle owner - can be dict or None
            if isinstance(owner_data, dict):
                owner_name = owner_data.get('name', '')
            else:
                owner_name = owner_data if owner_data else ''
            
            # Handle category - can be dict or None
            if isinstance(category_data, dict):
                category_name = category_data.get('name', '')
            else:
                category_name = category_data if category_data else ''
            
            # Handle manufacturer - can be string or None
            manufacturer = item.get('manufacturer', '') or ''
            if isinstance(manufacturer, dict):
                manufacturer = manufacturer.get('name', '')
            
            filtered_inventory.append({
                'id': item['id'],
                'inventory_number': item['inventory_number'],
                'description': item['description'],
                'location_path': location_path,
                'location_name': location_name,
                'owner': owner_name,
                'manufacturer': manufacturer,
                'category': category_name,
                'available_quantity': available_qty,
                'total_quantity': item.get('quantity', 0),
            })
    
    return JsonResponse({'inventory': filtered_inventory})


@login_required
def api_get_equipment_sets_user(request):
    """
    Get available equipment sets (user version).
    This version is accessible to regular users.
    """
    try:
        from .models import EquipmentSet
        equipment_sets = EquipmentSet.objects.filter(is_active=True)

        result = []
        for equipment_set in equipment_sets:
            # Check availability of all items in the set
            all_items_available = True
            total_items = 0

            for set_item in equipment_set.items.all():
                inventory_item = set_item.inventory_item
                if inventory_item:
                    total_items += 1
                    # Simple availability check
                    if not inventory_item.available_for_rent or inventory_item.status != 'in_stock':
                        all_items_available = False
                        break

            if all_items_available and total_items > 0:
                result.append({
                    'id': equipment_set.id,
                    'name': equipment_set.name,
                    'description': equipment_set.description,
                    'items_count': total_items,
                })

        return JsonResponse({'success': True, 'equipment_sets': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_get_equipment_set_details_user(request, set_id):
    """
    Get detailed information about a specific equipment set (user version).
    This version is accessible to regular users.

    Returns comprehensive details about an equipment set including
    all items, their availability, and metadata.

    Args:
        request: HTTP request object
        set_id: ID of the equipment set to get details for

    Returns:
        JsonResponse: Detailed equipment set information
    """
    try:
        from .models import EquipmentSet
        equipment_set = get_object_or_404(EquipmentSet, id=set_id, is_active=True)

        items_data = []
        for set_item in equipment_set.items.all():
            inventory_item = set_item.inventory_item
            if inventory_item:
                # Check item availability
                is_available = inventory_item.available_for_rent and inventory_item.status == 'in_stock'

                items_data.append({
                    'id': set_item.id,
                    'inventory_item_id': inventory_item.id,
                    'inventory_number': inventory_item.inventory_number,
                    'description': inventory_item.description,
                    'quantity_needed': set_item.quantity,
                    'quantity_available': inventory_item.quantity if is_available else 0,
                    'is_available': is_available,
                    'location': inventory_item.location.full_path if inventory_item.location else _('Location not specified'),
                    'category': inventory_item.category.name if inventory_item.category else _('No category')
                })

        result = {
            'id': equipment_set.id,
            'name': equipment_set.name,
            'description': equipment_set.description,
            'items': items_data,
            'total_items': len(items_data)
        }

        return JsonResponse({'success': True, 'equipment_set': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_get_rooms_user(request):
    """
    Get available rooms (user version).
    This version is accessible to regular users.
    """
    try:
        from .models import Room
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime

        # Get time parameters for availability checking
        start_date_str = request.GET.get('start_date', '')
        end_date_str = request.GET.get('end_date', '')

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = parse_datetime(start_date_str)
                if not start_date:
                    from django.utils.dateparse import parse_date
                    date_only = parse_date(start_date_str)
                    if date_only:
                        start_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.min.time()))
            except:
                pass

        if end_date_str:
            try:
                end_date = parse_datetime(end_date_str)
                if not end_date:
                    from django.utils.dateparse import parse_date
                    date_only = parse_date(end_date_str)
                    if date_only:
                        end_date = timezone.make_aware(timezone.datetime.combine(date_only, timezone.datetime.max.time()))
            except:
                pass

        rooms = Room.objects.filter(is_active=True)

        result = []
        for room in rooms:
            # Check room availability
            is_available = True
            availability_info = _("Available")

            if start_date and end_date:
                if not room.is_available_for_time(start_date, end_date):
                    is_available = False
                    availability_info = _("Not available for selected period")

            result.append({
                'id': room.id,
                'name': room.name,
                'description': room.description,
                'capacity': room.capacity,
                'location': room.location,
                'is_available': is_available,
                'availability_info': availability_info,
            })

        return JsonResponse({'success': True, 'rooms': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_get_room_schedule_user(request):
    """
    Get room schedule for regular users (without staff requirement).
    Returns room scheduling information for the specified period.
    """
    print(f"🔍 api_get_room_schedule_user ENTRY POINT")
    try:
        print(f"🔍 api_get_room_schedule_user called with params: {request.GET}")
        from datetime import datetime
        from datetime import timedelta
        from django.utils import timezone
        from django.utils.dateparse import parse_date

        # Get parameters
        room_id = request.GET.get('room_id')
        start_date_str = request.GET.get('start_date', '')
        end_date_str = request.GET.get('end_date', '')

        # Parse dates
        start_date = None
        end_date = None

        if start_date_str:
            start_date = parse_date(start_date_str)
        if end_date_str:
            end_date = parse_date(end_date_str)

        # If dates are not specified, use current week
        if not start_date:
            start_date = timezone.now().date()
        if not end_date:
            end_date = start_date + timedelta(days=6)

        # Get rooms
        if room_id:
            rooms = Room.objects.filter(id=room_id, is_active=True)
        else:
            rooms = Room.objects.filter(is_active=True)

        result = []
        for room in rooms:
            # Get all room rentals in the specified period
            room_rentals = RoomRental.objects.filter(
                room=room,
                rental_request__status__in=['reserved', 'issued'],
                rental_request__requested_start_date__date__lte=end_date,
                rental_request__requested_end_date__date__gte=start_date
            ).select_related('rental_request__user')

            # Build schedule by days
            schedule = []
            current_date = start_date
            while current_date <= end_date:
                # German day names mapping
                german_days = {
                    0: 'MO',  # Monday
                    1: 'DI',  # Tuesday
                    2: 'MI',  # Wednesday
                    3: 'DO',  # Thursday
                    4: 'FR',  # Friday
                    5: 'SA',  # Saturday
                    6: 'SO'   # Sunday
                }

                day_schedule = {
                    'date': current_date.isoformat(),
                    'day_name': current_date.strftime('%A'),
                    'day_short': german_days[current_date.weekday()],
                    'day_number': current_date.day,
                    'is_today': current_date == timezone.now().date(),
                    'is_weekend': current_date.weekday() >= 5,
                    'slots': []
                }

                # Split day into 30-minute slots (10:00-18:00)
                for hour in range(10, 18):
                    for minute in [0, 30]:
                        slot_start = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))
                        slot_start = timezone.make_aware(slot_start)
                        slot_end = slot_start + timedelta(minutes=30)

                        # Check for overlaps with rentals
                        slot_status = 'available'
                        slot_info = None

                        for rental in room_rentals:
                            rental_start = rental.rental_request.requested_start_date
                            rental_end = rental.rental_request.requested_end_date

                            # Check if slot overlaps with rental
                            if (slot_start < rental_end and slot_end > rental_start):
                                slot_status = 'occupied'
                                slot_info = {
                                    'user_name': rental.rental_request.user.get_full_name() or rental.rental_request.user.username,
                                    'project': rental.rental_request.project_name or 'No project',
                                    'status': rental.rental_request.status,
                                    'people_count': rental.people_count or 1,
                                    'start_time': rental.rental_request.requested_start_date.strftime('%H:%M'),
                                    'end_time': rental.rental_request.requested_end_date.strftime('%H:%M')
                                }
                                break

                        day_schedule['slots'].append({
                            'time': slot_start.strftime('%H:%M'),
                            'status': slot_status,
                            'info': slot_info
                        })

                schedule.append(day_schedule)
                current_date += timedelta(days=1)

            result.append({
                'id': room.id,
                'name': room.name,
                'capacity': room.capacity,
                'location': room.location,
                'schedule': schedule
            })

        print(f"🔍 Returning {len(result)} rooms with schedules")
        return JsonResponse({
            'success': True,
            'rooms': result,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        })

    except Exception as e:
        import traceback
        print(f"Error in api_get_room_schedule_user: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_get_user_rental_details(request):
    """
    Get detailed rental information for the current user.
    Returns rental details filtered by type (active, returned, overdue).
    """
    from django.utils import timezone

    try:
        rental_type = request.GET.get('type', 'active')

        # Get user's rental requests based on type
        user_rentals = RentalRequest.objects.select_related('created_by').prefetch_related(
            'items__inventory_item',
            'room_rentals__room'
        ).filter(user=request.user)

        if rental_type == 'active':
            # Active rentals are those that are draft/reserved/issued and NOT expired
            rentals = user_rentals.filter(
                status__in=['draft', 'reserved', 'issued']
            ).filter(
                requested_end_date__isnull=False,
                requested_end_date__gte=timezone.now()
            )
        elif rental_type == 'returned':
            rentals = user_rentals.filter(status='returned')
        elif rental_type == 'overdue':
            # Overdue rentals are those that are active but past their end date
            rentals = user_rentals.filter(
                status__in=['reserved', 'issued']
            ).filter(
                requested_end_date__isnull=False,
                requested_end_date__lt=timezone.now()
            )
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid type parameter'
            }, status=400)

        # Prepare rental data
        rental_data = []
        for rental in rentals:
            # Get rental items
            rental_items = []
            for item in rental.items.all():
                outstanding = (item.quantity_issued or 0) - (item.quantity_returned or 0)

                # Safely get inventory item info
                inventory_item = item.inventory_item
                if inventory_item:
                    description = inventory_item.description or 'No description'
                    inventory_number = inventory_item.inventory_number or 'N/A'
                else:
                    description = 'Unknown item'
                    inventory_number = 'N/A'

                rental_items.append({
                    'id': item.id if item else 0,
                    'inventory_item': {
                        'description': description,
                        'inventory_number': inventory_number
                    },
                    'quantity_requested': item.quantity_requested,
                    'quantity_issued': item.quantity_issued or 0,
                    'quantity_returned': item.quantity_returned or 0,
                    'outstanding': outstanding
                })

            # Get room rentals
            room_rentals = []
            for room_rental in rental.room_rentals.all():
                # Safely get room info
                room = room_rental.room
                if room:
                    room_name = room.name or 'Unknown room'
                    room_capacity = room.capacity or 0
                    room_location = room.location or 'Location not specified'
                else:
                    room_name = 'Unknown room'
                    room_capacity = 0
                    room_location = 'Location not specified'

                room_rentals.append({
                    'room': {
                        'name': room_name,
                        'capacity': room_capacity,
                        'location': room_location
                    },
                    'people_count': room_rental.people_count or 0,
                    'notes': room_rental.notes or '',
                    'requested_start_date': room_rental.requested_start_date.isoformat() if room_rental.requested_start_date else None,
                    'requested_end_date': room_rental.requested_end_date.isoformat() if room_rental.requested_end_date else None,
                })

            # Calculate days overdue if applicable
            days_overdue = 0
            if rental_type == 'overdue' and rental.requested_end_date:
                days_overdue = (timezone.now().date() - rental.requested_end_date.date()).days

            rental_data.append({
                'id': rental.id if rental else 0,
                'project_name': rental.project_name or '',
                'purpose': rental.purpose or '',
                'requested_start_date': rental.requested_start_date.isoformat() if rental.requested_start_date else None,
                'requested_end_date': rental.requested_end_date.isoformat() if rental.requested_end_date else None,
                'actual_end_date': rental.actual_end_date.isoformat() if rental.actual_end_date else None,
                'status': rental.status or '',
                'status_display': rental.get_status_display() if rental else '',
                'items': rental_items or [],
                'room_rentals': room_rentals or [],
                'days_overdue': days_overdue or 0
            })

        return JsonResponse({
            'success': True,
            'type': rental_type or '',
            'user': {
                'name': f"{request.user.profile.first_name} {request.user.profile.last_name}" if hasattr(request.user, 'profile') and request.user.profile and request.user.profile.first_name and request.user.profile.last_name else (request.user.email if request.user else ''),
                'email': request.user.email or ''
            },
            'rentals': rental_data or []
        })

    except Exception as e:
        import traceback
        print(f"Error in api_get_user_rental_details: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e) if e else 'Unknown error'
        }, status=500)


@login_required
def api_check_room_availability(request):
    """
    Check if a room is available for a specific time period.

    Args:
        request: HTTP request object with room_id, start_date, start_time, end_date, end_time

    Returns:
        JsonResponse: Availability status and any conflicts
    """
    if request.method != 'GET':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        room_id = request.GET.get('room_id')
        start_date = request.GET.get('start_date')
        start_time = request.GET.get('start_time')
        end_date = request.GET.get('end_date')
        end_time = request.GET.get('end_time')

        if not all([room_id, start_date, start_time, end_date, end_time]):
            return JsonResponse({'error': _('Missing required parameters')}, status=400)

        # Parse dates and times
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime

        start_datetime_str = f"{start_date}T{start_time}"
        end_datetime_str = f"{end_date}T{end_time}"

        start_datetime = parse_datetime(start_datetime_str)
        end_datetime = parse_datetime(end_datetime_str)

        if not start_datetime or not end_datetime:
            return JsonResponse({'error': _('Invalid date/time format')}, status=400)

        # Convert naive datetime to aware datetime if needed
        if timezone.is_naive(start_datetime):
            start_datetime = timezone.make_aware(start_datetime)
        if timezone.is_naive(end_datetime):
            end_datetime = timezone.make_aware(end_datetime)

        # Get room
        from .models import Room
        room = get_object_or_404(Room, id=room_id)

        # Check if room is available for the specified time
        is_available = room.is_available_for_time(start_datetime, end_datetime)

        if is_available:
            return JsonResponse({
                'success': True,
                'is_available': True,
                'message': _('Room is available for the selected period.')
            })
        else:
            # Get conflicting rentals for more detailed information
            conflicts = room.get_conflicting_rentals(start_datetime, end_datetime)
            conflict_info = []

            for conflict in conflicts:
                user = conflict.rental_request.user
                user_name = _("Unknown user")

                # Try to get name from profile
                try:
                    if hasattr(user, 'profile') and user.profile:
                        profile = user.profile
                        if hasattr(profile, 'first_name') and profile.first_name and hasattr(profile, 'last_name') and profile.last_name:
                            user_name = f"{profile.first_name} {profile.last_name}"
                        elif hasattr(profile, 'first_name') and profile.first_name:
                            user_name = profile.first_name
                        elif hasattr(profile, 'last_name') and profile.last_name:
                            user_name = profile.last_name
                    elif hasattr(user, 'first_name') and user.first_name and hasattr(user, 'last_name') and user.last_name:
                        user_name = f"{user.first_name} {user.last_name}"
                    elif hasattr(user, 'username') and user.username:
                        user_name = user.username
                    elif hasattr(user, 'email') and user.email:
                        user_name = user.email.split('@')[0]
                    else:
                        user_name = _("User #{user_id}").format(user_id=user.id)
                except:
                    user_name = _("User #{user_id}").format(user_id=user.id)

                project = conflict.rental_request.project_name
                status = conflict.rental_request.get_status_display()
                conflict_info.append(f"{user_name} ({project}) - {status}")

            return JsonResponse({
                'success': True,
                'is_available': False,
                'message': _('Room is not available for the selected period.'),
                'conflicts': conflict_info
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@staff_member_required
def api_save_template(request):
    """
    Save selected equipment items as a reusable template.

    Args:
        request: HTTP request object with template data

    Returns:
        JsonResponse: Success status and template ID or error message
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)

        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        items = data.get('items', [])

        if not name:
            return JsonResponse({'error': _('Template name is required')}, status=400)

        if not items:
            return JsonResponse({'error': _('At least one item is required')}, status=400)

        # Check if template with this name already exists
        from .models import EquipmentTemplate
        if EquipmentTemplate.objects.filter(name=name).exists():
            return JsonResponse({'error': _('Template with this name already exists')}, status=400)

        # Create template
        template = EquipmentTemplate.objects.create(
            name=name,
            description=description,
            created_by=request.user
        )

        # Create template items
        from .models import EquipmentTemplateItem
        for item_data in items:
            try:
                inventory_item = inventory_service.get_item(item_data['inventory_item_id'])
                quantity = item_data.get('quantity', 1)

                EquipmentTemplateItem.objects.create(
                    template=template,
                    inventory_item=inventory_item,
                    quantity=quantity
                )
            except InventoryItem.DoesNotExist:
                return JsonResponse({'error': _('Invalid inventory item ID')}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        return JsonResponse({
            'success': True,
            'template_id': template.id,
            'message': _('Template saved successfully')
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': _('Invalid JSON data')}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_get_templates(request):
    """
    Get all available equipment templates.

    Returns:
        JsonResponse: List of templates with basic info
    """
    try:
        from .models import EquipmentTemplate

        templates = EquipmentTemplate.objects.select_related('created_by').prefetch_related('items').all()

        template_data = []
        for template in templates:
            template_data.append({
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'created_by_name': template.created_by.get_full_name() or template.created_by.email if template.created_by else 'Unknown',
                'created_at': template.created_at.isoformat(),
                'items_count': template.items.count()
            })

        return JsonResponse({
            'success': True,
            'templates': template_data
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_load_template(request, template_id):
    """
    Load a specific template with its items.

    Args:
        request: HTTP request object
        template_id: ID of the template to load

    Returns:
        JsonResponse: Template data with items
    """
    try:
        from .models import EquipmentTemplate

        template = get_object_or_404(EquipmentTemplate, id=template_id)

        # Get template items with inventory details
        items_data = []
        for item in template.items.select_related('inventory_item__category', 'inventory_item__location').all():
            items_data.append({
                'quantity': item.quantity,
                'inventory_item': {
                    'id': item.inventory_item.id,
                    'description': item.inventory_item.description,
                    'inventory_number': item.inventory_item.inventory_number,
                    'category': {
                        'name': item.inventory_item.category.name if item.inventory_item.category else ''
                    } if item.inventory_item.category else None,
                    'location': {
                        'name': item.inventory_item.location.name if item.inventory_item.location else ''
                    } if item.inventory_item.location else None
                }
            })

        return JsonResponse({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'items': items_data
            }
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@staff_member_required
def api_delete_template(request, template_id):
    """
    Delete an equipment template.

    Args:
        request: HTTP request object
        template_id: ID of the template to delete

    Returns:
        JsonResponse: Success status or error message
    """
    if request.method != 'DELETE':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        from .models import EquipmentTemplate

        template = get_object_or_404(EquipmentTemplate, id=template_id)
        template_name = template.name
        template.delete()

        return JsonResponse({
            'success': True,
            'message': _('Template deleted successfully')
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def api_issue_from_reservation(request):
    """
    Issue a rental from reservation status with ability to adjust positions and dates.

    Args:
        request: HTTP request object with rental_id, start_date, end_date, created_by, notes, item_quantities

    Returns:
        JsonResponse: Success status and message
    """
    if request.method != 'POST':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        data = json.loads(request.body)
        rental_id = data.get('rental_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        created_by = data.get('created_by')
        notes = data.get('notes', '')
        item_quantities = data.get('item_quantities', {})
        new_items = data.get('new_items', [])

        if not all([rental_id, start_date, end_date, created_by]):
            return JsonResponse({'error': _('Missing required parameters')}, status=400)

        # Parse dates
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime

        start_datetime = parse_datetime(start_date)
        end_datetime = parse_datetime(end_date)

        if not start_datetime or not end_datetime:
            return JsonResponse({'error': _('Invalid date format')}, status=400)

        # Convert naive datetime to aware datetime if needed
        if timezone.is_naive(start_datetime):
            start_datetime = timezone.make_aware(start_datetime)
        if timezone.is_naive(end_datetime):
            end_datetime = timezone.make_aware(end_datetime)

        # Get rental request
        rental = get_object_or_404(RentalRequest, id=rental_id)

        # Check if rental is in draft or reserved status
        if rental.status not in ['draft', 'reserved']:
            return JsonResponse({'error': _('Rental must be in draft or reserved status to issue')}, status=400)

        # Check if rental has any equipment items (rooms alone cannot be issued)
        # For mixed rentals, we issue only equipment, rooms remain reserved
        has_equipment = rental.items.exists()
        if not has_equipment:
            return JsonResponse({'error': _('Cannot issue rental with only rooms. Equipment is required to change status from reserved to issued.')}, status=400)
        
        # Note: For mixed rentals (rooms + equipment), we can issue equipment
        # Rooms will remain in reserved status and auto-return after scheduled time

        # Get the user by ID
        try:
            from registration.models import OKUser
            created_by_user = OKUser.objects.get(id=created_by)
        except OKUser.DoesNotExist:
            return JsonResponse({'error': _('Invalid user ID')}, status=400)

        # Update rental request - only equipment rentals can be issued
        rental.status = 'issued'
        rental.requested_start_date = start_datetime
        rental.requested_end_date = end_datetime
        rental.created_by = created_by_user
        if notes:
            rental.notes = notes
        rental.save()

        # Update item quantities if provided
        if item_quantities:
            for item_id, quantity in item_quantities.items():
                try:
                    rental_item = RentalItem.objects.get(id=item_id, rental_request=rental)
                    
                    # Validate that the requested quantity is available
                    available_qty = RentalService.get_available_quantity_for_period(
                        rental_item.inventory_item_id,
                        start_datetime,
                        end_datetime,
                        exclude_rental_request=rental.id
                    )
                    
                    # Add back the currently issued quantity (if any) since we're excluding this rental
                    # This allows increasing quantity_issued up to the available limit
                    current_issued = rental_item.quantity_issued or 0
                    available_qty += current_issued
                    
                    if available_qty < quantity:
                        return JsonResponse({
                            'error': _('Item "{item_description}" is not available in requested quantity. Available: {available}, requested: {requested}').format(
                                item_description=rental_item.inventory_item.description,
                                available=available_qty,
                                requested=quantity
                            )
                        }, status=400)
                    
                    # Calculate difference and create transaction instead of setting directly
                    # This ensures the signal handler updates quantity_issued correctly
                    old_issued = rental_item.quantity_issued or 0
                    quantity_to_issue = quantity - old_issued
                    
                    if quantity_to_issue > 0:
                        # Create transaction for the difference
                        RentalService.create_transaction(
                            rental_item=rental_item,
                            transaction_type='issue',
                            quantity=quantity_to_issue,
                            performed_by=created_by_user
                        )
                    # Note: quantity_issued will be updated by the signal handler
                    # Don't set it directly to avoid double increment
                except RentalItem.DoesNotExist:
                    continue

        # Add new items to the rental
        if new_items:
            for new_item_data in new_items:
                try:
                    inventory_id = new_item_data.get('inventory_id')
                    quantity = new_item_data.get('quantity', 1)

                    # Get the inventory item
                    inventory_item = inventory_service.get_item(inventory_id)
                    if not inventory_item:
                        return JsonResponse({'error': _('Inventory item not found')}, status=400)

                    # Check availability - pass item_id (int) not dict
                    available_qty = RentalService.get_available_quantity_for_period(
                        inventory_id,
                        start_datetime,
                        end_datetime,
                        exclude_rental_request=rental.id
                    )

                    if available_qty < quantity:
                        return JsonResponse({
                            'error': _('Item "{item_description}" is not available for the selected period. Available: {available}, requested: {requested}').format(
                                item_description=inventory_item['description'],
                                available=available_qty,
                                requested=quantity
                            )
                        }, status=400)

                    # Create new rental item
                    new_rental_item = RentalItem.objects.create(
                        rental_request=rental,
                        inventory_item_id=inventory_item['id'],
                        quantity_requested=quantity,
                        quantity_issued=0  # Will be set by transaction
                    )
                    
                    # Create transaction to issue the item
                    RentalService.create_transaction(
                        rental_item=new_rental_item,
                        transaction_type='issue',
                        quantity=quantity,
                        performed_by=created_by_user
                    )

                except Exception as e:
                    return JsonResponse({'error': str(e)}, status=400)

        # Update room rentals if any - only update dates, keep status as reserved
        room_rentals = RoomRental.objects.filter(rental_request=rental)
        for room_rental in room_rentals:
            room_rental.start_date = start_datetime
            room_rental.end_date = end_datetime
            # Rooms remain in reserved status - they are not physically issued
            room_rental.save()

        return JsonResponse({
            'success': True,
            'message': _('Rental successfully issued from reservation')
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@staff_member_required
def api_get_staff_users(request):
    """
    Get list of staff users for dropdown selection.

    Returns:
        JsonResponse: List of staff users with id, name, and email
    """
    if request.method != 'GET':
        return JsonResponse({'error': _('Method not allowed')}, status=405)

    try:
        from registration.models import OKUser

        # Get all staff users
        staff_users = OKUser.objects.filter(is_staff=True).select_related('profile')

        users_data = []
        for user in staff_users:
            name = user.email
            if hasattr(user, 'profile') and user.profile:
                if user.profile.first_name and user.profile.last_name:
                    name = f"{user.profile.first_name} {user.profile.last_name}"
                elif user.profile.first_name:
                    name = user.profile.first_name
                elif user.profile.last_name:
                    name = user.profile.last_name

            users_data.append({
                'id': user.id,
                'name': name,
                'email': user.email
            })

        return JsonResponse({
            'success': True,
            'users': users_data
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)
