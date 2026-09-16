from decimal import Decimal
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from inventory.models import InventoryItem
from inventory.models import Location
from inventory.models import Organization
from registration.models import OKUser as User
from rental.models import LabelFormat
from rental.models import RentalConfig
from rental.services.label_printer_service import LabelPrinterError
from rental.services.label_printer_service import LabelPrinterService
from rental.services.label_printer_service import PrinterSettings
from unittest import mock
import json


SETTINGS = PrinterSettings(
    host='192.0.2.10', port=9100, dpi=203, gap_mm=Decimal('2.0'))


class TSPLJobTests(TestCase):
    """The TSPL a label job is made of."""

    def _label(self, **item):
        item.setdefault('inventory_number', 'OK-000481')
        return LabelPrinterService.build_label(item, 51, 25, SETTINGS)

    def test_job_carries_the_label_geometry(self):
        """The media size travels with the job, not with the workstation."""
        tspl = self._label()
        self.assertIn('SIZE 51 mm,25 mm', tspl)
        self.assertIn('GAP 2.0 mm,0 mm', tspl)
        self.assertIn('PRINT 1,1', tspl)

    def test_label_holds_every_field_of_the_html_layout(self):
        tspl = self._label(
            description='Kabeltrommel 10m',
            owner='OKMQ',
            location='Ausleihe -> Regal 6',
        )
        self.assertIn('"Kabeltrommel 10m"', tspl)
        self.assertIn('"OKMQ"', tspl)
        self.assertIn('"Ausleihe -> Regal 6"', tspl)
        self.assertIn('BARCODE ', tspl)
        self.assertIn('"128"', tspl)
        self.assertIn('"OK-000481"', tspl)

    def test_everything_stays_inside_the_label(self):
        """No element may start past the label edge or run over it."""
        tspl = self._label(
            description='Sehr langer Gerätename der nicht auf das Etikett passt',
            owner='OKMQ',
            location='Ausleihe -> Schrank 3 -> Regal 3 -> ganz hinten links',
        )
        width_dots = int(51 * 203 / 25.4)
        height_dots = int(25 * 203 / 25.4)
        for line in tspl.splitlines():
            if not line.startswith(('TEXT ', 'BARCODE ')):
                continue
            head = line.split('"', 1)[0]
            x, y = (int(value) for value in head.split()[1].split(',')[:2])
            self.assertGreaterEqual(x, 0, line)
            self.assertLess(x, width_dots, line)
            self.assertLess(y, height_dots, line)

        # The bars plus the widest text must fit across the label.
        bars = [ln for ln in tspl.splitlines() if ln.startswith('BARCODE ')][0]
        bar_x = int(bars.split()[1].split(',')[0])
        narrow = int(bars.split(',')[6])
        bar_width = ((len('OK-000481') + 2) * 11 + 13) * narrow
        self.assertLessEqual(bar_x + bar_width, width_dots)

    def test_a_top_offset_moves_the_content_down(self):
        """The offset is the knob for a roll that sits high under the head."""
        def first_y(tspl):
            line = [ln for ln in tspl.splitlines()
                    if ln.startswith(('TEXT ', 'BARCODE '))][0]
            return int(line.split()[1].split(',')[1])

        offset_dots = int(3 * 203 / 25.4)
        plain = first_y(self._label(description='Kabeltrommel 10m'))
        shifted = first_y(LabelPrinterService.build_label(
            {'inventory_number': 'OK-000481',
             'description': 'Kabeltrommel 10m'},
            51, 25,
            PrinterSettings(host='192.0.2.10', offset_y_mm=Decimal('3.0')),
        ))
        # Nothing may be printed above the offset line, and since the rows are
        # redistributed over what is left, the first one does not travel the
        # full offset.
        self.assertGreaterEqual(shifted, offset_dots)
        self.assertGreater(shifted, plain)
        self.assertLessEqual(shifted - plain, offset_dots)

    def test_an_offset_never_pushes_content_over_the_far_edge(self):
        """The offset trims the usable area instead of displacing the layout."""
        height_dots = int(25 * 203 / 25.4)
        width_dots = int(51 * 203 / 25.4)
        tspl = LabelPrinterService.build_label(
            {'inventory_number': 'OK-000481',
             'description': 'Kabeltrommel 10m',
             'owner': 'OKMQ',
             'location': 'Ausleihe -> Regal 6'},
            51, 25,
            PrinterSettings(host='192.0.2.10', offset_x_mm=Decimal('4.0'),
                            offset_y_mm=Decimal('6.0')),
        )
        for line in tspl.splitlines():
            if not line.startswith(('TEXT ', 'BARCODE ')):
                continue
            x, y = (int(v) for v in line.split()[1].split(',')[:2])
            self.assertLess(y, height_dots, line)
            self.assertLess(x, width_dots, line)

    def test_the_number_is_not_repeated_as_the_description(self):
        tspl = self._label(description='OK-000481')
        self.assertEqual(tspl.count('"OK-000481"'), 2)  # barcode plus number

    def test_quotes_in_a_description_cannot_break_the_job(self):
        tspl = self._label(description='Kabel "kurz"')
        self.assertIn(r'\"kurz\"', tspl)

    def test_umlauts_are_sent_in_the_printers_own_character_set(self):
        job = LabelPrinterService.build_job(
            [{'inventory_number': 'OK-1', 'description': 'Kabelbrücke'}],
            51, 25, SETTINGS)
        self.assertTrue(job.startswith(b'CODEPAGE 1252'))
        self.assertIn('Kabelbrücke'.encode('cp1252'), job)

    def test_one_job_holds_every_label(self):
        job = LabelPrinterService.build_job(
            [{'inventory_number': 'OK-1'}, {'inventory_number': 'OK-2'}],
            51, 25, SETTINGS)
        self.assertEqual(job.count(b'PRINT 1,1'), 2)
        self.assertEqual(job.count(b'CODEPAGE'), 1)

    def test_an_unreachable_printer_is_reported_not_swallowed(self):
        with mock.patch(
            'rental.services.label_printer_service.socket.create_connection',
            side_effect=OSError('Connection refused'),
        ):
            with self.assertRaises(LabelPrinterError):
                LabelPrinterService.send(b'SIZE 51 mm,25 mm\n', SETTINGS)


