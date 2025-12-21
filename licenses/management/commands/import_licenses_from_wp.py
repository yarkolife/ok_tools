"""
Django management command to import licenses and contributions from WordPress SQL dump or CSV.

Usage:
    # Local
    python manage.py import_licenses_from_wp /path/to/wp_posts.sql
    python manage.py import_licenses_from_wp /path/to/wp_posts.csv
    
    # In Docker container (production)
    docker compose exec web python manage.py import_licenses_from_wp /path/to/wp_posts.csv --unique-by title
    
    # Options
    --dry-run                    Run without creating records (validation only)
    --skip-existing-licenses     Skip licenses that already exist (by number)
    --unique-by {id,title+date,title}  Unique constraint (default: id)
    --default-profile-id ID      Default profile ID if profile cannot be found
    --create-missing-profiles    Create new profiles for authors found in content
    
Examples:
    # Import only unique shows by title (2820 records)
    docker compose exec web python manage.py import_licenses_from_wp /app/docker-local/wp_posts.csv --unique-by title
    
    # Dry run to check
    docker compose exec web python manage.py import_licenses_from_wp /app/docker-local/wp_posts.csv --unique-by title --dry-run
"""
import csv
import os
import re
from datetime import datetime, timedelta
from html import unescape
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from licenses.models import License, Category
from contributions.models import Contribution
from registration.models import Profile, MediaAuthority
from django.conf import settings


