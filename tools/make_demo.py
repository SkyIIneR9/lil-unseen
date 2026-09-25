"""Render an invented report for UI checks; never reads game data."""
from pathlib import Path
import json

root = Path(__file__).resolve().parent.parent
data = json.loads((root / 'tests/fixtures/report.json').read_text(encoding='utf-8'))
destination = root / '.verification'
destination.mkdir(exist_ok=True)
for language, template in [('en', 'viewer_en.html'), ('ru', 'viewer.html')]:
    data['stats']['ui_language'] = language
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    html = (root / 'research_unseen' / template).read_text(encoding='utf-8').replace('__REPORT_DATA__', payload)
    (destination / ('demo_' + language + '.html')).write_text(html, encoding='utf-8')
print(destination)
