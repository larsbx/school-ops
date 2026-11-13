// Executable abstraction; signatures/TLS/hashes are checker observations.
// No operation changes enterprise policy or establishes device enforcement.
module release {
  type Checks = { identity_ok: bool, version_ok: bool, zip_ok: bool, crx_ok: bool,
    signature_ok: bool, tls_ok: bool, manifest_ok: bool, download_ok: bool }
  pure def admitted(c: Checks): bool = c.identity_ok and c.version_ok and
    c.zip_ok and c.crx_ok and c.signature_ok and c.tls_ok and c.manifest_ok and c.download_ok
  pure def bit(mask: int, shift: int): bool = (mask / (2^shift)) % 2 == 1
  pure def checks(mask: int): Checks = {
    identity_ok: bit(mask, 0), version_ok: bit(mask, 1), zip_ok: bit(mask, 2),
    crx_ok: bit(mask, 3), signature_ok: bit(mask, 4), tls_ok: bit(mask, 5),
    manifest_ok: bit(mask, 6), download_ok: bit(mask, 7) }
  pure val acceptedMasks = 0.to(255).filter(mask => admitted(checks(mask)))

  // Integer version is a projection of the validated Chrome version ordering.
  type Binding = { identity: int, archive: int, package: int, version: int,
    updateURL: int, packageURL: int }
  pure val expected = { identity: 1, archive: 1, package: 1, version: 2,
    updateURL: 1, packageURL: 1 }
  pure val previous = expected.with("version", 1).with("archive", 0).with("package", 0)
  pure def authorized(plan: Binding, prior: Binding): bool = plan.version > 0 and
    plan.identity == prior.identity and plan.updateURL == prior.updateURL and prior.version < plan.version
  pure val candidates = Set(expected, expected.with("identity", 0),
    expected.with("archive", 0), expected.with("package", 0), expected.with("version", 1),
    expected.with("updateURL", 0), expected.with("packageURL", 0))
  // The full admission truth table is separately exhausted above. For state
  // exploration retain all eight single-check failures, plus empty/success.
  pure val masks = Set(0, 255, 254, 253, 251, 247, 239, 223, 191, 127)
  type State = { plan: Binding, prior: Binding, signed: bool, uploaded: bool,
    activated: bool, verified: bool, interrupted: bool, lastMask: int,
    policyApplied: bool, managedEnforced: bool }
  pure val initial = { plan: expected, prior: previous, signed: false, uploaded: false,
    activated: false, verified: false, interrupted: false, lastMask: 0,
    policyApplied: false, managedEnforced: false }
  pure def sign(s: State, candidate: Binding, signatureOK: bool): State =
    if (not(s.interrupted) and authorized(s.plan, s.prior) and candidate == s.plan and signatureOK)
      s.with("signed", true) else s
  pure def upload(s: State, candidate: Binding, bytesOK: bool): State =
    if (not(s.interrupted) and s.signed and candidate == s.plan and bytesOK)
      s.with("uploaded", true) else s
  pure def activate(s: State, candidate: Binding, predecessorOK: bool): State =
    if (not(s.interrupted) and s.uploaded and candidate == s.plan and predecessorOK)
      s.with("activated", true) else s
  pure def observe(s: State, candidate: Binding, mask: int): State =
    s.with("lastMask", mask).with("verified",
      not(s.interrupted) and s.activated and candidate == s.plan and admitted(checks(mask)))
  pure def interrupt(s: State): State = s.with("interrupted", true).with("verified", false)
  pure def recover(s: State): State = s.with("interrupted", false)
  pure def safe(s: State): bool = s.plan == expected and s.prior == previous and
    (not(s.signed) or authorized(s.plan, s.prior)) and
    (not(s.uploaded) or s.signed) and (not(s.activated) or s.uploaded) and
    (not(s.verified) or (s.activated and admitted(checks(s.lastMask)))) and
    not(s.policyApplied) and not(s.managedEnforced)

