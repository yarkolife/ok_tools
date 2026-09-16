from django.test import TestCase
from rental import label_layout
from rental.label_layout import LineSpec


ITEM = {
    'inventory_number': 'OK-001131',
    'description': '[Laptop 25] HP ProBook 650 G1',
    'owner': 'OKMQ',
    'location': 'Ausleihe -> Schrank 3 -> Fach 8',
}


class LocationRunTests(TestCase):
    """How a location path is broken into words and codes."""

    def _runs(self, location, **kwargs):
        return label_layout.location_runs(location, **kwargs)

    def test_the_code_of_every_level_is_marked_to_print_larger(self):
        runs = self._runs('Ausleihe -> Schrank 3 -> Fach 8')
        codes = [run.text for run in runs if run.role == 'code']
        self.assertEqual(codes, ['3', '8'])
        self.assertTrue(all(run.scale > 1 for run in runs
                            if run.role == 'code'))

    def test_a_letter_code_counts_as_a_code(self):
        runs = self._runs('Regal B2')
        self.assertEqual([run.text for run in runs if run.role == 'code'],
                         ['B2'])

    def test_a_location_without_codes_stays_one_run(self):
        """Not every house numbers its shelves."""
        runs = self._runs('Seminarraum')
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].text, 'Seminarraum')
        self.assertEqual(runs[0].scale, 1.0)

    def test_highlighting_can_be_turned_off(self):
        runs = self._runs('Schrank 3', highlight_codes=False)
        self.assertEqual([run.role for run in runs], [''])

    def test_nothing_is_shortened_while_it_fits(self):
        runs = self._runs('Ausleihe -> Schrank 3', fits=lambda runs: True)
        self.assertIn('Ausleihe', [run.text for run in runs])
        self.assertIn('Schrank ', [run.text for run in runs])

    def test_the_words_are_abbreviated_before_a_level_is_dropped(self):
        """A level carries a code; the words in front of it do not."""
        seen = []

        def fits(runs):
            text = ''.join(run.text for run in runs)
            seen.append(text)
            return len(text) <= 24

        runs = self._runs(
            'Ausleihe -> Stativschrank -> Ton / MIX Stative', fits=fits)
        text = ''.join(run.text for run in runs)
        self.assertIn('Stat.', text)
        self.assertNotIn('Stativschrank', text)

    def test_a_level_is_dropped_only_when_abbreviating_was_not_enough(self):
        runs = self._runs(
            'Ausleihe -> Schrank 3 -> Regal 3 -> Fach 8',
            fits=lambda runs: len(''.join(r.text for r in runs)) <= 20,
        )
        text = ''.join(run.text for run in runs)
        self.assertNotIn('Ausleihe', text)
        self.assertIn('8', text)

    def test_the_last_level_survives_even_when_nothing_fits(self):
        runs = self._runs('Ausleihe -> Schrank 3 -> Fach 8',
                          fits=lambda runs: False)
        self.assertTrue(runs)
        self.assertIn('8', ''.join(run.text for run in runs))

    def test_a_leading_level_everybody_knows_can_be_dropped_outright(self):
        runs = self._runs('Ausleihe -> Schrank 3', drop_leading=1)
        self.assertNotIn('Ausleihe', ''.join(run.text for run in runs))

    def test_shortening_keeps_the_beginning_of_a_word(self):
        self.assertEqual(label_layout.shorten_word('Schrank'), 'Schr.')
        self.assertEqual(label_layout.shorten_word('Fach'), 'Fach')
        self.assertEqual(label_layout.shorten_word('Regal'), 'Regal')


class RowTests(TestCase):
    """The rows a configured label prints."""

    def test_the_default_layout_is_number_owner_bars_name_location(self):
        rows = label_layout.build_rows(ITEM, label_layout.DEFAULT_LINES)
        self.assertEqual(
            [row.content for row in rows],
            ['number_owner', 'barcode', 'description', 'location'],
        )

    def test_a_row_with_nothing_to_say_is_left_out(self):
        rows = label_layout.build_rows(
            {'inventory_number': 'OK-1'}, label_layout.DEFAULT_LINES)
        self.assertEqual([row.content for row in rows],
                         ['number_owner', 'barcode'])

    def test_a_description_repeating_the_number_is_left_out(self):
        rows = label_layout.build_rows(
            {'inventory_number': 'OK-1', 'description': 'OK-1'},
            label_layout.DEFAULT_LINES)
        self.assertNotIn('description', [row.content for row in rows])

    def test_the_lines_decide_the_order(self):
        """A house that wants the bars first can have them first."""
        rows = label_layout.build_rows(ITEM, [
            LineSpec(content=label_layout.CONTENT_BARCODE),
            LineSpec(content=label_layout.CONTENT_NUMBER),
        ])
        self.assertEqual([row.content for row in rows],
                         ['barcode', 'number'])

    def test_a_line_carries_its_size_and_alignment(self):
        rows = label_layout.build_rows(ITEM, [
            LineSpec(content=label_layout.CONTENT_DESCRIPTION,
                     size=label_layout.SIZE_LARGE,
                     align=label_layout.ALIGN_LEFT),
        ])
        self.assertEqual(rows[0].size, label_layout.SIZE_LARGE)
        self.assertEqual(rows[0].align, label_layout.ALIGN_LEFT)

    def test_the_number_and_owner_row_keeps_them_apart(self):
        rows = label_layout.build_rows(ITEM, [
            LineSpec(content=label_layout.CONTENT_NUMBER_OWNER)])
        roles = [run.role for run in rows[0].runs]
        self.assertEqual(roles[0], 'number')
        self.assertEqual(roles[-1], 'owner')
        self.assertIn('OK-001131', rows[0].text)
        self.assertIn('OKMQ', rows[0].text)

    def test_an_item_without_an_owner_still_shows_its_number(self):
        rows = label_layout.build_rows(
            {'inventory_number': 'OK-1'},
            [LineSpec(content=label_layout.CONTENT_NUMBER_OWNER)])
        self.assertEqual(rows[0].text, 'OK-1')
