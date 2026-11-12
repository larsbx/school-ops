# Verify the release model

Use Lean 4.19.0 and the pinned Quint dependency. Run here:

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 verify.py
```

1. **Read the receipt** in `verification-output/verification.json`. Check
   the Lean theorem inventory and axiom audit, Quint's reached states and
   closure check, and the negative controls.
2. **Check the runtime comparison.** Review all 256 Boolean admission inputs
   across Python, Lean and Quint.
3. **Run concrete acceptance** for CRX signing, HTTPS, interrupted publication
   and device behavior. The proofs cover the abstract release model and
   Boolean admission rule. [Release guide](../RELEASE.md)

[Proof obligations, runner options and model limits](../.llm.txt)
