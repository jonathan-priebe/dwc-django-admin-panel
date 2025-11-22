"""
Django management command to import Mystery Gift files from dlc_source directory.

Usage:
    python manage.py import_mystery_gifts [--game-id GAMEID] [--dry-run]
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from dwc_admin.models import MysteryGift


# Game ID to readable game name mapping (based on Wiki)
GAME_NAMES = {
    # Pokemon Diamond/Pearl/Platinum
    'ADAD': 'Pokemon Diamond (Germany)',
    'ADAE': 'Pokemon Diamond (USA)',
    'ADAF': 'Pokemon Diamond (France)',
    'ADAI': 'Pokemon Diamond (Italy)',
    'ADAJ': 'Pokemon Diamond (Japan)',
    'ADAK': 'Pokemon Diamond (Korea)',
    'ADAS': 'Pokemon Diamond (Spain)',
    'APAE': 'Pokemon Pearl (USA)',
    'APAJ': 'Pokemon Pearl (Japan)',
    'CPUD': 'Pokemon Platinum (Germany)',
    'CPUE': 'Pokemon Platinum (USA)',
    'CPUF': 'Pokemon Platinum (France)',
    'CPUI': 'Pokemon Platinum (Italy)',
    'CPUJ': 'Pokemon Platinum (Japan)',
    'CPUK': 'Pokemon Platinum (Korea)',
    'CPUS': 'Pokemon Platinum (Spain)',

    # Pokemon HeartGold/SoulSilver
    'IPKD': 'Pokemon HeartGold (Germany)',
    'IPKE': 'Pokemon HeartGold (USA)',
    'IPKF': 'Pokemon HeartGold (France)',
    'IPKI': 'Pokemon HeartGold (Italy)',
    'IPKJ': 'Pokemon HeartGold (Japan)',
    'IPKK': 'Pokemon HeartGold (Korea)',
    'IPKS': 'Pokemon HeartGold (Spain)',
    'IPGD': 'Pokemon SoulSilver (Germany)',
    'IPGE': 'Pokemon SoulSilver (USA)',
    'IPGF': 'Pokemon SoulSilver (France)',
    'IPGI': 'Pokemon SoulSilver (Italy)',
    'IPGJ': 'Pokemon SoulSilver (Japan)',
    'IPGK': 'Pokemon SoulSilver (Korea)',
    'IPGS': 'Pokemon SoulSilver (Spain)',

    # Pokemon Black/White
    'IRBD': 'Pokemon Black (Germany)',
    'IRBE': 'Pokemon Black (USA)',
    'IRBF': 'Pokemon Black (France)',
    'IRBI': 'Pokemon Black (Italy)',
    'IRBJ': 'Pokemon Black (Japan)',
    'IRBK': 'Pokemon Black (Korea)',
    'IRBS': 'Pokemon Black (Spain)',
    'IRAD': 'Pokemon White (Germany)',
    'IRAE': 'Pokemon White (USA)',
    'IRAF': 'Pokemon White (France)',
    'IRAI': 'Pokemon White (Italy)',
    'IRAJ': 'Pokemon White (Japan)',
    'IRAK': 'Pokemon White (Korea)',
    'IRAS': 'Pokemon White (Spain)',

    # Pokemon Black 2/White 2
    'IREO': 'Pokemon Black 2 (Europe)',
    'IREE': 'Pokemon Black 2 (USA)',
    'IREJ': 'Pokemon Black 2 (Japan)',
    'IREK': 'Pokemon Black 2 (Korea)',
    'IRDO': 'Pokemon White 2 (Europe)',
    'IRDE': 'Pokemon White 2 (USA)',
    'IRDJ': 'Pokemon White 2 (Japan)',
    'IRDK': 'Pokemon White 2 (Korea)',

    # Mario Kart Wii
    'RMCE': 'Mario Kart Wii (USA)',
    'RMCJ': 'Mario Kart Wii (Japan)',
    'RMCK': 'Mario Kart Wii (Korea)',
    'RMCP': 'Mario Kart Wii (Europe)',

    # Animal Crossing
    'B3RE': 'Animal Crossing: City Folk (USA)',
    'B3RJ': 'Animal Crossing: City Folk (Japan)',
    'B3RP': 'Animal Crossing: City Folk (Europe)',
}


# Region detection from filename patterns
def detect_region(filename):
    """Detect region from filename"""
    filename_upper = filename.upper()

    if 'US' in filename_upper or 'EN' in filename_upper:
        return 'US'
    elif 'EU' in filename_upper or 'UK' in filename_upper:
        return 'EU'
    elif 'JP' in filename_upper:
        return 'JP'
    elif 'KR' in filename_upper or 'KO' in filename_upper:
        return 'KR'
    elif 'AU' in filename_upper:
        return 'AU'
    elif 'DE' in filename_upper:
        return 'DE'
    elif 'FR' in filename_upper:
        return 'FR'
    elif 'IT' in filename_upper:
        return 'IT'
    elif 'ES' in filename_upper:
        return 'ES'

    return 'ALL'


class Command(BaseCommand):
    help = 'Import Mystery Gift .myg files from dlc_source directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--game-id',
            type=str,
            help='Import only for specific game ID (e.g. CPUE)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing mystery gifts with same filename',
        )

    def handle(self, *args, **options):
        game_id_filter = options.get('game_id')
        dry_run = options.get('dry_run', False)
        overwrite = options.get('overwrite', False)

        # Find dlc_source directory
        # In Docker: /app/dlc_source/dlc
        # On host: <project_root>/dlc_source/dlc
        base_dir = Path(settings.BASE_DIR).parent  # Go up from admin_panel to /app
        dlc_dir = base_dir / 'dlc_source' / 'dlc'

        # Fallback: check if we're in Docker and dlc_source is at root
        if not dlc_dir.exists():
            dlc_dir = Path('/app/dlc_source/dlc')

        if not dlc_dir.exists():
            dlc_dir = Path('/dlc_source/dlc')

        if not dlc_dir.exists():
            self.stdout.write(self.style.ERROR(
                f'DLC directory not found: {dlc_dir}\n'
                f'Please run: git clone --depth 1 --filter=blob:none --sparse '
                f'https://github.com/jonathan-priebe/dwc_network_server_emulator.git dlc_source && '
                f'cd dlc_source && git sparse-checkout set dlc'
            ))
            return

        self.stdout.write(self.style.SUCCESS(f'Scanning DLC directory: {dlc_dir}'))

        imported_count = 0
        skipped_count = 0
        error_count = 0

        # Iterate through game ID directories
        for game_dir in sorted(dlc_dir.iterdir()):
            if not game_dir.is_dir():
                continue

            game_id = game_dir.name

            # Filter by game ID if specified
            if game_id_filter and game_id != game_id_filter:
                continue

            game_name = GAME_NAMES.get(game_id, f'Unknown Game ({game_id})')

            self.stdout.write(f'\n{self.style.WARNING(f"Processing {game_id}: {game_name}")}')

            # Find all .myg files
            myg_files = list(game_dir.glob('*.myg'))

            if not myg_files:
                self.stdout.write(f'  No .myg files found')
                continue

            for myg_file in sorted(myg_files):
                filename = myg_file.name
                file_size = myg_file.stat().st_size

                # Check if already exists
                existing = MysteryGift.objects.filter(filename=filename).first()

                if existing and not overwrite:
                    self.stdout.write(f'  {self.style.WARNING("⊘")} {filename} (already exists, skipping)')
                    skipped_count += 1
                    continue

                # Detect region from filename
                region = detect_region(filename)

                # Create title from filename
                title = filename.replace('.myg', '').replace('_', ' ').title()
                title = f'{game_name} - {title}'

                if dry_run:
                    action = 'Would update' if existing else 'Would import'
                    self.stdout.write(f'  {self.style.SUCCESS("✓")} {action}: {filename} ({file_size} bytes, region: {region})')
                    imported_count += 1
                    continue

                try:
                    # Open and save file
                    with open(myg_file, 'rb') as f:
                        if existing:
                            # Update existing
                            existing.file.delete(save=False)  # Delete old file
                            existing.file.save(filename, File(f), save=False)
                            existing.file_size = file_size
                            existing.game_id = game_id
                            existing.title = title
                            existing.region = region
                            existing.save()

                            self.stdout.write(f'  {self.style.SUCCESS("↻")} Updated: {filename}')
                        else:
                            # Create new
                            mystery_gift = MysteryGift(
                                filename=filename,
                                game_id=game_id,
                                title=title,
                                region=region,
                                file_size=file_size,
                                enabled=True,
                                event_type='Mystery Gift',
                                description=f'Auto-imported from dlc_source for {game_name}',
                                created_by='auto-import'
                            )
                            mystery_gift.file.save(filename, File(f), save=False)
                            mystery_gift.save()

                            self.stdout.write(f'  {self.style.SUCCESS("✓")} Imported: {filename}')

                    imported_count += 1

                except Exception as e:
                    self.stdout.write(f'  {self.style.ERROR("✗")} Error importing {filename}: {e}')
                    error_count += 1

        # Summary
        self.stdout.write(f'\n{self.style.SUCCESS("="*60)}')
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'DRY RUN: Would import {imported_count} mystery gifts'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully imported/updated {imported_count} mystery gifts'))

        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped_count} existing gifts (use --overwrite to update)'))

        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Failed to import {error_count} gifts'))
