"""In-game adapter. Importing this module does not import or start Ren'Py."""
import json
import os
import posixpath
from localization import ui_text


def frozen(value):
    return tuple(frozen(v) for v in value) if isinstance(value, list) else value


class Navigator:
    def __init__(self, engine):
        self.engine = engine
        self.index = None
        self.signature = None
        self.current = None
        self.last_errors = []

    def load(self):
        path = os.path.join(self.engine.config.basedir, 'research_unseen', 'output', 'navigation.json')
        try:
            stat = os.stat(path)
        except OSError:
            raise RuntimeError('No navigation report. Close the game and run research_unseen/refresh_report.cmd.')
        signature = (stat.st_mtime_ns, stat.st_size)
        if signature != self.signature:
            with open(path, 'r', encoding='utf-8') as stream:
                index = json.load(stream)
            if index.get('version') != 1:
                raise RuntimeError('Unsupported navigation report version.')
            self.index, self.signature = index, signature
        return self.index

    def checked_node(self, record):
        node = self.engine.game.script.lookup(frozen(record['name']))
        expected = (record['kind'], self.filename_key(record['file']), record['line'])
        actual = (type(node).__name__, self.filename_key(node.filename), node.linenumber)
        if actual != expected:
            raise RuntimeError('Navigation report mismatch: expected %r at %s:%s, loaded %r at %s:%s. '
                               'Close the game and refresh the report.' % (
                                   record['kind'], record['file'], record['line'],
                                   type(node).__name__, node.filename, node.linenumber))
        return node

    def text(self, key):
        return ui_text(key, (self.index or {}).get('ui_language', 'en'))

    def filename_key(self, filename):
        # Script.finish_load rewrites archived node.filename from
        # game/Foo.rpy to Foo.rpyc. The node's stable name stays unchanged.
        value = posixpath.normpath(str(filename).replace('\\', '/')).casefold()
        basedir = getattr(self.engine.config, 'basedir', None)
        if basedir:
            base = posixpath.normpath(str(basedir).replace('\\', '/')).casefold().rstrip('/') + '/'
            if value.startswith(base):
                value = value[len(base):]
        if value.startswith('game/'):
            value = value[len('game/'):]
        if value.endswith(('.rpyc', '.rpymc')):
            value = value[:-1]
        return value

    def plan(self, identifier):
        index = self.load()
        if identifier not in index['entries']:
            raise RuntimeError('Dialogue ID is absent from navigation.json. Refresh the report.')
        entry = index['entries'][identifier]
        target = self.engine.game.script.translator.default_translates.get(identifier)
        if target is None or self.checked_node(entry['target']) is not target:
            raise RuntimeError('Dialogue no longer matches this report. Refresh the report.')
        visual, audio = [], []
        for record in entry['visual']:
            node = self.checked_node(record)
            if type(node).__name__ not in ('Scene', 'Show', 'Hide'):
                raise RuntimeError('Unsupported visual command in navigation report.')
            visual.append(node)
        for record in entry['audio']:
            node = self.checked_node(record)
            parsed = getattr(node, 'parsed', None)
            if type(node).__name__ != 'UserStatement' or not parsed or parsed[0][0] not in ('play', 'stop', 'queue'):
                raise RuntimeError('Unsupported audio command in navigation report.')
            # Check the live channel, not only the report's claimed channel.
            from navigation import audio_channel
            if audio_channel(node) != record['channel']:
                raise RuntimeError('Audio channel changed. Refresh the report.')
            audio.append(node)
        return entry, target, visual, audio

    def jump(self, identifier, from_console=True):
        renpy = self.engine
        if not renpy.game.context().rollback:
            raise RuntimeError('Load a save and use the navigator during normal dialogue.')
        if from_console:
            console = getattr(getattr(renpy.store, '_console', None), 'console', None)
            if console is None or not console.can_renpy():
                raise RuntimeError('Open the console during normal dialogue.')
        # Resolve and check every referenced node before changing presentation/stack.
        entry, target, visual, audio = self.plan(identifier)
        context = renpy.game.context()
        old_next = context.next_node
        errors = []
        renpy.config.skipping = None
        try:
            # Avoid carrying audio from the unrelated source scene. One-shot
            # sound effects and voices are not replayed out of their timeline.
            channels = {'music', 'sound', 'voice'}
            channels.update(r['channel'] for r in entry['audio'])
            for channel in channels:
                try:
                    renpy.music.stop(channel=channel, fadeout=0)
                except Exception as error:
                    errors.append('stop audio: ' + str(error))
            if not entry['visual_known']:
                # Unknown does not mean the old scene was correct: use a blank
                # master layer and clearly report the missing visual context.
                renpy.scene(layer='master')
            for node in visual:
                try:
                    node.execute()
                except Exception as error:
                    errors.append('%s:%s: %s' % (node.filename, node.linenumber, error))
            for node in audio:
                try:
                    node.call('execute')
                except Exception as error:
                    errors.append('%s:%s: %s' % (node.filename, node.linenumber, error))
        finally:
            context.next_node = old_next
        self.current = identifier
        self.last_errors = errors
        renpy.show_screen('unseen_research_controls')
        warnings = []
        if not entry['visual_known']:
            warnings.append(self.text('visual'))
        if not entry['music_known']:
            warnings.append(self.text('music'))
        if errors:
            warnings.append(self.text('errors'))
            for error in errors:
                print('Unseen navigator: ' + error)
        if warnings:
            renpy.notify(' · '.join(warnings))
        if from_console:
            renpy.pop_call()
        renpy.jump(target.name)

    def next(self, direction=1):
        index = self.load()
        fragments = index['fragments']
        current = next((i for i, f in enumerate(fragments) if self.current in f['ids']), -1)
        positions = range(current + 1, len(fragments)) if direction >= 0 else range(current - 1, -1, -1)
        seen = self.engine.game.persistent._seen_translates
        for position in positions:
            fragment = fragments[position]
            if fragment['bonus_off']:
                continue
            pending = [identifier for identifier in fragment['ids'] if identifier not in seen]
            if direction < 0:
                pending = fragment['ids'][:1]
            if pending:
                return self.jump(pending[0], from_console=False)
        self.engine.notify(self.text('end'))


_navigator = None


def navigator():
    global _navigator
    if _navigator is None:
        import renpy
        _navigator = Navigator(renpy.exports)
    return _navigator


def jump(identifier):
    return navigator().jump(identifier, from_console=True)


def next_fragment(direction=1):
    return navigator().next(direction)
