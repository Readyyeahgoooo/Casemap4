# Codex Review Task: Batch Enrichment Validation

**Generated:** 2026-04-13T06:11:42.411631+00:00
**Batch size:** 1 candidates

## Instructions

For each case below, verify:
1. **Topic assignment** — Does the case genuinely belong to the assigned topic?
2. **Principles** — Are the extracted legal principles accurate and non-hallucinated?
3. **Paragraph spans** — Do the paragraph references exist in the case?
4. **Relationships** — Are case-law relationships (FOLLOWS, APPLIES, etc.) correct?

For each case, set `review_status` to `verified` or `rejected` and add `review_notes`.

## Output Format

Write a JSON file `data/batch/reviewed.json` with the same structure as the input,
but with `review_status` and `review_notes` updated for each candidate.

---

### Case 1: HKSAR v. LAM CHEUK TING (林卓廷)
- **Citation:** [2025] HKCFA 7
- **Assigned Topic:** Actus Reus (`actus_reus`)
- **Source:** https://www.hklii.hk/en/cases/hkcfa/2025/7
- **Principles (3):**
  1. `Mens rea for s.30(1)(b) disclosure offence` (para [40])
  2. `Proper construction of s.30(1)(b)` (para [70])
  3. `Limits of purposive interpretation` (para [72])
- **Relationships (2):**
  - : 
  - : 
- **review_status:** `pending`
- **review_notes:** 
