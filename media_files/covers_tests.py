"""Tests for automatic cover generation (media_files.covers).

Pure logic (series parsing, deterministic variation, config resolving,
template rendering) uses SimpleTestCase; resolver rules and config loading
from the database use TestCase.
"""

from django.test import SimpleTestCase, TestCase
from PIL import Image

from media_files.covers import variations
from media_files.covers.config import (
    CoverConfig,
    DEFAULT_BODY_FONT,
    DEFAULT_LOGO_PATH,
    DEFAULT_TITLE_FONT,
    get_cover_config,
)
from media_files.covers.data import CoverData
from media_files.covers.resolver import resolve_template
from media_files.covers.series import parse_series
from media_files.covers.templates import (
    BaseCover,
    JournalCover,
    TrailerCover,
    get_template,
)


def _synthetic_bg(size=(1280, 720)):
    """A plain RGB image standing in for an extracted video frame."""
    return Image.new('RGB', size, (90, 90, 110))


def _test_config(**overrides):
    """A CoverConfig pointing at the bundled assets."""
    base = dict(
        enabled=True,
        logo_path=str(DEFAULT_LOGO_PATH),
        title_font_path=str(DEFAULT_TITLE_FONT),
        body_font_path=str(DEFAULT_BODY_FONT),
    )
    base.update(overrides)
    return CoverConfig(**base)


class SeriesParserTest(SimpleTestCase):
    """Episode/series extraction from titles."""

    def test_parses_folge(self):
        info = parse_series('Haltestelle - das Straßenbahnmagazin Folge 248')
        self.assertTrue(info.matched)
        self.assertEqual(info.part, 248)
        self.assertEqual(info.marker, 'Folge')
        self.assertEqual(info.series, 'Haltestelle - das Straßenbahnmagazin')

    def test_parses_teil_with_total(self):
        info = parse_series('CSD Halle 13.09.2025 Teil: 2/4')
        self.assertEqual(info.part, 2)
        self.assertEqual(info.total, 4)
        self.assertEqual(info.series, 'CSD Halle 13.09.2025')

    def test_no_marker(self):
        info = parse_series('Democrazy')
        self.assertFalse(info.matched)
        self.assertIsNone(info.part)

    def test_empty_title(self):
        self.assertFalse(parse_series('').matched)


class VariationsTest(SimpleTestCase):
    """Deterministic per-number variation."""

    def test_stable_for_same_number(self):
        self.assertEqual(
            variations.variant_index(17150, 3),
            variations.variant_index(17150, 3),
        )

    def test_index_in_range(self):
        for n in range(0, 500, 7):
            self.assertIn(variations.variant_index(n, 3), (0, 1, 2))

    def test_count_one_is_zero(self):
        self.assertEqual(variations.variant_index(123, 1), 0)

    def test_distributes_across_numbers(self):
        seen = {variations.variant_index(n, 3) for n in range(100)}
        self.assertGreater(len(seen), 1)

    def test_pick_stable(self):
        choices = ('a', 'b', 'c')
        self.assertEqual(
            variations.pick(42, choices), variations.pick(42, choices))
        self.assertIsNone(variations.pick(42, []))


class CoverConfigTest(SimpleTestCase):
    """Accent and template resolution on a plain CoverConfig."""

    def test_accent_override_wins(self):
        cfg = _test_config(category_colors={'Trailer': '#123456'})
        self.assertEqual(cfg.accent_for_category('Trailer'), '#123456')

    def test_builtin_category_color(self):
        cfg = _test_config()
        self.assertEqual(cfg.accent_for_category('Trailer'), '#FF6B00')

    def test_unknown_category_stable_hash(self):
        cfg = _test_config()
        a = cfg.accent_for_category('Some Channel Specific Category')
        b = cfg.accent_for_category('Some Channel Specific Category')
        self.assertEqual(a, b)
        self.assertTrue(a.startswith('#'))

    def test_template_for_category_builtin(self):
        self.assertEqual(_test_config().template_for_category('Trailer'), 'trailer')

    def test_template_for_category_default_base(self):
        self.assertEqual(_test_config().template_for_category('Heimatdoku'), 'base')

    def test_template_rules_override(self):
        cfg = _test_config(category_templates={'Heimatdoku': 'journal'})
        self.assertEqual(cfg.template_for_category('Heimatdoku'), 'journal')


