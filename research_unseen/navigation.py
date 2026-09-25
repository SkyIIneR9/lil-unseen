"""Conservative media reconstruction along structural script branches.

No condition is evaluated and no game Python is executed. At branch merges,
only media state identical on every incoming path is retained.
"""
import ast
import copy


def describe(node, **extra):
    return dict(name=node.name, kind=type(node).__name__, file=node.filename,
                line=node.linenumber, **extra)


def layer_of(node):
    if type(node).__name__ == 'Scene':
        return getattr(node, 'layer', None) or 'master'
    spec = getattr(node, 'imspec', None)
    if spec:
        return (spec[4] if len(spec) >= 6 else spec[2]) or 'master'
    return 'master'


def audio_channel(node):
    parsed = getattr(node, 'parsed', None)
    if not parsed or not isinstance(parsed, tuple) or len(parsed) != 2:
        return None
    words, params = parsed
    if not isinstance(params, dict) or not words or words[0] not in ('play', 'stop', 'queue'):
        return None
    channel = params.get('channel')
    if channel is not None:
        try:
            channel = ast.literal_eval(str(channel))
        except (ValueError, SyntaxError):
            return None
    elif len(words) == 2:
        channel = words[1]
    if not isinstance(channel, str):
        return None
    # One-shot sounds are deliberately not replayed out of their timeline.
    if channel in ('sound', 'voice', 'audio'):
        return None
    return channel


def blank_state():
    return {'visual': {}, 'audio': {}, 'notes': set()}


def merged(states):
    result = blank_state()
    for category in ('visual', 'audio'):
        keys = set().union(*(s[category] for s in states))
        for key in keys:
            values = [s[category].get(key) for s in states]
            if values[0] is not None and all(v == values[0] for v in values):
                result[category][key] = values[0]
    result['notes'] = set().union(*(s['notes'] for s in states))
    return result


def navigation_for(nodes):
    records = {}
    run_number = 0

    def walk(block, state=None):
        nonlocal run_number
        state = copy.deepcopy(state) if state is not None else blank_state()
        run_number += 1
        run, position = run_number, 0
        for node in block:
            kind = type(node).__name__
            if kind == 'Label':
                walk(node.block)
                state = blank_state()
            elif kind in ('TranslateSay', 'Translate'):
                if getattr(node, 'language', None) is not None:
                    continue
                media = []
                for commands in state['visual'].values():
                    media.extend(commands)
                audio = []
                for commands in state['audio'].values():
                    audio.extend(commands)
                records[node.identifier] = {
                    'target': describe(node), 'visual': media, 'audio': audio,
                    'visual_known': 'master' in state['visual'],
                    'music_known': 'music' in state['audio'],
                    'notes': sorted(state['notes']), 'run': run, 'position': position,
                }
                position += 1
            elif kind == 'Scene':
                state['visual'][layer_of(node)] = [describe(node)]
            elif kind in ('Show', 'Hide'):
                layer = layer_of(node)
                if layer in state['visual']:
                    state['visual'][layer].append(describe(node))
            elif kind in ('ShowLayer', 'Camera'):
                state['notes'].add('Изменение камеры/слоя не восстанавливается.')
            elif kind == 'If':
                outcomes = [walk(children, state) for condition, children in node.entries]
                if not any(str(condition) == 'True' for condition, _ in node.entries):
                    outcomes.append(state)
                state = merged(outcomes)
            elif kind == 'Menu':
                outcomes = [walk(children, state) for _, _, children in node.items if children is not None]
                state = merged(outcomes + [state])
            elif kind == 'While':
                walk(node.block, state)
                state = blank_state()
            elif kind in ('Call', 'Jump', 'Return'):
                state = blank_state()
            elif kind in ('Python', 'EarlyPython'):
                source = getattr(getattr(node, 'code', None), 'source', '')
                try:
                    tree = ast.parse(str(source).strip())
                    calls = any(isinstance(n, ast.Call) for n in ast.walk(tree))
                except SyntaxError:
                    calls = True
                if calls:
                    state = blank_state()
                    state['notes'].add('Перед репликой есть Python-вызов; его побочные эффекты не воспроизводятся.')
            elif kind == 'UserStatement':
                channel = audio_channel(node)
                if channel:
                    verb = node.parsed[0][0]
                    item = describe(node, channel=channel, verb=verb)
                    if verb in ('play', 'stop'):
                        state['audio'][channel] = [item]
                    elif channel in state['audio']:
                        state['audio'][channel].append(item)
                elif str(getattr(node, 'line', '')).startswith(('show screen ', 'hide screen ', 'call screen ')):
                    state['notes'].add('Пользовательские экраны сцены не восстанавливаются.')
            elif kind in ('Init', 'TranslateBlock', 'TranslateEarlyBlock'):
                walk(node.block)
            if kind in ('Label', 'If', 'Menu', 'While', 'Call', 'Jump', 'Return'):
                run_number += 1
                run, position = run_number, 0
        return state

    walk(nodes)
    return records


def add_fragments(rows):
    """Group only consecutive unseen dialogue nodes in one linear AST run."""
    fragments = []
    previous = None
    for row in rows:
        nav = row['navigation']
        same = previous is not None and (
            row['file'], row['label'], nav['run'], nav['position'], row['conditions']
        ) == (
            previous['file'], previous['label'], previous['navigation']['run'],
            previous['navigation']['position'] + 1, previous['conditions']
        )
        if not same:
            fragments.append({'id': row['id'], 'ids': [], 'label': row['label'],
                              'file': row['file'], 'bonus_off': row['bonus_off'],
                              'status': row['status']})
        fragment = fragments[-1]
        fragment['ids'].append(row['id'])
        row['fragment_id'] = fragment['id']
        previous = row
    sizes = {f['id']: len(f['ids']) for f in fragments}
    for row in rows:
        row['fragment_size'] = sizes[row['fragment_id']]
    return fragments
