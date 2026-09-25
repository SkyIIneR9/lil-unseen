"""Build a source-only release from an explicit allowlist, never from a game tree."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.1.0'
FILES = (
    'README.md', 'README_RU.md', 'LICENSE', 'CONTRIBUTING.md', 'ROADMAP.md',
    '.gitignore', '.gitattributes', '.github/workflows/tests.yml',
    'game/0unseen_research.rpy',
    'research_unseen/export_unseen.py', 'research_unseen/renpy_reader.py',
    'research_unseen/navigation.py', 'research_unseen/unseen_runtime.py',
    'research_unseen/localization.py', 'research_unseen/viewer.html',
    'research_unseen/viewer_en.html', 'research_unseen/refresh_report.cmd',
    'research_unseen/test_reader.py', 'research_unseen/test_navigation.py',
    'research_unseen/test_export.py',
    'tests/verify_viewer.cjs', 'tests/fixtures/report.json',
    'tools/build_release.py', 'tools/make_demo.py',
)


def main():
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit('Missing release files: ' + ', '.join(missing))
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / ('lil-unseen-' + VERSION + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            bundle.write(ROOT / name, 'lil-unseen/' + name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print('Built %s (%d files)' % (archive, len(FILES)))


if __name__ == '__main__':
    main()
