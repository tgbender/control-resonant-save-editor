# CONTROL Resonant save editor

An unofficial, experimental local save editor for CONTROL Resonant, with readable Python source. No third-party Python packages, network calls, telemetry, or game injection.

> **Experimental.** Exports pass checksum and structure validation, but loading them in the game has not been verified. Always keep a backup of your saves.

## Features

- Inspect and edit 28 named currency/material types already present in a save (whole numbers from 0 to 999999).
- Export existing crafting materials and Reset Items at 99.
- Inspect 52 cosmetic ownership flags covering 53 named wardrobe items; export selected or all mapped unlocks.
- Inspect ability ownership, boss-choice counts, equipped abilities, upgrade graphs, and map flags.
- Compare numeric facts between saves.
- Export complete four-file slot copies with checksums and a change manifest. Source files are never overwritten.
- Experimental command-line ability unlocks (see [Ability scripts](#ability-scripts)).

## Requirements

- Python 3.10 or newer with Tkinter. The standard library is sufficient. Some Linux distributions package Tkinter separately (for example `python3-tk`).
- Optional: [uv](https://docs.astral.sh/uv/) to run the editor with a uv-managed Python.

## Launch

With uv:

```bash
uv run --offline --no-project python editor_gui.py
```

`--offline` stops uv from downloading anything, so it needs a Python that uv already manages. If you don't have one yet, run this once first (this step does download Python):

```bash
uv python install 3.12
```

On Windows, double-click `Launch Editor.cmd`, which runs the same uv command and does not install or download anything. With any other Python installation, run `python editor_gui.py`.

## Edit a save

1. Close the game.
2. Back up the save folder. Copying it into this project's `backups/` folder works well: the editor's **Open** dialog starts there, and Git ignores it. On Steam, saves are in `<Steam>/userdata/<account-id>/3669870/remote/`.
3. Click **Open persistent save…** and choose a `*-persi-global` file from your backup. Its matching `-header`, `-player`, and `-bundle-container` files must be in the same folder.
4. Make an edit:
   - select a value, enter a new one, and click **Export edited slot copy**;
   - click **Export 99 crafting items**; or
   - click **Cosmetics…** and export selected or all unlocks.
5. Each export creates a new folder under `exports/` containing all four slot files and an `edit-manifest.json` listing every change.
6. To combine edits, open the exported `*-persi-global` file and export again.
7. To install, close the game and copy the four slot files from the export folder into the save folder, replacing the files with the same names. Don't copy `edit-manifest.json`.
8. Start the game, load the slot, save, and reload. Keep your backup until the changes survive that round trip.

If Steam Cloud is enabled, Steam may report a sync conflict or restore the cloud copy after you install an export. If it asks, keep the local files.

The editor does not locate accounts, choose the newest checkpoint, make backups, or install exports for you. Only the flat four-file save layout is supported; Epic `.chunk` and Xbox WGS containers are not implemented.

## Command line

Every tool validates the save's checksum and version and refuses anything unsupported. Exports go to a new folder under `exports/`; nothing is written back to the source.

```bash
# Validate a save and list its numeric facts as JSON
uv run --offline --no-project python resonant_save.py inspect "path/to/slot-0_auto-0-persi-global"

# Compare numeric facts between two saves
uv run --offline --no-project python resonant_save.py diff "path/to/before-persi-global" "path/to/after-persi-global"

# Export one numeric edit: fact ID in hex, --expect must match the current value
# (1e32cdb1862aa913 is Source)
uv run --offline --no-project python resonant_save.py export "path/to/slot-0_auto-0-persi-global" --fact 1e32cdb1862aa913 --expect 120 --value 500

# Read-only ability and progression report as JSON
uv run --offline --no-project python progression.py "path/to/slot-0_auto-0-persi-global"

# List cosmetics with their IDs, then export some or all unlocks
uv run --offline --no-project python cosmetics.py "path/to/slot-0_auto-0-persi-global"
uv run --offline --no-project python cosmetics.py "path/to/slot-0_auto-0-persi-global" --unlock <id> [<id> ...]
uv run --offline --no-project python cosmetics.py "path/to/slot-0_auto-0-persi-global" --unlock-all
```

### Ability scripts

These scripts are experimental. Both use an inferred choice-counter model, and neither changes equipped abilities or upgrade graphs.

```bash
# Add Shield and Volatile Anomaly; requires Barrage to be owned already
uv run --offline --no-project python artist_abilities.py "path/to/slot-0_auto-0-persi-global"

# Add the alternate ability for each of the four regional bosses; requires
# existing completion and ownership evidence for all four
uv run --offline --no-project python alternate_abilities.py "path/to/slot-0_auto-0-persi-global"
```

## Validation and limitations

- **Supported format:** RMDB 2/2, persistent schema 23, world facts schema 4. Saves with other versions are refused. A game update could change what fields mean without changing these version numbers, so compatibility with later patches is not guaranteed.
- **Game version:** Checked against Steam build 25767184 (October 2026). Saves from that build parse, inspect, and export correctly; loading edited exports in the game is still unverified.
- **Tests:** Tests use generated fixtures, not player saves or extracted game assets. They check checksum rejection, edit scope, preservation of unknown data, source-file preservation, stale reads, mapping hashes, and unlock prerequisites. Passing them does not prove in-game compatibility.
- **Cosmetics:** Only ownership flags change. Sixteen other outfit facts without direct wardrobe-item mappings are excluded, and one mapped flag controls two rain-jacket variants. Equipped appearance and individual colors are not edited.
- **Entitlements:** Promotional entitlements can affect persistence. This editor does not edit entitlement markers.
- **Abilities and cosmetics:** Ability unlock scripts and cosmetic unlocks remain experimental pending reproducible game-loading and save/reload validation.
- **Metadata:** The bundled metadata contains internal identifiers and short display names needed by the editor. It contains no full localization tables, game archives, player progression snapshots, account IDs, or saved games.

## Tests and packaging

```bash
uv run --offline --no-project python -m unittest -v
uv run --offline --no-project python package_release.py
```

Packaging uses an exact allowlist, rejects unexpected files, and scans text for private-path and credential patterns. Don't share a used working folder by copying or zipping it yourself: `backups/` and `exports/` contain player data. Git ignores both, and `package_release.py` never includes them.

## Provenance

Save parsing and editing code was developed independently. World-fact IDs are CityHash64 hashes of internal `wf_<hex>` record names. Other progression identifiers use a separate case-folded FNV-1a hash. See [FORMAT.md](FORMAT.md) for the observed layout.

`cityhash64.py` adapts Google's CityHash algorithm and retains its MIT notice. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This project is not affiliated with or endorsed by Remedy Entertainment. The included MIT license covers this project's code; game names and third-party material retain their respective ownership.
