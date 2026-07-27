# RUN 00.5 — Continuity Scorer Repair Specification

Status: design only  
Primary requirement: deterministic closed-set relational fidelity  
No numeric pass threshold, component weight, or scientific cutoff is selected here

## 1. Defect being repaired

The audited scorer uses identifier/phrase presence as a proxy for continuity. A response can gain credit by enumerating identifiers without preserving which identifier belongs to which thread, what its status is, or what action follows. Because the current runner still publishes composite continuity values, identifier shotgunning can masquerade as continuity.

The replacement must answer a stricter question:

> Did the candidate preserve the required relations, omit none, contradict none, and add no unsupported state claims?

Mention frequency is not relational fidelity. Verbosity is not evidence. A scorer may inspect only the information actually visible to the scored arm plus scorer-only gold relations; it may not ground every arm against hidden original artifacts.

## 2. Scorer-only task contract

Each static continuity task should carry a versioned, non-model-visible `RelationalGold` object:

```text
RelationalGold(
  task_id,
  entity_universe: tuple[EntityId, ...],
  predicate_universe: tuple[PredicateId, ...],
  required_relations: frozenset[Relation],
  allowed_supporting_relations: frozenset[Relation],
  contradiction_pairs: Mapping[Relation, frozenset[Relation]],
  permitted_aliases: Mapping[EntityId, frozenset[str]],
  model_visible_information_hash,
  schema_version
)

Relation(subject_id, predicate_id, object_id)
```

All IDs and predicates are closed-set and task-local. Suitable predicate categories include `has_goal`, `thread_status`, `preserves_fact`, `next_action`, `depends_on`, and `touches_thread`; the final versioned enum is an implementation artifact requiring approval, not an adaptive ontology.

Gold relations, contradiction maps, accepted answer phrases, and scorer labels must never enter the packet, repair prompt, padding, or model cache key.

## 3. Candidate representation

For continuity tasks, the output contract should add a required closed-set field:

```json
{
  "answer": "human-readable answer or paraphrase",
  "evidence_used": ["model-visible evidence identifiers"],
  "next_state": {"thread_touch": ["closed-set thread identifiers"]},
  "continuity_assertions": [
    {"subject_id": "...", "predicate_id": "...", "object_id": "..."}
  ]
}
```

The prose `answer` remains useful to the user, but the primary continuity result comes from the structured assertion set. The validator rejects unknown entities, predicates, relation shapes, duplicate relation records, and state operations before scoring.

If Anthony does not authorize this schema addition, the fallback is a pinned deterministic parser with an explicitly enumerated alias/relation grammar. That fallback will classify language outside the grammar as indeterminate, not guess with substrings. It is less capable of crediting free paraphrase and is not preferred.

## 4. Deterministic primary assessment

Let `R` be required relations, `A` be allowed supporting relations, and `C` be the candidate's validated assertion set.

The scorer returns sets and a categorical result, not an unratified weighted scalar:

- `correct_preservation = C ∩ R`;
- `omissions = R − C`;
- `unsupported_additions = C − (R ∪ A)`;
- `contradictions =` asserted relations explicitly mapped as contradicting a required relation, including a correct subject/predicate assigned the wrong object/status;
- `wrong_thread_assignments =` known entities joined by a non-gold subject/predicate/object relation;
- `duplicate_assertions =` repeated normalized relations detected before set conversion;
- `orphan_identifier_mentions =` known identifiers present in prose but absent from a validated assertion that uses them;
- `invented_identifiers =` identifier-like values outside the closed entity universe;
- `overproduction = true` when duplicate, unsupported, contradictory, invented, or relationless enumeration is present;
- `primary_continuity = EXACT_RELATIONAL_FIDELITY` only when every required relation is present and all failure sets are empty;
- otherwise `primary_continuity = RELATIONAL_FIDELITY_NOT_EARNED`;
- malformed or unobserved outputs are `NOT_SCORED` and retain their canonical terminal execution status.

This categorical rule contains no numeric threshold. Descriptive counts may be reported, but they may not be combined into a primary weighted score without later ratification.

### 4.1 Required distinctions

| Case | Required classification |
|---|---|
| Correct preservation | Relation appears exactly with the correct subject, predicate, and object; enters `correct_preservation`. |
| Omission | Required relation absent; enters `omissions`. Silence is not contradiction. |
| Contradiction | Candidate asserts a mutually exclusive/wrong relation; enters `contradictions`, even if the correct identifiers are also mentioned. |
| Unsupported addition | Well-formed relation is neither required nor allowed by model-visible evidence; enters `unsupported_additions`. |
| Identifier copying without relational fidelity | Identifier is merely named or listed with no validated relation; enters `orphan_identifier_mentions` and earns no preservation credit. |
| Overproduction/shotgun enumeration | Candidate lists all IDs, duplicates relations, or asserts alternative relations indiscriminately; enters the applicable failure sets and cannot produce exact relational fidelity. |
| Semantically correct paraphrase | Prose wording may vary without penalty when the structured relations are exact. If structured assertions are unavailable, paraphrase is handled only by the isolated semantic component below. |

Mentioning the required relation plus many unsupported relations does not pass. “Recall” divorced from precision is diagnostic only and cannot become the headline.

## 5. Grounding boundary

The scorer receives an `ArmEvidenceView` derived from the exact model-visible information set for that arm. Unsupported additions are assessed against that view. It must not receive original seed artifacts, hidden expected answers, or facts omitted from the arm and then use those hidden values to grant grounding credit.

