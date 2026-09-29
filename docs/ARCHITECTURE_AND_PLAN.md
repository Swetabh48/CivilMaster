# CivilMaster - Output Quality Rebuild: Context, Architecture & Plan

_Last updated: 2026-09-29 (Phases 0-2 core landed; Phase 3 scaffold)_

This document is the working context for rebuilding CivilMaster solution quality. It records
what exists today, what the audit found, the target architecture, and the phased plan.
Read this first before changing the solve pipeline, diagrams, exports, or training.

---

## 1. Summary

Poor UI/PDF output comes from **pipeline and serving gaps**, not from "having no model" or
focusing on a single data file. The corpus is large; the QLoRA adapter **is already trained**.

**Already true**

- Adapter on disk: `training/adapters/civilmaster-lora/` (Qwen2.5-3B, r=32, alpha=64, ~228 MB).
- Full corpus (exam papers, assignments, notes, codes) - plan is corpus-wide, not one sheet.
- Pack splitting, exports, auth, Vercel + Modal scaffolding exist.

**What breaks quality for users right now**

1. **Trained adapter is not loaded in production.** Modal is CPU-only; torch/peft/transformers are
 commented out of requirements -> `llm.py` skips LoRA. Users get template narrative (`llm_used: false`).
2. **Formula engine cannot read normal questions** (`symbol = number` only). Audit: 0/7 textbook questions.
3. **Diagrams used invented defaults** (`L=4000`, `w=10`) -> fake SFD/BMD in PDFs. Phase 0 removes this.
4. **UI ignored pack `problems[]`** -> multi-question uploads looked empty. Phase 0 renders per-question cards.

Rebuild rule: **LLM reads/explains; Python computes/draws; every number verified.** Phase 3 keeps
*your* fine-tune, served on GPU, trained for parse + narrate on clean data from the full corpus.

---

## 2. What has been done so far

### 2.1 Project history

| Area | State |
|-|-|
| API, auth, users | Done |
| Formula registry + SVG helpers | Done; Phase 0 makes diagrams honest |
| Solver, RAG, assignments | Done |
| Next.js UI | Done; Phase 0 pack cards |
| QLoRA + **trained adapter on disk** | Done |
| Corpus ingest | Done (large private set) |
| Deploy | Vercel + Modal CPU (GPU needed to serve LoRA) |
| PDF/DOCX/DXF | Done |
| Lab pack split (`problem_prep.py`) | Done |
| This architecture doc | Done |
| Phase 0 code | Landed: no fake defaults, no constant-only answers, pack UI, PDF aspect + narrative |

### 2.2 Trained vs served

| Layer | Status |
|-|-|
| Adapter weights | **Trained and present** |
| Modal `/lora` volume wiring | Present |
| Modal GPU + torch/peft in image | **Missing** -> LoRA never loads live |
| Live solves | Registry + template write-up |

"Model never trained" is wrong. "Model does not run for users yet" is right.

---

## 3. Diagnosis (evidence)

### 3.1 Serving gap (not missing weights)

| Evidence | Location |
|-|-|
| No `gpu=` on Modal serve | `training/modal_serve.py` |
| torch/peft/transformers commented out | `backend/requirements.txt` |
| LoRA skip without CUDA/deps | `backend/app/services/llm.py` |
| Ollama localhost unreachable on Modal | `backend/app/core/config.py` |

### 3.2 SFT mix quality (orthogonal to "adapter exists")

Historical `civilmaster_sft.jsonl` (~547 rows) was heavy on synthetic plug-ins + noisy OCR mines.
The **source corpus** is still the right material for Phase 3 - rebuild clean parse/narrate rows
with vision transcription across papers and labs, then re-serve.

### 3.3 Formula engine

28 one-liners; weak NL parse; no unit conversion; no multi-step / IS 800 / IS 456 design.
Audit 0/7. Was also reporting `xu,max/d = 0.48` alone + fake beam diagram - Phase 0 blocks that.

### 3.4 Diagrams (Phase 0)

`svg_templates.py` draws only when required params exist. No invented L/w. PDF keeps real aspect;
no pillow fake beam when SVG missing.

