# Factory Supply Order · original Factorio guided practice pilot

- **Status:** draft, not approved for classroom use or canonical course inclusion.
- **Original activity:** `L-FACTORIO-SUPPLY-01`, in [Factorio PR #8](https://github.com/larsbx/factorio-mods/pull/8).
- **Provisional internal resource:** [R-FACTORIO-003](../../../../resources/r-factorio-003.md).
- **Intended setting:** upper-elementary arithmetic and vocabulary, with grade placement and accessibility pending teacher review. This does not add to, copy, or assume completion of Grade 2 coursework.

**Entry checks:** Ask the learner to count 17 counters, make three equal groups of four, and identify which five counters are unassigned. Confirm they can move items between chests and distinguish three separate crates. If not, model one transfer and check independently. These are proposed readiness checks, not prior mastery records.

| Trivium | World action / reasoning | Separate teacher review |
| --- | --- | --- |
| Grammar | Identify *crate*, *stock*, *shipment*, *reserve* and accurately label the four distinct chests. | Have the learner explain why reserve means unshipped stock. |
| Logic | Move 4 iron plates into **each** of three distinct steel crates and retain 5 in the separate wooden reserve chest, with 17 initially supplied. | Independently verify `3 × 4 = 12` and `17 − 12 = 5` with equal groups and a subtraction check. |
| Rhetoric | Describe the allocation using a spoken explanation, table, drawing or counters. | Look for all three distinct groups, the five held back, and an intelligible conservation argument. |

**Quadrivium:** Arithmetic is the genuine connection. Geometry, music and astronomy mastery are not asserted.

The mod uses actual Factorio inventory counts; the answer choices alone cannot complete the in-world task. Negative cases include unevenly loaded crates, unrelated items, incorrect reserve count and removing plates after completion but before export. Content/build-bound checkpoints reset on mismatch. A reset does not mint new stock, and a missing saved chest blocks reissuance.

## Draft receipt classification

The local inspector accepts **only** the exact four-field claim in [activity.json](activity.json), using the already-defined `schoolops.factorio.practice.v1` schema. The producer path is `script-output/schoolops/factory-supply-order.json`.

```sh
python3 tools/factorio_practice.py /path/to/script-output/schoolops/factory-supply-order.json
python3 -m unittest discover -s tests -p test_factorio_practice.py -v
```

This metadata registration **does not prove** the game produced the receipt. The existing compatibility lock still selects Factorio PR #7 and currently verifies the earlier smelting and Ratio Loading Bay receipts only. A later exact-head candidate run must prove producer runtime, save/reload, genuine exported bytes and SchoolOps classification before a new compatibility pin is accepted. Do not treat a synthetic fixture as engine evidence.

The receipt is unsigned, editable and replayable. Successful inspection returns `unverified_practice_completion_claim`, *not* assignment completion, grade, learner record, provider mastery or authenticated teacher evidence. No actual learner names, credentials, private observations, account or provider content are included. Both original exercise and written content remain draft pending owner pedagogy, accessibility and class acceptance. A manifest does not authorize reuse of outside content.
