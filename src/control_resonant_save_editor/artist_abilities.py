"""Narrow, experimental export of the Artist's three ability ownership flags.

Does not install saves or change equipped slots. In-game acceptance is unverified.
"""
import struct
from pathlib import Path

from .resonant_save import Save, checksum, read_slot, write_export
from .progression import DEFAULTS

BARRAGE = 0x55F052DC0F9FF225
SHIELD = 0xBF347DE9048C94D5
SEEKERS = 0x1167D3900FB6C359
UNLOCKED_COUNT = 0xF2C74FC7AB4625B6
SELECTED_COUNT = 0xAD9B22B652492BA1
ABILITY_NAMES = {BARRAGE: 'Barrage', SHIELD: 'Shield', SEEKERS: 'Volatile Anomaly'}


def unlock_artist_abilities(save):
    if not save.booleans.get(BARRAGE):
        raise ValueError('This edit requires an existing Barrage unlock')
    for key in (UNLOCKED_COUNT, SELECTED_COUNT):
        if key not in save.facts or save.facts[key][0] not in (1, 2, 3):
            raise ValueError('Unexpected Artist choice count; refusing edit')
    for key in ABILITY_NAMES:
        if DEFAULTS[f'{key:016x}']['type'] != 'boolean':
            raise ValueError('Ability definition is not Boolean')
    # Keep earned-choice allowance and selected-choice count aligned with the
    # three owned abilities. This is an inferred model, not a traced grant path.
    numeric = Save(save.patch({k: (save.facts[k][0], 3) for k in
                               (UNLOCKED_COUNT, SELECTED_COUNT)}))
    flags = dict(numeric.booleans)
    flags.update({key: True for key in ABILITY_NAMES})
    bool_offset = 28 + 16 * len(numeric.facts)
    out = bytearray(numeric.data[:bool_offset])
    out.extend(struct.pack('<I', len(flags)))
    for key, value in sorted(flags.items()):
        out.extend(struct.pack('<QB', key, value))
    out.extend(numeric.data[numeric.unknown_tail_offset:])
    struct.pack_into('<I', out, 12, checksum(out))
    result = Save(bytes(out))
    if (result.data[result.unknown_tail_offset:] != save.data[save.unknown_tail_offset:]
            or result.booleans != flags):
        raise ValueError('Unexpected changes outside Artist ability fields')
    return result.data


def export(source):
    source = Path(source)
    if not source.name.endswith('-persi-global'):
        raise ValueError('Expected persistent global file')
    save = Save.read(source)
    edited = unlock_artist_abilities(save)
    if edited == save.data:
        raise ValueError('All three Artist abilities and choice counts are already unlocked')
    files = read_slot(source, save)
    manifest = {'boolean_changes': [{'id': f'{k:016x}', 'ability': ABILITY_NAMES[k],
                                     'before': save.booleans.get(k), 'after': True}
                                    for k in (SHIELD, SEEKERS) if save.booleans.get(k) is not True],
                'numeric_changes': [{'id': f'{k:016x}', 'fact': DEFAULTS[f'{k:016x}']['fact_name'],
                                     'before': save.facts[k][0], 'after': 3}
                                    for k in (UNLOCKED_COUNT, SELECTED_COUNT) if save.facts[k][0] != 3],
                'validation': 'CRC and structure verified; unknown tail and loadout unchanged; in-game acceptance unverified',
                'counter_model': 'Inferred: three owned Artist abilities correspond to three unlocked and selected choices.'}
    return write_export('-artist-abilities', source.name, files, edited, manifest)


def main():
    import argparse
    parser = argparse.ArgumentParser(prog='control-resonant-artist', description=__doc__)
    parser.add_argument('save', type=Path)
    args = parser.parse_args()
    try:
        print(export(args.save))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
