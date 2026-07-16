"""
Regression tests for dead/shadowed method definitions in InventoryService.

An earlier revision of ``inventory/services/inventory_service.py`` carried a
block of thin delegating wrappers (``validate_inventory_file``,
``import_inventory_data``, ``validate_inspection_file``,
``import_inspection_data``) that called module-level names which were never
imported -- and in two cases did not exist anywhere in the codebase. They never
raised NameError only because each was shadowed by a real implementation later
in the same class body. These tests lock in both halves of that fix: no
duplicate definitions, and no unresolvable global references.
"""

import ast
import builtins
import inspect
import io

from django.forms import ValidationError
from django.test import TestCase
from openpyxl import Workbook

from inventory.services import inventory_service as service_module
from inventory.services.inventory_service import InventoryService


def _class_node():
    """Return the AST node for the InventoryService class body."""
    tree = ast.parse(inspect.getsource(service_module))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'InventoryService':
            return node
    raise AssertionError('InventoryService class not found in module source')


class InventoryServiceNoShadowedMethodsTest(TestCase):
    """The class body must not define the same method name twice."""

    def test_no_duplicate_method_definitions(self):
        """A later def silently shadows an earlier one -- ban duplicates."""
        seen = {}
        duplicates = []
        for item in _class_node().body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name in seen:
                    duplicates.append(
                        f'{item.name} defined at line {seen[item.name]} '
                        f'and again at line {item.lineno}'
                    )
                seen[item.name] = item.lineno
        self.assertEqual(
            duplicates, [],
            'InventoryService defines duplicate methods; the later definition '
            'silently shadows the earlier one:\n' + '\n'.join(duplicates)
        )

    def test_methods_reference_no_undefined_globals(self):
        """Every global a method calls must actually resolve at runtime.

        This is what would have caught the original bug: the wrappers called
        validate_inventory_import / inventory_import / validate_inspection_import
        / inspection_import, none of which were imported by the module.
        """
        module_names = set(vars(service_module)) | set(vars(builtins))
        class_node = _class_node()
        local_defs = {
            item.name for item in class_node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        undefined = set()
        for item in class_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            bound = set()
            for sub in ast.walk(item):
                if isinstance(sub, ast.arg):
                    bound.add(sub.arg)
                elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    bound.add(sub.id)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for alias in sub.names:
                        bound.add(alias.asname or alias.name.split('.')[0])
                elif isinstance(sub, ast.ExceptHandler) and sub.name:
                    bound.add(sub.name)
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)) and sub is not item:
                    # Nested def/class binds its own name in the enclosing scope.
                    bound.add(sub.name)
            for sub in ast.walk(item):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    name = sub.id
                    if (name not in bound and name not in module_names
                            and name not in local_defs):
                        undefined.add(f'{item.name}: {name}')

        self.assertEqual(
            sorted(undefined), [],
            'InventoryService methods reference names that are neither '
            'imported nor defined; calling them raises NameError:\n'
            + '\n'.join(sorted(undefined))
        )


class InventoryServiceSurvivingImplementationTest(TestCase):
    """The kept implementations must be the real, self-contained ones."""

    HEADER = [
        'inventory_number', 'description', 'serial_number', 'manufacturer',
        'location', 'quantity', 'status', 'unused', 'owner',
        'inventory_number_owner', 'purchase_date', 'purchase_cost',
    ]

    def _workbook(self, header):
        wb = Workbook()
        wb.worksheets[0].append(header)
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    def test_validate_inventory_file_accepts_correct_header(self):
        """The surviving validator runs without NameError on a good file."""
        InventoryService.validate_inventory_file(self._workbook(self.HEADER))

    def test_validate_inventory_file_rejects_bad_header(self):
        """A bad header raises ValidationError -- not NameError."""
        bad = list(self.HEADER)
        bad[0] = 'wrong_column'
        with self.assertRaises(ValidationError):
            InventoryService.validate_inventory_file(self._workbook(bad))

    def test_import_inventory_data_is_not_a_delegating_wrapper(self):
        """import_inventory_data must be the real implementation."""
        source = inspect.getsource(InventoryService.import_inventory_data)
        self.assertNotIn('return inventory_import(', source)
        self.assertIn('created', source)


class InventoryServiceExportTest(TestCase):
    """export_inventory_items referenced an unimported InventoryResource."""

    def test_export_inventory_items_runs(self):
        """The export path must not raise NameError: InventoryResource."""
        dataset = InventoryService.export_inventory_items()
        self.assertIsNotNone(dataset.xlsx)

    def test_inventory_resource_import_stays_function_local(self):
        """A module-level import of admin here would be a circular import."""
        self.assertNotIn(
            'InventoryResource', set(vars(service_module)),
            'InventoryResource must be imported inside export_inventory_items, '
            'not at module level: inventory/admin.py imports InventoryService, '
            'so a module-level import back would be circular.'
        )
