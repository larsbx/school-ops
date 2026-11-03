# Generate Unit 2 learner practice

Draft. From the repository root, start a new session in a new private directory:

```sh
python -m exercise_bank.unit2 new /tmp/unit2-first --activity composition --limit 20
python -m exercise_bank.unit2 resume /tmp/unit2-first
```

Choose the taught limit (10 or 20) and activity: entry, composition, difference, stories,
parity or check. Use a new directory for each new session. A fresh random seed
resamples the form; individual items can recur. Resume reads the saved session
and restores its exact prompts. It does not store learner responses or progress;
retain any working paper privately. Existing directories are never overwritten.

Distribute only the generated learner sheet. Keep the teacher key and session
manifest private. Use `resume DIRECTORY --teacher` to recover the matching key.
Worked teaching demonstrations in the lesson plans are examples, not the session
question bank. Review generated forms for suitability and prior exposure before use.
