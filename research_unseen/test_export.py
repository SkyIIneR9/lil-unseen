"""End-to-end export against independently invented Ren'Py-shaped records."""
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zlib

from localization import ui_text, translate_annotation
from unseen_runtime import Navigator


def fixture_bytes():
    ast = types.ModuleType('renpy.ast')
    persistent_module = types.ModuleType('renpy.persistent')
    renpy = types.ModuleType('renpy')
    renpy.ast, renpy.persistent = ast, persistent_module
    for kind in ('Define', 'PyCode', 'Label', 'Scene', 'TranslateSay'):
        setattr(ast, kind, type(kind, (), {'__module__': ast.__name__}))
    persistent_module.Persistent = type('Persistent', (), {'__module__': persistent_module.__name__})

    def obj(kind, **attrs):
        instance = getattr(ast, kind)()
        instance.__dict__.update(attrs)
        return instance

    options = [obj('Define', varname='version', code=obj('PyCode', source="'synthetic-test'"))]
    scene = obj('Scene', name=('sample', 1), filename='game/sample.rpy', linenumber=2, layer='master')
    rows = [obj('TranslateSay', identifier='sample_%d' % i, name=('sample', i + 2), language=None,
                filename='game/sample.rpy', linenumber=i + 3, who=None,
                what='Invented line %d </script><p>literal text</p>' % i) for i in range(3)]
    story = [obj('Label', name='sample', block=[scene] + rows)]
    persistent = persistent_module.Persistent()
    persistent._seen_translates = {'sample_0'}
    persistent._seen_ever = {'sample': True}
    persistent._changed = {'_seen_translates': 1}
    with patch.dict(sys.modules, {'renpy': renpy, 'renpy.ast': ast, 'renpy.persistent': persistent_module}):
        return (zlib.compress(pickle.dumps(({}, options))),
                zlib.compress(pickle.dumps(({}, story))),
                zlib.compress(pickle.dumps(persistent)))


class ExportTests(unittest.TestCase):
    def test_export_in_both_languages_preserves_inputs_and_escapes_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / 'game'
            (game / 'saves').mkdir(parents=True)
            options, story, persistent = fixture_bytes()
            (game / 'options.rpyc').write_bytes(options)
            (game / 'sample.rpyc').write_bytes(story)
            saved = game / 'saves/persistent'
            saved.write_bytes(persistent)
            exporter = Path(__file__).with_name('export_unseen.py')
            for language in ('en', 'ru'):
                out = root / language
                result = subprocess.run([sys.executable, '-X', 'utf8', str(exporter), '--root', str(root),
                                         '--output', str(out), '--ui-language', language],
                                        capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = json.loads((out / 'unseen.json').read_text(encoding='utf-8'))
                self.assertEqual([r['id'] for r in rows], ['sample_1', 'sample_2'])
                self.assertEqual(rows[0]['fragment_size'], 2)
                index = json.loads((out / 'navigation.json').read_text(encoding='utf-8'))
                self.assertEqual(index['ui_language'], language)
                self.assertEqual(len(index['fragments']), 1)
                html = (out / 'unseen.html').read_text(encoding='utf-8')
                self.assertIn('lang="%s"' % language, html)
                self.assertNotIn('</script><p>literal text', html)
                self.assertNotIn('__REPORT_DATA__', html)
                self.assertEqual(saved.read_bytes(), persistent)

    def test_missing_game_root_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('export_unseen.py')),
                                     '--root', directory], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Game folder not found', result.stderr)

    def test_panel_language_defaults_and_selection(self):
        nav = Navigator(None)
        self.assertEqual(nav.text('next'), 'Next fragment')
        nav.index = {'ui_language': 'ru'}
        self.assertEqual(nav.text('next'), 'Следующий фрагмент')
        self.assertEqual(translate_annotation('Выбор: sample [доступен при flag]', 'en'),
                         'Choice: sample [available when flag]')


if __name__ == '__main__':
    unittest.main()
