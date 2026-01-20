"""
Management command to migrate module settings from environment variables to database configs.

This command reads environment variables and populates the module configuration models
ONLY if the database values are empty or set to defaults (one-time migration).

After initial migration, database values take priority over environment variables.
If env variables are removed, database values remain unchanged.
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Command(BaseCommand):
    help = _('Migrate module settings from environment variables to database configs')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=_('Show what would be migrated without actually saving'),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING(_('DRY RUN MODE - No changes will be saved')))
        
        migrated_count = 0
        
        # Registration config
        try:
            from registration.models import RegistrationConfig
            config = RegistrationConfig.get_config()
            
            form_pdf = os.getenv('REGISTRATION_FORM_PDF')
            form_type = os.getenv('REGISTRATION_FORM_TYPE')
            
            updated = False
            
            # Only migrate if value in DB is empty/missing (one-time migration)
            if form_pdf and (not config.form_pdf or config.form_pdf == ''):
                self.stdout.write(f'  Registration: form_pdf = {form_pdf}')
                if not dry_run:
                    config.form_pdf = form_pdf
                updated = True
            
            if form_type and (not config.form_type or config.form_type == ''):
                self.stdout.write(f'  Registration: form_type = {form_type}')
                if not dry_run:
                    config.form_type = form_type
                updated = True
            
            if updated:
                if not dry_run:
                    config.save()
                    migrated_count += 1
                    self.stdout.write(self.style.SUCCESS(_('✓ Registration config migrated')))
                else:
                    migrated_count += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error migrating registration config: {e}'))
        
        # Rental config
        if getattr(settings, 'RENTAL_ENABLED', False):
            try:
                from rental.models import RentalConfig
                config = RentalConfig.get_config()
                
                requires_approval = os.getenv('RENTAL_USER_REQUEST_REQUIRES_APPROVAL')
                site_base_url = os.getenv('SITE_BASE_URL') or getattr(settings, 'SITE_BASE_URL', '')
                request_url_template = os.getenv('RENTAL_REQUEST_URL_TEMPLATE')
                recipient_emails = os.getenv('RENTAL_APPROVAL_RECIPIENT_EMAILS')
                token_max_age = os.getenv('RENTAL_APPROVAL_TOKEN_MAX_AGE_SECONDS')
                
                updated = False
                
                # Only migrate if value in DB is default/empty (one-time migration)
                if requires_approval:
                    value = str(requires_approval).lower() in ('true', '1', 'yes', 'on')
                    # Only migrate if current value is default (False)
                    if config.user_request_requires_approval == False:
                        self.stdout.write(f'  Rental: user_request_requires_approval = {value}')
                        if not dry_run:
                            config.user_request_requires_approval = value
                        updated = True
                
                if site_base_url and (not config.site_base_url or config.site_base_url == ''):
                    self.stdout.write(f'  Rental: site_base_url = {site_base_url}')
                    if not dry_run:
                        config.site_base_url = site_base_url
                    updated = True
                
                if request_url_template and (not config.request_url_template or config.request_url_template == ''):
                    self.stdout.write(f'  Rental: request_url_template = {request_url_template}')
                    if not dry_run:
                        config.request_url_template = request_url_template
                    updated = True
                
                if recipient_emails and (not config.approval_recipient_emails or config.approval_recipient_emails == ''):
                    self.stdout.write(f'  Rental: approval_recipient_emails = {recipient_emails}')
                    if not dry_run:
                        config.approval_recipient_emails = recipient_emails
                    updated = True
                
                if token_max_age:
                    try:
                        value = int(token_max_age)
                        # Only migrate if current value is default (604800)
                        if config.approval_token_max_age_seconds == 604800:
                            self.stdout.write(f'  Rental: approval_token_max_age_seconds = {value}')
                            if not dry_run:
                                config.approval_token_max_age_seconds = value
                            updated = True
                    except ValueError:
                        pass
                
                if updated:
                    if not dry_run:
                        config.save()
                        migrated_count += 1
                        self.stdout.write(self.style.SUCCESS(_('✓ Rental config migrated')))
                    else:
                        migrated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error migrating rental config: {e}'))
        
        # Media Files config
        if getattr(settings, 'MEDIA_FILES_ENABLED', False):
            try:
                from media_files.models import MediaFilesConfig
                config = MediaFilesConfig.get_config()
                
                updated = False
                
                # Boolean settings - only migrate if value is default
                bool_settings = {
                    'VIDEO_OVERLAY_RENDERING_ENABLED': ('overlay_rendering_enabled', False),
                    'VIDEO_AUTO_COPY_ON_SCHEDULE': ('auto_copy_on_schedule', False),
                    'VIDEO_AUTO_COPY_TO_ARCHIVE': ('auto_copy_to_archive', False),
                    'VIDEO_AUTO_COPY_TO_PLAYOUT': ('auto_copy_to_playout', False),
                    'VIDEO_USE_WEEKLY_FOLDERS': ('use_weekly_folders', True),
                    'VIDEO_ARCHIVE_PROTECTED': ('archive_protected', True),
                    'VIDEO_AUTO_DELETE_FROM_CUSTOM': ('auto_delete_from_custom', True),
                    'VIDEO_COPY_VERIFY_CHECKSUM': ('copy_verify_checksum', True),
                    'VIDEO_COPY_USE_MD5_FOR_ARCHIVE': ('copy_use_md5_for_archive', True),
                }
                
                for env_key, (attr_name, default_value) in bool_settings.items():
                    env_value = os.getenv(env_key)
                    if env_value:
                        value = str(env_value).lower() in ('true', '1', 'yes', 'on')
                        current_value = getattr(config, attr_name)
                        # Only migrate if current value is default (one-time migration)
                        if current_value == default_value:
                            self.stdout.write(f'  Media Files: {attr_name} = {value}')
                            if not dry_run:
                                setattr(config, attr_name, value)
                            updated = True
                
                # Integer settings - only migrate if value is default
                int_settings = {
                    'VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS': ('source_preference_custom_days', 7),
                }
                
                for env_key, (attr_name, default_value) in int_settings.items():
                    env_value = os.getenv(env_key)
                    if env_value:
                        try:
                            value = int(env_value)
                            current_value = getattr(config, attr_name)
                            # Only migrate if current value is default (one-time migration)
                            if current_value == default_value:
                                self.stdout.write(f'  Media Files: {attr_name} = {value}')
                                if not dry_run:
                                    setattr(config, attr_name, value)
                                updated = True
                        except ValueError:
                            pass
                
                # String settings - only migrate if value is empty
                str_settings = {
                    'VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME': 'default_playout_storage_name',
                    'VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH': 'default_playout_storage_path',
                }
                
                for env_key, attr_name in str_settings.items():
                    env_value = os.getenv(env_key)
                    if env_value:
                        current_value = getattr(config, attr_name)
                        # Only migrate if current value is empty (one-time migration)
                        if not current_value or current_value == '':
                            self.stdout.write(f'  Media Files: {attr_name} = {env_value}')
                            if not dry_run:
                                setattr(config, attr_name, env_value)
                            updated = True
                
                # Supported formats - only migrate if value is default
                supported_formats = os.getenv('VIDEO_SUPPORTED_FORMATS')
                if supported_formats:
                    # Default is 'mp4,mov,mpeg,mpg'
                    if config.supported_formats == 'mp4,mov,mpeg,mpg':
                        self.stdout.write(f'  Media Files: supported_formats = {supported_formats}')
                        if not dry_run:
                            config.supported_formats = supported_formats
                        updated = True
                
                if updated:
                    if not dry_run:
                        config.save()
                        migrated_count += 1
                        self.stdout.write(self.style.SUCCESS(_('✓ Media Files config migrated')))
                    else:
                        migrated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error migrating media_files config: {e}'))
        
        # Licenses config
        if getattr(settings, 'LICENSES_ENABLED', True):
            try:
                from licenses.models import LicensesConfig
                config = LicensesConfig.get_config()
                
                screen_board_duration = os.getenv('SCREEN_BOARD_DURATION') or os.getenv('VIDEO_SCREEN_BOARD_DURATION')
                
                if screen_board_duration:
                    try:
                        value = int(screen_board_duration)
                        # Only migrate if current value is default (20)
                        if config.screen_board_duration == 20:
                            self.stdout.write(f'  Licenses: screen_board_duration = {value}')
                            if not dry_run:
                                config.screen_board_duration = value
                                config.save()
                                migrated_count += 1
                                self.stdout.write(self.style.SUCCESS(_('✓ Licenses config migrated')))
                            else:
                                migrated_count += 1
                    except ValueError:
                        pass
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error migrating licenses config: {e}'))
        
        # Tools config (if enabled)
        try:
            if getattr(settings, 'TOOLS_ENABLED', False):
                from tools.models import ToolsConfig
                config = ToolsConfig.get_config()
                
                updated = False
                
                storage_path = os.getenv('TOOLS_STORAGE_PATH')
                output_path = os.getenv('TOOLS_OUTPUT_PATH')
                max_upload_size = os.getenv('TOOLS_MAX_UPLOAD_SIZE')
                ffmpeg_path = os.getenv('TOOLS_FFMPEG_PATH')
                ffprobe_path = os.getenv('TOOLS_FFPROBE_PATH')
                
                # Only migrate if value is empty (one-time migration)
                if storage_path and (not config.storage_path or config.storage_path == ''):
                    self.stdout.write(f'  Tools: storage_path = {storage_path}')
                    if not dry_run:
                        config.storage_path = storage_path
                    updated = True
                
                if output_path and (not config.output_path or config.output_path == ''):
                    self.stdout.write(f'  Tools: output_path = {output_path}')
                    if not dry_run:
                        config.output_path = output_path
                    updated = True
                
                if max_upload_size:
                    try:
                        value = int(max_upload_size)
                        # Only migrate if current value is default (500)
                        if config.max_upload_size == 500:
                            self.stdout.write(f'  Tools: max_upload_size = {value}')
                            if not dry_run:
                                config.max_upload_size = value
                            updated = True
                    except ValueError:
                        pass
                
                if ffmpeg_path and config.ffmpeg_path == 'ffmpeg':
                    self.stdout.write(f'  Tools: ffmpeg_path = {ffmpeg_path}')
                    if not dry_run:
                        config.ffmpeg_path = ffmpeg_path
                    updated = True
                
                if ffprobe_path and config.ffprobe_path == 'ffprobe':
                    self.stdout.write(f'  Tools: ffprobe_path = {ffprobe_path}')
                    if not dry_run:
                        config.ffprobe_path = ffprobe_path
                    updated = True
                
                if updated and not dry_run:
                    config.save()
                    migrated_count += 1
                    self.stdout.write(self.style.SUCCESS(_('✓ Tools config migrated')))
                else:
                    migrated_count += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error migrating tools config: {e}'))
        
        # Organization config
        try:
            from registration.models import OrganizationConfig
            config = OrganizationConfig.get_config()
            
            updated = False
            
            # Only migrate if value is empty/default (one-time migration)
            org_name = os.getenv('ORG_NAME')
            if org_name and config.name == 'Open Channel Merseburg-Querfurt e.V.':
                self.stdout.write(f'  Organization: name = {org_name}')
                if not dry_run:
                    config.name = org_name
                updated = True
            
            org_short_name = os.getenv('ORG_SHORT_NAME')
            if org_short_name and config.short_name == 'OK Merseburg':
                self.stdout.write(f'  Organization: short_name = {org_short_name}')
                if not dry_run:
                    config.short_name = org_short_name
                updated = True
            
            org_website = os.getenv('ORG_WEBSITE')
            if org_website and (not config.website or config.website == ''):
                self.stdout.write(f'  Organization: website = {org_website}')
                if not dry_run:
                    config.website = org_website
                updated = True
            
            org_email = os.getenv('ORG_EMAIL')
            if org_email and (not config.email or config.email == ''):
                self.stdout.write(f'  Organization: email = {org_email}')
                if not dry_run:
                    config.email = org_email
                updated = True
            
            org_phone = os.getenv('ORG_PHONE')
            if org_phone and (not config.phone or config.phone == ''):
                self.stdout.write(f'  Organization: phone = {org_phone}')
                if not dry_run:
                    config.phone = org_phone
                updated = True
            
            org_fax = os.getenv('ORG_FAX')
            if org_fax and (not config.fax or config.fax == ''):
                self.stdout.write(f'  Organization: fax = {org_fax}')
                if not dry_run:
                    config.fax = org_fax
                updated = True
            
            org_address = os.getenv('ORG_ADDRESS')
            if org_address and (not config.address or config.address == ''):
                # Replace \\n with actual newlines
                address = org_address.replace('\\n', '\n')
                self.stdout.write(f'  Organization: address = {address}')
                if not dry_run:
                    config.address = address
                updated = True
            
            org_description = os.getenv('ORG_DESCRIPTION')
            if org_description and (not config.description or config.description == ''):
                self.stdout.write(f'  Organization: description = {org_description}')
                if not dry_run:
                    config.description = org_description
                updated = True
            
            org_opening_hours = os.getenv('ORG_OPENING_HOURS')
            if org_opening_hours and (not config.opening_hours or config.opening_hours == ''):
                # Replace \\n with actual newlines
                hours = org_opening_hours.replace('\\n', '\n')
                self.stdout.write(f'  Organization: opening_hours = {hours}')
                if not dry_run:
                    config.opening_hours = hours
                updated = True
            
            state_media_institution = os.getenv('STATE_MEDIA_INSTITUTION')
            if state_media_institution and config.state_media_institution == 'MSA':
                self.stdout.write(f'  Organization: state_media_institution = {state_media_institution}')
                if not dry_run:
                    config.state_media_institution = state_media_institution
                updated = True
            
            organization_owner = os.getenv('ORG_ORGANIZATION_OWNER') or os.getenv('ORGANIZATION_OWNER')
            if organization_owner and config.organization_owner == 'OKMQ':
                self.stdout.write(f'  Organization: organization_owner = {organization_owner}')
                if not dry_run:
                    config.organization_owner = organization_owner
                updated = True
            
            broadcast_start = os.getenv('ORG_BROADCAST_START') or os.getenv('BROADCAST_START')
            if broadcast_start:
                from datetime import datetime, time as dt_time
                try:
                    # Check if current value is default
                    default_time = dt_time(6, 0)  # 06:00
                    if config.broadcast_start == default_time or config.broadcast_start.strftime('%H:%M') == '06:00':
                        time_obj = datetime.strptime(broadcast_start, '%H:%M').time()
                        self.stdout.write(f'  Organization: broadcast_start = {broadcast_start}')
                        if not dry_run:
                            config.broadcast_start = time_obj
                        updated = True
                except (ValueError, AttributeError):
                    pass
            
            broadcast_end = os.getenv('ORG_BROADCAST_END') or os.getenv('BROADCAST_END')
            if broadcast_end:
                from datetime import datetime, time as dt_time
                try:
                    # Check if current value is default
                    default_time = dt_time(23, 0)  # 23:00
                    if config.broadcast_end == default_time or config.broadcast_end.strftime('%H:%M') == '23:00':
                        time_obj = datetime.strptime(broadcast_end, '%H:%M').time()
                        self.stdout.write(f'  Organization: broadcast_end = {broadcast_end}')
                        if not dry_run:
                            config.broadcast_end = time_obj
                        updated = True
                except (ValueError, AttributeError):
                    pass
            
            peertube_channel = os.getenv('ORG_PEERTUBE_CHANNEL') or os.getenv('PEERTUBE_CHANNEL')
            if peertube_channel and (not config.peertube_channel or config.peertube_channel == ''):
                self.stdout.write(f'  Organization: peertube_channel = {peertube_channel}')
                if not dry_run:
                    config.peertube_channel = peertube_channel
                updated = True
            
            if updated:
                if not dry_run:
                    config.save()
                    migrated_count += 1
                    self.stdout.write(self.style.SUCCESS(_('✓ Organization config migrated')))
                else:
                    migrated_count += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error migrating organization config: {e}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(_('\nWould migrate {count} config(s)').format(count=migrated_count)))
        else:
            self.stdout.write(self.style.SUCCESS(_('\n✓ Successfully migrated {count} config(s)').format(count=migrated_count)))