class Command(BaseCommand):
    """Command to import licenses and contributions from WordPress SQL dump."""

    help = 'Import licenses and contributions from WordPress wp_posts SQL or CSV file'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to wp_posts.sql or wp_posts.csv file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually creating records (validation only)'
        )
        parser.add_argument(
            '--skip-existing-licenses',
            action='store_true',
            help='Skip licenses that already exist (by number)'
        )
        parser.add_argument(
            '--default-profile-id',
            type=int,
            help='Default profile ID to use if profile cannot be found by title'
        )
        parser.add_argument(
            '--unique-by',
            type=str,
            choices=['id', 'title+date', 'title'],
            default='id',
            help='Unique constraint: id (all records), title+date (skip exact duplicates), title (first broadcast only)'
        )
        parser.add_argument(
            '--create-missing-profiles',
            action='store_true',
            help='Create new profiles for authors found in content but not in database'
        )

    def parse_sql_value(self, value_str):
        """Parse SQL value, handling quotes and NULL."""
        value_str = value_str.strip()
        if value_str.upper() == 'NULL' or value_str == '':
            return None
        if value_str.startswith("'") and value_str.endswith("'"):
            # Remove quotes and unescape
            return unescape(value_str[1:-1].replace("''", "'"))
        if value_str.startswith('"') and value_str.endswith('"'):
            return unescape(value_str[1:-1].replace('""', '"'))
        # Try to convert to number
        try:
            return int(value_str)
        except ValueError:
            try:
                return float(value_str)
            except ValueError:
                return value_str

    def parse_sql_value_field(self, text, start_pos):
        """Parse a single SQL value field, handling quotes and escapes."""
        pos = start_pos
        # Skip whitespace
        while pos < len(text) and text[pos] in (' ', '\t', '\n', '\r'):
            pos += 1
        
        if pos >= len(text):
            return None, pos
        
        # Handle NULL
        if pos + 4 <= len(text) and text[pos:pos+4].upper() == 'NULL':
            return None, pos + 4
        
        # Handle numbers (including negative)
        if text[pos].isdigit() or (text[pos] == '-' and pos + 1 < len(text) and text[pos+1].isdigit()):
            num_end = pos + 1
            while num_end < len(text) and (text[num_end].isdigit() or text[num_end] == '.'):
                num_end += 1
            try:
                num_str = text[pos:num_end]
                value = int(num_str) if '.' not in num_str else float(num_str)
                return value, num_end
            except ValueError:
                pass
        
        # Handle quoted strings
        if text[pos] in ("'", '"'):
            quote_char = text[pos]
            pos += 1
            value = ""
            while pos < len(text):
                # Handle escaped characters (MySQL style: \' or \\)
                if text[pos] == '\\' and pos + 1 < len(text):
                    pos += 1
                    esc_char = text[pos]
                    if esc_char == 'n':
                        value += '\n'
                    elif esc_char == 'r':
                        value += '\r'
                    elif esc_char == 't':
                        value += '\t'
                    elif esc_char == '\\':
                        value += '\\'
                    elif esc_char == quote_char:
                        value += quote_char
                    elif esc_char == "'":
                        value += "'"
                    elif esc_char == '"':
                        value += '"'
                    else:
                        value += esc_char
                    pos += 1
                # Handle end of string
                elif text[pos] == quote_char:
                    pos += 1
                    break
                else:
                    value += text[pos]
                    pos += 1
            return value, pos
        
        # Handle unquoted strings (until comma or closing paren)
        value_start = pos
        while pos < len(text) and text[pos] not in (',', ')', ' ', '\t', '\n', '\r'):
            pos += 1
        return text[value_start:pos].strip(), pos
    
    def parse_sql_record(self, text, start_pos):
        """Parse a single SQL record (values in parentheses)."""
        pos = start_pos
        # Skip whitespace
        while pos < len(text) and text[pos] in (' ', '\t', '\n', '\r', ','):
            pos += 1
        
        if pos >= len(text) or text[pos] != '(':
            return None, pos
        
        pos += 1  # Skip opening paren
        fields = []
        
        while pos < len(text):
            # Skip whitespace
            while pos < len(text) and text[pos] in (' ', '\t', '\n', '\r'):
                pos += 1
            
            if pos >= len(text):
                break
            
            # Check for closing paren
            if text[pos] == ')':
                pos += 1
                break
            
            # Parse field
            value, new_pos = self.parse_sql_value_field(text, pos)
            fields.append(value)
            pos = new_pos
            
            # Skip whitespace and comma
            while pos < len(text) and text[pos] in (' ', '\t', '\n', '\r', ','):
                pos += 1
        
        return fields, pos
    
    def parse_sql_insert(self, content):
        """Parse SQL INSERT statement and extract records."""
        records = []
        
        # Find INSERT statement
        insert_match = re.search(
            r"INSERT INTO\s+`?wp_posts`?\s*\([^)]+\)\s*VALUES\s*",
            content,
            re.DOTALL | re.IGNORECASE
        )
        if not insert_match:
            raise CommandError('INSERT statement not found in SQL file')
        
        values_start = insert_match.end()
        # Find the end of VALUES block - look for semicolon after all records
        # We need to find the semicolon that closes the INSERT statement
        # It should be after the last closing parenthesis
        values_end = content.find(';', values_start)
        if values_end == -1:
            raise CommandError('VALUES block not properly terminated')
        
        # Make sure we have the complete VALUES block
        # Check if there are more INSERT statements after this one
        next_insert = content.find('INSERT INTO', values_end)
        if next_insert != -1:
            # There's another INSERT, so our VALUES block ends before it
            values_end = next_insert
        
        values_block = content[values_start:values_end].strip()
        
        # Remove trailing semicolon if present
        if values_block.endswith(';'):
            values_block = values_block[:-1]
        
        self.stdout.write(f'Parsing VALUES block ({len(values_block)} characters)\n')
        
        # Parse records one by one
        pos = 0
        record_count = 0
        cs_sendung_count = 0
        
        while pos < len(values_block):
            # Skip whitespace and commas
            while pos < len(values_block) and values_block[pos] in (' ', '\t', '\n', '\r', ','):
                pos += 1
            
            if pos >= len(values_block):
                break
            
            # Parse record
            fields, new_pos = self.parse_sql_record(values_block, pos)
            if fields is None:
                break
            
            record_count += 1
            pos = new_pos
            
            # Check if this is a cs_sendung record
            # post_type is field index 20 (0-based: ID, post_author, post_date, post_date_gmt, post_content, post_title, post_excerpt, post_status, comment_status, ping_status, post_password, post_name, to_ping, pinged, post_modified, post_modified_gmt, post_content_filtered, post_parent, guid, menu_order, post_type, ...)
            if len(fields) > 20:
                post_type = str(fields[20]).strip().lower() if fields[20] else ''
                if post_type == 'cs_sendung':
                    cs_sendung_count += 1
                    try:
                        # Extract fields
                        post_id = int(fields[0]) if fields[0] else None
                        post_date_str = str(fields[2]) if fields[2] else ''  # post_date (index 2)
                        post_content = str(fields[4]) if fields[4] else ''  # post_content (index 4)
                        post_title = str(fields[5]) if fields[5] else ''  # post_title (index 5)
                        
                        if post_id and post_date_str and post_title:
                            post_author_id = str(fields[1]) if len(fields) > 1 and fields[1] else None
                            records.append({
                                'id': post_id,
                                'post_author_id': post_author_id,
                                'post_date': post_date_str,
                                'post_content': post_content,
                                'post_title': post_title,
                            })
                    except (ValueError, IndexError, TypeError) as e:
                        continue
        
        self.stdout.write(f'Parsed {record_count} total records\n')
        self.stdout.write(f'Found {cs_sendung_count} records with post_type="cs_sendung"\n')
        
        return records
    
    def parse_csv(self, file_path):
        """Parse CSV file and extract cs_sendung records."""
        records = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                total_rows = 0
                cs_sendung_count = 0
                
                for row in reader:
                    total_rows += 1
                    
                    # Check if this is a cs_sendung record
                    # post_type is column index 20
                    if len(row) > 20:
                        post_type = row[20].strip().lower() if row[20] else ''
                        if post_type == 'cs_sendung':
                            cs_sendung_count += 1
                            try:
                                # Extract fields
                                # Columns: ID, post_author, post_date, post_date_gmt, post_content, post_title, ...
                                post_id = int(row[0]) if row[0] else None
                                post_author_id = row[1] if len(row) > 1 and row[1] else None
                                post_date_str = row[2] if len(row) > 2 and row[2] else ''
                                post_content = row[4] if len(row) > 4 and row[4] else ''
                                post_title = row[5] if len(row) > 5 and row[5] else ''
                                
                                if post_id and post_date_str and post_title:
                                    records.append({
                                        'id': post_id,
                                        'post_author_id': post_author_id,
                                        'post_date': post_date_str,
                                        'post_content': post_content,
                                        'post_title': post_title,
                                    })
                            except (ValueError, IndexError, TypeError) as e:
                                continue
                
                self.stdout.write(f'Parsed {total_rows} total rows\n')
                self.stdout.write(f'Found {cs_sendung_count} records with post_type="cs_sendung"\n')
                
        except Exception as e:
            raise CommandError(f'Error reading CSV file: {e}')
        
        return records
    
    def filter_unique_records(self, records, unique_by):
        """Filter records based on uniqueness criteria."""
        if unique_by == 'id':
            # All records are unique by ID (no filtering needed)
            return records
        
        if unique_by == 'title':
            # Group by title and keep the LAST occurrence (most recent, usually has more complete info)
            from collections import defaultdict
            title_groups = defaultdict(list)
            
            for record in records:
                title, _ = self.parse_title(record['post_title'])
                if title:
                    title_groups[title].append(record)
            
            # Keep only the last record for each title
            unique_records = []
            duplicates_skipped = 0
            total_records = len(records)
            
            for title, group_records in title_groups.items():
                # Sort by date (most recent last) and take the last one
                sorted_records = sorted(group_records, key=lambda x: x.get('post_date', ''))
                unique_records.append(sorted_records[-1])
                duplicates_skipped += len(sorted_records) - 1
            
            if duplicates_skipped > 0:
                self.stdout.write(self.style.WARNING(
                    f'Filtered out {duplicates_skipped} duplicate records (unique-by: {unique_by}, keeping most recent)'
                ))
            
            return unique_records
        
        # For title+date, use original logic
        seen = set()
        unique_records = []
        duplicates_skipped = 0
        
        for record in records:
            if unique_by == 'title+date':
                # Unique by title + date combination
                key = (record['post_title'], record['post_date'])
            else:
                key = None
            
            if key and key in seen:
                duplicates_skipped += 1
                continue
            
            if key:
                seen.add(key)
            unique_records.append(record)
        
        if duplicates_skipped > 0:
            self.stdout.write(self.style.WARNING(
                f'Filtered out {duplicates_skipped} duplicate records (unique-by: {unique_by})'
            ))
        
        return unique_records
    
    def clean_html(self, html_text):
        """Remove HTML tags from text."""
        if not html_text:
            return ''
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_text)
        # Decode HTML entities
        text = unescape(text)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def parse_title(self, title):
        """Parse title to extract title and subtitle."""
        if not title:
            return None, None
        
        # Remove date/time pattern: "vom DD. Monat YYYY, HH:MM Uhr"
        title_clean = re.sub(r'\s*vom\s+\d+\.\s+\w+\s+\d{4},\s+\d{1,2}:\d{2}\s+Uhr\s*$', '', title, flags=re.IGNORECASE)
        title_clean = title_clean.strip()
        
        # Split by | for subtitle
        if '|' in title_clean:
            parts = title_clean.split('|', 1)
            main_title = parts[0].strip()
            subtitle = parts[1].strip() if len(parts) > 1 else None
        else:
            main_title = title_clean
            subtitle = None
        
        return main_title, subtitle

    def extract_author_from_content(self, content):
        """Extract author name from post content."""
        if not content:
            return None
        
        # Clean HTML tags first
        content_clean = re.sub(r'<[^>]+>', ' ', content)
        content_clean = re.sub(r'\s+', ' ', content_clean).strip()
        
        # More specific patterns for author in content
        # Pattern: "Ein Film von [Name]" - most common
        patterns = [
            r'Ein\s+Film\s+von\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){0,2})\s*(?:vom|$|\.|,|;|:)',
            r'Film\s+von\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){0,2})\s*(?:vom|$|\.|,|;|:)',
            r'Regie:\s*([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){0,2})\s*(?:vom|$|\.|,|;|:)',
            r'Regie\s+von\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){0,2})\s*(?:vom|$|\.|,|;|:)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content_clean, re.IGNORECASE)
            if match:
                author_name = match.group(1).strip()
                # Validate: should be 2-4 words, each starting with capital letter
                words = author_name.split()
                if len(words) >= 2 and len(words) <= 4:
                    # Check that all words start with capital letter
                    if all(word and word[0].isupper() for word in words):
                        # Remove common suffixes that might have been caught
                        author_name = re.sub(r'\s+(vom|von|der|die|das|und|oder|mit|für|zu|in|auf|an|aus|bei|nach|über|unter|durch|gegen|ohne|um|seit|während|trotz|wegen|statt|außer|innerhalb|außerhalb|oberhalb|unterhalb|diesseits|jenseits|beiderseits|abseits|längs|entlang|entgegen|gemäß|entsprechend|zufolge|mangels|zwecks|hinsichtlich|bezüglich|betreffs|infolge|aufgrund|anlässlich|anstelle|anstatt|inmitten|mittels|vermittels|per|pro|kontra|plus|minus|mal|geteilt|gleich|ungleich|größer|kleiner|größergleich|kleinergleich|ist|sind|war|waren|wird|werden|wurde|wurden|hat|haben|hatte|hatten|wird|werden|wurde|wurden|kann|können|konnte|konnten|muss|müssen|musste|mussten|soll|sollen|sollte|sollten|darf|dürfen|durfte|durften|will|wollen|wollte|wollten|mag|mögen|mochte|mochten|möchte|möchten)\s*$', '', author_name, flags=re.IGNORECASE)
                        return author_name.strip()
        
        return None
    
    def find_profile_by_name(self, name, exact_only=False):
        """Try to find profile by first and last name.
        
        Args:
            name: Author name to search for
            exact_only: If True, only return exact matches (first+last name)
        """
        if not name:
            return None
        
        # Split name into parts
        name_parts = name.strip().split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
            
            # Try exact match first
            profile = Profile.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name
            ).first()
            
            if profile:
                return profile
            
            # If exact_only, don't try partial matches
            if exact_only:
                return None
            
            # Try with swapped order (maybe last name is first)
            profile = Profile.objects.filter(
                first_name__iexact=last_name,
                last_name__iexact=first_name
            ).first()
            
            if profile:
                return profile
            
            # Try first name only (maybe last name is different)
            # This helps with cases like "Franziska Dohse" vs "Franziska Fischer"
            profile = Profile.objects.filter(
                first_name__iexact=first_name
            ).first()
            
            if profile:
                return profile
            
            # Try partial match (first name starts with, last name contains)
            profile = Profile.objects.filter(
                first_name__istartswith=first_name,
                last_name__icontains=last_name
            ).first()
            
            if profile:
                return profile
            
            # Try last name only (maybe first name is missing or different)
            profile = Profile.objects.filter(
                last_name__iexact=last_name
            ).first()
            
            if profile:
                return profile
            
            # Try last name contains
            profile = Profile.objects.filter(
                last_name__icontains=last_name
            ).first()
            
            if profile:
                return profile
        
        # Try searching by last name only if single word
        elif len(name_parts) == 1:
            if exact_only:
                return None
                
            profile = Profile.objects.filter(
                last_name__iexact=name_parts[0]
            ).first()
            if profile:
                return profile
            
            # Try contains
            profile = Profile.objects.filter(
                last_name__icontains=name_parts[0]
            ).first()
            if profile:
                return profile
        
        return None
    
    def find_profile_by_title(self, title):
        """Try to find profile by matching title with license titles."""
        if not title:
            return None
        
        # Try to find existing license with similar title
        # and get its profile
        title_clean = self.parse_title(title)[0]
        if title_clean:
            # Search for licenses with similar title
            license_obj = License.objects.filter(
                title__icontains=title_clean[:50]  # First 50 chars
            ).first()
            if license_obj:
                return license_obj.profile
        
        return None
    
    def create_profile_by_name(self, name):
        """Create a new Profile by name."""
        if not name:
            return None
        
        # Split name into first and last name
        name_parts = name.strip().split(maxsplit=1)
        if len(name_parts) == 1:
            first_name = name_parts[0]
            last_name = None
        else:
            first_name = name_parts[0]
            last_name = name_parts[1]
        
        # Get or use default media_authority
        media_authority, _created = MediaAuthority.objects.get_or_create(
            name=settings.OK_NAME_SHORT
        )
        
        # Create profile
        profile = Profile.objects.create(
            first_name=first_name,
            last_name=last_name,
            media_authority=media_authority,
            verified=False,
            member=False,
        )
        
        return profile
    
    def handle(self, *args, **options):
        """Execute the command."""
        file_path = options['file_path']
        dry_run = options['dry_run']
        skip_existing = options['skip_existing_licenses']
        default_profile_id = options.get('default_profile_id')
        unique_by = options.get('unique_by', 'id')
        create_missing_profiles = options.get('create_missing_profiles', False)

        # Validate file path
        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')

        is_csv = file_path.lower().endswith('.csv')
        is_sql = file_path.lower().endswith('.sql')
        
        if not (is_csv or is_sql):
            raise CommandError('File must be a SQL file (.sql) or CSV file (.csv)')

        file_type = 'CSV' if is_csv else 'SQL'
        self.stdout.write(self.style.SUCCESS(
            f'\n{"=" * 60}\n'
            f'  Importing from WordPress {file_type}: {file_path}\n'
            f'  Unique by: {unique_by}\n'
            f'{"=" * 60}\n'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved\n'))

        # Parse file
        try:
            if is_csv:
                records = self.parse_csv(file_path)
            else:
                # Read SQL file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                records = self.parse_sql_insert(content)
            
            self.stdout.write(f'Found {len(records)} records with post_type="cs_sendung"\n')
            
            # Filter unique records
            records = self.filter_unique_records(records, unique_by)
            self.stdout.write(f'After filtering: {len(records)} unique records\n')
            
        except Exception as e:
            raise CommandError(f'Error parsing file: {e}')

        # Get default category
        try:
            default_category = Category.objects.first()
            if not default_category:
                default_category = Category.objects.create(name='Not Selected')
        except Exception as e:
            raise CommandError(f'Error getting Category: {e}')

        # Get default profile
        default_profile = None
        if default_profile_id:
            try:
                default_profile = Profile.objects.get(id=default_profile_id)
            except Profile.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'Default profile ID {default_profile_id} not found'
                ))
        if not default_profile:
            # Try to get any profile as fallback
            default_profile = Profile.objects.first()
            if default_profile:
                self.stdout.write(self.style.WARNING(
                    f'Using first available profile as default: {default_profile}'
                ))

        if not default_profile:
            raise CommandError('No profile found. Please create at least one profile or use --default-profile-id')

        # Get starting number for auto-generation
        max_number = License.objects.order_by('-number').first()
        next_license_number = (max_number.number + 1) if max_number else 1
        self.stdout.write(f'Starting license number: {next_license_number}\n')

        # Statistics
        stats = {
            'total_records': len(records),
            'licenses_created': 0,
            'licenses_skipped': 0,
            'contributions_created': 0,
            'contributions_skipped': 0,
            'errors': 0,
        }

        errors = []

        # Process records
        for record in records:
            try:
                wp_id = record['id']
                post_date_str = record['post_date']
                post_title = record['post_title']
                post_content = record['post_content']

                # Parse title
                title, subtitle = self.parse_title(post_title)
                if not title:
                    stats['errors'] += 1
                    errors.append(f'WP ID {wp_id}: No title found')
                    continue

                # Parse date
                try:
                    broadcast_date = datetime.strptime(post_date_str, '%Y-%m-%d %H:%M:%S')
                    broadcast_date = timezone.make_aware(broadcast_date)
                except Exception as e:
                    stats['errors'] += 1
                    errors.append(f'WP ID {wp_id}: Invalid date format: {post_date_str} - {e}')
                    continue

                # Clean description
                description = self.clean_html(post_content)

                # Find or create license
                license_obj = None
                if not dry_run:
                    # Check if license exists
                    try:
                        license_obj = License.objects.get(number=wp_id)
                        if skip_existing:
                            stats['licenses_skipped'] += 1
                            self.stdout.write(self.style.WARNING(
                                f'WP ID {wp_id}: License already exists - skipping'
                            ))
                        else:
                            # Update existing license
                            license_obj.title = title
                            if subtitle:
                                license_obj.subtitle = subtitle
                            if description:
                                license_obj.description = description
                            license_obj.suggested_date = broadcast_date
                            license_obj.save()
                            self.stdout.write(self.style.SUCCESS(
                                f'WP ID {wp_id}: Updated license: {title}'
                            ))
                    except License.DoesNotExist:
                        # Find profile - try multiple methods
                        profile = None
                        
                        # 1. Try to extract author from content and find by name
                        author_name = self.extract_author_from_content(post_content)
                        if author_name:
                            # If create_missing_profiles is enabled, only look for exact matches
                            # to avoid using partial matches (e.g., "Franziska Dohse" vs "Franziska Thon")
                            profile = self.find_profile_by_name(author_name, exact_only=create_missing_profiles)
                            if profile:
                                self.stdout.write(self.style.SUCCESS(
                                    f'WP ID {wp_id}: Found profile by author name: {author_name} -> {profile}'
                                ))
                            else:
                                # Create profile if option is enabled
                                if create_missing_profiles:
                                    profile = self.create_profile_by_name(author_name)
                                    if profile:
                                        self.stdout.write(self.style.SUCCESS(
                                            f'WP ID {wp_id}: Created new profile: {author_name} -> {profile}'
                                        ))
                                    else:
                                        self.stdout.write(self.style.WARNING(
                                            f'WP ID {wp_id}: Author "{author_name}" extracted but failed to create profile'
                                        ))
                                else:
                                    # If create_missing_profiles is disabled, try partial match
                                    profile = self.find_profile_by_name(author_name, exact_only=False)
                                    if profile:
                                        self.stdout.write(self.style.SUCCESS(
                                            f'WP ID {wp_id}: Found profile by author name (partial match): {author_name} -> {profile}'
                                        ))
                                    else:
                                        # Log when author found but profile not found
                                        self.stdout.write(self.style.WARNING(
                                            f'WP ID {wp_id}: Author "{author_name}" extracted but profile not found in database'
                                        ))
                        
                        # 2. Try to find by title (existing licenses)
                        if not profile:
                            profile = self.find_profile_by_title(post_title)
                        
                        # 3. Use default profile as fallback
                        if not profile:
                            profile = default_profile
                            if author_name:
                                self.stdout.write(self.style.WARNING(
                                    f'WP ID {wp_id}: Author "{author_name}" not found, using default profile'
                                ))

                        # Use next available license number
                        current_number = next_license_number
                        next_license_number += 1

                        # Create new license
                        with transaction.atomic():
                            license_obj = License.objects.create(
                                number=current_number,
                                title=title,
                                subtitle=subtitle,
                                description=description,
                                duration=timedelta(seconds=0),
                                suggested_date=broadcast_date,
                                profile=profile,
                                category=default_category,
                                repetitions_allowed=False,
                                media_authority_exchange_allowed=False,
                                media_authority_exchange_allowed_other_states=False,
                                youth_protection_necessary=False,
                                youth_protection_category='none',
                                store_in_ok_media_library=False,
                                is_live=False,
                                confirmed=False,
                                is_screen_board=False,
                                infoblock=False,
                            )
                            stats['licenses_created'] += 1
                            self.stdout.write(self.style.SUCCESS(
                                f'WP ID {wp_id}: Created license #{current_number}: {title}'
                            ))
                else:
                    # Dry run - check and show what profile would be used
                    try:
                        License.objects.get(number=wp_id)
                        stats['licenses_skipped'] += 1
                        self.stdout.write(self.style.WARNING(
                            f'WP ID {wp_id}: Would skip existing license: {title}'
                        ))
                    except License.DoesNotExist:
                        # Find profile - try multiple methods (same as real import)
                        profile = None
                        author_name = self.extract_author_from_content(post_content)
                        if author_name:
                            # If create_missing_profiles is enabled, only look for exact matches
                            profile = self.find_profile_by_name(author_name, exact_only=create_missing_profiles)
                            if profile:
                                self.stdout.write(self.style.SUCCESS(
                                    f'WP ID {wp_id}: ✓ Author "{author_name}" -> Profile: {profile}'
                                ))
                            else:
                                if create_missing_profiles:
                                    self.stdout.write(self.style.SUCCESS(
                                        f'WP ID {wp_id}: ✓ Author "{author_name}" -> Would create new profile'
                                    ))
                                else:
                                    # Try partial match if create_missing_profiles is disabled
                                    profile = self.find_profile_by_name(author_name, exact_only=False)
                                    if profile:
                                        self.stdout.write(self.style.SUCCESS(
                                            f'WP ID {wp_id}: ✓ Author "{author_name}" -> Profile (partial match): {profile}'
                                        ))
                                    else:
                                        self.stdout.write(self.style.WARNING(
                                            f'WP ID {wp_id}: ⚠ Author "{author_name}" found but profile not in database (would use default)'
                                        ))
                        else:
                            # No author found in content
                            if 'Film' in post_content or 'von' in post_content.lower():
                                # Content might have author info but pattern didn't match
                                pass
                        
                        if not profile:
                            profile = self.find_profile_by_title(post_title)
                            if profile:
                                self.stdout.write(f'WP ID {wp_id}: Would use profile by title match: {profile}')
                        
                        if not profile:
                            # Would use default profile
                            pass
                        
                        stats['licenses_created'] += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'WP ID {wp_id}: Would create license: {title}'
                        ))

                # Create contribution (duplicates allowed if date/time differs)
                if license_obj or dry_run:
                    if not dry_run:
                        # Check if contribution already exists with same date/time
                        existing_contribution = Contribution.objects.filter(
                            license=license_obj,
                            broadcast_date=broadcast_date
                        ).first()

                        if existing_contribution:
                            stats['contributions_skipped'] += 1
                            self.stdout.write(self.style.WARNING(
                                f'WP ID {wp_id}: Contribution already exists for {broadcast_date} - skipping'
                            ))
                        else:
                            # Create new contribution
                            with transaction.atomic():
                                Contribution.objects.create(
                                    license=license_obj,
                                    broadcast_date=broadcast_date,
                                    live=False,
                                )
                                stats['contributions_created'] += 1
                                self.stdout.write(self.style.SUCCESS(
                                    f'WP ID {wp_id}: Created contribution for {broadcast_date}'
                                ))
                    else:
                        # Dry run
                        stats['contributions_created'] += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'WP ID {wp_id}: Would create contribution for {broadcast_date}'
                        ))

            except Exception as e:
                error_msg = f'WP ID {record.get("id", "unknown")}: Error - {str(e)}'
                errors.append(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))
                stats['errors'] += 1
                continue

        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f'\n{"=" * 60}\n'
            f'  Import Summary\n'
            f'{"=" * 60}\n'
            f'Total records processed: {stats["total_records"]}\n'
            f'Licenses created: {stats["licenses_created"]}\n'
            f'Licenses skipped: {stats["licenses_skipped"]}\n'
            f'Contributions created: {stats["contributions_created"]}\n'
            f'Contributions skipped: {stats["contributions_skipped"]}\n'
            f'Errors: {stats["errors"]}\n'
        ))

        if errors:
            self.stdout.write(self.style.ERROR('\nErrors encountered:\n'))
            for error in errors[:20]:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
            if len(errors) > 20:
                self.stdout.write(self.style.ERROR(f'  ... and {len(errors) - 20} more errors'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN - No records were actually created. Remove --dry-run to import.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Import completed!'))