  // Exact finite successor set, not random sampling. A fixed point and safety
  // on that fixed point jointly certify all reachable states in this model.
  pure def successors(s: State): Set[State] = candidates.fold(
    Set(s, interrupt(s), recover(s)), (out, candidate) =>
      masks.fold(out.union(Set(sign(s, candidate, true), sign(s, candidate, false),
        upload(s, candidate, true), upload(s, candidate, false),
        activate(s, candidate, true), activate(s, candidate, false))),
        (more, mask) => more.union(Set(observe(s, candidate, mask)))))
  pure def expand(known: Set[State]): Set[State] =
    known.fold(known, (out, s) => out.union(successors(s)))
  pure val reach1 = expand(Set(initial))
  pure val reach2 = expand(reach1)
  pure val reach3 = expand(reach2)
  pure val reach4 = expand(reach3)
  pure val reach5 = expand(reach4)
  pure val reach6 = expand(reach5)
  pure val reach7 = expand(reach6)
  pure val reach8 = expand(reach7)
  pure val exhaustiveClosed = reach8 == expand(reach8)
  pure val exhaustiveSafe = reach8.forall(s => safe(s))
  pure val exhaustiveCount = reach8.size()

  var s: State
  action init = s' = initial
  action signStep = { nondet candidate = candidates.oneOf(); nondet ok = Set(false, true).oneOf(); s' = sign(s, candidate, ok) }
  action uploadStep = { nondet candidate = candidates.oneOf(); nondet ok = Set(false, true).oneOf(); s' = upload(s, candidate, ok) }
  action activateStep = { nondet candidate = candidates.oneOf(); nondet ok = Set(false, true).oneOf(); s' = activate(s, candidate, ok) }
  action observeStep = { nondet candidate = candidates.oneOf(); nondet mask = masks.oneOf(); s' = observe(s, candidate, mask) }
  action interruptStep = s' = interrupt(s)
  action recoverStep = s' = recover(s)
  action step = any { signStep, uploadStep, activateStep, observeStep, interruptStep, recoverStep }
  val safety = safe(s)

  // Explicit guard-removal mutants. The verification runner REQUIRES both
  // unsafe controls to violate safety and checks a concrete witness trace.
  action unsafeManifestFirst = s' = s.with("activated", true)
  action unsafeAcceptMissingManifest = s' = s.with("verified", true).with("lastMask", 191)
  action mutantManifestStep = any { step, unsafeManifestFirst }
  action mutantAcceptanceStep = any { step, unsafeAcceptMissingManifest }

  run normalReleaseTest = init.then(s' = sign(s, expected, true))
    .then(s' = upload(s, expected, true)).then(s' = activate(s, expected, true))
    .then(s' = observe(s, expected, 255)).expect(s.verified and safety)
  run interruptedReleaseRecoveryTest = init.then(s' = sign(s, expected, true))
    .then(s' = upload(s, expected, true)).then(interruptStep)
    .then(s' = activate(s, expected, true)).expect(not(s.activated) and s.uploaded)
    .then(recoverStep).then(s' = activate(s, expected, true))
    .then(s' = observe(s, expected, 255)).expect(s.verified and safety)
  run interruptedAcceptedObservationTest = init.then(s' = sign(s, expected, true))
    .then(s' = upload(s, expected, true)).then(s' = activate(s, expected, true))
    .then(s' = observe(s, expected, 255)).then(interruptStep).then(recoverStep)
    .expect(s.activated and s.uploaded and not(s.verified) and safety)
  run failedRecheckTest = init.then(s' = sign(s, expected, true))
    .then(s' = upload(s, expected, true)).then(s' = activate(s, expected, true))
    .then(s' = observe(s, expected, 255)).then(s' = observe(s, expected, 127))
    .expect(not(s.verified) and safety)
  run malformedVersionsTest = init.expect(
    not(authorized(expected.with("version", 0), previous)) and
    not(authorized(expected.with("version", 1), previous)) and
    not(authorized(expected.with("identity", 0), previous)) and
    not(authorized(expected.with("updateURL", 0), previous)))
  run retriesTest = init.then(s' = sign(s, expected, true))
    .then(s' = upload(s, expected, true)).then(s' = activate(s, expected, true))
    .then(s' = observe(s, expected, 255)).expect(
      sign(s, expected, true) == s and upload(s, expected, true) == s and
      activate(s, expected, true) == s and observe(s, expected, 255) == s)
  run substitutedBindingsTest = init.then(s' = sign(s, expected, true))
    .then(s' = upload(s, expected, true)).then(s' = activate(s, expected, true))
    .expect(candidates.exclude(Set(expected)).forall(c => not(observe(s, c, 255).verified)))
  run guardTruthTableTest = init.expect(0.to(255).forall(mask => admitted(checks(mask)) == (mask == 255)))
}
