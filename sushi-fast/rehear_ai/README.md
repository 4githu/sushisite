# Independent Research16 assessment

This package implements a separate sixteen-criterion research task. It does not
generate the existing OpenAI ten-metric report and is not called automatically
by `/update`, `/finish`, questions or report recovery. Core/fake need only Python
and Pydantic 2.13.4 (`requirements.txt` here). No API key or GPU is required.
Core/fake do not import torch, Transformers, the OpenAI SDK, FastAPI, DB or development tools.
The directory can be copied out and used on its own Python path.

The official team rubric/anchors/policy and model artifacts were not supplied.
No production rubric, weights or grading policy is included. All test rubric
definitions are `TEST_ONLY`; the fake engine abstains on all sixteen criteria.
Passing these tests does not establish assessment quality.

## Contracts and evidence

`RubricBundle` requires a source, rubric/policy versions, purpose, nonempty policy
JSON and exactly sixteen distinct IDs. Each criterion needs its supplied label,
definition and five distinct 1–5 anchors. IDs come from the supplied bundle;
the analysis document's tentative ID range is not a substitute for the official
definitions. The code does not invent weights, aggregate scores or map research
scores to the service's 0–100 metrics. Structural validation cannot authenticate
a document's official status or determine whether a citation supports a reason.

`rehear_ai.evidence.build_evidence_pack(neutral_export, source_version=...)`
accepts source ID, segments and optional QA/omission metadata. See `SourceCase`
in `evidence.py` for the neutral export schema. Existing backend DTOs use
`odi.EVC.assessment_adapter.build_evidence_pack(records, source_version=...,
stt_by_step=..., segment_offsets_s=..., slides=..., qa_history=...)`.

The adapter preserves raw transcript text, client observation time and existing
measured speech features. It excludes previous model evaluations/prose, E/V/C,
AI reactions and report scores. The neutral metric allowlist also rejects model
scores masquerading as measurements. Raw `SpeechTextResult` words can be supplied
by step. Existing report DTOs do not retain these words; absent words stay missing.
An explicit observed segment start offset is required for absolute word times.
The adapter never derives a start offset from segment end minus speech duration.

Slides are segment observations, not an exact display timeline. Existing slide
DTO text completeness is unknown and recorded as such. F0, volume, gaze time
series, precise slide timeline and external fact sources are not fabricated.
`qa_history=None` means unavailable; an explicit empty list means known empty.
Coverage counts supplied sources plus explicitly listed omissions, not the
unknown size or duration of an entire original dataset. No transcript shortening
occurs inside the engine; known truncation and unknown slide completeness persist.

`AssessmentResult` contains sixteen IDs matching the bundle, strict integer
1–5/null scores, reason, evidence IDs and consistent abstention fields. Scoring
requires references; abstention requires null plus an abstain reason. Result
metadata contains schema/source/rubric/policy/prompt versions, canonical content
digests, base/tokenizer/adapter identity, runtime binding, inference settings,
call count and coverage. Unknown evidence IDs, altered provenance and incorrect
coverage are rejected. Existing references are not proof of semantic support.

`store_internal_result(mapping, run_id=..., result=..., evidence=..., rubric=...)`
is explicit caller-owned storage after validation. A conflicting run ID is
rejected. It is not wired to service lifecycle hooks, persistent DB/recovery or
the public report projection; callers must retain the evidence and rubric too.

## CLI

Run from `sushi-fast/`, or put that directory on `PYTHONPATH`:

```sh
.venv/bin/python -m tools.rehear_cli --help
.venv/bin/python -m tools.rehear_cli eval \
  --input evidence-pack.json --rubric supplied-rubric.json \
  --engine fake --repeat 2 --output new-result.json
make -f Makefile.ai ai-eval INPUT=evidence-pack.json RUBRIC=supplied-rubric.json OUTPUT=new-result.json
```

