"""Read-only progression decoding. Never edits flags, graphs, or loadouts."""
import json
import struct
from pathlib import Path
from .resonant_save import ROOT, Save

DEFINITIONS = json.loads((ROOT / 'progression_definitions.json').read_text(encoding='utf8'))
DEFAULTS = json.loads((ROOT / 'fact_defaults.json').read_text(encoding='utf8'))

def inspect_progression(save: Save):
    position = save.unknown_tail_offset
    def u32():
        nonlocal position
        if position+4 > len(save.data): raise ValueError('Truncated progression data')
        value=struct.unpack_from('<I',save.data,position)[0];position+=4
        return value
    def count(limit=10000):
        value=u32()
        if value>limit: raise ValueError('Unsupported progression count')
        return value
    def version():
        value=u32()
        if value!=1: raise ValueError(f'Unsupported progression schema {value}')
    def node(key):
        text=f'{key:08x}'
        return {'id':text,'names':DEFINITIONS['nodes'].get(text,[])}
    result={'active_world_level':u32(),'graphs':[],'equipped_abilities':[]}
    version()
    for _ in range(count(32)):
        version();key=u32()
        unlocked=[node(u32()) for _ in range(count())]
        active=[node(u32()) for _ in range(count())]
        result['graphs'].append({'id':f'{key:08x}',
                                'name':DEFINITIONS['graphs'].get(f'{key:08x}','Unknown graph'),
                                'unlocked_nodes':unlocked,'active_nodes':active})
    result['ability_loadout_offset']=position
    version()
    for _ in range(count(32)):
        slot,ability=u32(),u32()
        result['equipped_abilities'].append({'slot_id':f'{slot:08x}','ability_id':f'{ability:08x}',
                                             'name':DEFINITIONS['abilities'].get(f'{ability:08x}','Unknown ability')})
    result['unparsed_remainder_offset']=position
    result['ability_facts']=[]
    result['map_unlocks']=[]
    for key,row in sorted(DEFAULTS.items(),key=lambda item:item[1]['fact_name']):
        name=row['fact_name']
        if not name.startswith(('ability_unlocks/','ability_select_unlocks/','talents/','map_unlocks/')): continue
        integer=int(key,16)
        present=integer in save.facts or integer in save.booleans
        stored=save.facts[integer][0] if integer in save.facts else save.booleans.get(integer)
        fact={'id':key,'name':name,'type':row['type'],'stored':present,'stored_value':stored,
              'asset_default':row['default'],'effective_value':stored if present else row['default']}
        result['map_unlocks' if name.startswith('map_unlocks/') else 'ability_facts'].append(fact)
    result['notes']=[
        'Absent facts are reported separately from explicitly stored false values; effective values use game-definition defaults.',
        'Graph active nodes are not treated as owned upgrades. The save maintains a separate unlocked list.',
        'Knowing a flag and loadout ID does not prove that changing those fields alone performs a complete ability unlock.',
        'This inspector does not edit any save data.'
    ]
    return result

def markdown_report(report, source):
    lines=['# CONTROL Resonant progression snapshot','',f'Source: `{source}`','',
           'This report is read-only. Absent flags are distinguished from values explicitly stored in the save.','',
           '## Equipped ability','', '| Ability | Ability ID | Slot ID |','|---|---|---|']
    for row in report['equipped_abilities']:
        lines.append(f"| {row['name']} | `{row['ability_id']}` | `{row['slot_id']}` |")
    if not report['equipped_abilities']: lines.append('| No explicit loadout entry | — | — |')
    lines+=['','## Ability unlocks and boss choices','', '| Fact | Value | Evidence |','|---|---|---|']
    for row in report['ability_facts']:
        evidence='Explicitly stored' if row['stored'] else 'Absent; asset default shown'
        lines.append(f"| `{row['name']}` | {row['effective_value']} | {evidence} |")
    for graph in report['graphs']:
        lines+=['',f"## {graph['name']} graph",'',
                f"{len(graph['unlocked_nodes'])} unlocked nodes; {len(graph['active_nodes'])} active graph nodes. These are separate lists.",'',
                '| Unlocked node | ID |','|---|---|']
        for row in graph['unlocked_nodes']:
            names=', '.join(row['names']) or 'Unresolved'
            lines.append(f"| {names} | `{row['id']}` |")
        if not graph['unlocked_nodes']: lines.append('| None explicitly stored | — |')
        lines+=['','Active graph-node names: '+', '.join('/'.join(row['names']) or row['id'] for row in graph['active_nodes'])+'.']
    lines+=['','## Map unlock flags','', '| Fact | Value | Evidence |','|---|---|---|']
    for row in report['map_unlocks']:
        evidence='Explicitly stored' if row['stored'] else 'Absent; asset default shown'
        lines.append(f"| `{row['name']}` | {row['effective_value']} | {evidence} |")
    lines+=['','## Limits','']+['- '+note for note in report['notes']]
    return '\n'.join(lines)+'\n'

def main():
    import argparse
    parser=argparse.ArgumentParser(prog='control-resonant-progression',description=__doc__)
    parser.add_argument('save',type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(inspect_progression(Save.read(args.save)),indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