class DirectPrintEndpointTests(TestCase):
    """The endpoint that hands a label job to the configured printer."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            email='labelstaff@example.com', password='testpass', is_staff=True)
        self.client.force_login(self.staff)
        self.item = InventoryItem.objects.create(
            inventory_number='OK-PRINT-9',
            description='Shure SM58',
            location=Location.objects.get_or_create_by_path('Ausleihe'),
            owner=Organization.objects.create(name='OKMQ'),
            quantity=1,
        )
        config = RentalConfig.get_config()
        config.label_printer_host = '192.0.2.10'
        config.label_gap_mm = Decimal('2.0')
        config.save()
        # The roll formats come from a data migration, which a transactional
        # test elsewhere can wipe out of the reused test database.
        self.label_format, _created = LabelFormat.objects.get_or_create(
            slug='roll_51x25',
            defaults={'name': 'Roll label', 'width_mm': 51, 'height_mm': 25},
        )
        self.url = reverse('rental:barcode_print_direct')

    def _post(self, **payload):
        payload.setdefault('ids', [self.item.id])
        payload.setdefault('format', 'roll_51x25')
        return self.client.post(
            self.url, data=json.dumps(payload),
            content_type='application/json')

    def test_a_roll_format_reaches_the_printer(self):
        with mock.patch.object(LabelPrinterService, 'send') as send:
            resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['printed'], 1)
        payload = send.call_args[0][0]
        self.assertIn(b'SIZE 51 mm,25 mm', payload)
        self.assertIn(b'OK-PRINT-9', payload)

    def test_the_printer_address_comes_from_the_config_not_the_request(self):
        with mock.patch.object(LabelPrinterService, 'send') as send:
            self._post(host='198.51.100.7', port=1234)
        settings = send.call_args[0][1]
        self.assertEqual(settings.host, '192.0.2.10')
        self.assertEqual(settings.port, 9100)

    def test_any_configured_label_size_reaches_the_printer(self):
        """A new roll needs its millimetres entered, nothing more."""
        LabelFormat.objects.create(
            slug='roll_100x50', name='Big roll label',
            width_mm=100, height_mm=50)
        with mock.patch.object(LabelPrinterService, 'send') as send:
            resp = self._post(format='roll_100x50')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'SIZE 100 mm,50 mm', send.call_args[0][0])

    def test_a_format_may_carry_the_gap_of_its_own_roll(self):
        self.label_format.gap_mm = Decimal('3.0')
        self.label_format.save()
        with mock.patch.object(LabelPrinterService, 'send') as send:
            self._post()
        self.assertIn(b'GAP 3.0 mm', send.call_args[0][0])

    def test_without_its_own_gap_a_format_uses_the_printer_setting(self):
        with mock.patch.object(LabelPrinterService, 'send') as send:
            self._post()
        self.assertIn(b'GAP 2.0 mm', send.call_args[0][0])

    def test_sheet_formats_are_refused(self):
        """An A4 sheet layout has no physical label size to send."""
        for label_format in ('standard', 'compact', 'nonsense'):
            with self.subTest(label_format=label_format):
                with mock.patch.object(LabelPrinterService, 'send') as send:
                    resp = self._post(format=label_format)
                self.assertEqual(resp.status_code, 400)
                send.assert_not_called()

    def test_without_a_configured_printer_the_request_is_refused(self):
        config = RentalConfig.get_config()
        config.label_printer_host = ''
        config.save()
        with mock.patch.object(LabelPrinterService, 'send') as send:
            resp = self._post()
        self.assertEqual(resp.status_code, 409)
        send.assert_not_called()

    def test_an_unreachable_printer_answers_with_a_readable_error(self):
        with mock.patch.object(
            LabelPrinterService, 'send',
            side_effect=LabelPrinterError('192.0.2.10:9100 — timed out'),
        ):
            resp = self._post()
        self.assertEqual(resp.status_code, 502)
        self.assertIn('192.0.2.10:9100', resp.json()['error'])

    def test_missing_ids_are_refused(self):
        resp = self._post(ids=[])
        self.assertEqual(resp.status_code, 400)

    def test_only_staff_may_print(self):
        self.client.logout()
        user = User.objects.create_user(
            email='nostaff@example.com', password='testpass')
        self.client.force_login(user)
        with mock.patch.object(LabelPrinterService, 'send') as send:
            resp = self._post()
        self.assertIn(resp.status_code, (302, 403))
        send.assert_not_called()
