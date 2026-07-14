---
name: agentic-rag
description: Ground Zotero Web Library research tasks in the active library scope. Use when answering factual or summary questions, comparing papers, inspecting the knowledge-base scope, extracting a literature-matrix value from supplied evidence, or drafting cited review text with the Agentic RAG tools or an Evidence Pack. Apply backend scope, retrieval refinement, parent-context reading, citation, degradation, and insufficient-evidence rules.
---

# Agentic RAG

## Non-negotiable Rules

- Use only evidence returned for the active backend-controlled scope. Never request or infer a broader `knowledge_base_id` or `item_keys` scope.
- Ground every paper fact in retrieved evidence. Never invent papers, page numbers, methods, experimental results, citations, or conclusions.
- Treat retrieval rank and reranker scores as ordering signals, not factual confidence.
- Preserve supplied citation markers exactly. Never manufacture a marker.
- State that evidence is insufficient and name the missing evidence type when the sufficiency gate fails.

## Operating Loop

1. Classify the task as `factual`, `summary`, `comparative`, `matrix`, `writing`, or `scope`.
2. Identify the evidence needed and success condition before searching.
3. Use `list_scope_documents` when the request is about scope or when comparison coverage is unclear.
4. Use `search_evidence` for concise retrieval. Select `mode` and optional metadata/chunk filters from the task; do not repeat an identical call.
5. Inspect warnings, source types, section paths, query lineage, and cross-paper coverage. Treat semantic or reranker failure as a degraded retrieval path, not automatically as task failure.
6. Use `read_chunk_context` for claims that require method, result, limitation, table, figure-caption, or section-level detail. Prefer its parent context over assembling unrelated neighboring chunks.
7. If evidence is incomplete, change at least one retrieval dimension: query wording, mode, filters, target paper, or chunk type. Stop when the evidence is sufficient, the controlled budget is exhausted, or no meaningful refinement remains.
8. Run the sufficiency gate, then answer with inline citations or abstain with a concrete evidence gap.

## Sufficiency Gate

Before answering, verify all of the following:

- Each factual claim has supporting text and an existing citation marker.
- Content questions use chunk evidence rather than metadata alone.
- Comparative claims have evidence for every paper or explicitly mark the missing side.
- Synthesis is distinguishable from what an individual paper states.
- Conflicting or degraded evidence is visible in the answer.

## Capability Boundaries

- Use only `search_evidence`, `read_chunk_context`, and `list_scope_documents` in the current Function Calling runtime.
- Treat `figure_caption` and `table` chunks as text evidence only. Do not claim visual inspection unless an actual figure/table evidence object is supplied.
- Handle a matrix cell only when its extraction evidence is supplied. The current chat runtime does not expose `read_matrix` or `compare_matrix`.
- Do not claim a persistent `TaskPlan`, `EvidenceState`, claim verifier, or other Phase 2 state-machine result until the runtime returns it.

## Output Rules

- Lead with the answer, then provide only the evidence needed to support it.
- Keep citations adjacent to the claims they support.
- Compare by a shared dimension and mark unavailable cells as "evidence not found" in the response language.
- Return only the requested value and citations for a matrix cell.
- Label review-level synthesis and retain citations on underlying factual claims.
- Return an evidence-insufficient answer instead of filling gaps with general knowledge.

## References

Read these as follows:

- Read `references/tool-contract.md` whenever calling tools or consuming an Evidence Pack.
- Read `references/retrieval-policy.md` for comparison, matrix, writing, query refinement, or degraded retrieval.
- Read `references/citation-format.md` before producing cited output.
