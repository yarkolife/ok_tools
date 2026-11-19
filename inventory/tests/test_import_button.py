"""The "Import" button on an import's change page runs the import."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from inventory.admin import InspectionImportAdmin
from inventory.admin import InventoryImportAdmin
from inventory.models import InspectionImport
from inventory.models import InventoryImport
from registration.models import OKUser
from unittest.mock import patch


class ImportButtonTest(TestCase):
    """Before, the button only saved the object and imported nothing."""

    def setUp(self):
        self.client.force_login(OKUser.objects.create_superuser(
            email='admin-import@example.com', password='pw'))

    def _press_import(self, model, admin_class, url_name):
        obj = model.objects.create(
            file=SimpleUploadedFile('import.csv', b'a;b\n'))
        url = f'/admin/inventory/{url_name}/{obj.pk}/change/'
        page = self.client.get(url)
        self.assertContains(page, 'name="_run_import"')
        form = page.context['adminform'].form
        data = {
            name: form.initial.get(name)
            for name in form.fields
            if name != 'file' and form.initial.get(name) is not None
        }
        data['_run_import'] = '1'

        # The model validates the spreadsheet itself; that is not under test.
        with patch.object(model, 'clean'), \
                patch.object(admin_class, 'import_files') as import_files:
            response = self.client.post(url, data)

        self.assertRedirects(response, url, fetch_redirect_response=False)
        import_files.assert_called_once()
        queryset = import_files.call_args.args[1]
        self.assertEqual(list(queryset), [obj])

    def test_inventory_import_button_runs_the_import(self):
        """The inventory import starts for exactly this file."""
        self._press_import(
            InventoryImport, InventoryImportAdmin, 'inventoryimport')

    def test_inspection_import_button_runs_the_import(self):
        """The inspection import starts for exactly this file."""
        self._press_import(
            InspectionImport, InspectionImportAdmin, 'inspectionimport')
