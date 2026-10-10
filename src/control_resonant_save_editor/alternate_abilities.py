"""Export the four alternate abilities for already-defeated Resonants.

Uses the existing Artist editor's inferred ownership/choice-counter model.
Does not install saves or change equipped abilities or upgrade graphs.
"""
import struct
from pathlib import Path

from .resonant_save import Save, checksum, read_slot, write_export
from .progression import DEFAULTS, inspect_progression

REWARDS = (
    ('heat', 'Ignite', 'heat_aura_unlocked', 'flame_wave_unlocked'),
    ('dancer', 'Push', 'collapse_push_unlocked', 'ground_slam_unlocked'),
    ('astral', 'Spike', 'astral_construct_summon_unlocked', 'sunder_unlocked'),
    ('mold', 'Growth', 'turret_summon_unlocked', 'needles_unlocked'),
)
BY_NAME = {row['fact_name']: (int(key, 16), row) for key, row in DEFAULTS.items()}


def fact(name, kind):
    key, definition = BY_NAME[name]
    if definition['type'] != kind:
        raise ValueError(f'Unexpected definition type: {name}')
    return key


def unlock_alternates(save):
    flags = dict(save.booleans)
    changes = {}
    for boss, label, alternate, owned in REWARDS:
        required = (
            f'quests/resonants/defeated_{boss}_resonant',
            f'ability_unlocks/{owned}',
            f'ability_select_unlocks/{boss}_boss_ability_selected',
            f'ability_select_unlocks/{boss}_boss_ability_unlocked',
        )
        for name in required:
            if not save.booleans.get(fact(name, 'boolean'), False):
                raise ValueError(f'{label} requires an existing completion/unlock: {name}')
        flags[fact(f'ability_unlocks/{alternate}', 'boolean')] = True
        # As in artist_abilities.py, align selected/available choices with ownership.
        # This counter interpretation is inferred, not a traced engine grant path.
        for suffix in ('selected_count', 'unlocked_count'):
            name = f'ability_select_unlocks/{boss}_boss_ability_{suffix}'
            key = fact(name, 'number')
            if key not in save.facts or save.facts[key][0] not in (1, 2):
                raise ValueError(f'Unexpected choice count: {name}')
            if save.facts[key][0] != 2:
                changes[key] = (save.facts[key][0], 2)
    numeric = Save(save.patch(changes))
    bool_offset = 28 + 16 * len(numeric.facts)
    output = bytearray(numeric.data[:bool_offset])
    output.extend(struct.pack('<I', len(flags)))
    for key, value in sorted(flags.items()):
        output.extend(struct.pack('<QB', key, value))
    output.extend(numeric.data[numeric.unknown_tail_offset:])
    struct.pack_into('<I', output, 12, checksum(output))
    edited = Save(bytes(output))
    if (edited.booleans != flags or edited.facts.keys() != save.facts.keys()
            or any(edited.facts[key][0] != (2 if key in changes else value)
                   for key, (value, _) in save.facts.items())
            or edited.data[edited.unknown_tail_offset:] != save.data[save.unknown_tail_offset:]):
        raise ValueError('Unexpected changes outside alternate ability fields')
    before, after = inspect_progression(save), inspect_progression(edited)
    if (before['graphs'] != after['graphs']
            or before['equipped_abilities'] != after['equipped_abilities']):
        raise ValueError('Upgrade graphs or equipped abilities changed unexpectedly')
    return edited.data


def export(source):
    source = Path(source)
    if not source.name.endswith('-persi-global'):
        raise ValueError('Expected a persistent-global save')
    save = Save.read(source)
    edited = unlock_alternates(save)
    if edited == save.data:
        raise ValueError('All four alternates are already unlocked')
    if unlock_alternates(Save(edited)) != edited:
        raise ValueError('Alternate ability edit is not idempotent; refusing export')
    files = read_slot(source, save)
    parsed = Save(edited)
    manifest = {
        'abilities': [label for _, label, _, _ in REWARDS],
        'boolean_changes': [{'id': f'{key:016x}', 'fact': DEFAULTS[f'{key:016x}']['fact_name'],
                             'before': save.booleans.get(key), 'after': value}
                            for key, value in parsed.booleans.items()
                            if save.booleans.get(key) != value],
        'numeric_changes': [{'id': f'{key:016x}', 'fact': DEFAULTS[f'{key:016x}']['fact_name'],
                             'before': save.facts[key][0], 'after': value}
                            for key, (value, _) in parsed.facts.items()
                            if save.facts[key][0] != value],
        'validation': 'CRC, exact edit scope, tail/graphs/loadout preservation and idempotence verified; game loading unverified',
        'counter_model': 'Inferred: two owned abilities correspond to two unlocked and selected choices.',
    }
    return write_export('-alternate-abilities', source.name, files, edited, manifest)


def main():
    import argparse
    parser = argparse.ArgumentParser(prog='control-resonant-alternates', description=__doc__)
    parser.add_argument('save', type=Path)
    try:
        print(export(parser.parse_args().save))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
