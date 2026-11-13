import Std

/-!
An abstract, executable release-admission and publication-order model.

Hashes, identities, signatures, TLS, and file-system observations are inputs.
The theorems do not establish cryptography, Python refinement, network freshness,
or Chrome enforcement. `Checks` is the exact eight-bit admission projection used
by release_core.publication_admitted; the verification runner exhausts all 256
Boolean assignments and the Python API's malformed-input boundary separately.
-/
namespace SchoolOps.Release

structure Checks where
  identity_ok : Bool
  version_ok : Bool
  zip_ok : Bool
  crx_ok : Bool
  signature_ok : Bool
  tls_ok : Bool
  manifest_ok : Bool
  download_ok : Bool
  deriving DecidableEq, Repr

def admitted (c : Checks) : Bool :=
  c.identity_ok && c.version_ok && c.zip_ok && c.crx_ok &&
  c.signature_ok && c.tls_ok && c.manifest_ok && c.download_ok

theorem admission_iff_all_checks (c : Checks) : admitted c = true ↔
    c.identity_ok = true ∧ c.version_ok = true ∧ c.zip_ok = true ∧
    c.crx_ok = true ∧ c.signature_ok = true ∧ c.tls_ok = true ∧
    c.manifest_ok = true ∧ c.download_ok = true := by
  simp [admitted, Bool.and_eq_true, and_assoc]

