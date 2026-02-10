"""API endpoints for Contributions module."""

from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import Min
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
import logging

from .models import Contribution
from ok_tools.datetime import TZ

logger = logging.getLogger('contributions')


class ProgramScheduleView(APIView):
    """
    API endpoint for retrieving TV program schedule.
    
    Authentication: Token-based authentication required
    URL: /contributions/api/program/
    Method: GET
    
    Query parameters:
    - date: Specific date (YYYY-MM-DD)
    - date_from: Start date of period (YYYY-MM-DD)
    - date_to: End date of period (YYYY-MM-DD)
    - start_time: Start time (HH:MM, optional)
    - end_time: End time (HH:MM, optional)
    
    Returns JSON array with program schedule including screen boards.
    """
    
    INFO_BLOCK_TITLE = 'Info block'
    TOLERANCE = timedelta(minutes=1)
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def get(self, request):
        """
        Retrieve program schedule.
        
        Args:
            request: HTTP request
            
        Returns:
            Response with program schedule data
        """
        try:
            # Parse date parameters
            date_from, date_to, time_from, time_to = self._parse_date_params(request)
            
            logger.info(
                f"Program schedule API: user={request.user.email}, "
                f"date_from={date_from}, date_to={date_to}, "
                f"time_from={time_from}, time_to={time_to}, "
                f"ip={request.META.get('REMOTE_ADDR')}"
            )
            
            # Get program data
            program_data = self._get_program_data(date_from, date_to, time_from, time_to)
            
            return Response(program_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Program schedule API error: user={request.user.email}, "
                f"error={str(e)}",
                exc_info=True
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _parse_date_params(self, request):
        """
        Parse date and time parameters from request.
        
        Returns:
            tuple: (date_from, date_to, time_from, time_to)
        """
        date_str = request.query_params.get('date')
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        time_from_str = request.query_params.get('start_time', '00:00')
        time_to_str = request.query_params.get('end_time', '23:59')
        
        # Parse time
        time_from = datetime.strptime(time_from_str, '%H:%M').time()
        time_to = datetime.strptime(time_to_str, '%H:%M').time()
        
        # Parse dates
        if date_str:
            # Single date
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            date_from = timezone.make_aware(
                datetime.combine(date_obj, time_from)
            )
            date_to = timezone.make_aware(
                datetime.combine(date_obj, time_to)
            )
        elif date_from_str and date_to_str:
            # Date range
            date_from_obj = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to_obj = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            date_from = timezone.make_aware(
                datetime.combine(date_from_obj, time_from)
            )
            date_to = timezone.make_aware(
                datetime.combine(date_to_obj, time_to)
            )
        else:
            # Default: today
            today = timezone.now().astimezone(TZ).date()
            date_from = timezone.make_aware(
                datetime.combine(today, time_from)
            )
            date_to = timezone.make_aware(
                datetime.combine(today, time_to)
            )
        
        return date_from, date_to, time_from, time_to
    
    def _get_program_data(self, date_from, date_to, time_from, time_to):
        """
        Get program data for the specified date range.
        
        Args:
            date_from: Start datetime
            date_to: End datetime
            time_from: Start time (for screen board logic)
            time_to: End time (for screen board logic)
            
        Returns:
            list: Program schedule data
        """
        # Get contributions for the date range
        queryset = Contribution.objects.filter(
            broadcast_date__gte=date_from,
            broadcast_date__lte=date_to
        ).select_related('license', 'license__profile').order_by('broadcast_date')
        
        # Format contributions and add screen boards
        program_data = []
        prev_contr = None
        
        for contribution in queryset:
            # Add screen board if there's a gap
            if prev_contr is not None:
                end_time = self._get_end_time(prev_contr)
                start_time = self._get_start_time(contribution)
                
                if end_time != start_time:
                    # Calculate gap duration
                    today = datetime.now().date()
                    delta = datetime.combine(today, start_time) - datetime.combine(today, end_time)
                    
                    if delta > self.TOLERANCE:
                        # Get date for screen board
                        screen_board_date = contribution.broadcast_date.astimezone(tz=TZ).date()
                        program_data.append(self._create_screen_board(
                            screen_board_date,
                            end_time,
                            start_time
                        ))
            
            # Add current contribution
            program_data.append(self._format_contribution(contribution))
            prev_contr = contribution
        
        # Add screen board at the end if needed
        if prev_contr is not None:
            end_time = self._get_end_time(prev_contr)
            if end_time != time(hour=0, minute=0):
                screen_board_date = (prev_contr.broadcast_date + prev_contr.license.duration).date()
                program_data.append(self._create_screen_board(
                    screen_board_date,
                    end_time,
                    time(hour=0, minute=0)
                ))
        
        # Merge consecutive info blocks
        program_data = self._merge_info_blocks(program_data)
        
        return program_data
    
    def _get_start_time(self, contribution):
        """
        Get start time of a contribution in local timezone.
        
        Args:
            contribution: Contribution object
            
        Returns:
            time: Start time
        """
        return contribution.broadcast_date.astimezone(tz=TZ).time()
    
    def _get_end_time(self, contribution):
        """
        Get end time of a contribution in local timezone.
        
        Args:
            contribution: Contribution object
            
        Returns:
            time: End time
        """
        if contribution is None:
            return time(hour=0, minute=0)
        
        end_datetime = contribution.broadcast_date.astimezone(tz=TZ) + contribution.license.duration
        return end_datetime.time()
    
    def _format_contribution(self, contribution):
        """
        Format a contribution for API response.
        
        Args:
            contribution: Contribution object
            
        Returns:
            dict: Formatted contribution data
        """
        license_obj = contribution.license
        is_infoblock = getattr(license_obj, 'infoblock', False)
        
        if is_infoblock:
            return {
                'broadcast_date': str(contribution.broadcast_date.astimezone(tz=TZ).date()),
                'broadcast_start_time': str(self._get_start_time(contribution)),
                'broadcast_end_time': str(self._get_end_time(contribution)),
                'title': self.INFO_BLOCK_TITLE,
                'subtitle': '',
                'description': '',
                'credits': '',
                'contribution': False,
                'category': '',
                'store_in_ok_media_library': '',
                'number': '',
            }
        
        return {
            'broadcast_date': str(contribution.broadcast_date.astimezone(tz=TZ).date()),
            'broadcast_start_time': str(self._get_start_time(contribution)),
            'broadcast_end_time': str(self._get_end_time(contribution)),
            'title': str(license_obj.title) if license_obj.title else '',
            'subtitle': str(license_obj.subtitle) if license_obj.subtitle else '',
            'description': str(license_obj.description) if license_obj.description else '',
            'credits': f'A contribution by {license_obj.profile}' if license_obj.profile else '',
            'contribution': True,
            'category': str(license_obj.category) if license_obj.category else '',
            'store_in_ok_media_library': str(license_obj.store_in_ok_media_library) if license_obj.store_in_ok_media_library else '',
            'number': str(license_obj.number) if license_obj.number else '',
        }
    
    def _create_screen_board(self, date, start_time, end_time):
        """
        Create a screen board entry.
        
        Args:
            date: Date for screen board
            start_time: Start time
            end_time: End time
            
        Returns:
            dict: Screen board data
        """
        return {
            'broadcast_date': str(date),
            'broadcast_start_time': str(start_time),
            'broadcast_end_time': str(end_time),
            'title': self.INFO_BLOCK_TITLE,
            'subtitle': '',
            'description': '',
            'credits': '',
            'contribution': False,
            'category': '',
            'store_in_ok_media_library': '',
            'number': '',
        }
    
    def _merge_info_blocks(self, program_data):
        """
        Merge consecutive Info block entries on the same day.
        
        Args:
            program_data: List of program entries
            
        Returns:
            list: Program data with merged info blocks
        """
        if not program_data:
            return program_data
        
        merged = []
        
        def is_info_row(row):
            return (
                row.get('title') == self.INFO_BLOCK_TITLE
                and row.get('contribution') is False
            )
        
        prev = None
        for current in program_data:
            if prev is not None and is_info_row(prev) and is_info_row(current):
                # Only merge when date is identical (no crossing midnight)
                if prev.get('broadcast_date') == current.get('broadcast_date'):
                    # Extend end time of previous Info block
                    prev['broadcast_end_time'] = current['broadcast_end_time']
                    continue
                else:
                    merged.append(prev)
                    prev = current
            else:
                if prev is not None:
                    merged.append(prev)
                prev = current
        
        if prev is not None:
            merged.append(prev)
        
        return merged
