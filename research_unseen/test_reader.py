import pickle
import struct
import unittest
import zlib

from export_unseen import dialogue_nodes
from renpy_reader import Record, loads, rpyc_load


def node(kind, **attrs):
    result = type(kind, (Record,), {})()
    result.__dict__.update(attrs)
    return result


class ExtractionTests(unittest.TestCase):
    def test_nested_choices_and_else_keep_label_and_guards(self):
        first = node('TranslateSay', identifier='scene_a', language=None)
        second = node('TranslateSay', identifier='scene_b', language=None)
        branch = node('If', entries=[('flag', [first]), ('other', []), ('True', [
            node('Menu', items=[('Choice', 'available', [second])])])])
        root = node('Label', name='scene', block=[branch])
        result = list(dialogue_nodes([root]))
        self.assertEqual([n.identifier for n, _, _ in result], ['scene_a', 'scene_b'])
        self.assertEqual([label for _, label, _ in result], ['scene', 'scene'])
        self.assertEqual(result[1][2], ('not (flag) and not (other)', 'Выбор: Choice [доступен при available]'))

    def test_translations_are_not_counted_twice(self):
        original = node('TranslateSay', identifier='same', language=None)
        translated = node('TranslateSay', identifier='same', language='russian')
        self.assertEqual(len(list(dialogue_nodes([original, translated]))), 1)

    def test_reader_rejects_executable_global(self):
        with self.assertRaises(pickle.UnpicklingError):
            loads(b'cos\nsystem\n.')

    def test_game_global_is_an_inert_record(self):
        cls = loads(b'crenpy.ast\nPython\n.')
        self.assertTrue(issubclass(cls, Record))
        self.assertEqual(cls.__name__, 'Python')

    def test_rpyc_prefers_compiled_translations_in_slot_two(self):
        one = zlib.compress(pickle.dumps({'slot': 1}))
        two = zlib.compress(pickle.dumps({'slot': 2}))
        data = b'RENPY RPC2' + struct.pack('<III', 1, 46, len(one))
        data += struct.pack('<III', 2, 46 + len(one), len(two)) + bytes(12) + one + two
        self.assertEqual(rpyc_load(data), {'slot': 2})
        self.assertEqual(rpyc_load(data, slot=1), {'slot': 1})


if __name__ == '__main__':
    unittest.main()
