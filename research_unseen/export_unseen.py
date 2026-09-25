"""Offline, read-only dialogue coverage report for this Ren'Py installation.

Usage: python research_unseen/export_unseen.py
Reads current archives and persistent; writes only under research_unseen/output.
No game scripts, pickle globals, conditions or character expressions are executed.
"""
import argparse
import ast
import collections
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import zlib

from renpy_reader import Archive, PyCode, Record, loads, rpyc_load, walk_objects
from navigation import navigation_for, add_fragments
from localization import translate_annotation
from event_order import tracker_events, event_queues


def script_sources(root):
    # Ren'Py scans sorted archive names and then reverses them; loose files win.
    sources = {}
    for path in sorted((root / 'game').glob('*.rpa'), reverse=True):
        archive = Archive(path)
        for name in archive.index:
            if name.endswith('.rpyc'):
                sources.setdefault(name, (str(path.name), lambda a=archive, n=name: a.read(n)))
    for path in sorted((root / 'game').rglob('*.rpyc')):
        name = path.relative_to(root / 'game').as_posix()
        sources[name] = (str(path.relative_to(root)), path.read_bytes)
    return sources


def dialogue_nodes(nodes, label='', conditions=()):
    """Walk syntactic child blocks (never control-flow next pointers)."""
    for node in nodes:
        kind = type(node).__name__
        if kind == 'Label':
            label = str(node.name)
            yield from dialogue_nodes(node.block, label, conditions)
        elif kind in ('TranslateSay', 'Translate'):
            if getattr(node, 'language', None) is None:
                yield node, label, conditions
        elif kind == 'If':
            previous = []
            for expression, block in node.entries:
                expression = str(expression)
                guards = ['not (' + p + ')' for p in previous]
                if expression != 'True':
                    guards.append('(' + expression + ')')
                condition = ' and '.join(guards) or 'True'
                yield from dialogue_nodes(block, label, conditions + (condition,))
                previous.append(expression)
        elif kind == 'Menu':
            for caption, expression, block in node.items:
                if block is not None:
                    choice = 'Выбор: ' + str(caption)
                    if str(expression) != 'True':
                        choice += ' [доступен при ' + str(expression) + ']'
                    yield from dialogue_nodes(block, label, conditions + (choice,))
        elif kind == 'While':
            yield from dialogue_nodes(node.block, label, conditions + ('while ' + str(node.condition),))
        elif kind in ('Init', 'TranslateBlock', 'TranslateEarlyBlock'):
            yield from dialogue_nodes(node.block, label, conditions)
        elif kind == 'UserStatement':
            for block in getattr(node, 'blocks', []) or []:
                if isinstance(block, list):
                    yield from dialogue_nodes(block, label, conditions + ('Вложенный пользовательский оператор',))


