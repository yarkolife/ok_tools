import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import InventoryItem, Location, Organization
from rental.models import LabelFormat, RentalItem, RentalRequest

User = get_user_model()


class BarcodeApiTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            email='staff@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_login(self.staff)
        self.location = Location.objects.create(name='Test Room')

    def _create_item(self, inventory_number='OK-TEST', available_for_rent=True, status='in_stock'):
        return InventoryItem.objects.create(
            inventory_number=inventory_number,
            location=self.location,
            quantity=5,
            status=status,
            available_for_rent=available_for_rent,
        )

    def _create_rental(self, user=None, status='issued'):
        if user is None:
            user = User.objects.create_user(email='borrower@example.com', password='testpass')
        return RentalRequest.objects.create(
            user=user,
            created_by=self.staff,
            project_name='Test Project',
            purpose='Testing',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now() + timedelta(days=7),
            status=status,
        )

    def _create_rental_item(self, rental, item, quantity_issued=2, quantity_returned=0):
        return RentalItem.objects.create(
            rental_request=rental,
            inventory_item=item,
            quantity_requested=quantity_issued,
            quantity_issued=quantity_issued,
            quantity_returned=quantity_returned,
        )

    def test_barcode_lookup_success(self):
        item = self._create_item('OK-TEST-BC1')
        url = reverse('rental:api_barcode_lookup') + '?num=OK-TEST-BC1'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['id'], item.id)
        self.assertEqual(data['inventory_number'], 'OK-TEST-BC1')
        self.assertIn('description', data)

    def test_barcode_lookup_not_found(self):
        url = reverse('rental:api_barcode_lookup') + '?num=NONEXISTENT'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_barcode_lookup_missing_param(self):
        url = reverse('rental:api_barcode_lookup')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_scan_return_success(self):
        item = self._create_item('OK-SCAN-TEST')
        rental = self._create_rental()
        ri = self._create_rental_item(rental, item, quantity_issued=2, quantity_returned=0)

        url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-SCAN-TEST'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ri.refresh_from_db()
        self.assertEqual(ri.quantity_returned, 1)
        self.assertFalse(data['complete'])

    def test_scan_return_rejects_display_code(self):
        """The return page used to send R-YYMM-NNNN, which is not the pk."""
        self._create_item('OK-SCAN-CODE')
        rental = self._create_rental()
        display_code = f"R-{rental.created_at.strftime('%y%m')}-{rental.pk:04d}"

        url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            url,
            data=json.dumps({
                'rental_id': display_code,
                'inventory_number': 'OK-SCAN-CODE',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_scan_return_item_not_found(self):
        self._create_item('OK-SCAN-OTHER')
        rental = self._create_rental()

        url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-SCAN-OTHER'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_scan_return_already_complete(self):
        item = self._create_item('OK-SCAN-COMP')
        rental = self._create_rental()
        self._create_rental_item(rental, item, quantity_issued=1, quantity_returned=1)

        url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-SCAN-COMP'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_scan_return_invalid_rental_status(self):
        item = self._create_item('OK-SCAN-DRAFT')
        rental = self._create_rental(status='draft')
        self._create_rental_item(rental, item)

        url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-SCAN-DRAFT'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class BarcodePrintViewTests(TestCase):
    """Label sheet and roll layouts served by BarcodePrintView."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            email='printstaff@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_login(self.staff)
        shelf = Location.objects.get_or_create_by_path(
            'Ausleihe -> Schrank 3 -> Regal 3')
        self.owner = Organization.objects.create(name='OKMQ')
        self.item = InventoryItem.objects.create(
            inventory_number='OK-PRINT-1',
            description='Shure SM58',
            location=shelf,
            owner=self.owner,
            quantity=1,
        )
        self._ensure_roll_formats()

    def _ensure_roll_formats(self):
        """Recreate the seeded roll formats.

        The rows come from a data migration, which a transactional test
        elsewhere can wipe out of the reused test database.
        """
        for slug, width, height in (
            ('roll_51x25', 51, 25),
            ('roll_70x32', 70, 32),
        ):
            LabelFormat.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': 'Roll label',
                    'width_mm': width,
                    'height_mm': height,
                },
            )

    def _print(self, label_format=None, rotate=None):
        url = reverse('rental:barcode_print') + f'?ids={self.item.id}'
        if label_format:
            url += f'&format={label_format}'
        if rotate:
            url += f'&rotate={rotate}'
        return self.client.get(url)

    def test_standard_label_shows_location_and_owner(self):
        resp = self._print()
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'rental/barcode_print.html')
        # The location prints as runs now, its shelf codes marked up so they
        # can print larger than the words around them.
        self.assertContains(resp, 'Ausleihe')
        self.assertContains(resp, 'Schrank ')
        self.assertContains(resp, 'run-code')
        self.assertContains(resp, 'OKMQ')

    def test_the_sheet_label_reads_number_owner_bars_name_location(self):
        """The order the rows print in, top to bottom."""
        html = self._print().content.decode()
        # Only the markup, since the stylesheet above it names every row too.
        body = html[html.index('<div class="label-grid">'):]
        positions = [
            body.index('line-number_owner'),
            body.index('<svg'),
            body.index('line-description'),
            body.index('line-location'),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_roll_formats_use_roll_template_and_page_size(self):
        for label_format, size in (
            ('roll_51x25', '51mm 25mm'),
            ('roll_70x32', '70mm 32mm'),
        ):
            with self.subTest(label_format=label_format):
                resp = self._print(label_format)
                self.assertEqual(resp.status_code, 200)
                self.assertTemplateUsed(resp, 'rental/barcode_print_roll.html')
                self.assertContains(resp, f'size: {size}')
                self.assertContains(resp, 'OK-PRINT-1')
                self.assertContains(resp, 'OKMQ')

    def test_barcode_svg_scales_and_never_repeats_the_number(self):
        """Every layout prints the number once, below the bars, not inside."""
        for label_format in (None, 'compact', 'roll_51x25', 'roll_70x32'):
            with self.subTest(label_format=label_format):
                html = self._print(label_format).content.decode()
                self.assertIn('viewBox=', html)
                self.assertNotIn('<text', html)
                self.assertEqual(html.count('OK-PRINT-1'), 1)

    def test_rotated_roll_swaps_page_size_and_turns_the_content(self):
        """rotate=90 prints the label sideways for portrait label media."""
        html = self._print('roll_51x25', rotate='90').content.decode()
        self.assertIn('size: 25mm 51mm', html)
        self.assertIn('rotate(90deg)', html)

    def test_roll_is_not_rotated_without_the_parameter(self):
        for rotate in (None, '180', 'yes'):
            with self.subTest(rotate=rotate):
                html = self._print('roll_51x25', rotate=rotate).content.decode()
                self.assertIn('size: 51mm 25mm', html)
                self.assertNotIn('rotate(90deg)', html)

    def test_any_configured_label_size_prints(self):
        """A size nobody tuned by hand still lays out sensibly."""
        LabelFormat.objects.create(
            slug='roll_100x50', name='Big roll label',
            width_mm=100, height_mm=50)
        resp = self._print('roll_100x50')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'rental/barcode_print_roll.html')
        html = resp.content.decode()
        self.assertIn('size: 100mm 50mm', html)
        # The type scale grows with the label instead of stepping to one of
        # two fixed values.
        self.assertNotIn('--fs-desc: 6pt', html)
        self.assertIn('OK-PRINT-1', html)

    def test_an_inactive_format_is_not_offered(self):
        LabelFormat.objects.create(
            slug='roll_retired', name='Retired', width_mm=60, height_mm=40,
            is_active=False)
        resp = self._print('roll_retired')
        self.assertTemplateUsed(resp, 'rental/barcode_print.html')

    def test_unknown_format_falls_back_to_standard(self):
        resp = self._print('does-not-exist')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'rental/barcode_print.html')
