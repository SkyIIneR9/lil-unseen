"""Read literal Replay targets from the game's own tracker screens.

No screen code or conditions are evaluated. Order is gallery source order,
not a claim about story chronology or event reachability.
"""
import ast
from collections import defaultdict

from renpy_reader import walk_objects


def tracker_events(nodes):
    result = {}
    for screen in walk_objects(nodes):
        name = str(getattr(screen, 'name', ''))
        if type(screen).__name__ != 'SLScreen' or not name.endswith('tracker'):
            continue
        candidates = []
        for node in walk_objects(screen):
            for key, value in getattr(node, 'keyword', []) or []:
                if key != 'action':
                    continue
                try:
                    expression = ast.parse(str(value), mode='eval')
                except SyntaxError:
                    continue
                for call in ast.walk(expression):
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                            and call.func.id == 'Replay' and call.args
                            and isinstance(call.args[0], ast.Constant)
                            and isinstance(call.args[0].value, str)):
                        location = getattr(node, 'location', ('', 0))
                        candidates.append((location[1], call.args[0].value))
        if candidates:
            result[name] = list(dict.fromkeys(label for _, label in sorted(candidates)))
    return result


def event_queues(fragments, entries, trackers):
    """Keep labels together, ordering known events across files by gallery rank.

    Shared events can belong to several queues. Unmapped labels have explicit
    file-based fallback queues; we do not guess a character from a substring.
    """
    by_label = defaultdict(list)
    for fragment in fragments:
        by_label[fragment['label']].append(fragment)

    def line(fragment):
        return entries[fragment['ids'][0]]['target']['line']

    queues, mapped = [], set()
    for name, labels in sorted(trackers.items(), key=lambda item: (item[0] in ('maintracker', 'secrettracker'), item[0])):
        ordered = []
        for label in labels:
            ordered.extend(sorted(by_label.get(label, []), key=lambda f: (f['file'], line(f))))
        if ordered:
            ids = [f['id'] for f in ordered]
            mapped.update(ids)
            queues.append({'id': name, 'kind': 'gallery', 'name': name[:-7], 'fragments': ids})

    fallback = defaultdict(list)
    for fragment in fragments:
        if fragment['id'] not in mapped:
            fallback[fragment['file']].append(fragment)
    for filename, group in sorted(fallback.items()):
        # Scene order comes from its first unread source line, not label spelling.
        first = {}
        for fragment in group:
            label = fragment['label']
            first[label] = min(first.get(label, line(fragment)), line(fragment))
        group.sort(key=lambda f: (first[f['label']], f['label'], line(f)))
        queues.append({'id': 'file:' + filename, 'kind': 'file', 'name': filename,
                       'fragments': [f['id'] for f in group]})
    return queues