def say_nodes(node):
    if type(node).__name__ in ('TranslateSay', 'Say'):
        return [node]
    return [n for n in getattr(node, 'block', []) if type(n).__name__ in ('Say', 'TranslateSay')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--persistent', type=Path, help='Use exactly this persistent snapshot')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'output')
    parser.add_argument('--ui-language', choices=('en', 'ru'), default='en', help='Report and in-game panel language (does not translate game dialogue)')
    args = parser.parse_args()
    args.root = args.root.resolve()
    if not (args.root / 'game').is_dir():
        parser.error('Game folder not found. Copy game/ and research_unseen/ beside the game executable, or pass --root PATH.')
    sources = script_sources(args.root)
    for path in (args.root / 'game').rglob('*.rpy'):
        compiled = path.with_suffix('.rpyc')
        if not compiled.exists() or path.stat().st_mtime > compiled.stat().st_mtime:
            raise RuntimeError('Source is newer than compiled data: %s. Run the game normally to compile it, then rerun the report.' % path)
    if 'options.rpyc' not in sources:
        parser.error('options.rpyc not found. Start and close the game once, or check --root.')
    options = rpyc_load(sources['options.rpyc'][1]())[1]
    config = {}
    for node in walk_objects(options):
        if type(node).__name__ == 'Define' and node.varname in ('save_directory', 'version'):
            config[node.varname] = ast.literal_eval(node.code.source)

    candidates = [args.root / 'game' / 'saves' / 'persistent']
    if os.environ.get('APPDATA') and config.get('save_directory'):
        candidates.append(Path(os.environ['APPDATA']) / 'RenPy' / config['save_directory'] / 'persistent')
    if args.persistent:
        candidates = [args.persistent]
    snapshots = []
    for path in candidates:
        if path.exists():
            raw = path.read_bytes()
            persistent = loads(zlib.decompress(raw))
            snapshots.append((path, raw, persistent))
    if not snapshots:
        raise RuntimeError('No persistent found. Pass --persistent PATH.')
    # This engine chooses _seen_translates by its per-field change timestamp.
    # _seen_ever uses dictionary union. Do not union old dialogue sets silently.
    selected = max(snapshots, key=lambda item: getattr(item[2], '_changed', {}).get('_seen_translates', 0))
    seen = set(getattr(selected[2], '_seen_translates', set()))
    seen_ever = {}
    for _, _, persistent in snapshots:
        seen_ever.update(getattr(persistent, '_seen_ever', {}))
    language = getattr(getattr(selected[2], '_preferences', None), 'language', None)
    if language is not None:
        raise RuntimeError('This report reads the patched original-language script. Active translation language is %r; translation mapping must be added first.' % language)

    rows, identifiers, unsupported, duplicate_ids, manifests = [], set(), [], [], []
    trackers = {}
    missing_say_names = 0
    for name, (origin, read) in sorted(sources.items()):
        raw = read()
        _, nodes = rpyc_load(raw)
        # Read the game's gallery, not similarly named mod tracker screens.
        if name == 'screens.rpyc':
            trackers = tracker_events(nodes)
        navigation = navigation_for(nodes)
        objects = list(walk_objects(nodes))
        all_translates = {id(n) for n in objects if type(n).__name__ in ('Translate', 'TranslateSay') and getattr(n, 'language', None) is None}
        walked = set()
        ordinary_says = [n for n in objects if type(n).__name__ == 'Say']
        if ordinary_says and not all_translates:
            unsupported.append({'file': name, 'reason': 'Say nodes without generated Translate nodes', 'count': len(ordinary_says)})
        for node, label, conditions in dialogue_nodes(nodes):
            walked.add(id(node))
            identifier = node.identifier
            if identifier in identifiers:
                duplicate_ids.append(identifier)
                continue
            identifiers.add(identifier)
            sayings = say_nodes(node)
            if not sayings:
                missing_say_names += 1
            statement_seen = any(getattr(s, 'name', None) in seen_ever for s in sayings)
            rows.append({
                'id': identifier, 'label': label, 'file': node.filename,
                'line': node.linenumber, 'seen': identifier in seen,
                'label_seen': label in seen_ever, 'statement_seen': statement_seen,
                'speaker': ' / '.join(str(s.who or ('Narrator' if args.ui_language == 'en' else 'Рассказчик')) for s in sayings),
                'text': '\n'.join(str(s.what) for s in sayings),
                'conditions': '\n'.join(conditions),
                'bonus_off': any(c in ('not (bonus == True)', '(bonus == False)') for c in conditions),
                'source': origin, 'mod': name.startswith(('0x52-URM/', 'progress mod/', 'mods/')),
                'navigation': navigation[node.identifier],
            })
        if all_translates - walked:
            unsupported.append({'file': name, 'reason': 'Unvisited Translate nodes', 'count': len(all_translates - walked)})
        manifests.append({'name': name, 'source': origin, 'sha256': hashlib.sha256(raw).hexdigest(), 'blocks': len(walked)})
        print('%s: %d blocks' % (name, len(walked)), flush=True)
    if unsupported or duplicate_ids:
        raise RuntimeError('Incomplete/ambiguous extraction: ' + repr((unsupported, duplicate_ids[:20])))

    for row in rows:
        row['conditions'] = translate_annotation(row['conditions'], args.ui_language)
        row['navigation']['notes'] = [translate_annotation(note, args.ui_language) for note in row['navigation']['notes']]

    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row['file'], row['label']].append(row)
    summaries, unseen = [], []
    for (filename, label), group in sorted(grouped.items()):
        group.sort(key=lambda r: r['line'])
        read_count = sum(r['seen'] for r in group)
        status = 'partial' if 0 < read_count < len(group) else 'unseen' if read_count == 0 else 'complete'
        summary = {'file': filename, 'label': label, 'total': len(group), 'seen': read_count,
                   'unseen': len(group) - read_count, 'status': status,
                   'label_seen': any(r['label_seen'] for r in group), 'mod': all(r['mod'] for r in group)}
        summaries.append(summary)
        for index, row in enumerate(group):
            if not row['seen']:
                item = dict(row, status=status)
                for direction, position in [('before', index - 1), ('after', index + 1)]:
                    if 0 <= position < len(group):
                        neighbor = group[position]
                        item[direction] = {key: neighbor[key] for key in ('speaker', 'text', 'line', 'seen', 'conditions')}
                    else:
                        item[direction] = None
                unseen.append(item)
    fragments = add_fragments(unseen)
    queues = event_queues(fragments, {r['id']: r['navigation'] for r in unseen}, trackers)
    game_rows = [r for r in rows if not r['mod']]
    stats = {
        'generated': datetime.datetime.now().astimezone().isoformat(),
        'script_version': config.get('version'), 'language': language, 'ui_language': args.ui_language,
        'total_blocks': len(rows), 'seen_blocks': sum(r['seen'] for r in rows),
        'unseen_blocks': len(unseen), 'game_blocks': len(game_rows),
        'game_seen': sum(r['seen'] for r in game_rows),
        'game_unseen': sum(not r['seen'] for r in game_rows),
        'partial_labels': sum(s['status'] == 'partial' and not s['mod'] for s in summaries),
        'unseen_in_partial_labels': sum(r['status'] == 'partial' and not r['mod'] for r in unseen),
        'unseen_in_visited_labels': sum(r['label_seen'] and not r['mod'] for r in unseen),
        'unseen_bonus_off': sum(r['bonus_off'] for r in unseen),
        'unseen_other_branches': sum(not r['bonus_off'] for r in unseen),
        'partial_unseen_other_branches': sum(r['status'] == 'partial' and not r['bonus_off'] for r in unseen),
        'unmatched_persistent_ids': len(seen - identifiers),
        'unseen_but_statement_seen': sum(r['statement_seen'] for r in unseen),
        'blocks_without_say': missing_say_names,
        'fragments': len(fragments),
        'gallery_queues': sum(q['kind'] == 'gallery' for q in queues),
        'fragments_other_branches': sum(not f['bonus_off'] for f in fragments),
        'visual_prepared_other_branches': sum(r['navigation']['visual_known'] and not r['bonus_off'] for r in unseen),
        'music_prepared_other_branches': sum(r['navigation']['music_known'] and not r['bonus_off'] for r in unseen),
        'persistent_sources': [{'path': str(p), 'sha256': hashlib.sha256(raw).hexdigest(),
                                'seen_ids': len(getattr(data, '_seen_translates', set()))}
                               for p, raw, data in snapshots],
        'selected_persistent': str(selected[0]),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'summary.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'manifest.json').write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'unseen.json').write_text(json.dumps(unseen, ensure_ascii=False), encoding='utf-8')
    navigation_data = {'version': 1, 'ui_language': args.ui_language, 'generated': stats['generated'], 'fragments': fragments,
                       'queues': queues,
                       'entries': {r['id']: r['navigation'] for r in unseen}}
    (args.output / 'navigation.json').write_text(json.dumps(navigation_data, ensure_ascii=False), encoding='utf-8')
    write_tsv(args.output / 'labels.tsv', summaries, ['file', 'label', 'total', 'seen', 'unseen', 'status', 'label_seen', 'mod'])
    write_tsv(args.output / 'unseen.tsv', unseen, ['file', 'line', 'label', 'id', 'speaker', 'text', 'conditions', 'status', 'label_seen', 'statement_seen', 'bonus_off', 'mod'])
    template_name = 'viewer_en.html' if args.ui_language == 'en' else 'viewer.html'
    template = (Path(__file__).parent / template_name).read_text(encoding='utf-8')
    payload = json.dumps({'stats': stats, 'rows': unseen}, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    (args.output / 'unseen.html').write_text(template.replace('__REPORT_DATA__', payload), encoding='utf-8')
    # Verify the inputs remain byte-for-byte unchanged.
    for path, original, _ in snapshots:
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            raise RuntimeError('Persistent changed during export; close the game and rerun.')
    print(json.dumps(stats, ensure_ascii=True, indent=2))


def write_tsv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
