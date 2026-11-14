"""Which manual chapters may be out of date? Runs on the host, needs git, not Django.

    python handbuch/aktualitaet.py            # commits after each chapter's stand
    python handbuch/aktualitaet.py --staged   # pre-commit: pages changed, chapter not
    python handbuch/aktualitaet.py --bump     # new version: confirm unchanged chapters

A chapter lists in ``handbuch/kapitel.py`` (``pfade``) the files of the pages it
describes. Without arguments the script prints, per chapter, the commits that
touched those files after the chapter's ``stand`` date and exits with 1 if
there are any. When the chapter is still right, raise its ``stand`` (and
``version``) after checking.

With ``--staged`` it compares the files staged for the next commit: when
described pages change but the chapter (``handbuch/inhalt/<slug>.md``) and
``handbuch/kapitel.py`` do not, it prints a reminder. It never blocks a commit.

``version`` of a chapter means "checked against this OK-Tools version"; the
manual notes chapters older than the installed version. ``--bump`` runs after
raising ``VERSION``: chapters whose pages have no commits after ``stand`` and
no uncommitted changes get the current version and today's date. The others
are listed and keep their values until someone has read them.

The registry is read with ``ast`` because importing it would start Django.
"""

from datetime import date
from datetime import timedelta
from pathlib import Path
import ast
import subprocess
import sys


REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / 'handbuch' / 'kapitel.py'
VERSION_FILE = REPO / 'ok_tools' / 'version.py'


def _value(node):
    """Literal value of a keyword argument; date(y, m, d) becomes a date."""
    if node is None:
        return None
    if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'date':
        return date(*(ast.literal_eval(arg) for arg in node.args))
    try:
        return ast.literal_eval(node)
    except ValueError:
        return None


def read_chapters(registry: Path = REGISTRY):
    """[{'slug', 'title', 'stand', 'pfade'}] of every Kapitel(...) in the registry."""
    tree = ast.parse(registry.read_text(encoding='utf-8'))
    chapters = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'Kapitel':
            values = {kw.arg: _value(kw.value) for kw in node.keywords}
            chapters.append({
                'slug': values.get('slug'),
                'title': values.get('title') or values.get('slug'),
                'stand': values.get('stand'),
                'pfade': tuple(values.get('pfade') or ()),
            })
    return chapters


def current_version(version_file: Path = VERSION_FILE) -> str:
    """VERSION from ok_tools/version.py, read without importing Django."""
    tree = ast.parse(version_file.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'VERSION' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f'No VERSION in {version_file}')


def bump_registry(text: str, slugs, version: str, today: date) -> str:
    """Registry source with ``version`` and ``stand`` replaced for ``slugs``."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def pos(lineno, col):
        # ast columns are UTF-8 byte offsets.
        return offsets[lineno - 1] + len(lines[lineno - 1].encode('utf-8')[:col].decode('utf-8'))

    new = {'version': repr(version), 'stand': f'date({today.year}, {today.month}, {today.day})'}
    edits = []
    for node in ast.walk(ast.parse(text)):
        if not (isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'Kapitel'):
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords}
        if _value(keywords.get('slug')) not in slugs:
            continue
        for name, replacement in new.items():
            value = keywords[name]
            edits.append((pos(value.lineno, value.col_offset),
                          pos(value.end_lineno, value.end_col_offset), replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def uncommitted_files():
    """Paths changed in the working tree or the index compared to HEAD."""
    return set(_git('diff', 'HEAD', '--name-only').splitlines())


def _git(*args):
    return subprocess.run(
        ['git', *args], cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout


def matches(path: str, pfade) -> bool:
    """Is the repository path one of the watched files or inside a watched folder?"""
    for entry in pfade:
        if entry.endswith('/'):
            if path.startswith(entry):
                return True
        elif path == entry:
            return True
    return False


def chapter_files(chapter):
    """Files whose change counts as updating the chapter."""
    return {f"handbuch/inhalt/{chapter['slug']}.md", 'handbuch/kapitel.py'}


def commits_since_stand(chapter):
    """['<hash> <date> <subject>'] touching the chapter's pages after its stand day."""
    if not chapter['pfade'] or not chapter['stand']:
        return []
    since = (chapter['stand'] + timedelta(days=1)).isoformat()
    out = _git('log', f'--since={since}T00:00', '--date=short',
               '--format=%h %ad %s', '--', *chapter['pfade'])
    return [line for line in out.splitlines() if line.strip()]


def staged_reminders(chapters, staged):
    """{title: [paths]} for chapters whose pages are staged without the chapter."""
    staged = set(staged)
    result = {}
    for chapter in chapters:
        touched = sorted(p for p in staged if matches(p, chapter['pfade']))
        if touched and not (chapter_files(chapter) & staged):
            result[chapter['title']] = touched
    return result


def main(argv):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    chapters = read_chapters()
    if '--staged' in argv:
        staged = _git('diff', '--cached', '--name-only').splitlines()
        for title, paths in staged_reminders(chapters, staged).items():
            print(f'Handbuch: "{title}" beschreibt geänderte Seiten:')
            for path in paths[:10]:
                print(f'  {path}')
            print('  Kapitel prüfen; wenn es noch stimmt, stand/version in handbuch/kapitel.py anheben.')
        return 0

    if '--bump' in argv:
        version, today = current_version(), date.today()
        changed = uncommitted_files()
        confirmed = []
        for chapter in chapters:
            commits = commits_since_stand(chapter)
            pending = sorted(p for p in changed if matches(p, chapter['pfade']))
            if commits or pending:
                print(f"{chapter['title']}: Seiten geändert, bitte Kapitel prüfen "
                      f'(dann stand/version von Hand anheben)')
                for line in commits:
                    print(f'  {line}')
                for path in pending[:10]:
                    print(f'  nicht committet: {path}')
            else:
                confirmed.append(chapter['slug'])
                print(f"{chapter['title']}: unverändert -> {version}, Stand {today:%d.%m.%Y}")
        if confirmed:
            # newline='' keeps the file's line endings.
            with open(REGISTRY, encoding='utf-8', newline='') as f:
                text = f.read()
            with open(REGISTRY, 'w', encoding='utf-8', newline='') as f:
                f.write(bump_registry(text, set(confirmed), version, today))
        return 1 if len(confirmed) < len(chapters) else 0

    outdated = 0
    for chapter in chapters:
        commits = commits_since_stand(chapter)
        if commits:
            outdated += 1
            print(f"{chapter['title']} (Stand {chapter['stand']:%d.%m.%Y}): "
                  f'{len(commits)} Commit(s) seitdem')
            for line in commits:
                print(f'  {line}')
        else:
            print(f"{chapter['title']}: aktuell")
    return 1 if outdated else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