Input is a serialized `EvidencePack`, not a report or an audio file. The CLI
refuses `TEST_ONLY` rubrics unless `--allow-test-rubric` is given. Existing output
paths are preserved; choose a new path for each run. Error output omits raw input
and generated model text. Fake success prints `fake_contract_only`; its call
count is fake engine dispatches, not real model inference. The result contains
all sixteen abstentions. `--repeat` writes the last result with cumulative call
count and reports the repeat count; it does not create a full experiment archive.

Response caching defaults off. Optional `cache_enabled=true` in engine config
uses a bounded 128-entry private engine cache keyed by full evidence, rubric,
policy, actual prompt text/version, provider, base/tokenizer/adapter revisions,
runtime binding/versions and inference settings. Cached responses report
`cache_hit=true` without incrementing inference count. There is no shared
cross-engine cache. Model KV caching is a different concept.

## Local Qwen boundary

```sh
.venv/bin/python -m tools.rehear_cli eval \
  --input evidence-pack.json --rubric supplied-rubric.json \
  --engine qwen_local --config verified-local-config.json --output new-result.json
```

Use a separate, verified model environment. `EngineConfig` requires explicit
local model/tokenizer directories, base/tokenizer revisions, `qwen2` or `qwen3`
family, and exact installed `runtime_versions` for torch/transformers. If LoRA
is used, supply its directory, adapter revision and pinned peft version too.
Device/dtype and token/time/retry budgets are explicit config fields. No model
or dependency download is performed. Actual installed versions must match the
provided lock. No tested ML version lock is shipped: this workspace has none of
torch, transformers or peft installed. Inventing a compatible lock would not be
runtime verification.

The lazy loader uses local-only `AutoTokenizer`, `AutoModelForCausalLM` and
optional `PeftModel`, disallows remote code and checks the loaded model family.
It reuses one loaded runtime per engine, serializes calls without an unbounded
queue, uses the tokenizer chat template (Qwen3 non-thinking mode) and decodes
only newly generated tokens. Oversize inputs fail instead of being silently
truncated. Generated JSON is parsed/validated strictly, not assumed to support
OpenAI `.parse` or constrained structured generation. Invalid/truncated JSON
fails and is not cached. There is no service-report task in the prompt.

Retries do not start after the overall assessment deadline. Generation `max_time`
is cooperative and the late-result check cannot forcibly
kill a running device/kernel or bound model-loading time. Defaults are 4,096 new
tokens, 16,384 input tokens, 120s, zero retries and temperature 0. Actual model
context capacity/JSON reliability must be verified against the chosen artifacts.
Revisions are caller-supplied provenance labels; local directory contents are
not independently verified as those commits. Preserve immutable snapshots and
their artifact hashes for real research runs.

Runtime binding is recorded as `builtin_fake`, `injected_loader` (test seam), or
`transformers_local`. Tests verify load-once/generate-twice and loader/template/
adapter arguments using injected fakes, not real weights. Actual Qwen execution,
family/template compatibility, GPU behavior and scoring quality remain unverified.
An optional OpenAI research-comparison engine is not implemented; the CLI exposes
only fake and qwen_local. The existing service's three provider seams remain intact.

Loader API references consulted (implementation references, not proof of a real run):

- [Transformers Qwen3](https://huggingface.co/docs/transformers/main/en/model_doc/qwen3)
- [Transformers chat templates](https://huggingface.co/docs/transformers/main/en/chat_templating)
- [PEFT model loading](https://huggingface.co/docs/peft/main/en/package_reference/peft_model)

## Required materials before production assessment

1. The team's approved sixteen IDs, definitions and all eighty 1–5 anchors,
   with authoritative source and immutable rubric version.
2. Approved missing-input, coverage, abstention, evidence and weighting/aggregation
   policy, including policy source/version. No default research policy is invented.
3. Exact Qwen family/base and tokenizer artifacts with revisions/hashes, plus
   LoRA artifacts/revision or an explicit decision to run without LoRA.
4. A tested torch/transformers/peft environment lock, hardware/inference settings,
   and permitted expert-labeled evaluation examples for quality validation.
