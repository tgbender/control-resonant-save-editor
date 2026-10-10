"""Independent, dependency-free CONTROL Resonant save research/editor.

Existing numeric facts only. Unknown bytes are preserved. Exports never replace
an existing file or a live save. A valid CRC does not prove in-game compatibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from datetime import datetime, timezone
import zlib

def documents_dir() -> Path:
    """The user's Documents folder, following Windows folder redirection (e.g. OneDrive)."""
    if sys.platform == 'win32':
        import ctypes
        import uuid
        folder_id = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID('FDD39AD0-238F-46AF-ADB4-6C85480369C7').bytes_le)
        path = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(path)) == 0:
            try:
                return Path(path.value)
            finally:
                ctypes.windll.ole32.CoTaskMemFree(path)
    documents = Path.home() / 'Documents'
    return documents if documents.is_dir() else Path.home()

ROOT = Path(__file__).resolve().parent
# Exports and suggested backups live outside the code, which may be an installed package.
WORKSPACE = documents_dir() / 'CONTROL Resonant save editor'
MAX_SIZE = 16 * 1024 * 1024
MAX_ITEM_AMOUNT = 999999
SLOT_SUFFIXES = ('persi-global', 'header', 'bundle-container', 'player')
ITEM_DEFINITIONS = json.loads((ROOT / 'identified_items.json').read_text(encoding='utf8'))
IDENTIFIED_ITEMS = {int(key, 16): row['name'] for key, row in ITEM_DEFINITIONS.items()}
MATERIAL_IDS = {
    int(key, 16) for key, row in ITEM_DEFINITIONS.items()
    if row['fact_name'].startswith(('currency/common_material/', 'currency/rare_material/', 'currency/charm_component/'))
    or row['fact_name'] == 'currency/special_material/respec_items'
}

def checksum(data: bytes) -> int:
    return zlib.crc32(data[16:])

def validate_container(data: bytes) -> None:
    if not 16 <= len(data) <= MAX_SIZE:
        raise ValueError('Invalid save size')
    if data[:4] != b'RMDB' or struct.unpack_from('<II', data, 4) != (2, 2):
        raise ValueError('Unsupported RMDB version (expected 2, 2)')
    if struct.unpack_from('<I', data, 12)[0] != checksum(data):
        raise ValueError('Checksum mismatch; refusing to edit')

class Save:
    def __init__(self, data: bytes):
        validate_container(data)
        if len(data) < 32 or struct.unpack_from('<II', data, 16) != (23, 4):
            raise ValueError('Unsupported persistent-global schema (expected 23, 4)')
        self.data = bytes(data)
        count = struct.unpack_from('<I', data, 24)[0]
        end = 28 + count * 16
        if count > 100000 or end + 4 > len(data):
            raise ValueError('Truncated numeric fact table')
        self.facts = {}
        previous = -1
        for offset in range(28, end, 16):
            key, value = struct.unpack_from('<Qd', data, offset)
            if key <= previous or not math.isfinite(value):
                raise ValueError('Invalid numeric fact table')
            self.facts[key] = (value, offset + 8)
            previous = key
        bool_count = struct.unpack_from('<I', data, end)[0]
        tail = end + 4 + bool_count * 9
        if bool_count > 1000000 or tail > len(data):
            raise ValueError('Truncated Boolean fact table')
        self.booleans = {}
        previous = -1
        for offset in range(end + 4, tail, 9):
            key, value = struct.unpack_from('<QB', data, offset)
            if key <= previous or value not in (0, 1):
                raise ValueError('Invalid Boolean fact table')
            self.booleans[key] = bool(value)
            previous = key
        self.unknown_tail_offset = tail

    @classmethod
    def read(cls, path):
        path = Path(path)
        if path.stat().st_size > MAX_SIZE:
            raise ValueError('Save exceeds size limit')
        return cls(path.read_bytes())

    def patch(self, changes: dict[int, tuple[float, float]]) -> bytes:
        """key -> (expected current value, replacement); never adds new facts."""
        result = bytearray(self.data)
        for key, (expected, value) in changes.items():
            if key not in self.facts:
                raise ValueError(f'Unknown numeric fact {key:016x}')
            old, offset = self.facts[key]
            if not math.isfinite(expected) or old != expected:
                raise ValueError(f'Fact {key:016x} changed: expected {expected}, found {old}')
            if not math.isfinite(value) or abs(value) > 2**53:
                raise ValueError('Replacement must be finite and within +/- 2^53')
            if old != value:
                struct.pack_into('<d', result, offset, value)
        struct.pack_into('<I', result, 12, checksum(result))
        Save(bytes(result))
        return bytes(result)

    def report(self):
        return {
            'bytes': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest(),
            'checksum_valid': True, 'schema': [23, 4],
            'numeric_facts': {f'{k:016x}': v for k, (v, _) in self.facts.items()},
            'boolean_fact_count': len(self.booleans),
            'unknown_tail_offset': self.unknown_tail_offset,
            'identified_items': {f'{k:016x}': name for k, name in IDENTIFIED_ITEMS.items() if k in self.facts},
            'note': 'Named currency IDs are derived from installed-game definitions using CityHash64 of their internal world-fact record names.'}