Scorer-only gold relations establish correctness, but not model-visible support. A relation can therefore be gold yet unsupported by the actual packet; that is a packet-sufficiency defect, and the cell is protocol-invalid rather than model-wrong. The receipt records both hashes so this case is discoverable.

## 6. Semantic paraphrase component

Free-form semantic judgment is optional and separately labeled:

```text
SemanticParaphraseAssessment =
  NOT_RUN | DETERMINISTIC_ALIAS_MATCH | HUMAN_PASS | HUMAN_FAIL | INDETERMINATE
```

Rules:

- Exact IDs and approved aliases may be normalized deterministically.
- A correct prose paraphrase accompanied by exact structured relations receives the deterministic primary result regardless of prose wording.
- If a human or model judge is later authorized, it operates only on de-identified prose and a pinned rubric, records its identity and rationale, and cannot modify `primary_continuity`.
- Semantic judgment is never silently substituted for a missing structured assertion.
- No semantic-judge result may become the M0 headline without separate preregistration and authorization.

## 7. Status integration

The scorer is called only after typed inference, parse, and schema success:

- `TIMEOUT`, `TRANSPORT_ERROR`, `INVALID_RESPONSE`, `NO_FINAL_RESPONSE`, `NOT_RUN`, and `DRY_RUN_ONLY`: scorer not called; `NOT_SCORED`.
- `PARSE_FAILED` and `SCHEMA_FAILED`: scorer not called; `NOT_SCORED`.
- relation/schema-valid but fidelity failure: terminal `SEMANTIC_FAILED`, with the deterministic failure sets preserved.
- exact relational fidelity plus all other acceptance requirements: eligible for `COMPLETED_VALID` after required persistence/reload.

No failure is represented as a numeric zero or an empty successful answer.

## 8. Adversarial fixtures

All fixtures share one tiny closed universe with multiple threads and deliberately reusable identifiers so relation assignment, not token presence, controls the result.

| Fixture | Candidate behavior | Expected primary result | Required diagnostic |
|---|---|---|---|
| Exact correct state | Asserts every required relation once, no extras | `EXACT_RELATIONAL_FIDELITY` | all required relations in `correct_preservation`; all failure sets empty |
| Correct paraphrase | Uses different prose but emits the same exact structured relations | `EXACT_RELATIONAL_FIDELITY` | prose may receive deterministic alias match or remain separate; no primary penalty |
| One critical omission | Omits one required relation while preserving the others | `RELATIONAL_FIDELITY_NOT_EARNED` | exact missing tuple in `omissions` |
| One contradiction | Assigns a closed but mutually exclusive status/action | `RELATIONAL_FIDELITY_NOT_EARNED` | exact tuple pair in `contradictions` |
| All identifiers dumped without relations | Prose lists every entity; assertion set empty | `RELATIONAL_FIDELITY_NOT_EARNED` | identifiers in `orphan_identifier_mentions`; no preservation credit |
| Invented identifiers | Adds an ID outside the universe | validation failure before primary scoring | `SCHEMA_FAILED` with invented ID/path |
| Correct identifiers assigned to wrong threads | Uses only known IDs but swaps subject/object relations | `RELATIONAL_FIDELITY_NOT_EARNED` | `wrong_thread_assignments` and/or `contradictions` |
| Verbose but noncommittal | Long prose repeats goals and possibilities without assertions | `RELATIONAL_FIDELITY_NOT_EARNED` | required tuples in `omissions`; mentions, if any, orphaned |
| Malformed output | Truncated or non-JSON response | `NOT_SCORED` | terminal `PARSE_FAILED`, not a continuity value |
| Empty/no final response | Typed no-final response, or a genuinely observed empty final | `NOT_SCORED` | typed no-final remains `NO_FINAL_RESPONSE` with `output=null`; an observed empty candidate becomes `PARSE_FAILED`; neither is successful or scored |

Additional required fixtures:

- exact required relation plus an unsupported extra relation;
- exact required relations repeated many times;
- all possible subject/object combinations;
- correct entity IDs with wrong predicate;
- a gold relation absent from the model-visible evidence view;
- an answer-key phrase present only in the Episode B question;
- a relation copied from hidden artifacts but absent from the arm packet.

## 9. Receipt and reporting schema

Each scored candidate records:

- scorer and relation-schema version/hash;
- task gold hash and arm evidence-view hash;
- normalized candidate assertion set and duplicate records;
- each deterministic result set from §4;
- categorical primary result;
- optional semantic component and its provenance;
- execution terminal status and whether scoring was invoked;
- a declaration that no composite numeric continuity headline was emitted.

Aggregate reporting uses exact-relational-fidelity counts and categorical failure distributions over the planned denominator. It may show descriptive relation counts, but no weighted composite or pass threshold is created in RUN 00.5.

## 10. Independence and acceptance

The corpus author and scorer implementer should not silently tune aliases or relations against observed model outputs. The final fixture corpus must be frozen and content-addressed before any authorized model run. Changes after seeing output require a new version and provenance receipt.

The scorer repair is acceptable only when all adversarial fixtures pass and identifier shotgunning receives no primary continuity credit.

## 11. Decisions for Anthony

Anthony must approve:

1. adding required structured `continuity_assertions` to the static continuity output contract;
2. the versioned closed-set predicate vocabulary and task relation annotations;
3. whether an optional human/model semantic paraphrase component is permitted at all;
4. any future numeric aggregation, weight, threshold, or semantic-judge headline. None is selected here.
