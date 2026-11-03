//! Draft source-metadata exercise generation, without copied scripture or hadith.
//! Rust v2 forms are intentionally NOT binary-compatible with the archived Python v1.
//! A learner form never exposes the private 128-bit session nonce.

use rand::{rngs::OsRng, seq::SliceRandom, RngCore, SeedableRng};
use rand_chacha::ChaCha20Rng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::error::Error;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::Path;

pub const VERSION: &str = "g3-is-source-metadata-rust-v2";
pub type Result<T> = std::result::Result<T, Box<dyn Error>>;

const NAMES: &[&str] = &["Hana", "Samir", "Laila", "Yusuf", "Mariam", "Zayd"];
const OBJECTS: &[&str] = &["notebook", "ruler", "pencil", "folder", "book", "card"];
const PLACES: &[&str] = &["shelf", "desk", "table", "drawer", "box", "bag"];
const TEACHER_NOTES: &[&str] = &[
    "A locator points to a record.",
    "A summary is not exact source wording.",
    "Source labels help us look up claims.",
];

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Card {
    pub id: String,
    pub text: String,
    pub kind: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Payload {
    pub schema: u8,
    pub version: String,
    pub status: String,
    pub session_id: String, // PRIVATE: do not include this nonce on the learner sheet.
    pub records: Vec<Card>,
    pub claims: Vec<Card>,
    pub learner_sha256: String,
    pub teacher_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Manifest {
    #[serde(flatten)]
    pub payload: Payload,
    pub form_id: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Form {
    pub learner: String,
    pub teacher: String,
    pub manifest: Manifest,
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    let result = Sha256::digest(bytes);
    let mut digest = [0_u8; 32];
    digest.copy_from_slice(&result);
    digest
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8] = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for &value in bytes {
        result.push(DIGITS[(value >> 4) as usize] as char);
        result.push(DIGITS[(value & 0x0f) as usize] as char);
    }
    result
}

// serde_json Value uses lexicographically sorted keys without preserve_order.
// Hash canonical UTF-8 JSON + LF, not a platform-dependent pretty rendering.
fn canonical<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let value = serde_json::to_value(value)?;
    let mut bytes = serde_json::to_vec(&value)?;
    bytes.push(b'\n');
    Ok(bytes)
}

fn error(message: &'static str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}

fn choice<'a>(rng: &mut ChaCha20Rng, choices: &'a [&'a str]) -> &'a str {
    choices.choose(rng).expect("nonempty built-in choices")
}

fn descriptions() -> [(&'static str, &'static str); 5] {
    [
        ("quran_locator", "Qur'anic passage locator"),
        ("translation_metadata", "Translation metadata without words"),
        ("teacher_explanation", "Teacher-created explanation"),
        ("hadith_locator", "Hadith collection/report locator"),
        ("fictional_note", "Invented classroom note"),
    ]
}

fn claim_descriptions() -> [(&'static str, &'static str); 4] {
    [
        ("fictional_quote", "Quotation from a fictional diary"),
        ("teacher_comment", "Teacher explanation"),
        ("cautious_inference", "Qualified learner inference"),
        ("unsupported_claim", "Unsupported historical/authenticity claim"),
    ]
}

/// Deterministic, source-safe form construction. This is an authoring prototype,
/// NOT proof of religious correctness, educational validity, or balanced difficulty.
pub fn build(session_id: &str) -> Result<Form> {
    if session_id.len() != 32
        || !session_id
            .as_bytes()
            .iter()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(b))
    {
        return Err(error("expected 32 lowercase hex digits for private session nonce").into());
    }
    let seed = sha256(format!("{VERSION}:{session_id}").as_bytes());
    let public_tag = hex(&sha256(format!("public:{VERSION}:{session_id}").as_bytes()))[..12]
        .to_uppercase();
    let mut rng = ChaCha20Rng::from_seed(seed);

    let name = choice(&mut rng, NAMES);
    let object = choice(&mut rng, OBJECTS);
    let place = choice(&mut rng, PLACES);
    let note = choice(&mut rng, TEACHER_NOTES);

    let mut entries: Vec<(&str, String)> = vec![
        (
            "quran_locator",
            "Qur'an, sūrah 49, āyah 13. Arabic wording and English text not included."
                .to_string(),
        ),
        (
            "translation_metadata",
            format!(
                "Translation file {public_tag}: passage 49:13; translator and edition not selected; English wording absent."
            ),
        ),
        (
            "teacher_explanation",
            format!("Classroom author: teacher. Original note: '{note}'"),
        ),
        (
            "hadith_locator",
            "Collection: Sahih al-Bukhari; report 8. Text and independent chain study absent."
                .to_string(),
        ),
        (
            "fictional_note",
            format!("Fictional note {public_tag}: {name} placed a {object} on a {place}."),
        ),
    ];
    entries.shuffle(&mut rng);
    let records: Vec<Card> = entries
        .into_iter()
        .enumerate()
        .map(|(i, (kind, text))| Card {
            id: ((b'A' + i as u8) as char).to_string(),
            text,
            kind: kind.to_string(),
        })
        .collect();

    let mut claims: Vec<(&str, String)> = vec![
        (
            "fictional_quote",
            format!("Invented diary {public_tag} directly says '{name} saw a {object}.'"),
        ),
        (
            "teacher_comment",
            "A teacher note says: 'We must check which source words are supplied.'".into(),
        ),
        (
            "cautious_inference",
            format!(
                "{name} suggests: 'The missing translator field means I cannot quote that translation.'"
            ),
        ),
        (
            "unsupported_claim",
            "A student says: 'The number of a hadith report by itself proves a precise Hijrah route and independently authenticates every narrator.'".into(),
        ),
    ];
    claims.shuffle(&mut rng);
    let claims: Vec<Card> = claims
        .into_iter()
        .enumerate()
        .map(|(i, (kind, text))| Card {
            id: format!("T{}", i + 1),
            text,
            kind: kind.to_string(),
        })
        .collect();

    let mut learner = vec![
        "# Grade 3 source-literacy practice — NEW draft session".to_string(),
        String::new(),
        format!("- Public form reference: {public_tag}"),
        "- Status: unapproved educational practice, **not** a Qur'an or hadith text.".into(),
        "- No named translator, copied scripture, authenticated report, or actual Hijrah route appears here.".into(),
        "- You may answer orally, on paper, by pointing or AAC. No devotional or personal questions.".into(),
        String::new(),
        "## Record cards".into(),
        String::new(),
        "| Card | Original learning record |".into(),
        "| --- | --- |".into(),
    ];
    for card in &records {
        learner.push(format!("| {} | {} |", card.id, card.text));
    }
    learner.extend([
        "".into(),
        "## Task 1 (G3-IS-P1)".into(),
        "".into(),
        "For each record card, classify it as Qur'an locator, missing-translation metadata, teacher explanation, hadith locator or fictional note. Use each type once.".into(),
        "".into(),
        "## Task 2 (G3-IS-P1)".into(),
        "".into(),
        "Identify the sūrah and āyah of the Qur'an locator, the collection and number of the hadith locator, and explain why the translator's wording remains unknown.".into(),
        "".into(),
        "## Claim cards".into(),
        "".into(),
        "| Card | Original exercise statement |".into(),
        "| --- | --- |".into(),
    ]);
    for card in &claims {
        learner.push(format!("| {} | {} |", card.id, card.text));
    }
    learner.extend([
        "".into(),
        "## Task 3 (G3-IS-P2)".into(),
        "".into(),
        "Classify each T-card as quotation of a fictional diary, teacher explanation, qualified learner inference, or unsupported historical/authenticity claim.".into(),
        "".into(),
        "## Task 4 (G3-IS-P2)".into(),
        "".into(),
        "Explain which statement cannot be justified from a report number alone; also explain why missing translator metadata cannot establish exact English words.".into(),
        "".into(),
        "These cards are original educational fiction and metadata, never primary source words.".into(),
        "".into(),
    ]);

    let mut teacher = vec![
        "# Teacher key — keep separate from learner materials".to_string(),
        String::new(),
        format!("- Private session reference: {session_id}"),
        "- Draft evidence only; no automated religious/source approval or learner grading.".into(),
        String::new(),
        "## Task 1: record classifications".into(),
        String::new(),
    ];
    for card in &records {
        let (_, desc) = descriptions()
            .into_iter()
            .find(|(kind, _)| *kind == card.kind)
            .expect("one of five source types");
        teacher.push(format!("- {}: {desc}", card.id));
    }
    teacher.extend([
        "".into(),
        "## Task 2: lookup and uncertainty".into(),
        "".into(),
        "- Qur'an reference: sūrah 49, āyah 13.".into(),
        "- Hadith reference: Sahih al-Bukhari, report 8.".into(),
        "- No chosen translator, edition or English wording supplied. Report number is not authentication.".into(),
        "".into(),
        "## Task 3: claim classifications".into(),
        "".into(),
    ]);
    for card in &claims {
        let (_, desc) = claim_descriptions()
            .into_iter()
            .find(|(kind, _)| *kind == card.kind)
            .expect("one of four claim types");
        teacher.push(format!("- {}: {desc}", card.id));
    }
    teacher.extend([
        "".into(),
        "## Task 4: model rationale".into(),
        "".into(),
        "- The unsupported claim confuses report metadata with historical evidence and chain review.".into(),
        "- Translation metadata lacking translator/edition/words cannot establish an exact quotation.".into(),
        "- **G3-IS-P1**: 4/5 type labels and both locators. Correct false sacred attribution.".into(),
        "- **G3-IS-P2**: 3/4 claim labels, rejects unsupported claim, and states missing translation words.".into(),
        "- Human teacher judges reasoning; do not infer mastery or assess personal faith or worship.".into(),
        "".into(),
    ]);
    let learner = learner.join("\n");
    let teacher = teacher.join("\n");

    let payload = Payload {
        schema: 2,
        version: VERSION.to_string(),
        status: "draft-not-ready".into(),
        session_id: session_id.into(),
        records,
        claims,
        learner_sha256: hex(&sha256(learner.as_bytes())),
        teacher_sha256: hex(&sha256(teacher.as_bytes())),
    };
    let form_id = hex(&sha256(&canonical(&payload)?));
    Ok(Form {
        learner,
        teacher,
        manifest: Manifest { payload, form_id },
    })
}

fn create_private_dir(output: &Path) -> io::Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;
        let mut builder = fs::DirBuilder::new();
        builder.mode(0o700);
        builder.create(output)
    }
    #[cfg(not(unix))]
    {
        fs::create_dir(output)
    }
}