def validate_item_value(key: int, value: float) -> None:
    """Named items hold counts; unnamed facts keep the generic patch() limits."""
    if key in IDENTIFIED_ITEMS and not (float(value).is_integer() and 0 <= value <= MAX_ITEM_AMOUNT):
        raise ValueError(f'{IDENTIFIED_ITEMS[key]} must be a whole number from 0 to {MAX_ITEM_AMOUNT}')

def require_snapshot(save: Save, expected_sha256: str | None) -> None:
    if expected_sha256 and hashlib.sha256(save.data).hexdigest() != expected_sha256:
        raise ValueError('The save changed after opening it. Reopen it before exporting.')

def read_slot(source: Path, save: Save) -> dict[str, bytes]:
    """Read and validate all four slot files; refuse a slot that changes while being read."""
    stem = source.name.removesuffix('-persi-global')
    files = {}
    for suffix in SLOT_SUFFIXES:
        path = source.with_name(f'{stem}-{suffix}')
        if path.stat().st_size > MAX_SIZE:
            raise ValueError('Slot file exceeds size limit')
        files[path.name] = path.read_bytes()
        validate_container(files[path.name])
    if files[source.name] != save.data or any(source.with_name(n).read_bytes() != d for n, d in files.items()):
        raise ValueError('Source changed during read; try a stable backup')
    return files

def write_export(label: str, source_name: str, files: dict[str, bytes], edited: bytes, manifest: dict) -> Path:
    """Write a new timestamped slot copy under WORKSPACE/exports; never replaces an existing file."""
    exports = WORKSPACE / 'exports'
    exports.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + label
    # Coarse clocks (older Pythons on Windows) can repeat a timestamp for back-to-back exports.
    for attempt in range(1, 100):
        output = exports / (stamp if attempt == 1 else f'{stamp}-{attempt}')
        try:
            output.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('Could not create a unique export folder')
    records = []
    for name, original in files.items():
        content = edited if name == source_name else original
        with (output / name).open('xb') as f:
            f.write(content)
        records.append({'file': name, 'original_sha256': hashlib.sha256(original).hexdigest(),
                        'export_sha256': hashlib.sha256(content).hexdigest()})
    with (output / 'edit-manifest.json').open('x', encoding='utf8') as f:
        json.dump({'source': source_name, **manifest, 'files': records}, f, indent=2)
    return output

def material_changes(save: Save, amount: int = 99):
    if not isinstance(amount, int) or not 0 <= amount <= MAX_ITEM_AMOUNT:
        raise ValueError(f'Material amount must be an integer from 0 to {MAX_ITEM_AMOUNT}')
    return {key: (save.facts[key][0], amount) for key in sorted(MATERIAL_IDS & save.facts.keys())
            if save.facts[key][0] != amount}

def export_slot(source: Path, key: int, expected: float, value: float, expected_sha256: str | None = None) -> Path:
    return export_slot_changes(source, {key: (expected, value)}, expected_sha256)

def export_slot_changes(source: Path, changes: dict[int, tuple[float, float]],
                        expected_sha256: str | None = None) -> Path:
    if not source.name.endswith('-persi-global'):
        raise ValueError('Select a slot-*-persi-global file')
    save = Save.read(source)
    require_snapshot(save, expected_sha256)
    for key, (_, value) in changes.items():
        validate_item_value(key, value)
    patched = save.patch(changes)
    if patched == save.data:
        raise ValueError('No change requested')
    files = read_slot(source, save)
    manifest = {'changes': [{'fact_id': f'{key:016x}', 'before': expected, 'after': value,
                             'identified_item': IDENTIFIED_ITEMS.get(key)}
                            for key, (expected, value) in changes.items() if expected != value],
                'warning': 'Experimental; game loading is not yet validated. Unnamed fields have unconfirmed semantics.'}
    return write_export('', source.name, files, patched, manifest)

def main():
    p = argparse.ArgumentParser(prog='control-resonant-save', description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Validate and list numeric facts')
    inspect.add_argument('save', type=Path)
    diff = sub.add_parser('diff', help='Compare numeric facts between two snapshots')
    diff.add_argument('before', type=Path); diff.add_argument('after', type=Path)
    export = sub.add_parser('export', help='Export a complete slot copy with one numeric edit')
    export.add_argument('save', type=Path)
    export.add_argument('--fact', required=True, type=lambda s: int(s, 16))
    export.add_argument('--expect', required=True, type=float)
    export.add_argument('--value', required=True, type=float)
    args = p.parse_args()
    try:
        if args.command == 'inspect':
            print(json.dumps(Save.read(args.save).report(), indent=2))
        elif args.command == 'diff':
            a, b = Save.read(args.before), Save.read(args.after)
            result = []
            for key in sorted(a.facts.keys() | b.facts.keys()):
                old = a.facts.get(key, (None,))[0]; new = b.facts.get(key, (None,))[0]
                if old != new: result.append({'id': f'{key:016x}', 'before': old, 'after': new})
            print(json.dumps(result, indent=2))
        else:
            print(export_slot(args.save, args.fact, args.expect, args.value))
    except (OSError, ValueError, struct.error) as exc:
        p.exit(1, f'Error: {exc}\n')

if __name__ == '__main__':
    main()