### 3.5 UI / ingest

Pack UI renders `problems[]`. Photos/scans still need Phase 1 vision. Regex split remains fragile.

### 3.6 Component status

| Component | Status |
|-|-|
| Auth / deploy / corpus | Keep |
| Fine-tuned adapter | **Trained** - serve next |
| Parsing / solvers / computed drawings | Phase 1-2 |
| Narrative | Template until LoRA or hosted LLM is wired |

---



## Progress snapshot (2026-09-29)

| Phase | Status |
|---|---|
| 0 Honesty + pack UI + no fake diagrams | Done |
| 1 Schemas + NL parse + LLM gateway stub + orchestrator | Core done (hosted LLM optional via env) |
| 2 Beams, IS 800 lap, IS 456 LSM, section stress, soil + drawings | Done for audit set (7/7 eval) |
| 3 Clean SFT from solvers + GPU retrain/serve of your adapter | Scaffold (uild_solver_sft.py); needs Modal GPU billing |

Run: python eval/run.py → expect **7/7**.

## 4. Target architecture

### 4.1 Principles

1. **An LLM reads and explains; code computes and draws.** No arithmetic or diagram geometry comes
 from the LLM.
2. **Every number is traceable.** Each number in the final output comes from the question's givens,
 a solver step, or a cited code table.
3. **No output beats wrong output.** Missing data gives "needs input", never defaults. Unsupported
 questions are labelled as such.
4. **One schema, many renderers.** UI, PDF, DOCX and DXF all render from the same `Solution` object.
5. **Measured, not guessed.** An evaluation set gates every change.

### 4.2 Pipeline

```mermaid
flowchart LR
 U[Upload / typed text] -> T[1. Transcribe<br/>vision LLM for images & scans]
 T -> S[2. Split & classify<br/>LLM -> list of RawProblem]
 S ->|numerical / design| P[3. Parse<br/>LLM -> ProblemSpec JSON<br/>pint units]
 S ->|theory| R[RAG over corpus<br/>+ LLM answer with citations]
 S ->|detailing| G[Drawing generator<br/>from given dims]
 P -> V[4. Solve<br/>topic solver: steps, answers, checks]
 V -> D[5. Draw<br/>Drawing IR from solver output]
 V -> W[6. Write-up<br/>LLM explains solver steps]
 D -> X[7. Verify<br/>number grounding, units,<br/>equilibrium, ranges]
 W -> X
 R -> X
 G -> X
 X -> O[Solution v2 JSON]
 O -> UI[Next.js UI]
 O -> PDF[HTML + KaTeX -> PDF]
 O -> DOCX[DOCX]
 O -> DXF[DXF]
```

**Problem kinds and their paths**

| Kind | Path | Output |
|-|-|-|
| `numerical` / `design` | Parse -> Solver -> Draw -> Write-up -> Verify | Given, To find, diagrams, steps, checks, answer |
| `theory` | RAG (real embeddings) -> LLM answer with source citations | Structured answer + sources |
| `detailing` | Parametric drawing generator (Phase 2), else checklist | SVG + DXF drawing, or honest guidance |
| `unsupported` / parse failed | - | Labelled "not solved" + what's missing; optional LLM attempt marked **unverified** |

### 4.3 Module layout (target)

