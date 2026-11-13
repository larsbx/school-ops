# Ratio Loading Bay · Factorio practice pilot

- Status: draft guided practice. Curriculum scope and classroom use await review.
- Source activity: `L-FACTORIO-RATIO-01`.
- Resource: [R-FACTORIO-002](../../../../resources/r-factorio-002.md).
- Proposed audience: Grade 6. The pilot supports the [Compare ratios and rates investigation](../../../scaffolds/grade-6/mathematics.md). Course, unit and outcome IDs are unassigned.

**Entry check.** Ask the learner to build two groups each containing two iron
and three copper counters, report the totals, and transfer items between two
in-game chests. If grouping needs support, model one group, make a second with
the learner, and recheck with three groups. Demonstrate the controls or use
counters or a table for the teacher-led practice.

| Proposed objective | Learner task | Teacher review |
| --- | --- | --- |
| Read and represent an ordered ratio (grammar) | Label iron and copper in the order 2:3. Record iron, copper and total in a table. | Check the order and units. Each group contains five plates. |
| Scale both terms by a common factor (logic) | Load 15 plates in the requested ratio. Compare 4 iron and 6 copper with 5 iron and 10 copper. | 6 iron and 9 copper use three groups and meet the total. 4:6 preserves the ratio with a total of 10. 5:10 meets the total of 15 with a different ratio. |
| Explain equivalent ratios (rhetoric) | Explain the load to a partner using a table, drawing, counters or speech. | Look for one multiplier applied to both quantities and an independent check of the shipment total. |

Arithmetic is the primary Quadrivium art. If the learner scales only one
quantity, regroup both colors together and ask for a new example. The game
checks the inventory and a selected explanation. The teacher reviews the
learner's reasoning during guided practice.

## Receipt acceptance

Follow the [upstream review procedure](https://github.com/larsbx/factorio-mods/blob/d39bda5e9c99f3de5d66f282c54018dfba5bcbf3/docs/ratio-loading-bay-review.md)
in a disposable save. After completion, export the receipt and run these
commands from the SchoolOps checkout.

```sh
python3 tools/factorio_practice.py /path/to/script-output/schoolops/ratio-loading-bay.json
python3 -m unittest discover -s tests -p test_factorio_practice.py -v
```

The inspector matches the entire receipt to [activity.json](activity.json).
A recognized receipt yields an unverified practice completion claim for staff
review. The file is editable and replayable. Teacher review of reasoning,
accessibility and classroom suitability is pending. Keep private teaching
observations in the school's authorized workflow. Inspection creates no
identity link, assignment, learner record, grade or mastery outcome.

The [smelting pilot](../README.md) accepts its legacy `0.2.0` and current `0.3.0`
receipts. The current smelting mapping was added after inspecting the exact
receipt exported by the actual engine's disposable save/reload acceptance.
Ratio Loading Bay accepts exactly `0.3.0`; other versions remain unsupported.

The [automated compatibility workflow](../../../../docs/factorio-automation.md)
repeats runtime and receipt checks and prepares a review package.