fn write_private(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path)?;
    file.write_all(bytes)?;
    file.sync_all()
}

/// Random new-session nonce never accepted through the learner-facing CLI.
pub fn new_session(output: &Path) -> Result<Manifest> {
    let mut bytes = [0u8; 16];
    OsRng.fill_bytes(&mut bytes);
    create_session(output, &hex(&bytes))
}

/// Deterministic seam for tests; caller must secure the nonce and output path.
pub fn create_session(output: &Path, session_id: &str) -> Result<Manifest> {
    let form = build(session_id)?;
    // No overwrites: a failed write may leave an incomplete directory, which
    // resume must reject; never silently reuse/replace an old session.
    create_private_dir(output)?;
    write_private(&output.join("learner.md"), form.learner.as_bytes())?;
    write_private(&output.join("teacher.md"), form.teacher.as_bytes())?;
    write_private(&output.join("manifest.json"), &canonical(&form.manifest)?)?;
    Ok(form.manifest)
}

fn read_regular_file(path: &Path) -> io::Result<Vec<u8>> {
    let meta = fs::symlink_metadata(path)?;
    if !meta.is_file() || meta.file_type().is_symlink() {
        return Err(error("not a regular saved session file"));
    }
    fs::read(path)
}

/// Read-only validation of exact Rust-v2 form + key; reject v1 without touching it.
pub fn resume_session(output: &Path) -> Result<Manifest> {
    let dir = fs::symlink_metadata(output)?;
    if !dir.is_dir() || dir.file_type().is_symlink() {
        return Err(error("saved session path must be a real directory").into());
    }
    let manifest_bytes = read_regular_file(&output.join("manifest.json"))?;
    let manifest: Manifest = serde_json::from_slice(&manifest_bytes)?;
    if manifest.payload.schema != 2 || manifest.payload.version != VERSION {
        return Err(error("unsupported session schema/version; Python v1 uses its original reader").into());
    }
    let expected = build(&manifest.payload.session_id)?;
    if manifest != expected.manifest || manifest_bytes != canonical(&expected.manifest)? {
        return Err(error("saved manifest does not match the deterministic Rust form").into());
    }
    if read_regular_file(&output.join("learner.md"))? != expected.learner.as_bytes()
        || read_regular_file(&output.join("teacher.md"))? != expected.teacher.as_bytes()
    {
        return Err(error("saved learner sheet or teacher key was modified").into());
    }
    Ok(manifest)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_known_answer_and_canonical_json() {
        assert_eq!(
            hex(&sha256(b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        assert_eq!(
            canonical(&serde_json::json!({"b": 1, "a": "ā"})).unwrap(),
            b"{\"a\":\"\xc4\x81\",\"b\":1}\n"
        );
    }

    #[test]
    fn deterministic_distinct_and_secret_session() {
        let a = build(&"0".repeat(32)).unwrap();
        let b = build(&"0".repeat(32)).unwrap();
        let c = build(&"1".repeat(32)).unwrap();
        assert_eq!(a, b);
        assert_ne!(a.manifest.form_id, c.manifest.form_id);
        assert_ne!(a.learner, c.learner);
        assert!(!a.learner.contains(&"0".repeat(32)));
        assert!(a.teacher.contains(&"0".repeat(32)));
        let kinds: BTreeSet<_> = a.manifest.payload.records.iter().map(|c| &c.kind).collect();
        let claims: BTreeSet<_> = a.manifest.payload.claims.iter().map(|c| &c.kind).collect();
        assert_eq!(kinds.len(), 5);
        assert_eq!(claims.len(), 4);
        assert_eq!(a.manifest.payload.records.len(), 5);
        assert_eq!(a.manifest.payload.claims.len(), 4);
        assert!(!a.learner.contains("## Task 1: record classifications"));
        assert!(a.teacher.contains("## Task 1: record classifications"));
        assert!(build("student-identifier").is_err());
        assert!(build(&"G".repeat(32)).is_err());
    }

    #[test]
    fn create_resume_and_reject_tampering_and_overwrite() {
        let mut bytes = [0u8; 16];
        OsRng.fill_bytes(&mut bytes);
        let output = std::env::temp_dir().join(format!("grade3-islamic-rust-test-{}", hex(&bytes)));
        let manifest = create_session(&output, &"0".repeat(32)).unwrap();
        assert_eq!(manifest, resume_session(&output).unwrap());
        let learner = fs::read(output.join("learner.md")).unwrap();
        let teacher = fs::read(output.join("teacher.md")).unwrap();
        let metadata = fs::read(output.join("manifest.json")).unwrap();
        assert_eq!(manifest, resume_session(&output).unwrap());
        assert_eq!(learner, fs::read(output.join("learner.md")).unwrap());
        assert_eq!(teacher, fs::read(output.join("teacher.md")).unwrap());
        assert_eq!(metadata, fs::read(output.join("manifest.json")).unwrap());
        assert!(create_session(&output, &"1".repeat(32)).is_err());
        fs::write(output.join("learner.md"), b"tampered").unwrap();
        assert!(resume_session(&output).is_err());
        fs::write(output.join("learner.md"), &learner).unwrap();
        fs::write(output.join("manifest.json"), b"{}").unwrap();
        assert!(resume_session(&output).is_err());
        fs::remove_dir_all(output).unwrap();
    }

    #[test]
    fn reject_v1_version_without_mutation() {
        let mut bytes = [0u8; 16];
        OsRng.fill_bytes(&mut bytes);
        let output = std::env::temp_dir().join(format!("grade3-islamic-version-{}", hex(&bytes)));
        create_session(&output, &"2".repeat(32)).unwrap();
        let mut value: serde_json::Value =
            serde_json::from_slice(&fs::read(output.join("manifest.json")).unwrap()).unwrap();
        value["version"] = serde_json::json!("g3-is-source-metadata-v1");
        let before = canonical(&value).unwrap();
        fs::write(output.join("manifest.json"), &before).unwrap();
        assert!(resume_session(&output).is_err());
        assert_eq!(before, fs::read(output.join("manifest.json")).unwrap());
        fs::remove_dir_all(output).unwrap();
    }
}
