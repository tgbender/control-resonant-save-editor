"""Portable tests using generated fixtures only; no player saves or game assets."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from control_resonant_save_editor import resonant_save as rs
from control_resonant_save_editor import cosmetics
from control_resonant_save_editor import artist_abilities as artist
from control_resonant_save_editor import alternate_abilities as alternate
from control_resonant_save_editor.cityhash64 import cityhash64
from control_resonant_save_editor.progression import DEFAULTS, inspect_progression

SOURCE = 0x1E32CDB1862AA913
SENTINEL = 0x0102030405060708


def container(payload):
    data = bytearray(b'RMDB' + struct.pack('<III', 2, 2, 0) + payload)
    struct.pack_into('<I', data, 12, rs.checksum(data))
    return bytes(data)


def fixture(numbers=None, flags=None, tail=None):
    """Artificial schema example, deliberately not a playable checkpoint."""
    if numbers is None:
        numbers = {key: 5.0 for key in rs.IDENTIFIED_ITEMS}
        numbers.update({artist.UNLOCKED_COUNT: 1, artist.SELECTED_COUNT: 1})
    if flags is None:
        flags = {artist.BARRAGE: True, SENTINEL: False}
    if tail is None:
        # World level; unlocks v1; two empty graphs; loadout v1 with Barrage.
        tail = struct.pack('<17I', 1, 1, 2,
                           1, 0x79CA637B, 0, 0,
                           1, 0xF675CE88, 0, 0,
                           1, 1, 0x7AFF29C0, 0xB7999803, 0, 0)
        tail += b'ARTIFICIAL-OPAQUE-DATA\x00\xff'
    payload = bytearray(struct.pack('<III', 23, 4, len(numbers)))
    for key, value in sorted(numbers.items()):
        payload.extend(struct.pack('<Qd', key, value))
    payload.extend(struct.pack('<I', len(flags)))
    for key, value in sorted(flags.items()):
        payload.extend(struct.pack('<QB', key, value))
    return container(payload + tail)


def alternate_inputs():
    """Numbers and flags satisfying every alternate-ability prerequisite, plus the flags it adds."""
    numbers = {}; flags = {SENTINEL: False}; new_flags = set()
    for boss, _, target, owned in alternate.REWARDS:
        for name in (f'quests/resonants/defeated_{boss}_resonant', f'ability_unlocks/{owned}',
                     f'ability_select_unlocks/{boss}_boss_ability_selected',
                     f'ability_select_unlocks/{boss}_boss_ability_unlocked'):
            flags[alternate.fact(name, 'boolean')] = True
        new_flags.add(alternate.fact(f'ability_unlocks/{target}', 'boolean'))
        for suffix in ('selected_count', 'unlocked_count'):
            numbers[alternate.fact(f'ability_select_unlocks/{boss}_boss_ability_{suffix}', 'number')] = 1
    return numbers, flags, new_flags


def write_slot(directory, data=None):
    source = Path(directory) / 'slot-0_auto-0-persi-global'
    source.write_bytes(fixture() if data is None else data)
    for suffix in ('header', 'bundle-container', 'player'):
        source.with_name('slot-0_auto-0-' + suffix).write_bytes(container(b'ARTIFICIAL-COMPANION'))
    return source


class FormatTests(unittest.TestCase):
    def test_noop_and_each_numeric_edit_scope(self):
        original = fixture(); save = rs.Save(original)
        self.assertEqual(save.patch({}), original)
        for key, (value, offset) in save.facts.items():
            edited = save.patch({key: (value, value + 2)})
            changed = {i for i, (a, b) in enumerate(zip(original, edited)) if a != b}
            self.assertLessEqual(changed, set(range(12, 16)) | set(range(offset, offset+8)))
            self.assertEqual(rs.Save(edited).facts[key][0], value+2)

    def test_corruption_and_truncation(self):
        original = fixture()
        for offset in (0, 4, 12, 25, len(original)-1):
            bad = bytearray(original); bad[offset] ^= 1
            with self.assertRaises(ValueError): rs.Save(bad)
        for size in (0, 15, 20, 31):
            with self.assertRaises(ValueError): rs.Save(original[:size])

    def test_schema_and_count_validation_with_valid_crc(self):
        for offset, value in ((16, 999), (24, 0xFFFFFFFF)):
            bad = bytearray(fixture()); struct.pack_into('<I', bad, offset, value)
            struct.pack_into('<I', bad, 12, rs.checksum(bad))
            with self.assertRaises(ValueError): rs.Save(bad)

    def test_stale_unknown_and_invalid_values(self):
        save = rs.Save(fixture()); old = save.facts[SOURCE][0]
        for changes in ({SOURCE: (old+1, 2)}, {0: (0, 2)},
                        {SOURCE: (old, float('nan'))}, {SOURCE: (old, float('inf'))},
                        {SOURCE: (old, 2**54)}):
            with self.assertRaises(ValueError): save.patch(changes)

    def test_material_scope(self):
        save = rs.Save(fixture()); changes = rs.material_changes(save)
        self.assertTrue(changes)
        self.assertNotIn(SOURCE, changes)
        excluded = {'Living Shard', 'Talent Point', 'Health Upgrade Point', 'Power Upgrade Point', 'Resonant Token'}
        self.assertTrue(all(rs.IDENTIFIED_ITEMS[k] not in excluded for k in changes))
        edited = rs.Save(save.patch(changes))
        self.assertEqual(save.booleans, edited.booleans)
        self.assertEqual(save.data[save.unknown_tail_offset:], edited.data[edited.unknown_tail_offset:])

    def test_mapping_hashes(self):
        for key, row in {**rs.ITEM_DEFINITIONS, **cosmetics.DEFINITIONS}.items():
            self.assertEqual(f'{cityhash64(row["record"]):016x}', key)

    def test_progression_read_only_and_absent_defaults(self):
        save = rs.Save(fixture()); before = save.data; report = inspect_progression(save)
        facts = {r['id']: r for r in report['ability_facts']}
        self.assertTrue(facts[f'{artist.BARRAGE:016x}']['stored_value'])
        self.assertFalse(facts[f'{artist.SHIELD:016x}']['stored'])
        self.assertFalse(facts[f'{artist.SHIELD:016x}']['effective_value'])
        self.assertEqual(report['equipped_abilities'][0]['name'], 'barrage')
        self.assertEqual(save.data, before)

    def test_progression_truncation(self):
        with self.assertRaises(ValueError): inspect_progression(rs.Save(fixture(tail=b'\x01\x00')))


class UnlockTests(unittest.TestCase):
    def test_cosmetic_selection_and_all_scope(self):
        before = rs.Save(fixture())
        keys = {int(k, 16) for k in cosmetics.DEFINITIONS}
        edited, changes = cosmetics.unlock_cosmetics(before, keys)
        after = rs.Save(edited)
        self.assertTrue(changes)
        self.assertTrue(all(r['unlocked'] for r in cosmetics.inspect_cosmetics(after)))
        self.assertEqual(before.facts, after.facts)
        self.assertEqual(after.booleans[SENTINEL], False)
        self.assertEqual(before.data[before.unknown_tail_offset:], after.data[after.unknown_tail_offset:])
        self.assertEqual(cosmetics.unlock_cosmetics(after, keys), (edited, []))
        key = int(changes[0]['id'], 16)
        single, _ = cosmetics.unlock_cosmetics(before, [key])
        self.assertEqual(rs.Save(single).booleans, {**before.booleans, key: True})

    def test_cosmetic_rejects_non_cosmetic(self):
        with self.assertRaises(ValueError): cosmetics.unlock_cosmetics(rs.Save(fixture()), [artist.BARRAGE])

    def test_explicit_false_overrides_default(self):
        key = int(next(k for k, v in cosmetics.DEFINITIONS.items() if v['default']), 16)
        save = rs.Save(fixture(flags={key: False}))
        self.assertFalse(next(r['unlocked'] for r in cosmetics.inspect_cosmetics(save) if int(r['id'], 16) == key))
        edited, changes = cosmetics.unlock_cosmetics(save, [key])
        self.assertTrue(rs.Save(edited).booleans[key]); self.assertEqual(len(changes), 1)

    def test_artist_scope_and_idempotence(self):
        before = rs.Save(fixture()); edited = artist.unlock_artist_abilities(before); after = rs.Save(edited)
        self.assertEqual(after.booleans, {**before.booleans, artist.SHIELD: True, artist.SEEKERS: True})
        changed = {k for k in before.facts if before.facts[k][0] != after.facts[k][0]}
        self.assertEqual(changed, {artist.SELECTED_COUNT, artist.UNLOCKED_COUNT})
        self.assertEqual(before.data[before.unknown_tail_offset:], after.data[after.unknown_tail_offset:])
        self.assertEqual(artist.unlock_artist_abilities(after), edited)

    def test_artist_requires_barrage(self):
        with self.assertRaises(ValueError): artist.unlock_artist_abilities(rs.Save(fixture(flags={})))

    def test_alternates_require_boss_completion(self):
        with self.assertRaises(ValueError): alternate.unlock_alternates(rs.Save(fixture()))

    def test_alternate_unlock_scope(self):
        numbers, flags, new_flags = alternate_inputs()
        before = rs.Save(fixture(numbers, flags)); edited = alternate.unlock_alternates(before); after = rs.Save(edited)
        self.assertEqual(after.booleans, {**flags, **{k: True for k in new_flags}})
        self.assertTrue(all(v == 2 for v, _ in after.facts.values()))
        self.assertEqual(before.data[before.unknown_tail_offset:], after.data[after.unknown_tail_offset:])
        self.assertEqual(alternate.unlock_alternates(after), edited)


class ExportTests(unittest.TestCase):
    def test_exports_preserve_source_companions_and_omit_absolute_paths(self):
        for module in (rs, cosmetics, artist, alternate):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = write_slot(root, fixture(*alternate_inputs()[:2]) if module is alternate else None)
                original = {p.name: p.read_bytes() for p in root.iterdir()}
                with patch.object(rs, 'WORKSPACE', root):
                    if module is rs: out = rs.export_slot(source, SOURCE, 5, 42)
                    elif module is cosmetics: out = cosmetics.export_cosmetics(source, [int(k, 16) for k in cosmetics.DEFINITIONS])
                    else: out = module.export(source)
                manifest = json.loads((out/'edit-manifest.json').read_text())
                self.assertEqual(manifest['source'], source.name)
                self.assertEqual(len(manifest['files']), 4)
                for name, data in original.items():
                    self.assertEqual((root/name).read_bytes(), data)
                    if name != source.name: self.assertEqual((out/name).read_bytes(), data)
                rs.Save.read(out/source.name)

    def test_cosmetic_stale_guard_and_missing_companion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = write_slot(root); keys = [int(k, 16) for k in cosmetics.DEFINITIONS]
            with patch.object(rs, 'WORKSPACE', root):
                with self.assertRaises(ValueError): cosmetics.export_cosmetics(source, keys, 'stale')
                source.with_name('slot-0_auto-0-player').unlink()
                with self.assertRaises(OSError): cosmetics.export_cosmetics(source, keys)
                self.assertFalse((root/'exports').exists())

    def test_numeric_stale_guard_and_item_value_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = write_slot(root)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with patch.object(rs, 'WORKSPACE', root):
                with self.assertRaises(ValueError): rs.export_slot(source, SOURCE, 5, 42, 'stale')
                with self.assertRaises(ValueError): rs.export_slot_changes(source, {SOURCE: (5, 99)}, 'stale')
                for value in (-1, 2.5, rs.MAX_ITEM_AMOUNT + 1, float('nan')):
                    with self.assertRaises(ValueError): rs.export_slot(source, SOURCE, 5, value, digest)
                self.assertFalse((root/'exports').exists())
                # Unnamed facts keep the generic finite-value rules.
                rs.export_slot(source, artist.UNLOCKED_COUNT, 1, 1.5, digest)
                out = rs.export_slot(source, SOURCE, 5, rs.MAX_ITEM_AMOUNT, digest)
            self.assertEqual(rs.Save.read(out/source.name).facts[SOURCE][0], rs.MAX_ITEM_AMOUNT)

    def test_repeated_timestamp_gets_unique_folder(self):
        fixed = rs.datetime(2026, 1, 1, tzinfo=rs.timezone.utc)
        with tempfile.TemporaryDirectory() as directory, patch.object(rs, 'datetime') as clock:
            clock.now.return_value = fixed
            root = Path(directory); source = write_slot(root)
            with patch.object(rs, 'WORKSPACE', root):
                first = rs.export_slot(source, SOURCE, 5, 42)
                second = rs.export_slot(source, SOURCE, 5, 43)
            self.assertEqual(second.name, first.name + '-2')
            self.assertEqual(rs.Save.read(second/source.name).facts[SOURCE][0], 43)

    def test_manifests_list_only_real_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = write_slot(root)
            other = next(k for k in rs.IDENTIFIED_ITEMS if k != SOURCE)
            with patch.object(rs, 'WORKSPACE', root):
                out = rs.export_slot_changes(source, {SOURCE: (5, 42), other: (5, 5)})
            changes = json.loads((out/'edit-manifest.json').read_text())['changes']
            self.assertEqual([c['fact_id'] for c in changes], [f'{SOURCE:016x}'])

    def test_artist_export_refuses_noop_and_reports_actual_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Shield already owned and counts already 3: only Volatile Anomaly changes.
            numbers = {key: 5.0 for key in rs.IDENTIFIED_ITEMS}
            numbers.update({artist.UNLOCKED_COUNT: 3, artist.SELECTED_COUNT: 3})
            source = write_slot(root, fixture(numbers, {artist.BARRAGE: True, artist.SHIELD: True}))
            with patch.object(rs, 'WORKSPACE', root):
                out = artist.export(source)
                manifest = json.loads((out/'edit-manifest.json').read_text())
                self.assertEqual([c['ability'] for c in manifest['boolean_changes']], ['Volatile Anomaly'])
                self.assertEqual(manifest['numeric_changes'], [])
                write_slot(root, (out/source.name).read_bytes())
                with self.assertRaises(ValueError): artist.export(source)
            self.assertEqual(len(list((root/'exports').iterdir())), 1)


if __name__ == '__main__':
    unittest.main()