```
backend/app/
 llm/
 gateway.py # provider-agnostic: complete_json(schema, msgs, images), complete_text
 providers/ # hosted API, OpenAI-compatible (vLLM / fine-tune), ollama (dev)
 prompts/ # versioned prompt files: transcribe, split, parse_<topic>, narrate, theory
 pipeline/
 orchestrator.py # runs stages per problem; replaces services/solver.py
 ingest.py # transcription + split/classify; replaces services/problem_prep.py
 parse.py # RawProblem -> ProblemSpec (validate + retry with error feedback)
 narrate.py # solver trace -> narrative markdown
 theory.py # RAG + cited answer
 schemas/
 problem_spec.py # ProblemSpec + per-topic specs (discriminated union)
 solution_v2.py # Solution / ProblemSolution / Step / Diagram / Check / Answer
 solvers/
 base.py # Solver protocol, NeedsInput exception, registry by topic
 units.py # pint registry, SI-N-mm normalisation, formatting
 formula_lookup.py # legacy registry wrapped for simple single-formula questions
 beams.py # statically determinate beams
 sections.py # section properties, bending/shear stress
 steel_is800/ # bolts.py, welds.py, tension.py, tables/*.json
 rcc_is456/ # beam_lsm.py, slab.py, column.py, tables/*.json
 geotech.py # phase relations (sympy system solve), permeability
 fluids.py # hydrostatics, pipe flow
 drawing/
 ir.py # primitives: line, polyline, arc, circle, text, arrow, dimension, hatch
 svg.py # IR -> SVG
 dxf.py # IR -> DXF (ezdxf) - same geometry as the SVG
 beams.py # loading diagram + SFD + BMD (aligned, to scale, values labelled)
 sections.py # rect / I / T sections, RCC section with bars & stirrups
 joints.py # bolted/welded joint plan + elevation
 verify/
 grounding.py # every number in prose ∈ givens ∪ step values ∪ table constants
 checks.py # equilibrium, unit dimensions, plausible ranges, code limits
 render/
 templates/solution.html.j2
 pdf.py # Playwright Chromium page.pdf()
 docx.py
 jobs.py # async solve job (Modal Function.spawn / BackgroundTasks locally)
eval/
 cases/*.yaml # real questions + hand-checked answers
 run.py # stage and end-to-end scoring -> report
frontend/src/components/solution/
 ProblemCard.tsx StepList.tsx DiagramPanel.tsx AnswerBox.tsx Math.tsx SourceList.tsx
```

Current -> target: `services/solver.py` -> `pipeline/orchestrator.py`; `services/problem_prep.py` ->
`pipeline/ingest.py`; `formulas/registry.py` -> `solvers/formula_lookup.py` + topic solvers;
`diagrams/svg_templates.py` + `build_*_dxf` -> `drawing/*`; `services/llm.py` -> `llm/*`;
`services/export_docs.py` -> `render/*`.

### 4.4 Core schemas (sketch)

```python
class Quantity(BaseModel):
 value: float
 unit: str # pint-parsable: "kN/m", "mm", "N/mm**2"

class Load(BaseModel):
 kind: Literal["point", "udl", "uvl", "moment"]
 magnitude: Quantity # uvl: start intensity
 magnitude_end: Quantity | None = None
 position: Quantity | None = None # point / moment
 start: Quantity | None = None # distributed
 end: Quantity | None = None

class BeamSpec(BaseModel):
 topic: Literal["beam_analysis"]
 support: Literal["simply_supported", "cantilever", "overhang"]
 span: Quantity
 overhang_left: Quantity | None = None
 overhang_right: Quantity | None = None
 loads: list[Load]
 find: list[Literal["reactions", "sfd", "bmd", "max_bm", "max_sf", "contraflexure"]]

class BoltedJointSpec(BaseModel):
 topic: Literal["is800_bolted_joint"]
 joint: Literal["lap", "butt_single_cover", "butt_double_cover"]
 force: Quantity; force_is_factored: bool
 bolt_dia: Quantity; bolt_grade: str # "4.6"
 plate_thickness: Quantity; plate_width: Quantity
 steel_grade: str # "E250"

# … LsmBeamSpec, SectionSpec, SoilPhaseSpec, FormulaLookupSpec, …

class ProblemSpec(BaseModel):
 id: str
 title: str
 question_text: str
 kind: Literal["numerical", "design", "theory", "detailing"]
 body: BeamSpec | BoltedJointSpec | ... = Field(discriminator="topic")
 assumptions: list[str] = []

class Step(BaseModel):
 title: str
 formula_latex: str
 substitution_latex: str
 result: Quantity
 clause: str | None = None # "IS 800:2007 Cl. 10.3.3"
 note: str | None = None

class ProblemSolution(BaseModel):
 spec: ProblemSpec | None
 status: Literal["verified", "unverified", "needs_input", "unsupported"]
 given: list[tuple[str, Quantity]]
 to_find: list[str]
 diagrams: list[Diagram] # kind, svg, caption, has_dxf
 steps: list[Step]
 checks: list[Check] # name, passed, detail
 answers: list[Answer]
 narrative_md: str
 sources: list[Source] = [] # theory path citations
 missing_inputs: list[str] = []
 provenance: Provenance # solver id+version, llm model, prompt version, grounding result

class Solution(BaseModel):
 schema_version: Literal[2] = 2
 problems: list[ProblemSolution] # always a list; a single question is one item
```

