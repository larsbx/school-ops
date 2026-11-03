//! Usage: cargo run --manifest-path <crate>/Cargo.toml -- new|resume --output <dir>
use grade3_islamic_source_practice::{new_session, resume_session, Result};
use std::io;
use std::path::Path;

fn run() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 3 || args[1] != "--output" || !matches!(args[0].as_str(), "new" | "resume") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "usage: grade3-islamic-source-practice new|resume --output <private-directory>",
        )
        .into());
    }
    let output = Path::new(&args[2]);
    let (verb, manifest) = if args[0] == "new" {
        ("New draft form created", new_session(output)?)
    } else {
        (
            "Saved draft form verified, not rewritten",
            resume_session(output)?,
        )
    };
    println!(
        "{verb}\nPublic form hash: {}\nOutput directory: {}",
        manifest.form_id,
        output.display()
    );
    println!("Teacher key and manifest are private; distribute learner.md only.");
    Ok(())
}

fn main() {
    if let Err(err) = run() {
        eprintln!("Grade 3 practice error: {err}");
        std::process::exit(1);
    }
}