class TemplateRegistryTest(SimpleTestCase):
    """The name->class registry used by config/resolver."""

    def test_known_names(self):
        self.assertIs(get_template('base'), BaseCover)
        self.assertIs(get_template('journal'), JournalCover)
        self.assertIs(get_template('trailer'), TrailerCover)

    def test_unknown_defaults_to_base(self):
        self.assertIs(get_template('does-not-exist'), BaseCover)


class RenderSmokeTest(SimpleTestCase):
    """Each template renders a 1280x720 RGB image without crashing."""

    def _assert_cover(self, image):
        self.assertEqual(image.mode, 'RGB')
        self.assertEqual(image.size, (1280, 720))

    def test_base_renders(self):
        data = CoverData(title='Ein Test über Umläute: äöüß',
                         author='Max Mustermann', category='Heimatdoku', number=17150)
        self._assert_cover(BaseCover().render(_synthetic_bg(), data, _test_config()))

    def test_journal_renders(self):
        data = CoverData(title='Rudi Ra Teil 14', author='Studio', category='Familie',
                         number=14, series='Rudi Ra', episode_marker='Teil', episode_part=14)
        self._assert_cover(JournalCover().render(_synthetic_bg(), data, _test_config()))

    def test_trailer_renders(self):
        data = CoverData(title='Filmfest 2025', author='OK', category='Trailer', number=84)
        self._assert_cover(TrailerCover().render(_synthetic_bg(), data, _test_config()))

    def test_renders_without_metadata(self):
        # No license -> empty fields must not crash (only frame + logo).
        data = CoverData(number=999)
        self._assert_cover(BaseCover().render(_synthetic_bg(), data, _test_config()))

    def test_theme_override_applies(self):
        data = CoverData(title='X', category='Heimatdoku', number=5)
        theme = {'accent': '#FFD400', 'background_style': 'cinematic'}
        self._assert_cover(
            BaseCover().render(_synthetic_bg(), data, _test_config(), theme=theme))

    def test_overlay_renders_png(self):
        import tempfile
        from types import SimpleNamespace
        from PIL import Image
        from media_files.covers.templates.overlay import OverlayCover

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            Image.new('RGBA', (1280, 720), (230, 0, 126, 180)).save(tmp.name)
            overlay = SimpleNamespace(
                image=SimpleNamespace(path=tmp.name, name=tmp.name),
                text_area={'x': 60, 'y': 560, 'w': 1160, 'h': 120,
                           'align': 'left', 'color': '#FFFFFF'},
                logo_area=None,
                accent='', use_video_frame=True, darken_frame=True, draw_logo=True)
            data = CoverData(title='Podcast Folge 3', author='Host', number=3)
            self._assert_cover(
                OverlayCover(overlay).render(_synthetic_bg(), data, _test_config()))


class ResolverTest(TestCase):
    """Template resolution with DB-backed CoverTemplate rules."""

    def setUp(self):
        self.config = _test_config()

    def test_series_resolves_journal(self):
        data = CoverData(title='Rudi Ra Teil 3', number=3,
                         series='Rudi Ra', episode_marker='Teil', episode_part=3)
        template, theme = resolve_template(data, self.config)
        self.assertIsInstance(template, JournalCover)
        self.assertEqual(theme, {})

    def test_category_resolves_via_config(self):
        data = CoverData(title='Teaser', category='Trailer', number=1)
        template, _ = resolve_template(data, self.config)
        self.assertIsInstance(template, TrailerCover)

    def test_default_is_base(self):
        data = CoverData(title='Etwas', category='Heimatdoku', number=2)
        template, _ = resolve_template(data, self.config)
        self.assertIsInstance(template, BaseCover)

    def test_db_rule_overrides_with_theme(self):
        from media_files.models import CoverTemplate
        CoverTemplate.objects.create(
            name='Politik als Trailer', scope='category', match_pattern='Politisch',
            template='trailer', theme={'accent': '#FFD400'}, priority=10)
        data = CoverData(title='Demo', category='Politisch orientiert', number=7)
        template, theme = resolve_template(data, self.config)
        self.assertIsInstance(template, TrailerCover)
        self.assertEqual(theme, {'accent': '#FFD400'})

    def test_db_rule_priority(self):
        from media_files.models import CoverTemplate
        CoverTemplate.objects.create(
            name='low', scope='category', match_pattern='Heimat',
            template='trailer', priority=50)
        CoverTemplate.objects.create(
            name='high', scope='category', match_pattern='Heimat',
            template='journal', priority=10)
        data = CoverData(title='Doku', category='Heimatdoku', number=9)
        template, _ = resolve_template(data, self.config)
        self.assertIsInstance(template, JournalCover)

    def test_inactive_rule_ignored(self):
        from media_files.models import CoverTemplate
        CoverTemplate.objects.create(
            name='off', scope='category', match_pattern='Heimat',
            template='trailer', priority=1, is_active=False)
        data = CoverData(title='Doku', category='Heimatdoku', number=11)
        template, _ = resolve_template(data, self.config)
        self.assertIsInstance(template, BaseCover)

    def test_invalid_regex_is_skipped(self):
        from media_files.models import CoverTemplate
        CoverTemplate.objects.create(
            name='bad', scope='category', match_pattern='[unclosed',
            template='trailer', priority=1)
        data = CoverData(title='Doku', category='Heimatdoku', number=13)
        template, _ = resolve_template(data, self.config)
        self.assertIsInstance(template, BaseCover)


