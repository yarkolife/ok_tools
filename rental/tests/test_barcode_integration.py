import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import InventoryItem, Location
from rental.models import RentalItem, RentalRequest
from rental.services.barcode_service import BarcodeService

User = get_user_model()


class BarcodeIntegrationTests(TestCase):

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

    def test_generate_and_lookup_barcode(self):
        item = self._create_item('OK-E2E-001')

        svg = BarcodeService.generate_svg('OK-E2E-001')
        self.assertTrue(svg, 'SVG output should not be empty')
        self.assertIn('<svg', svg)

        url = reverse('rental:api_barcode_lookup') + '?num=OK-E2E-001'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['id'], item.id)
        self.assertEqual(data['inventory_number'], 'OK-E2E-001')

    def test_full_scan_issue_workflow(self):
        item = self._create_item('OK-E2E-002')
        rental = self._create_rental()
        self._create_rental_item(rental, item, quantity_issued=1, quantity_returned=0)

        lookup_url = reverse('rental:api_barcode_lookup') + '?num=OK-E2E-002'
        resp = self.client.get(lookup_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['inventory_number'], 'OK-E2E-002')

        return_url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-002'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['quantity_returned'], 1)
        self.assertTrue(data['complete'])

        ri = RentalItem.objects.get(rental_request=rental, inventory_item=item)
        self.assertEqual(ri.quantity_returned, 1)

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-002'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_scan_return_multiple_items(self):
        item_a = self._create_item('OK-E2E-003A')
        item_b = self._create_item('OK-E2E-003B')
        rental = self._create_rental()
        ri_a = self._create_rental_item(rental, item_a, quantity_issued=1, quantity_returned=0)
        ri_b = self._create_rental_item(rental, item_b, quantity_issued=1, quantity_returned=0)

        return_url = reverse('rental:api_scan_return_item')

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-003A'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['complete'])
        ri_a.refresh_from_db()
        self.assertEqual(ri_a.quantity_returned, 1)

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-003B'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['complete'])
        ri_b.refresh_from_db()
        self.assertEqual(ri_b.quantity_returned, 1)

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-003A'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-003B'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_scan_nonexistent_item(self):
        rental = self._create_rental()

        lookup_url = reverse('rental:api_barcode_lookup') + '?num=NONEXISTENT-999'
        resp = self.client.get(lookup_url)
        self.assertEqual(resp.status_code, 404)

        return_url = reverse('rental:api_scan_return_item')
        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'NONEXISTENT-999'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_scan_return_quantity_exact(self):
        item = self._create_item('OK-E2E-005')
        rental = self._create_rental()
        ri = self._create_rental_item(rental, item, quantity_issued=3, quantity_returned=0)

        return_url = reverse('rental:api_scan_return_item')

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-005'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['quantity_returned'], 1)
        self.assertFalse(data['complete'])

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-005'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['quantity_returned'], 2)
        self.assertFalse(data['complete'])

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-005'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['quantity_returned'], 3)
        self.assertTrue(data['complete'])

        resp = self.client.post(
            return_url,
            data=json.dumps({'rental_id': rental.id, 'inventory_number': 'OK-E2E-005'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

        ri.refresh_from_db()
        self.assertEqual(ri.quantity_returned, 3)
        self.assertTrue(ri.quantity_returned >= ri.quantity_issued)
