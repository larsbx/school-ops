# From ore to plate · Factorio practice pilot

- Status: draft. Audience and access review pending.
- Source activity: `L-FACTORIO-SMELTING-01`. This pilot has no canonical course, unit, or outcome assignment.
- Resource: [R-FACTORIO-001](../../../resources/r-factorio-001.md).
- Time: 10–15 minutes, with breaks or a longer run as needed.

**Entry check.** Ask the learner to count three objects, open an in-game inventory,
and place an object. Demonstrate controls or offer an oral or physical model when
needed. The pilot practices one-to-one counting in a process.

| Stage | Learner task | Staff check |
| --- | --- | --- |
| Build and observe | Place and fuel a stone furnace; put in two iron ore and observe two plates. | Ask the learner to point to ore, fuel and output. |
| Predict | Predict the output from three pieces of iron ore with enough fuel. | Three plates, with one plate paired to each piece of ore. |
| Name and explain | Identify the material input and explain how to predict the output to a partner. | Iron ore is the material input; coal supplies energy. Accept oral, drawn or object-based explanations. |

Arithmetic is the primary Quadrivium art. Grammar names the process parts,
logic uses one-to-one correspondence, and rhetoric explains the prediction.
If the explanation is incomplete, model two pairs with counters and ask for a
new prediction with three. The game checks production and two questions.
Staff can observe the explanation separately.

## Practice receipt

Follow the [Factorio guide](https://github.com/larsbx/factorio-mods/pull/6) in a
fresh local save. After finishing, choose **Export SchoolOps practice receipt**.
In a SchoolOps checkout, inspect that file locally:

```sh
python3 tools/factorio_practice.py /path/to/script-output/schoolops/from-ore-to-plate.json
python3 -m unittest discover -s tests -p test_factorio_practice.py
```

The inspector reads the receipt and checks the activity mapping in [activity.json](activity.json).
Its result is a self-reported practice claim for staff review. It creates no
assignment, identity link, grade or learner record. A receipt can be edited or
replayed. For this pilot, keep any private teaching observations in the school's
existing authorized workflow, outside the public curriculum repository and game.
The Biz-kit SchoolOps catalog and private learner workflow are outside this
offline pilot.

Khan Academy and Membean interfaces in the mod currently use original synthetic
items. This pilot has no provider sign-in or reporting.
