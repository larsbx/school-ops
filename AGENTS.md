# Working in school-ops

- This repository develops a K–12 curriculum. Follow the current scope brief
  for each course; do not infer grades, starting skills, standards, or schedules.
- Read `README.md`, `docs/curriculum-model.md`, and the relevant course before
  making curriculum changes. Preserve stable IDs and prerequisite relationships.
- Separate proposed curriculum, reviewed teaching material, and observed results.
  Do not mark material `ready` while its readiness fields are unresolved.
- Link outcomes to assessment criteria. Resource availability and exercise
  completion alone do not establish mastery.
- Use the connected Khan Academy capability for requested mathematics exercise
  searches. Only apply grade or standard search limits explicitly supplied by
  the user. Do not use web search to retrieve Khan Academy exercises.
- Exercise-selection replies must follow the Khan Academy tool's rendering rules.
  Use a separate interaction for repository edits and curriculum discussion.
- Register only resource links and metadata actually returned or supplied.
  Leave unknown IDs, URLs, standards, and source rights explicitly unresolved.
- Store external materials by reference and attribute sources. Do not assume
  permission to redistribute their content.
- Keep learner-specific records and class-specific assignment URLs out of this
  shared repository. Follow the private-records convention in `.gitignore`.
- Review relative links, index entries, ID references, and readiness fields before
  opening a pull request. Documentation-only changes do not require a new test suite.
- Use GitHub issues and pull requests for curriculum work. Do not assign people
  or notify external recipients unless the user asks.