theorem wrong_id_rejected (c : Checks) (h : c.identity_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem unauthorized_version_rejected (c : Checks) (h : c.version_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem changed_zip_rejected (c : Checks) (h : c.zip_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem wrong_crx_fingerprint_rejected (c : Checks) (h : c.crx_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem invalid_signature_rejected (c : Checks) (h : c.signature_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem unverified_tls_rejected (c : Checks) (h : c.tls_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem missing_manifest_rejected (c : Checks) (h : c.manifest_ok = false) : admitted c = false := by
  simp [admitted, h]
theorem failed_download_rejected (c : Checks) (h : c.download_ok = false) : admitted c = false := by
  simp [admitted, h]

def allChecks : Checks := ⟨true, true, true, true, true, true, true, true⟩
def noChecks : Checks := ⟨false, false, false, false, false, false, false, false⟩

theorem all_checks_admitted : admitted allChecks = true := rfl
theorem absent_checks_rejected : admitted noChecks = false := rfl

/- `version` abstracts the validated four-component Chrome numeric ordering.
   `archiveHash` binds the complete prepared ZIP, including its configuration.
   `packageHash` is the pinned, independently verified CRX fingerprint. -/
structure Binding where
  extensionId : String
  archiveHash : String
  packageHash : String
  version : Nat
  updateURL : String
  packageURL : String
  deriving DecidableEq, Repr

def Authorized (plan : Binding) (previous : Option Binding) : Prop :=
  0 < plan.version ∧ match previous with
    | none => True
    | some prior => plan.extensionId = prior.extensionId ∧
        plan.updateURL = prior.updateURL ∧ prior.version < plan.version

instance (plan : Binding) (previous : Option Binding) : Decidable (Authorized plan previous) := by
  unfold Authorized
  cases previous <;> infer_instance

theorem update_preserves_identity (p old : Binding) (h : Authorized p (some old)) :
    p.extensionId = old.extensionId := h.2.1
theorem update_preserves_channel (p old : Binding) (h : Authorized p (some old)) :
    p.updateURL = old.updateURL := h.2.2.1
theorem update_strictly_increases_version (p old : Binding) (h : Authorized p (some old)) :
    old.version < p.version := h.2.2.2
theorem rollback_not_authorized (p old : Binding) (h : p.version ≤ old.version) :
    ¬ Authorized p (some old) := by
  intro accepted
  exact Nat.not_lt_of_ge h (update_strictly_increases_version p old accepted)
theorem same_version_not_authorized (p old : Binding) (h : p.version = old.version) :
    ¬ Authorized p (some old) := rollback_not_authorized p old (Nat.le_of_eq h)

structure State where
  plan : Binding
  previous : Option Binding
  signed : Bool
  uploaded : Bool
  activated : Bool
  verified : Bool
  interrupted : Bool
  lastChecks : Checks
  policyApplied : Bool
  managedEnforced : Bool
  deriving DecidableEq, Repr

def initial (p : Binding) (previous : Option Binding) : State :=
  ⟨p, previous, false, false, false, false, false, noChecks, false, false⟩

def sign (s : State) (candidate : Binding) (signatureOK : Bool) : State :=
  if s.interrupted = false ∧ Authorized s.plan s.previous ∧
      candidate = s.plan ∧ signatureOK = true then
    { s with signed := true }
  else s

def upload (s : State) (candidate : Binding) (bytesOK : Bool) : State :=
  if s.interrupted = false ∧ s.signed = true ∧ candidate = s.plan ∧ bytesOK = true then
    { s with uploaded := true }
  else s

def activate (s : State) (candidate : Binding) (predecessorOK : Bool) : State :=
  if s.interrupted = false ∧ s.uploaded = true ∧ candidate = s.plan ∧ predecessorOK = true then
    { s with activated := true }
  else s

def observe (s : State) (candidate : Binding) (checks : Checks) : State :=
  if s.interrupted = false ∧ s.activated = true ∧ candidate = s.plan ∧ admitted checks = true then
    { s with verified := true, lastChecks := checks }
  else { s with verified := false, lastChecks := checks }

def interrupt (s : State) : State := { s with interrupted := true, verified := false }
def recover (s : State) : State := { s with interrupted := false }

def Safe (p : Binding) (previous : Option Binding) (s : State) : Prop :=
  s.plan = p ∧ s.previous = previous ∧
  (s.signed = true → Authorized s.plan s.previous) ∧
  (s.uploaded = true → s.signed = true) ∧
  (s.activated = true → s.uploaded = true) ∧
  (s.verified = true → s.activated = true ∧ admitted s.lastChecks = true) ∧
  s.policyApplied = false ∧ s.managedEnforced = false

theorem initial_safe (p : Binding) (previous : Option Binding) : Safe p previous (initial p previous) := by
  simp [Safe, initial]

theorem sign_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (candidate : Binding) (signatureOK : Bool) (h : Safe p prev s) :
    Safe p prev (sign s candidate signatureOK) := by
  rcases h with ⟨hplan, hprev, hsig, hup, hact, hver, hpol, henf⟩
  unfold sign
  split <;> simp_all [Safe]

theorem upload_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (candidate : Binding) (bytesOK : Bool) (h : Safe p prev s) :
    Safe p prev (upload s candidate bytesOK) := by
  rcases h with ⟨hplan, hprev, hsig, hup, hact, hver, hpol, henf⟩
  unfold upload
  split <;> simp_all [Safe]

theorem activate_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (candidate : Binding) (predecessorOK : Bool) (h : Safe p prev s) :
    Safe p prev (activate s candidate predecessorOK) := by
  rcases h with ⟨hplan, hprev, hsig, hup, hact, hver, hpol, henf⟩
  unfold activate
  split <;> simp_all [Safe]

theorem observe_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (candidate : Binding) (checks : Checks) (h : Safe p prev s) :
    Safe p prev (observe s candidate checks) := by
  rcases h with ⟨hplan, hprev, hsig, hup, hact, hver, hpol, henf⟩
  unfold observe
  split <;> simp_all [Safe]

theorem interrupt_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (h : Safe p prev s) : Safe p prev (interrupt s) := by
  rcases h with ⟨hplan, hprev, hsig, hup, hact, hver, hpol, henf⟩
  simp_all [Safe, interrupt]

theorem recover_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (h : Safe p prev s) : Safe p prev (recover s) := by
  simpa [Safe, recover] using h

inductive Event where
  | sign (candidate : Binding) (signatureOK : Bool)
  | upload (candidate : Binding) (bytesOK : Bool)
  | activate (candidate : Binding) (predecessorOK : Bool)
  | observe (candidate : Binding) (checks : Checks)
  | interrupt
  | recover
  deriving Repr

def step (s : State) : Event → State
  | .sign c ok => sign s c ok
  | .upload c ok => upload s c ok
  | .activate c ok => activate s c ok
  | .observe c checks => observe s c checks
  | .interrupt => interrupt s
  | .recover => recover s

theorem every_step_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (event : Event) (h : Safe p prev s) : Safe p prev (step s event) := by
  cases event with
  | sign c ok => exact sign_preserves_safe p prev s c ok h
  | upload c ok => exact upload_preserves_safe p prev s c ok h
  | activate c ok => exact activate_preserves_safe p prev s c ok h
  | observe c checks => exact observe_preserves_safe p prev s c checks h
  | interrupt => exact interrupt_preserves_safe p prev s h
  | recover => exact recover_preserves_safe p prev s h

def run (s : State) (events : List Event) : State := events.foldl step s

theorem every_trace_preserves_safe (p : Binding) (prev : Option Binding) (s : State)
    (events : List Event) (h : Safe p prev s) : Safe p prev (run s events) := by
  induction events generalizing s with
  | nil => exact h
  | cons event rest ih =>
    exact ih (step s event) (every_step_preserves_safe p prev s event h)

theorem reachable_safe (p : Binding) (prev : Option Binding) (events : List Event) :
    Safe p prev (run (initial p prev) events) :=
  every_trace_preserves_safe p prev (initial p prev) events (initial_safe p prev)

theorem release_binding_immutable (p : Binding) (prev : Option Binding) (events : List Event) :
    (run (initial p prev) events).plan = p := (reachable_safe p prev events).1

theorem release_never_applies_policy (p : Binding) (prev : Option Binding) (events : List Event) :
    (run (initial p prev) events).policyApplied = false :=
  (reachable_safe p prev events).2.2.2.2.2.2.1

theorem release_never_claims_managed_enforcement (p : Binding) (prev : Option Binding) (events : List Event) :
    (run (initial p prev) events).managedEnforced = false :=
  (reachable_safe p prev events).2.2.2.2.2.2.2

theorem verified_implies_exact_observation (s : State) (candidate : Binding) (c : Checks)
    (h : (observe s candidate c).verified = true) :
    candidate = s.plan ∧ admitted c = true ∧ s.activated = true ∧ s.interrupted = false := by
  unfold observe at h
  split at h <;> simp_all

theorem failed_recheck_revokes_current_acceptance (s : State) (candidate : Binding) (c : Checks)
    (h : admitted c = false) : (observe s candidate c).verified = false := by
  simp [observe, h]

theorem substituted_binding_rejected (s : State) (candidate : Binding) (c : Checks)
    (h : candidate ≠ s.plan) : (observe s candidate c).verified = false := by
  simp [observe, h]

theorem activate_requires_uploaded (s : State) (candidate : Binding) (ok : Bool)
    (h : s.uploaded = false) : activate s candidate ok = s := by
  simp [activate, h]

theorem stale_predecessor_cannot_activate (s : State) (candidate : Binding) :
    activate s candidate false = s := by simp [activate]

theorem bad_package_cannot_upload (s : State) (candidate : Binding) :
    upload s candidate false = s := by simp [upload]

theorem bad_signature_cannot_sign (s : State) (candidate : Binding) :
    sign s candidate false = s := by simp [sign]

theorem sign_retry_idempotent (s : State) (candidate : Binding) (ok : Bool) :
    sign (sign s candidate ok) candidate ok = sign s candidate ok := by
  unfold sign
  split <;> simp_all

theorem upload_retry_idempotent (s : State) (candidate : Binding) (ok : Bool) :
    upload (upload s candidate ok) candidate ok = upload s candidate ok := by
  unfold upload
  split <;> simp_all

theorem activation_retry_idempotent (s : State) (candidate : Binding) (ok : Bool) :
    activate (activate s candidate ok) candidate ok = activate s candidate ok := by
  unfold activate
  split <;> simp_all

theorem observation_retry_idempotent (s : State) (candidate : Binding) (c : Checks) :
    observe (observe s candidate c) candidate c = observe s candidate c := by
  unfold observe
  split <;> simp_all

theorem recovery_preserves_staged_content (s : State) :
    (recover (interrupt s)).plan = s.plan ∧
    (recover (interrupt s)).signed = s.signed ∧
    (recover (interrupt s)).uploaded = s.uploaded ∧
    (recover (interrupt s)).activated = s.activated := by
  simp [recover, interrupt]

theorem recovery_requires_new_observation (s : State) :
    (recover (interrupt s)).verified = false := rfl

theorem interrupted_cannot_publish (s : State) (candidate : Binding) (ok : Bool) :
    activate (interrupt s) candidate ok = interrupt s := by
  simp [activate, interrupt]

theorem interrupted_cannot_verify (s : State) (candidate : Binding) (checks : Checks) :
    (observe (interrupt s) candidate checks).verified = false := by
  simp [observe, interrupt]

end SchoolOps.Release
