import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import InventoryItem, Location
from rental.models import RentalItem, RentalRequest

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