`problems` is always a list, which removes today's "pack vs single" branching in the solver, UI,
and every exporter. Old solutions (no `schema_version`) render through a legacy view.

### 4.5 Solver contract

```python
class Solver(Protocol):
 topic: str
 version: str
 def solve(self, spec: BaseModel) -> SolverResult: ...
 # SolverResult: steps, answers, checks, drawing_data (e.g. x/SF/BM arrays, bolt layout)
 # raises NeedsInput(missing=["span"]) instead of guessing
```

- Internally everything is SI-N-mm via `pint`. Output units are chosen per quantity (kN, kN·m, N/mm²).
- Code tables (IS 800 partial safety factors, bolt grades, IS 456 Table 19, Mu,lim constants,
 IS 808 section properties) live as versioned JSON next to the solver and are cited in `Step.clause`.
- Built-in checks: beams (ΣFy = 0, ΣM = 0, BM = 0 at free ends/pins); design (capacity ≥ demand,
 min/max steel, pitch/edge limits).

### 4.6 Drawing engine

- One **drawing IR** (primitives + dimension lines + hatching), rendered by two backends: SVG
 (UI/PDF/DOCX via cairosvg) and DXF (AutoCAD). What students see and what they download are the same
 geometry.
- Drawings are built **only** from solver output or given dimensions. If a required value is missing,
 there is no drawing.
- Beam sheet = loading diagram with dimensions + SFD + BMD, vertically aligned on the same x-scale,
 with values at supports, load points, max BM and contraflexure points.

### 4.7 LLM gateway

