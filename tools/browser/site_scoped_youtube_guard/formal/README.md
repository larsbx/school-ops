# Self-hosted release verification

This layer verifies the release admission rule and an abstract publication state
machine. It runs without signing credentials, an HTTPS endpoint, administrator
rights, or a managed device. Concrete CRX parsing, signatures, TLS downloads,
wizard integration and interrupted file publication have separate Python
acceptance tests.

## Reproduce the checks

Use the pinned toolchains: **Lean 4.19.0** from [lean-toolchain](lean-toolchain)
and **Quint 0.33.1** from the committed npm lockfile. Lean imports only `Std`;
there is no mathlib download. The Quint runner uses its TypeScript evaluator,
so this check does not require Apalache, Java, Docker, or the Quint Rust backend.

From this directory:

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 verify.py
```

`verify.py --lake /absolute/path/to/lake` supports a standalone Lean installation.
`--output-dir` selects the directory for logs, negative-control traces and
`verification.json`; the default `verification-output/` is ignored by Git.
The runner checks tool versions, cleans the Lean build, rebuilds the current
sources, audits the compiled theorem dependencies, and records the source hashes
in its receipt. Its commands do not publish an extension or change policy.

## What is established

[Release.lean](Release.lean) contains **44 registered theorem declarations**.
The committed [obligation inventory](proof-obligations.json) and
[compiled axiom audit](Audit.lean) must cover exactly the same declarations.
The current proofs use only Lean's propositional extensionality axiom
(`propext`); the runner rejects any additional axiom, a missing audit entry, or
a proof placeholder.

| Obligation | Established property |
| --- | --- |
| Publication admission | Every one of the eight required observations must succeed. Wrong identity, unauthorized version, changed ZIP, different CRX fingerprint, bad signature, unverified TLS, a missing manifest or a failed download refuses admission. |
| Prior release | An update preserves the signing identity and update channel and strictly increases the abstract numeric version. Equal versions and rollbacks are refused. |
| Binding | All traces preserve the expected ID, prepared archive fingerprint, signed package fingerprint, version and endpoints. |
| Publication ordering | Signing verification precedes package staging; package staging precedes manifest activation. An invalid predecessor observation cannot activate a new manifest. |
| Retries | Repeating signing verification, package staging, manifest activation, or an identical publication observation is idempotent. |
| Interruption and recovery | Interruption prevents new activation or successful verification. Recovery preserves already staged content and requires a new observation before restoring current acceptance. |
| Rechecking | A failed verification observation clears acceptance in the model; a previous successful observation cannot make a failed recheck pass. |
| Authority boundary | No trace applies enterprise policy or establishes managed-device enforcement. |

The all-trace theorem is proved by induction over an arbitrary list of model
events. It is not restricted to the finite Quint examples.

## Independent bounded model

[release.qnt](release.qnt) implements the transitions independently. Its supplied
finite domain uses one update from abstract version 1 to version 2, the expected
binding and six individual field substitutions, both truth values for signing,
package and predecessor observations, and ten admission masks. These masks
include success, no observations, and each single failed observation.

The evaluator constructs the complete successor set and repeatedly expands it.
It then checks **both** that the reached set is closed under every supplied
transition and that every reached state satisfies the safety predicate. The
current fixed point contains **81 states**. A closure failure fails the runner;
the iteration count alone is never reported as exhaustive verification.

Eight named executable scenarios cover successful publication, interruption
before activation, interruption after a successful check, failed rechecking,
invalid prior versions/identity/channel, retries, binding substitutions and the
full guard truth table.

Two deliberately unsafe transitions must produce actual invariant violations:

- Activating a manifest before its package exists.
- Accepting a publication while the manifest observation is false.

The runner checks the resulting ITF witness states, not merely the checker's
nonzero exit code. Three additional Lean controls require refusal of a false
proposition, an injected axiom and a proof placeholder.

## Runtime connection and limits

The runtime's [`publication_admitted`](../release_core.py) function uses exactly
the eight named Boolean observations. The runner evaluates **all 256 Boolean
assignments** in Python and Lean and compares them with Quint's complete accepted
mask set. It also refuses 53 malformed Python inputs, including missing/extra
fields and truthy values that are not the Boolean `True`. External callers
supplying eight true flags do not establish any release evidence: the concrete
verifier must compute the observations itself.

This is a complete comparison for that small admission function. It is **not** a
proof that Python's CRX parser, OpenSSL integration, URL parser, TLS stack,
filesystem operations or wizard implement the entire state machine. The model
uses abstract identifiers and hashes, trusts its signature/TLS/file observations,
and represents validated Chrome version ordering by natural numbers. It does
not prove cryptographic security, hash collision resistance, the numeric version
encoding, operating-system durability, concurrent publisher coordination,
Chrome installation, or ongoing remote availability.

The initial-release branch represents an explicitly selected initial release;
it is not permission to omit a known predecessor. The state model starts with a
fixed candidate package fingerprint, so it describes publication once signing
has produced that candidate. It does not prove deterministic cryptographic
signing. A successful HTTPS observation is evidence about the bytes returned
during that check, not a guarantee that the endpoint will keep serving them.
Safety is established under the stated abstract observations; liveness and
eventual successful publication are not claimed.
