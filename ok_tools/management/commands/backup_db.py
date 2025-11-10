import os
import subprocess
import sys
import logging
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import gzip


class Command(BaseCommand):
    help = 'Create a backup of the PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Directory to save the backup file',
            default=getattr(settings, 'BACKUP_DIR', './backups')
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress the backup file using gzip'
        )

    def handle(self, *args, **options):
        # Set up logging
        logger = logging.getLogger(__name__)
        
        # Get database settings
        db_settings = settings.DATABASES['default']
        
        # Extract connection parameters
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']

        # Create output directory if it doesn't exist
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f'backup-{timestamp}.sql'
        backup_path = os.path.join(output_dir, backup_filename)

        # Set PGPASSWORD environment variable for secure password passing
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        # Build pg_dump command
        pg_dump_cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', str(db_port),
            '-U', db_user,
            '-d', db_name,
            '-f', backup_path
        ]

        try:
            # Execute pg_dump command
            self.stdout.write(f'Creating database backup: {backup_path}')
            result = subprocess.run(
                pg_dump_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                logger.error(f'pg_dump failed with return code {result.returncode}: {result.stderr}')
                raise CommandError(f'pg_dump failed: {result.stderr}')
            
            # Get the size of the created backup file
            backup_size = os.path.getsize(backup_path)
            logger.info(f'Backup created successfully: {backup_path}, Size: {backup_size} bytes, Return code: {result.returncode}')

            self.stdout.write(
                self.style.SUCCESS(f'Successfully created backup: {backup_path} (Size: {backup_size} bytes)')
            )

            # Compress the backup if requested
            if options['compress']:
                compressed_path = backup_path + '.gz'
                self.stdout.write(f'Compressing backup: {compressed_path}')
                
                with open(backup_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        f_out.writelines(f_in)
                
                # Remove the uncompressed file
                os.remove(backup_path)
                
                # Get the size of the compressed backup file
                compressed_size = os.path.getsize(compressed_path)
                logger.info(f'Backup compressed successfully: {compressed_path}, Size: {compressed_size} bytes')
                
                # Fix file ownership to match backup directory owner
                self._fix_file_ownership(compressed_path, output_dir)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully compressed backup: {compressed_path} (Size: {compressed_size} bytes)')
                )
            else:
                # Fix file ownership to match backup directory owner
                self._fix_file_ownership(backup_path, output_dir)
                logger.info(f'Backup operation completed successfully with return code: {result.returncode}')

        except FileNotFoundError:
            logger.error('pg_dump command not found. Make sure PostgreSQL is installed and in your PATH.')
            raise CommandError('pg_dump command not found. Make sure PostgreSQL is installed and in your PATH.')
        except Exception as e:
            logger.error(f'An error occurred during backup: {str(e)}')
            raise CommandError(f'An error occurred during backup: {str(e)}')
    
    def _fix_file_ownership(self, file_path, directory_path):
        """
        Fix file ownership to match the directory owner.
        This ensures backup files are owned by the host user, not root.
        """
        logger = logging.getLogger(__name__)
        try:
            # Get directory owner (uid, gid)
            dir_stat = os.stat(directory_path)
            dir_uid = dir_stat.st_uid
            dir_gid = dir_stat.st_gid
            
            # Get file owner
            file_stat = os.stat(file_path)
            file_uid = file_stat.st_uid
            file_gid = file_stat.st_gid
            
            # Only change ownership if file is owned by root (uid 0) and directory is not
            if file_uid == 0 and dir_uid != 0:
                os.chown(file_path, dir_uid, dir_gid)
                logger.info(f'Fixed file ownership: {file_path} -> uid={dir_uid}, gid={dir_gid}')
                self.stdout.write(
                    self.style.SUCCESS(f'Fixed file ownership to match directory owner')
                )
        except (OSError, PermissionError) as e:
            # Log but don't fail if we can't change ownership
            logger.warning(f'Could not fix file ownership for {file_path}: {e}')
            # Don't raise - ownership fix is not critical