- A single interface: `complete_json(schema, messages, images=None)` and `complete_text(messages)`.
- Providers are configured by env (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`): hosted
 API, OpenAI-compatible endpoint (vLLM serving a future fine-tune), Ollama for local dev.
- Structured output is validated with pydantic. On a validation error, retry up to 2 times with the
 error message fed back.
- Responses are cached by a hash of (prompt version, input). Prompts are versioned files, recorded in
 `provenance`.
- API keys are stored as Modal Secrets and never logged.

### 4.8 Verification layer

| Check | Rule | On failure |
|-|-|-|
| Number grounding | Every number in `narrative_md` matches (to rounding) a given, step value, or table constant | Regenerate once -> fall back to templated narrative |
| Units | Every step result has the expected dimensionality (pint) | Mark step failed; status `unverified` |
| Physics | Equilibrium, sign conventions, plausible ranges | Mark failed; show in Checks |
| Parse sanity | Spec givens appear in the question text | Flag for user confirmation |

### 4.9 Rendering

- **UI:** React components render `Solution v2` (KaTeX for equations, inline SVG diagrams, per-problem
 cards, status badges: verified / unverified / needs input).
- **PDF:** Jinja2 HTML template, same structure and CSS as the UI, KaTeX auto-render, printed with
 Playwright Chromium `page.pdf()` on the backend. Replaces reportlab so the UI and PDF can't drift.
- **DOCX:** python-docx from the same schema; equations as text/images, diagrams as PNG.
- **DXF:** from the drawing IR.

### 4.10 Execution & deployment

| Piece | Where |
|-|-|
| Frontend | Vercel (unchanged); polls `GET /assignments/{id}` for status and per-problem progress |
| API | Modal CPU (unchanged) + Chromium for PDF |
| Solve job | Modal `Function.spawn` (same image); FastAPI `BackgroundTasks` locally |
| LLM | Hosted API in Phases 1-2; optional Modal GPU / vLLM endpoint for the fine-tune in Phase 3 |
| DB | SQLite on Modal volume today; move to managed Postgres if concurrent writes become a problem |
| Embeddings | Real embedding model (sentence-transformers or API) for the theory path |

---

## 5. Plan - what is left to do

Estimates assume one developer. Targets are proposals to confirm against the first eval run.

### Phase 0 - Stop wrong output + measure (1-2 days)

| # | Task | Status |
|-|-|-|
| 0.1 | No diagram defaults; draw only with required values + matching type | **Done** |
| 0.2 | Never report constant-only formulas as the answer | **Done** |
| 0.3 | UI: render `solution.problems[]` per-question cards + diagrams | **Done** |
| 0.4 | PDF: real aspect ratio; include narrative with steps | **Done** |
| 0.5 | Show which backend produced the solution in the UI | **Done** (label on solve page) |
| 0.6 | Eval harness + audit 7/7 baseline (expand toward 100) | **Done (7 cases)** |

**Exit:** no diagram or answer that doesn't belong to the question; baseline eval report committed.

### Phase 1 - LLM for reading and writing (1-2 weeks)

| # | Task |
|-|-|
| 1.1 | LLM gateway + providers + config + Modal Secret |
| 1.2 | `ProblemSpec` and `Solution v2` schemas; legacy rendering for old solutions |
| 1.3 | Ingest: vision transcription for images/scans; LLM split + classify (numerical/design/theory/detailing) |
| 1.4 | Parse: `RawProblem -> ProblemSpec` with validation + retry; `pint` units |
| 1.5 | Wrap the existing registry as `formula_lookup` so simple questions keep working |
| 1.6 | Narrate + number-grounding verifier |
| 1.7 | Theory path: real embeddings, re-index corpus, cited answers |
| 1.8 | Async solve jobs + frontend polling/progress |
| 1.9 | Renderer v2: HTML + KaTeX + Playwright PDF; React solution components; DOCX v2 |

**Exit (proposed):** ≥ 90 % of in-scope eval questions parsed into a valid spec; 0 grounding violations
in shipped narratives; UI and PDF visually match; photos/scans work in production.

### Phase 2 - Real solvers and diagrams (2-4 weeks)

Order follows the corpus and current assignments. Swap 2.2 and 2.3 if the Steel Structures lab is
the immediate need.

| # | Solver | Covers | Drawings |
|-|-|-|-|
| 2.0 | Drawing IR + SVG/DXF backends | all | replaces `svg_templates.py` and `build_*_dxf` |
| 2.1 | Beams (SS / cantilever / overhang; point, UDL, UVL, moment) with section-wise SF/BM equations via sympy | SOM, SA-I | loading diagram + SFD + BMD to scale |
| 2.2 | IS 800: bolted lap/butt joints, fillet welds, tension members (yield, rupture, block shear) | Steel Structures + lab | joint plan + elevation (SVG + DXF) |
| 2.3 | IS 456 LSM: singly/doubly reinforced beams, shear, one-way slab, short column | Concrete Structures I/II | section with bars & stirrups |
| 2.4 | Section properties + bending/shear stress distribution | SOM | section + stress diagrams |
| 2.5 | Geotech phase relations (solve from any sufficient set), permeability | Geotech I/II | phase diagram |
| 2.6 | Fluids: hydrostatics, pipe flow (Darcy, Hazen-Williams) | FM I/II, Env. Engg | - |
| 2.7 | Detailing generators for common lab drawings (lap/butt joint, welded connection, column base) | Steel lab | SVG + DXF |
| 2.8 | "Edit givens & re-solve" in the UI | all | - |

**Exit per solver (proposed):** ≥ 95 % numeric accuracy (±2 %) on its eval slice; all built-in checks
pass; a correct diagram for 100 % of solved questions in that topic.

### Phase 3 - Own model, trained properly (ongoing)

1. Train for the pipeline's jobs: question -> `ProblemSpec` JSON, and solver trace -> explanation.
 Not arithmetic.
2. Dataset of 3-5k examples:
 - Transcribe exam papers and solved assignments with a vision LLM.
 - Solve them through Phase 2 solvers; generate write-ups.
 - Spot-check by hand.
 - Drop the existing OCR-noise and absurd synthetic rows.
3. Base model 7B-14B (3B is too small for reliable structured extraction). Serve on a GPU (Modal GPU
 needs a payment method on the account; vLLM behind the OpenAI-compatible provider).
4. A/B against the hosted model on the eval set; switch per stage only when it matches.

### Do not

- Retrain the 3B adapter on the current dataset.
- Add more regex to `problem_prep.py` or `extract_variables`.
- Add more fixed SVG templates.

---

## 6. Open decisions

| # | Decision | Recommendation |
|-|-|-|
| D1 | LLM for Phases 1-2: hosted frontier model vs self-hosted only | Hosted model with vision + structured output now. Self-hosted only keeps quality low until Phase 3 and needs paid GPU serving. |
| D2 | First subject | Beams first (exercises every stage), then IS 800 connections. Flip if the Steel lab is urgent. |
| D3 | PDF engine | Playwright Chromium (full KaTeX fidelity, same HTML/CSS as UI) over WeasyPrint + server-rendered math |
| D4 | Database | Stay on SQLite/Modal volume for now; revisit with async jobs and more users |
| D5 | Old solutions | Keep and render via legacy view; offer "re-solve with new engine" |

---

## 7. Risks

| Risk | Mitigation |
|-|-|
| LLM parse errors produce a wrong spec | Show parsed "Given" to the user; edit & re-solve; parse-sanity check |
| IS-code correctness in solvers | Tables as cited JSON; eval cases from faculty-solved papers; clause references in every step |
| LLM cost / latency | Cache by input hash; LLM only for transcribe/parse/narrate; async jobs |
| Modal request timeouts | Solve jobs run as spawned functions, not in the request |
| Copyright / privacy | Corpus contains textbooks and other students' named assignments. Keep `data/corpus` private and don't publish datasets containing book text. `training/datasets/mined_qa.json` and the mined SFT rows contain textbook excerpts - review before keeping them in a public repo. |

---

## Appendix A - Reproduce the audit

```bash
cd backend
python -c "from app.formulas.registry import solve_with_registry as s; print(s('A simply supported beam of span 6 m carries a UDL of 20 kN/m over the entire span. Draw the SFD and BMD and find the maximum bending moment.'))"
```

Audit questions:

1. A simply supported beam of span 6 m carries a UDL of 20 kN/m over the entire span. Draw the SFD and BMD and find the maximum bending moment.
2. A simply supported beam AB of span 5 m carries point loads of 20 kN at 1 m and 30 kN at 3 m from A. Draw SFD and BMD.
3. A cantilever of length 3 m carries a UDL of 10 kN/m. Find the maximum shear force and bending moment.
4. Design a lap joint for a tensile force of 145 kN using M16 bolts of grade 4.6. Plates are 12 mm x 120 mm of E250 steel.
5. Design a singly reinforced rectangular beam 230 mm x 450 mm effective depth for a factored moment of 120 kNm using M20 concrete and Fe415 steel.
6. A rectangular beam 200 mm wide and 400 mm deep is subjected to a bending moment of 50 kNm. Find the maximum bending stress.
7. A soil sample has a bulk density of 1.9 g/cc and water content 12%. G = 2.7. Find void ratio and degree of saturation.

Result: 0 / 7 solved (see §3.3). These seven should be the first entries in `eval/cases/`.

## Appendix B - Key facts

- Adapter: `training/adapters/civilmaster-lora/`, base `unsloth/Qwen2.5-3B-Instruct-bnb-4bit`, r=32, alpha=64.
 Also on Modal volume `civilmaster-lora-vol` at `/lora/civilmaster-lora`.
- Live: app `https://civilmaster-five.vercel.app`, API `https://swetabh48-civilmaster-api-fastapi-app.modal.run/health`.
- Corpus by volume: Env. Engg I/II (~119 files), BPC (59), FM-II (49), Geotech I/II + labs (~80),
 Concrete Structures I/II + lab (~61), Transportation (~67), Structural Analysis (~45), Steel Structure Lab (16).
