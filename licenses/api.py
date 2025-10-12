from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
import logging

from .models import License
from .serializers import LicenseMetadataSerializer

logger = logging.getLogger('django')


class LicenseMetadataView(APIView):
    """
    API endpoint for retrieving license metadata by video number.
    
    Authentication: Token-based authentication required
    URL: /licenses/api/metadata/<number>/
    Method: GET
    
    Returns JSON metadata for the specified license number.
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def get(self, request, number):
        """
        Retrieve license metadata by number.
        
        Args:
            request: HTTP request
            number: License number (videoNumber)
            
        Returns:
            Response with license metadata or 404 if not found
        """
        try:
            license = get_object_or_404(
                License.objects.select_related('profile', 'category'),
                number=number
            )
            serializer = LicenseMetadataSerializer(license)
            
            # Log successful API access
            logger.info(
                f"API access: user={request.user.email}, "
                f"license={number}, ip={request.META.get('REMOTE_ADDR')}"
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"API error: user={request.user.email}, "
                f"license={number}, error={str(e)}"
            )
            raise

