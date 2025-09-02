#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')
django.setup()

from licenses.models import License
from contributions.models import Contribution
from datetime import datetime, timedelta

def check_license_10532():
    """Check complete information about license 10532"""
    
    try:
        license_10532 = License.objects.get(id=10532)
        print(f"=== Complete Information for License 10532 ===")
        print(f"ID: {license_10532.id}")
        print(f"Title: {license_10532.title}")
        print(f"Subtitle: {license_10532.subtitle}")
        print(f"Profile: {license_10532.profile}")
        print(f"Created at: {license_10532.created_at}")
        
        # Get all contributions for this license
        contributions = license_10532.contribution_set.order_by('broadcast_date')
        print(f"\n=== All Contributions ===")
        print(f"Total contributions: {contributions.count()}")
        
        if contributions.exists():
            print("\nAll contributions (ordered by broadcast_date):")
            for i, contrib in enumerate(contributions):
                print(f"  {i+1}. {contrib.broadcast_date}")
            
            # Get first contribution
            first_contrib = contributions.first()
            current_date = datetime.now()
            
            # Handle timezone
            first_broadcast = first_contrib.broadcast_date
            if first_broadcast.tzinfo is not None:
                first_broadcast = first_broadcast.replace(tzinfo=None)
            
            time_since_first = current_date - first_broadcast
            archive_threshold = timedelta(days=180)
            
            print(f"\n=== Archive Analysis ===")
            print(f"First broadcast: {first_contrib.broadcast_date}")
            print(f"Days since first broadcast: {time_since_first.days}")
            print(f"Archive threshold: {archive_threshold.days} days")
            print(f"Should be archive: {time_since_first > archive_threshold}")
            
            if time_since_first > archive_threshold:
                print("Status: ARCHIVE")
            else:
                print("Status: ACTIVE")
            
            # Check for contributions in 2025
            contributions_2025 = contributions.filter(broadcast_date__year=2025)
            print(f"\nContributions in 2025: {contributions_2025.count()}")
            
            if contributions_2025.exists():
                print("2025 contributions:")
                for contrib in contributions_2025:
                    print(f"  {contrib.broadcast_date}")
            
            # Check for contributions in August 2025
            august_2025_contributions = contributions.filter(
                broadcast_date__year=2025,
                broadcast_date__month=8
            )
            print(f"\nContributions in August 2025: {august_2025_contributions.count()}")
            
            if august_2025_contributions.exists():
                print("August 2025 contributions:")
                for contrib in august_2025_contributions:
                    print(f"  {contrib.broadcast_date}")
        
        else:
            print("No contributions found for this license")
    
    except License.DoesNotExist:
        print("❌ License 10532 not found in database")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_license_10532()
