import unittest
from types import SimpleNamespace as NS

from event_order import tracker_events, event_queues
from renpy_reader import Record
from unseen_runtime import Navigator


def record(kind, **attrs):
    obj = type(kind, (Record,), {})()
    obj.__dict__.update(attrs)
    return obj


class EventOrderTests(unittest.TestCase):
    def test_tracker_uses_source_order_and_literal_replay_without_duplicates(self):
        def button(line, action):
            return record('SLDisplayable', location=('screens.rpy', line), keyword=[('action', action)])
        screen = record('SLScreen', name='exampletracker', keyword=[], children=[
            button(50, 'Replay("visit20")'), button(10, 'Replay("visit5")'),
            button(20, 'Replay("visit5")'), button(30, 'Replay(dynamic_label)'),
            button(40, 'dangerous_function()')])
        self.assertEqual(tracker_events([screen]), {'exampletracker': ['visit5', 'visit20']})

    def fixture(self):
        # Alphabetical/file order intentionally disagrees with gallery order.
        specs = [('b', 'visit20', 'a.rpy', 30), ('a2', 'visit5', 'z.rpy', 90),
                 ('c', 'other_person', 'a.rpy', 40), ('a1', 'visit5', 'z.rpy', 10),
                 ('u2', 'unmapped10', 'a.rpy', 5), ('u1', 'unmapped5', 'a.rpy', 1)]
        fragments = [dict(id=i, ids=[i], label=label, file=file, bonus_off=False) for i,label,file,line in specs]
        entries = {i: {'target': {'line': line}} for i,label,file,line in specs}
        queues = event_queues(fragments, entries, {'exampletracker': ['visit5','visit20'],
                                                 'othertracker': ['other_person']})
        return dict(fragments=fragments, entries=entries, queues=queues)

    def test_same_event_then_same_character_across_files(self):
        queues = self.fixture()['queues']
        self.assertEqual(queues[0]['fragments'], ['a1','a2','b'])
        self.assertEqual(queues[1]['fragments'], ['c'])
        self.assertEqual(queues[2]['fragments'], ['u1','u2'])

    def navigator(self):
        index = self.fixture()
        messages, jumps = [], []
        engine = NS(game=NS(persistent=NS(_seen_translates=set())), notify=messages.append,
                    restart_interaction=lambda: None)
        nav = Navigator(engine)
        nav.index = index
        nav.load = lambda: index
        nav.jump = lambda identifier, from_console: jumps.append(identifier)
        return nav, messages, jumps

    def test_next_stays_in_event_then_moves_to_next_gallery_event(self):
        nav, messages, jumps = self.navigator()
        nav.current = 'a1'
        nav.next()
        self.assertEqual(jumps, ['a2'])
        nav.current = 'a2'
        nav.next()
        self.assertEqual(jumps, ['a2','b'])
        nav.current = 'b'
        nav.next()
        self.assertEqual(jumps, ['a2','b'])
        self.assertTrue(messages)
        self.assertIn('3/3', nav.panel_status())

    def test_read_and_bonus_fragments_are_skipped(self):
        nav, _, jumps = self.navigator()
        nav.current = 'a1'
        nav.engine.game.persistent._seen_translates.add('a2')
        nav.next()
        self.assertEqual(jumps,['b'])
        nav.index['fragments'][0]['bonus_off'] = True
        nav.next()
        self.assertEqual(jumps,['b'])

    def test_previous_revisits_read_fragment_and_toggle_restores_legacy_list(self):
        nav, _, jumps = self.navigator()
        nav.current = 'b'
        nav.engine.game.persistent._seen_translates.add('a2')
        nav.next(-1)
        self.assertEqual(jumps,['a2'])
        nav.toggle_order()
        ordered, queue = nav.ordered_fragments(nav.index)
        self.assertIs(ordered,nav.index['fragments'])
        self.assertIsNone(queue)

    def test_shared_event_keeps_selected_gallery(self):
        nav, _, _ = self.navigator()
        nav.index['queues'].append(dict(id='sharedtracker', name='shared',kind='gallery',fragments=['a1','c']))
        nav.current, nav.queue_id = 'a1', 'sharedtracker'
        ordered, queue = nav.ordered_fragments(nav.index)
        self.assertEqual(queue['id'],'sharedtracker')
        self.assertEqual([f['id'] for f in ordered],['a1','c'])

    def test_old_reports_keep_working(self):
        nav, _, _ = self.navigator()
        del nav.index['queues']
        ordered, queue = nav.ordered_fragments(nav.index)
        self.assertIs(ordered,nav.index['fragments'])
        self.assertIsNone(queue)


if __name__ == '__main__':
    unittest.main()
