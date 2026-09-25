import copy
import unittest
from types import SimpleNamespace as NS

from navigation import navigation_for, add_fragments
from unseen_runtime import Navigator


def node(kind, line_number, **attrs):
    obj = type(kind, (), {})()
    obj.__dict__.update(name=('test.rpy', 1, line_number), filename='game/test.rpy', linenumber=line_number, **attrs)
    return obj


def say(line):
    return node('TranslateSay', line, identifier='line_%d' % line, language=None)


class NavigationTests(unittest.TestCase):
    def test_branch_inherits_media_but_ambiguous_merge_does_not_guess(self):
        scene = node('Scene', 1, layer=None)
        music = node('UserStatement', 2, parsed=(('play', 'music'), {'channel': None}), line='play music "a.ogg"')
        yes, no, after = say(4), say(7), say(8)
        choice = node('If', 3, entries=[('flag', [yes]), ('True', [node('Scene', 6, layer=None), no])])
        result = navigation_for([scene, music, choice, after])
        self.assertEqual(result[yes.identifier]['visual'][0]['line'], 1)
        self.assertEqual(result[no.identifier]['visual'][0]['line'], 6)
        self.assertFalse(result[after.identifier]['visual_known'])
        self.assertTrue(result[after.identifier]['music_known'])

    def test_python_call_invalidates_prior_media(self):
        result = navigation_for([node('Scene', 1, layer=None),
                                 node('Python', 2, code=NS(source='change_scene()')), say(3)])
        self.assertFalse(result['line_3']['visual_known'])
        self.assertTrue(result['line_3']['notes'])

    def test_fragments_do_not_cross_read_lines_or_control_boundaries(self):
        rows = [dict(id=str(i), file='test', label='test', conditions='', bonus_off=False,
                     status='partial', navigation={'run': run, 'position': position})
                for i, (run, position) in enumerate([(1, 0), (1, 1), (1, 3), (2, 0)])]
        fragments = add_fragments(rows)
        self.assertEqual([len(f['ids']) for f in fragments], [2, 1, 1])

    def engine(self):
        events = []
        scene, target = node('Scene', 1, layer=None), say(2)
        context = NS(rollback=True, next_node='original')
        def execute():
            events.append('scene')
            context.next_node = 'changed'
        scene.execute = execute
        class Signal(Exception):
            pass
        def jump(name):
            events.append(('jump', name))
            raise Signal()
        nodes = {scene.name: scene, target.name: target}
        script = NS(lookup=lambda name: nodes[name], translator=NS(default_translates={target.identifier: target}))
        engine = NS(game=NS(script=script, context=lambda: context, persistent=NS(_seen_translates=set())),
                    config=NS(skipping='fast'), store=NS(_console=NS(console=NS(can_renpy=lambda: True))),
                    music=NS(stop=lambda **kw: events.append('stop')), scene=lambda **kw: events.append('blank'),
                    show_screen=lambda name: events.append('panel'), notify=lambda msg: events.append('notice'),
                    pop_call=lambda: events.append('pop'), jump=jump, log=lambda message: events.append('log'))
        nav = Navigator(engine)
        entries = navigation_for([scene, target])
        index = {'entries': entries, 'fragments': [{'id': target.identifier, 'ids': [target.identifier], 'bonus_off': False}]}
        nav.load = lambda: index
        return nav, index, events, context, Signal

    def test_prepared_jump_restores_media_and_next_pointer_before_jump(self):
        nav, index, events, context, Signal = self.engine()
        with self.assertRaises(Signal):
            nav.jump('line_2')
        self.assertIn('scene', events)
        self.assertEqual(context.next_node, 'original')
        self.assertEqual(events.count('pop'), 1)
        self.assertEqual(events[-1][0], 'jump')

    def test_stale_media_plan_does_not_change_presentation_or_stack(self):
        nav, index, events, context, Signal = self.engine()
        index['entries']['line_2']['visual'][0]['line'] = 999
        with self.assertRaises(RuntimeError):
            nav.jump('line_2')
        self.assertEqual(events, [])
        self.assertEqual(context.next_node, 'original')

    def test_archive_filename_rewrite_is_not_a_stale_report(self):
        nav, index, events, context, Signal = self.engine()
        entry = index['entries']['line_2']
        for record in [entry['target']] + entry['visual']:
            live = nav.engine.game.script.lookup(record['name'])
            live.filename = 'test.rpyc'
        with self.assertRaises(Signal):
            nav.jump('line_2')
        self.assertIn('scene', events)
        self.assertEqual(events[-1][0], 'jump')

    def test_paths_keep_subdirectories_and_normalize_known_game_root(self):
        nav, *_ = self.engine()
        nav.engine.config.basedir = 'C:/Games/LiL'
        expected = nav.filename_key('game/scripts/Scene.rpy')
        self.assertEqual(nav.filename_key('scripts/Scene.rpyc'), expected)
        self.assertEqual(nav.filename_key('C:\\Games\\LiL\\game\\scripts\\Scene.rpyc'), expected)
        self.assertNotEqual(nav.filename_key('other/Scene.rpyc'), expected)

    def test_different_file_is_still_rejected_without_side_effects(self):
        nav, index, events, context, Signal = self.engine()
        record = index['entries']['line_2']['target']
        live = nav.engine.game.script.lookup(record['name'])
        live.filename = 'other/test.rpyc'
        with self.assertRaisesRegex(RuntimeError, 'expected.*loaded'):
            nav.jump('line_2')
        self.assertEqual(events, [])

    def test_next_skips_completed_fragments_using_live_persistent(self):
        nav, index, events, context, Signal = self.engine()
        index['fragments'] = [dict(id='a', ids=['a'], bonus_off=False),
                              dict(id='b', ids=['b'], bonus_off=False),
                              dict(id='c', ids=['c', 'd'], bonus_off=False)]
        nav.current = 'a'
        nav.engine.game.persistent._seen_translates = {'a', 'b', 'c'}
        nav.jump = lambda identifier, from_console: events.append((identifier, from_console))
        nav.next()
        self.assertEqual(events, [('d', False)])


if __name__ == '__main__':
    unittest.main()
