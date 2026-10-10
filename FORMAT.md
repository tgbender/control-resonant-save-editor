# Observed save layout

All integers below are little-endian. This describes the supported layout, not a promise of compatibility with future patches.

The container begins with `RMDB`, u32 version 2, u32 version 2, and a u32 CRC32 over bytes 16 through EOF. Persistent-global data begins with u32 version 23 and u32 world-facts version 4.

A u32 count at offset 24 precedes numeric world facts: sorted pairs of u64 ID and f64 value. A second u32 count precedes Boolean facts: sorted pairs of u64 ID and u8 value (0 or 1). Unknown bytes following these tables are preserved verbatim by editors.

Fact IDs are CityHash64 of the UTF-8 internal record name, for example `wf_8c295bd55a687182` for Source. They are not hashes of the descriptive fact path. The supplied mapping files record the names and defaults needed by the editor. Absence and explicit false are distinct: absent flags use their asset-defined defaults.

The read-only progression inspector decodes the following tail prefix: active world level, unlocks schema version 1, counted graphs, and ability loadout schema version 1. Each graph has schema version 1, a u32 graph ID, a counted unlocked-node list, and a separate counted active-node list. Loadout entries are u32 slot/ability pairs. Graphs and abilities use 32-bit case-folded FNV-1a identifiers. An active graph node is not necessarily owned.

Cosmetic editing adds only mapped wardrobe ownership flags, rebuilds the sorted Boolean table and count, and updates the CRC32. Numeric editing changes existing values only. Ability exports additionally change selected/available boss-choice counts according to an inferred model. Unknown tail bytes are never reconstructed.

Raw archives, full strings, disassembly, real save fixtures, and session-specific research logs are intentionally absent from this source distribution.
