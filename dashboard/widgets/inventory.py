"""
Inventory and Rental Widget for Dashboard

This widget provides statistics and analytics for equipment inventory
and rental requests in the OK_tools system.
"""

from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from inventory.models import InventoryItem, Organization, Category, Location
from rental.models import RentalRequest, RentalItem, RentalTransaction, EquipmentSet, RoomRental
from registration.models import Profile, MediaAuthority


class InventoryWidget:
    """
    Widget for inventory and rental statistics
    """
    
    def __init__(self, filters=None):
        self.filters = filters or {}
        self._cache = {}
        self._cache_timeout = 300  # 5 minutes
    
    def get_basic_stats(self):
        """Get basic inventory and rental statistics"""
        cache_key = f"basic_stats_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Date filtering
        date_filter = self._get_date_filter()
        
        # Basic inventory stats with extended filters
        inventory_queryset = InventoryItem.objects.filter(available_for_rent=True)
        inventory_queryset = self._apply_inventory_filters(inventory_queryset)
        
        total_items = inventory_queryset.count()
        in_stock_items = inventory_queryset.filter(status='in_stock').count()
        rented_items = inventory_queryset.filter(rented_quantity__gt=0).count()
        reserved_items = inventory_queryset.filter(reserved_quantity__gt=0).count()
        
        # Rental stats with extended filters
        rental_queryset = RentalRequest.objects.filter(**date_filter)
        rental_queryset = self._apply_rental_filters(rental_queryset)
        
        total_rentals = rental_queryset.count()
        active_rentals = rental_queryset.filter(status__in=['reserved', 'issued']).count()
        completed_rentals = rental_queryset.filter(status='returned').count()
        
        # Equipment sets
        total_equipment_sets = EquipmentSet.objects.filter(is_active=True).count()
        
        stats = {
            'total_items': total_items,
            'in_stock_items': in_stock_items,
            'rented_items': rented_items,
            'reserved_items': reserved_items,
            'total_rentals': total_rentals,
            'active_rentals': active_rentals,
            'completed_rentals': completed_rentals,
            'total_equipment_sets': total_equipment_sets,
            'utilization_rate': round((rented_items / total_items * 100) if total_items > 0 else 0, 1),
            'completion_rate': round((completed_rentals / total_rentals * 100) if total_rentals > 0 else 0, 1)
        }
        
        self._cache[cache_key] = stats
        return stats
    
    def get_inventory_by_category(self):
        """Get inventory statistics by category"""
        cache_key = f"inventory_by_category_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Get all categories and filter inventory items manually
        all_categories = Category.objects.all()
        result = []
        
        for category in all_categories:
            # Get inventory items for this category with filters
            category_items = InventoryItem.objects.filter(
                available_for_rent=True,
                category=category
            )
            category_items = self._apply_inventory_filters(category_items)
            
            total_items = category_items.count()
            if total_items > 0:
                in_stock_items = category_items.filter(status='in_stock').count()
                rented_items = category_items.filter(rented_quantity__gt=0).count()
                
                result.append({
                    'name': category.name,
                    'total_items': total_items,
                    'in_stock_items': in_stock_items,
                    'rented_items': rented_items,
                    'utilization_rate': round((rented_items / total_items * 100) if total_items > 0 else 0, 1)
                })
        
        # Sort by total_items descending
        result.sort(key=lambda x: x['total_items'], reverse=True)
        
        self._cache[cache_key] = result
        return result
    
    def get_inventory_by_owner(self):
        """Get inventory statistics by owner organization"""
        cache_key = f"inventory_by_owner_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Get all organizations and filter inventory items manually
        all_organizations = Organization.objects.all()
        result = []
        
        for owner in all_organizations:
            # Get inventory items for this owner with filters
            owner_items = InventoryItem.objects.filter(
                available_for_rent=True,
                owner=owner
            )
            owner_items = self._apply_inventory_filters(owner_items)
            
            total_items = owner_items.count()
            if total_items > 0:
                in_stock_items = owner_items.filter(status='in_stock').count()
                rented_items = owner_items.filter(rented_quantity__gt=0).count()
                
                result.append({
                    'name': owner.name,
                    'total_items': total_items,
                    'in_stock_items': in_stock_items,
                    'rented_items': rented_items,
                'utilization_rate': round((rented_items / total_items * 100) if total_items > 0 else 0, 1)
            })
        
        self._cache[cache_key] = result
        return result
    
    def get_rentals_by_status(self):
        """Get rental statistics by status"""
        cache_key = f"rentals_by_status_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        date_filter = self._get_date_filter()
        
        rental_queryset = RentalRequest.objects.filter(**date_filter)
        rental_queryset = self._apply_rental_filters(rental_queryset)
        
        statuses = rental_queryset.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        result = []
        for status in statuses:
            result.append({
                'status': status['status'],
                'count': status['count']
            })
        
        self._cache[cache_key] = result
        return result
    
    def get_rentals_by_type(self):
        """Get rental statistics by type (equipment, room, mixed)"""
        cache_key = f"rentals_by_type_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        date_filter = self._get_date_filter()
        
        rental_queryset = RentalRequest.objects.filter(**date_filter)
        rental_queryset = self._apply_rental_filters(rental_queryset)
        
        types = rental_queryset.values('rental_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        result = []
        for rental_type in types:
            result.append({
                'type': rental_type['rental_type'] or 'equipment',
                'count': rental_type['count']
            })
        
        self._cache[cache_key] = result
        return result
    
    def get_rentals_by_user_demographics(self):
        """Get rental statistics by user demographics"""
        cache_key = f"rentals_by_demographics_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        date_filter = self._get_date_filter()
        
        rental_queryset = RentalRequest.objects.filter(**date_filter)
        rental_queryset = self._apply_rental_filters(rental_queryset)
        
        # Gender distribution
        gender_stats = rental_queryset.select_related('user__profile').values(
            'user__profile__gender'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Member vs non-member
        member_stats = rental_queryset.select_related('user__profile').values(
            'user__profile__member'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Age groups - simplified approach to avoid SQL issues
        age_groups = []
        try:
            # Get all rental requests with user profiles
            rentals_with_profiles = RentalRequest.objects.filter(
                **date_filter
            ).select_related('user__profile').exclude(
                user__profile__isnull=True
            ).exclude(
                user__profile__birthday__isnull=True
            )
            
            # Group by age manually
            age_groups_dict = {
                'Under 18': 0,
                '18-25': 0,
                '26-35': 0,
                '36-50': 0,
                'Over 50': 0,
                'Unknown': 0
            }
            
            from datetime import date
            today = date.today()
            
            for rental in rentals_with_profiles:
                if rental.user.profile and rental.user.profile.birthday:
                    age = today.year - rental.user.profile.birthday.year
                    if age < 18:
                        age_groups_dict['Under 18'] += 1
                    elif age <= 25:
                        age_groups_dict['18-25'] += 1
                    elif age <= 35:
                        age_groups_dict['26-35'] += 1
                    elif age <= 50:
                        age_groups_dict['36-50'] += 1
                    else:
                        age_groups_dict['Over 50'] += 1
                else:
                    age_groups_dict['Unknown'] += 1
            
            # Convert to list format
            age_groups = [
                {'age_group': age_group, 'count': count}
                for age_group, count in age_groups_dict.items()
                if count > 0
            ]
            age_groups.sort(key=lambda x: x['count'], reverse=True)
            
        except Exception as e:
            print(f"Error calculating age groups: {e}")
            age_groups = []
        
        result = {
            'gender': list(gender_stats),
            'membership': list(member_stats),
            'age_groups': list(age_groups)
        }
        
        self._cache[cache_key] = result
        return result
    
    def get_rentals_trend(self):
        """Get rental trends over time"""
        cache_key = f"rentals_trend_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        date_filter = self._get_date_filter()
        
        rental_queryset = RentalRequest.objects.filter(**date_filter)
        rental_queryset = self._apply_rental_filters(rental_queryset)
        
        # Get trend data based on filter period - simplified approach to avoid SQL issues
        trend_data = []
        try:
            # Get all rental requests and group by period manually
            all_rentals = rental_queryset.select_related()
            
            # Group by period manually
            from collections import defaultdict
            period_data = defaultdict(int)
            
            for rental in all_rentals:
                if rental.created_at:
                    if 'days' in self.filters:
                        days = int(self.filters['days'])
                        if days <= 7:
                            # Daily data
                            period_key = rental.created_at.strftime('%Y-%m-%d')
                        elif days <= 30:
                            # Weekly data
                            period_key = rental.created_at.strftime('%Y-W%U')
                        else:
                            # Monthly data
                            period_key = rental.created_at.strftime('%Y-%m')
                    else:
                        # Default to monthly
                        period_key = rental.created_at.strftime('%Y-%m')
                    
                    period_data[period_key] += 1
            
            # Convert to list format
            trend_data = [
                {'period': period, 'count': count}
                for period, count in sorted(period_data.items())
            ]
            
        except Exception as e:
            print(f"Error calculating rental trends: {e}")
            trend_data = []
        
        result = trend_data
        
        self._cache[cache_key] = result
        return result
    
    def get_equipment_sets_stats(self):
        """Get equipment sets statistics"""
        cache_key = f"equipment_sets_stats_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Active equipment sets
        active_sets = EquipmentSet.objects.filter(is_active=True).count()
        
        # Equipment sets with all items available
        available_sets = 0
        for equipment_set in EquipmentSet.objects.filter(is_active=True):
            all_available = True
            for set_item in equipment_set.items.all():
                if not set_item.inventory_item.available_for_rent or set_item.inventory_item.status != 'in_stock':
                    all_available = False
                    break
            if all_available:
                available_sets += 1
        
        # Most popular equipment sets (by usage) - simplified approach
        popular_sets = []
        try:
            # Get all active equipment sets
            active_equipment_sets = EquipmentSet.objects.filter(is_active=True)
            
            # For now, just show the first 5 active sets as "popular"
            # In a real implementation, you would need to track usage through rental items
            popular_sets = [
                {
                    'name': set.name,
                    'usage_count': 0  # Placeholder - would need proper usage tracking
                }
                for set in active_equipment_sets[:5]
            ]
        except Exception as e:
            print(f"Error getting popular equipment sets: {e}")
            popular_sets = []
        
        result = {
            'active_sets': active_sets,
            'available_sets': available_sets,
            'popular_sets': popular_sets
        }
        
        self._cache[cache_key] = result
        return result
    
    def get_popular_inventory_stats(self):
        """Get popular inventory items statistics"""
        cache_key = f"popular_inventory_stats_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Date filtering for rental requests
        date_filter = self._get_date_filter()
        
        # Get rental items with extended filters
        rental_items_queryset = RentalItem.objects.filter(
            rental_request__created_at__gte=date_filter.get('created_at__gte', timezone.now() - timedelta(days=30))
        )
        
        # Apply rental filters through rental_request relationship
        if 'gender' in self.filters and self.filters['gender']:
            rental_items_queryset = rental_items_queryset.filter(
                rental_request__user__profile__gender=self.filters['gender']
            )
        
        if 'member' in self.filters and self.filters['member'] != '':
            is_member = self.filters['member'].lower() == 'true'
            rental_items_queryset = rental_items_queryset.filter(
                rental_request__user__profile__member=is_member
            )
        
        # Get popular inventory items by rental count
        popular_items = rental_items_queryset.select_related('inventory_item').values(
            'inventory_item__id',
            'inventory_item__inventory_number',
            'inventory_item__description',
            'inventory_item__manufacturer__name'
        ).annotate(
            rental_count=Count('id'),
            total_quantity=Sum('quantity_requested')
        ).order_by('-rental_count')[:10]
        
        # Total available inventory items for rent
        inventory_queryset = InventoryItem.objects.filter(available_for_rent=True)
        inventory_queryset = self._apply_inventory_filters(inventory_queryset)
        total_available_items = inventory_queryset.count()
        
        result = {
            'total_available_items': total_available_items,
            'popular_items': [
                {
                    'id': item['inventory_item__id'],
                    'name': self._format_inventory_item_name(
                        item['inventory_item__description'],
                        item['inventory_item__inventory_number']
                    ),
                    'inventory_number': item['inventory_item__inventory_number'],
                    'description': item['inventory_item__description'],
                    'manufacturer': item['inventory_item__manufacturer__name'],
                    'rental_count': item['rental_count'],
                    'total_quantity': item['total_quantity']
                }
                for item in popular_items
            ]
        }
        
        self._cache[cache_key] = result
        return result
    
    def get_room_rentals_stats(self):
        """Get room rental statistics"""
        cache_key = f"room_rentals_stats_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Create date filter for rental_request
        date_filter = {}
        if 'days' in self.filters:
            days = int(self.filters['days'])
            start_date = timezone.now() - timedelta(days=days)
            date_filter['rental_request__created_at__gte'] = start_date
        elif 'start_date' in self.filters and 'end_date' in self.filters:
            date_filter['rental_request__created_at__gte'] = self.filters['start_date']
            date_filter['rental_request__created_at__lte'] = self.filters['end_date']
        
        # Get room rentals with extended filters
        room_rentals_queryset = RoomRental.objects.filter(**date_filter)
        
        # Apply rental filters to the rental_request relationship
        if 'media_authority' in self.filters and self.filters['media_authority']:
            room_rentals_queryset = room_rentals_queryset.filter(rental_request__user__profile__media_authority_id=self.filters['media_authority'])
        
        if 'gender' in self.filters and self.filters['gender']:
            room_rentals_queryset = room_rentals_queryset.filter(rental_request__user__profile__gender=self.filters['gender'])
        
        if 'age_min' in self.filters and self.filters['age_min']:
            age_min = int(self.filters['age_min'])
            max_birthday = timezone.now().date() - timedelta(days=age_min * 365)
            room_rentals_queryset = room_rentals_queryset.filter(rental_request__user__profile__birthday__lte=max_birthday)
        
        if 'age_max' in self.filters and self.filters['age_max']:
            age_max = int(self.filters['age_max'])
            min_birthday = timezone.now().date() - timedelta(days=(age_max + 1) * 365)
            room_rentals_queryset = room_rentals_queryset.filter(rental_request__user__profile__birthday__gt=min_birthday)
        
        if 'member' in self.filters and self.filters['member'] != '':
            is_member = self.filters['member'].lower() == 'true'
            room_rentals_queryset = room_rentals_queryset.filter(rental_request__user__profile__member=is_member)
        
        if 'verified' in self.filters and self.filters['verified'] != '':
            is_verified = self.filters['verified'].lower() == 'true'
            room_rentals_queryset = room_rentals_queryset.filter(rental_request__user__profile__verified=is_verified)
        

        
        # Room usage by time periods - simplified approach to avoid SQL issues
        time_periods = []
        try:
            # Get all room rentals and group by month manually
            all_room_rentals = room_rentals_queryset.select_related('rental_request')
            
            # Group by month manually
            from collections import defaultdict
            monthly_data = defaultdict(int)
            
            for rental in all_room_rentals:
                if rental.rental_request and rental.rental_request.created_at:
                    month_key = rental.rental_request.created_at.strftime('%Y-%m')
                    monthly_data[month_key] += 1
            
            # Convert to list format
            time_periods = [
                {'period': month, 'count': count}
                for month, count in sorted(monthly_data.items())
            ]
            
        except Exception as e:
            print(f"Error calculating room time periods: {e}")
            time_periods = []
        
        # Most popular rooms
        popular_rooms = room_rentals_queryset.select_related('room').values(
            'room__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        result = {
            'time_periods': time_periods,
            'popular_rooms': [
                {
                    'room': item['room__name'],
                    'count': item['count']
                }
                for item in popular_rooms
            ]
        }
        
        self._cache[cache_key] = result
        return result
    
    def _get_date_filter(self):
        """Get date filter based on current filters"""
        date_filter = {}
        
        if 'days' in self.filters:
            days = int(self.filters['days'])
            start_date = timezone.now() - timedelta(days=days)
            date_filter['created_at__gte'] = start_date
        elif 'start_date' in self.filters and 'end_date' in self.filters:
            date_filter['created_at__gte'] = self.filters['start_date']
            date_filter['created_at__lte'] = self.filters['end_date']
        
        return date_filter
    
    def _apply_rental_filters(self, queryset):
        """Apply extended filters to rental queryset"""
        # Gender filter
        if 'gender' in self.filters and self.filters['gender']:
            queryset = queryset.filter(user__profile__gender=self.filters['gender'])
        
        # Membership filter
        if 'member' in self.filters and self.filters['member'] != '':
            is_member = self.filters['member'].lower() == 'true'
            queryset = queryset.filter(user__profile__member=is_member)
        
        return queryset
    
    def _apply_inventory_filters(self, queryset):
        """Apply extended filters to inventory queryset"""
        # Category filter
        if 'category' in self.filters and self.filters['category']:
            queryset = queryset.filter(category_id=self.filters['category'])
        
        # Owner filter
        if 'owner' in self.filters and self.filters['owner']:
            queryset = queryset.filter(owner_id=self.filters['owner'])
        
        # Location filter
        if 'location' in self.filters and self.filters['location']:
            queryset = queryset.filter(location_id=self.filters['location'])
        
        # Status filter
        if 'status' in self.filters and self.filters['status']:
            queryset = queryset.filter(status=self.filters['status'])
        
        return queryset
    
    def _format_inventory_item_name(self, description, inventory_number):
        """Format inventory item name by removing owner codes but keeping inventory number"""
        if not description:
            return inventory_number
        
        # Remove patterns like (OKMQ VS2), (OKMQ VS5), etc.
        import re
        # Remove patterns like (OKMQ VS2), (OKMQ VS5), (MSA), etc.
        cleaned_description = re.sub(r'\s*\([A-Z]+(?:\s+[A-Z0-9]+)*\)\s*$', '', description.strip())
        
        # Add inventory number in parentheses if it's not already there
        if inventory_number and f"({inventory_number})" not in cleaned_description:
            return f"{cleaned_description} ({inventory_number})"
        
        return cleaned_description
    
    def get_user_activity_analytics(self):
        """Get user activity analytics - rental vs license creation"""
        cache_key = f"user_activity_analytics_{hash(str(self.filters))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Date filtering
        date_filter = self._get_date_filter()
        
        # Get rental data with filters
        rental_queryset = RentalRequest.objects.filter(**date_filter)
        rental_queryset = self._apply_rental_filters(rental_queryset)
        
        # Get license data with same date filter
        from licenses.models import License
        license_queryset = License.objects.filter(**date_filter)
        
        # Apply similar filters to licenses
        if 'gender' in self.filters and self.filters['gender']:
            license_queryset = license_queryset.filter(profile__gender=self.filters['gender'])
        
        if 'member' in self.filters and self.filters['member'] != '':
            is_member = self.filters['member'].lower() == 'true'
            license_queryset = license_queryset.filter(profile__member=is_member)
        
        # Get users with rental activity
        rental_users = rental_queryset.values('user__id', 'user__first_name', 'user__last_name', 'user__profile__gender').annotate(
            rental_count=Count('id')
        ).order_by('-rental_count')
        
        # Get users with license creation activity
        license_users = license_queryset.values('profile__okuser__id', 'profile__first_name', 'profile__last_name', 'profile__gender').annotate(
            license_count=Count('id')
        ).order_by('-license_count')
        
        # Create dictionaries for quick lookup
        rental_user_dict = {user['user__id']: user for user in rental_users}
        license_user_dict = {user['profile__okuser__id']: user for user in license_users}
        
        # Anti-rating: Users who rent but don't create licenses
        anti_rating = []
        for user_id, rental_data in rental_user_dict.items():
            if user_id not in license_user_dict:
                username = f"{rental_data['user__first_name']} {rental_data['user__last_name']}".strip()
                anti_rating.append({
                    'user_id': user_id,
                    'username': username or f"User {user_id}",
                    'gender': rental_data['user__profile__gender'],
                    'rental_count': rental_data['rental_count'],
                    'license_count': 0
                })
        
        # Rating: Users who create licenses but don't rent much
        rating = []
        for user_id, license_data in license_user_dict.items():
            rental_count = rental_user_dict.get(user_id, {}).get('rental_count', 0)
            if rental_count <= 1:  # Rent 1 or less
                username = f"{license_data['profile__first_name']} {license_data['profile__last_name']}".strip()
                rating.append({
                    'user_id': user_id,
                    'username': username or f"User {user_id}",
                    'gender': license_data['profile__gender'],
                    'rental_count': rental_count,
                    'license_count': license_data['license_count']
                })
        
        # Sort and limit to top 5
        anti_rating.sort(key=lambda x: x['rental_count'], reverse=True)
        rating.sort(key=lambda x: x['license_count'], reverse=True)
        
        result = {
            'anti_rating': anti_rating[:5],  # Top 5 users who rent but don't create
            'rating': rating[:5]  # Top 5 users who create but don't rent much
        }
        
        self._cache[cache_key] = result
        return result
    
    def get_all_data(self):
        """Get all widget data"""
        return {
            'basic_stats': self.get_basic_stats(),
            'inventory_by_category': self.get_inventory_by_category(),
            'inventory_by_owner': self.get_inventory_by_owner(),
            'rentals_by_status': self.get_rentals_by_status(),
            'rentals_by_type': self.get_rentals_by_type(),
            'rentals_by_demographics': self.get_rentals_by_user_demographics(),
            'rentals_trend': self.get_rentals_trend(),
            'equipment_sets_stats': self.get_equipment_sets_stats(),
            'popular_inventory_stats': self.get_popular_inventory_stats(),
            'user_activity_analytics': self.get_user_activity_analytics(),
            'room_rentals_stats': self.get_room_rentals_stats()
        }
