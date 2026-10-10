"""Named cosmetic ownership inspection and export. Never installs live saves."""
import json
import struct
from pathlib import Path
from .resonant_save import ROOT, Save, checksum, read_slot, require_snapshot, write_export

DEFINITIONS = json.loads((ROOT / 'cosmetic_definitions.json').read_text(encoding='utf8'))
CATEGORIES = {'base': 'Outfits', 'top': 'Outerwear', 'hair': 'Hair', 'beard': 'Facial hair',
              'body': 'Body', 'accessories': 'Accessories'}


def inspect_cosmetics(save):
    return [{'id': key, 'name': row['name'], 'category': CATEGORIES[row['category']],
             'stored': int(key, 16) in save.booleans,
             'unlocked': save.booleans.get(int(key, 16), row['default'])}
            for key, row in sorted(DEFINITIONS.items(), key=lambda x: (x[1]['category'], x[1]['name']))]


def unlock_cosmetics(save, keys):
    keys = set(keys)
    if not keys or any(f'{key:016x}' not in DEFINITIONS for key in keys):
        raise ValueError('Select mapped cosmetic unlocks only')
    changes = {key for key in keys if not save.booleans.get(key, DEFINITIONS[f'{key:016x}']['default'])}
    if not changes:
        return save.data, []
    flags = dict(save.booleans)
    flags.update({key: True for key in changes})
    offset = 28 + len(save.facts) * 16
    result = bytearray(save.data[:offset])
    result.extend(struct.pack('<I', len(flags)))
    for key, value in sorted(flags.items()):
        result.extend(struct.pack('<QB', key, value))
    result.extend(save.data[save.unknown_tail_offset:])
    struct.pack_into('<I', result, 12, checksum(result))
    parsed = Save(bytes(result))
    if parsed.data[parsed.unknown_tail_offset:] != save.data[save.unknown_tail_offset:]:
        raise ValueError('Unexpected changes outside cosmetic flags')
    return bytes(result), [{'id': f'{key:016x}', 'name': DEFINITIONS[f'{key:016x}']['name'],
                            'before': save.booleans.get(key), 'after': True} for key in sorted(changes)]


def export_cosmetics(source, keys, expected_sha256=None):
    source = Path(source)
    if not source.name.endswith('-persi-global'):
        raise ValueError('Choose a persistent global save')
    save = Save.read(source)
    require_snapshot(save, expected_sha256)
    edited, changes = unlock_cosmetics(save, keys)
    if not changes:
        raise ValueError('All selected cosmetics are already unlocked')
    files = read_slot(source, save)
    manifest = {'cosmetic_changes': changes,
                'validation': 'CRC and save structure validated. Cosmetic unlocks have not been verified in-game.',
                'scope': 'Mapped wardrobe ownership flags only. Equipped appearance and all other save data preserved.'}
    return write_export('-cosmetics', source.name, files, edited, manifest)


def main():
    import argparse
    parser = argparse.ArgumentParser(prog='control-resonant-cosmetics', description=__doc__)
    parser.add_argument('save', type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--unlock-all', action='store_true')
    group.add_argument('--unlock', nargs='+', metavar='FACT_ID')
    args = parser.parse_args()
    try:
        if args.unlock_all or args.unlock:
            keys = DEFINITIONS if args.unlock_all else args.unlock
            print(export_cosmetics(args.save, [int(k, 16) for k in keys]))
        else:
            print(json.dumps(inspect_cosmetics(Save.read(args.save)), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
