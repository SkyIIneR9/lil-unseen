# LiL Unseen

[Русский](README.md) · English

Find dialogue you have not seen in **Lessons in Love**, including missed branches inside scenes you have already visited. Browse a local report, then optionally jump to a line in the game with background/music preparation and a **Next fragment** panel.

An unofficial fan research tool. The repository contains only the tool and synthetic test data. You need your own game installation; no game scripts, dialogue, images, saves, or URM code are distributed here. URM is not required.

## What it does

- Compares compiled dialogue IDs with Ren’Py's accumulated `persistent` read history.
- Groups consecutive unread dialogue into fragments; search by text, speaker, label, ID, or surrounding condition.
- Filters partially read scenes, visited labels, files, and explicit `bonus == False` branches.
- Copies console commands for prepared jumps, exact jumps, or scene starts.
- Provides Previous / Next fragment / Hide buttons inside the game.
- Exports local HTML, JSON and TSV. No server, network connection, account, or Python packages are needed to use the tool.
- Offers English and Russian report interfaces and panel labels. Game dialogue stays in the language of your installed scripts.

## Compatibility

Tested on Windows with **Ren’Py 8.2.3** and one Russian Lessons in Love installation whose folder says 0.60.0 but whose scripts declare 0.61.0. The original English edition, other releases, other mods, macOS and Linux have not been validated. This is an experimental first release, not a universal Ren’Py mod.

The exporter needs **Python 3.10+** on your computer. The in-game helper uses the Python bundled with the game. Node.js is only needed by contributors running the viewer tests.

The exporter reads RPA 2/3 archives and loose compiled scripts; loose files take precedence. Separately selected Ren’Py translations are currently unsupported: a non-`None` language in persistent produces an explicit error. Russian text patched directly into base scripts works in the tested build.

## Installation

1. Download the repository ZIP (**Code → Download ZIP**) and extract it.
2. Close the game. Copy the included **`game`** and **`research_unseen`** folders into your game root, beside the game executable. Merge the directories; the helper adds its own file.
3. Start the game once to compile the helper, then quit normally. The optional helper enables the Ren’Py console.
4. Run `research_unseen/refresh_report.cmd`, choose **E** for English or **R** for Russian, and wait for the report to open.

Expected layout:

```text
LessonsInLove/
  LessonsInLove….exe
  game/
    0unseen_research.rpy
    ...your existing game files...
  research_unseen/
    export_unseen.py
    refresh_report.cmd
    ...tool files...
```

For **report-only** use, omit `game/0unseen_research.rpy`. You can read the report without installing an in-game mod.

Manual export, from the game root:

```powershell
python research_unseen/export_unseen.py --ui-language en
```

For a custom game location or persistent backup:

```powershell
python research_unseen/export_unseen.py --root "D:\Games\LessonsInLove" --persistent "D:\Backups\persistent" --ui-language en
```

The in-game helper always reads `<game root>/research_unseen/output/navigation.json`. If running the exporter from an external checkout, also pass `--output` pointing to that directory. A custom output elsewhere is suitable for report-only use.

## Reading and jumping

1. Open `research_unseen/output/unseen.html` in a browser. It contains spoilers. Reading the HTML does not change game progress.
2. Load an **experimental save slot** in the game and stop during normal dialogue.
3. On a report card, click **Prepare scene & jump**, open the game console with **Shift+O** (letter O), paste the command and press Enter. If automatic copying fails, the command is selected for Ctrl+C.
4. Use **Next fragment** in the game to continue through the report queue. **Previous** can revisit read fragments. **Hide** removes the panel; another prepared jump brings it back.
5. After playing, quit normally and run the exporter again to refresh the report.

The default **Order: events** mode reads gaps within one label in source-line order, then follows the same character's in-game gallery order across files. It stops at the end of that queue; choose another event in the report. Shared events can belong to several galleries: navigation keeps the selected queue, while a fresh browser jump selects the first matching gallery (characters before main/secret).

Labels absent from galleries use a separate source-file queue, explicitly marked **Unmapped events in file**. This does not establish character ownership. Click **Order: events** to toggle the previous full-list order. The panel shows the queue, fragment position and current label. Continue within a fragment using normal clicks; Next fragment moves to the next group of gaps.

Both modes exclude explicit `bonus == False` branches and skip read fragments using live persistent state. **Browser filters do not control the queue.** Gallery order is not a guarantee of story chronology and does not select variables. After upgrading, fully restart the game and regenerate the report; old reports retain their previous order.

**Exact jump** skips media preparation. **Scene start** jumps to the label; conditions inside that scene still apply. Neither option chooses story variables for you.

## What a jump can and cannot restore

Prepared jumps replay identifiable `scene`, `show`, `hide`, and music commands. Music restarts from the beginning. Old sound effects and voices stop. If the background is unknown, the master layer is cleared; unknown music becomes silence. Dynamic images still depend on your current save variables. Cameras, custom screens, and other layers may retain state.

Preparation does not execute preceding story assignments or solve conditions. **After landing, ordinary game code runs normally**, including relationship changes and other consequences. Direct jumps can also display diagnostic or unreachable dialogue. Use a separate save for exploration; loading it later does not undo persistent read marks accumulated during exploration.

An unread ID means “not marked as executed by this persistent”, not proof that the player never read it, or that the branch is naturally reachable. Old versions, mods and lost persistent history can affect results. The tool does not load or merge every save slot. Surrounding conditions are clues, not a complete route walkthrough.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Python is missing / Microsoft Store opens | Install Python 3.10+ and enable its PATH option, then reopen the launcher. |
| Source is newer than compiled data | Start the game, quit normally, rerun the exporter. |
| No persistent found | Play and quit once, or pass `--persistent` explicitly. Windows AppData and local game saves are checked automatically. |
| `NameError: unseen_research_jump` | Check both tool folders are installed, then fully restart the game. |
| Navigation report mismatch | Close the game and regenerate the report from the same installation. Compiled archive filename rewrites are already handled. |
| Shift+O does not open the console | Verify the helper compiled and restart. Another mod may override console configuration. |
| Wrong/blank image, missing music | Some context cannot be reconstructed. Try Scene start or a save closer to the scene. |
| Incomplete/ambiguous extraction or unsupported language | That build is not supported yet; report the error and version, without uploading game scripts or saves. |

To uninstall the helper, close the game and remove **both** `game/0unseen_research.rpy` and `game/0unseen_research.rpyc`. Then the tool directory may be removed too. Do not remove either directory wholesale if it contains your other files.

## Privacy and distribution

Generated reports contain game dialogue, spoilers, your read history and local paths. Keep `research_unseen/output/` private. Do not publish generated reports, saves, persistent files, archives, decompiled scripts or extracted URM code. The supplied `.gitignore` excludes these artifacts; the release packer includes only an explicit list of tool files.

Offline parsing replaces supported Ren’Py pickle globals with inert records instead of importing the engine or executing embedded game Python. This is not a sandbox for arbitrary hostile files. Use data from your own trusted installation.

## Development

```powershell
python -m unittest discover -s research_unseen -p "test_*.py"
node tests/verify_viewer.cjs
python tools/build_release.py
```

Tests use invented fixtures and need no game assets. CI runs them on Windows and Linux. Engine integration was also checked locally with Ren’Py 8.2.3; that result does not validate every scene. The release archive is written under `dist/`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for bug reports and [ROADMAP.md](ROADMAP.md) for planned improvements. The tool code is under the [MIT license](LICENSE); the game and its assets are not covered by it.