class OverlayRuleTest(TestCase):
    """Overlay-pool rule matching and pool listing."""

    def test_rule_matches_title_and_lists_pool(self):
        import tempfile
        from PIL import Image
        from media_files.models import CoverOverlay, CoverOverlayRule
        from media_files.covers.resolver import resolve_overlay_rule, overlays_for_rule

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(tmp.name)
            CoverOverlay.objects.create(name='A', pool='podcast', image=tmp.name)
        rule = CoverOverlayRule.objects.create(
            name='Podcasts', scope='series', match_pattern='Podcast',
            pool='podcast', selection_mode='all', priority=5)

        match = resolve_overlay_rule(CoverData(title='Mein Podcast', number=1))
        self.assertEqual(match.pk, rule.pk)
        self.assertEqual(match.selection_mode, 'all')
        self.assertEqual(len(overlays_for_rule(rule)), 1)

    def test_explicit_overlays_override_pool(self):
        import tempfile
        from PIL import Image
        from media_files.models import CoverOverlay, CoverOverlayRule
        from media_files.covers.resolver import overlays_for_rule

        def mk(name, pool):
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(tmp.name)
                return CoverOverlay.objects.create(name=name, pool=pool, image=tmp.name)

        a, b, c = mk('A', 'big'), mk('B', 'big'), mk('C', 'big')
        rule = CoverOverlayRule.objects.create(
            name='Subset', scope='channel', pool='big', selection_mode='all')
        rule.overlays.set([a, c])  # explicit subset

        chosen = overlays_for_rule(rule)
        self.assertEqual({o.pk for o in chosen}, {a.pk, c.pk})

    def test_no_match_returns_none(self):
        from media_files.covers.resolver import resolve_overlay_rule
        self.assertIsNone(resolve_overlay_rule(CoverData(title='Nichts', number=1)))


class GetCoverConfigTest(TestCase):
    """Loading CoverConfig from the MediaFilesConfig singleton."""

    def test_reflects_singleton_fields(self):
        from media_files.models import MediaFilesConfig
        cfg = MediaFilesConfig.get_config()
        cfg.cover_enabled = True
        cfg.cover_output_dir = '/tmp/covers-test'
        cfg.cover_category_colors = {'Foo': '#010203'}
        cfg.cover_template_rules = {'Foo': 'journal'}
        cfg.save()

        resolved = get_cover_config()
        self.assertTrue(resolved.enabled)
        self.assertEqual(resolved.output_dir, '/tmp/covers-test')
        self.assertEqual(resolved.accent_for_category('Foo'), '#010203')
        self.assertEqual(resolved.template_for_category('Foo'), 'journal')

    def test_output_dir_from_storage_with_subdir(self):
        from media_files.models import MediaFilesConfig, StorageLocation
        storage = StorageLocation.objects.create(
            name='Cover Store', storage_type='CUSTOM', path='/mnt/store')
        cfg = MediaFilesConfig.get_config()
        cfg.cover_output_storage = storage
        cfg.cover_output_subdir = 'covers'
        cfg.cover_output_dir = '/should/be/ignored'
        cfg.save()

        # Storage selection wins over the manual path.
        self.assertEqual(get_cover_config().output_dir, '/mnt/store/covers')
