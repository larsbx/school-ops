//! Black-box security/regression checks for the Rust-v2 draft session contract.
//! No real learner identifiers, outcomes or religious quotations are used.
use grade3_islamic_source_practice::{build, create_session, resume_session};
use rand::RngCore;
use std::{fs, path::PathBuf};

struct TestDir(PathBuf);

impl TestDir {
    fn new() -> Self {
        let mut nonce = [0u8; 16];
        rand::rngs::OsRng.fill_bytes(&mut nonce);
        let filename: String = nonce.iter().map(|b| format!("{b:02x}")).collect();
        Self(std::env::temp_dir().join(format!("school-ops-rust-v2-{filename}")))
    }
}

impl Drop for TestDir {
    fn drop(&mut self) {
        if self.0.exists() {
            fs::remove_dir_all(&self.0).expect("clean up ephemeral private test directory");
        }
    }
}

#[test]
fn new_session_keeps_private_seed_out_of_learner_surface() {
    let dir = TestDir::new();
    let session_id = "a".repeat(32);
    let manifest = create_session(&dir.0, &session_id).expect("create a distinct test session");
    let learner = fs::read_to_string(dir.0.join("learner.md")).unwrap();
    let teacher = fs::read_to_string(dir.0.join("teacher.md")).unwrap();
    assert!(!learner.contains(&session_id), "private replay nonce leaked to learner sheet");
    assert!(!learner.contains("## Task 1: record classifications"));
    assert!(teacher.contains(&session_id));
    assert!(teacher.contains("## Task 1: record classifications"));
    assert_eq!(manifest, resume_session(&dir.0).expect("unchanged saved form validates"));
    let built = build(&session_id).expect("deterministic private reconstruction");
    assert_eq!(learner, built.learner);
    assert_eq!(teacher, built.teacher);
}

#[test]
fn resume_is_read_only_and_fail_closed_on_missing_assets() {
    for victim in ["learner.md", "teacher.md", "manifest.json"] {
        let dir = TestDir::new();
        create_session(&dir.0, &"b".repeat(32)).unwrap();
        fs::remove_file(dir.0.join(victim)).unwrap();
        assert!(resume_session(&dir.0).is_err(), "accepted missing {victim}");
    }
}

#[test]
fn malformed_or_modified_session_is_rejected_without_rewriting() {
    for victim in ["learner.md", "teacher.md", "manifest.json"] {
        let dir = TestDir::new();
        create_session(&dir.0, &"c".repeat(32)).unwrap();
        let path = dir.0.join(victim);
        let mut bytes = fs::read(&path).unwrap();
        bytes.extend_from_slice(b"\nmodified after issue\n");
        fs::write(&path, &bytes).unwrap();
        assert!(resume_session(&dir.0).is_err(), "accepted modified {victim}");
        assert_eq!(fs::read(path).unwrap(), bytes, "resume rewrote modified {victim}");
    }
}

#[test]
fn refuse_existing_directory_without_replacing_keys() {
    let dir = TestDir::new();
    create_session(&dir.0, &"d".repeat(32)).unwrap();
    let before = fs::read(dir.0.join("manifest.json")).unwrap();
    assert!(create_session(&dir.0, &"e".repeat(32)).is_err());
    assert_eq!(fs::read(dir.0.join("manifest.json")).unwrap(), before);
}

#[cfg(unix)]
#[test]
fn private_permissions_and_symlinked_key_are_rejected() {
    use std::os::unix::fs::{symlink, PermissionsExt};

    let dir = TestDir::new();
    create_session(&dir.0, &"f".repeat(32)).unwrap();
    let mode_dir = fs::metadata(&dir.0).unwrap().permissions().mode() & 0o777;
    assert_eq!(mode_dir, 0o700);
    for filename in ["learner.md", "teacher.md", "manifest.json"] {
        let mode = fs::metadata(dir.0.join(filename)).unwrap().permissions().mode() & 0o777;
        assert_eq!(mode, 0o600, "insecure mode for {filename}");
    }
    let original = fs::read(dir.0.join("teacher.md")).unwrap();
    let key = dir.0.join("teacher.md");
    fs::remove_file(&key).unwrap();
    let copy = dir.0.join("teacher-copy.md");
    fs::write(&copy, original).unwrap();
    symlink(&copy, &key).unwrap();
    assert!(resume_session(&dir.0).is_err(), "accepted symlinked private key");
}
