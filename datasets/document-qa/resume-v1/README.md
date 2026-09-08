# document-qa-resume-v1

The Document Q&A counterpart to `datasets/incident-investigator/smoke-v1` (docs/roadmap.md
Phase 5): 7 cases run against the real Document Q&A RAG platform
(github.com/fegbewunmi/document-qa) through `DocumentQAAdapter`
(`backend/app/adapters/document_qa/`).

## Corpus

The indexed document is a real resume PDF (`document.pdf` in that project's working
directory, gitignored - not committed anywhere). This was a deliberate substitution: the
design doc for document-qa (`docs/DESIGN-DOC.md` in that repo) describes a labeled test
set (Q-001 through Q-007) built against a "Widget X200 Maintenance Guide" fixture with
specific ground truth (an error code, a SKU, warranty terms) - but that PDF was never
actually committed to the repo and isn't present anywhere on disk. Rather than
reconstructing a fixture that doesn't exist, this dataset uses a real document that is
actually available, with expected values read directly from its text and fixed before any
query was run - not invented after seeing the system's output.

## Cases

- 5 grounded questions with answers verifiable directly from the resume text (current
  employer, graduate school, GPA, a specific percentage metric, and a compound multi-fact
  question about vector database experience that exercises retrieval specifically - the
  answer draws from a "TECHNICAL SKILLS" passage distinct from where the employer/degree
  facts live).
- 2 refusal cases, mirroring document-qa's own Q-004/Q-005 pattern: one fully out-of-corpus
  ("capital of France" - trips the static similarity-threshold refusal before any LLM
  call), one topically close but genuinely unstated ("favorite programming language" - the
  resume lists skills, not preferences; passes the threshold and the LLM correctly
  declines).

## A real behavior this dataset's design accounts for

The synthesis prompt asks the model to embed `[n]` citation markers directly in the answer
text, but it doesn't always comply even when `citedChunkIndices` is populated correctly
(observed directly against the live server - see `docs/phase-notes/phase-5.md`). The
adapter falls back to treating the whole answer as one groundable claim when no inline
markers are found, so `grounding_judge` stays meaningful regardless of this formatting
inconsistency.
