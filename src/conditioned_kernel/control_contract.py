"""Packet sufficiency and mechanically matched controls (RUN 00.6D).

Exact UTF-8 byte equality is the primary budget contract.
Token counts are diagnostic only. No models are invoked here.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

PACKET_CONTRACT_VERSION = "ck.packet_contract.v1"
TASK_DEP_ANNOTATION_VERSION = "ck.task_dep.v1"
PADDING_MECHANISM_VERSION = "ck.padding.spaces_v1"
CONTROL_VERIFIER_VERSION = "ck.control_verifier.v1"

# Frozen padding: only U+0020 SPACE after a fixed delimiter with no task content.
PAD_DELIMITER = "\n<<CK_PAD>>\n"  # no relation names, no task identifiers
PAD_BYTE = b" "  # U+0020

# Scientific-experiment guard (ExecutionScope.SCIENTIFIC_EXPERIMENT)
SCIENTIFIC_EXPERIMENT_GATE_REASON = "experiment_contract_not_ratified"


class FieldClass(str, Enum):
    REQUIRED_TASK_FACT = "REQUIRED_TASK_FACT"
    REQUIRED_OPERATIONAL_STATE = "REQUIRED_OPERATIONAL_STATE"
    OPTIONAL_SUPPORT = "OPTIONAL_SUPPORT"
    FORBIDDEN_ANSWER_LEAKAGE = "FORBIDDEN_ANSWER_LEAKAGE"
    IRRELEVANT = "IRRELEVANT"


class ConditionId(str, Enum):
    C0_BARE = "C0_bare"
    C1_BUDGET_MATCHED_BARE = "C1_budget_matched_bare"
    C2_INSTRUCTION_IDENTICAL = "C2_instruction_identical"
    C3_STATIC_CK = "C3_static_ck"


class ControlVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"


class PacketCompileError(ValueError):
    """Packet failed sufficiency or classification contract."""

    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


class ControlContractError(ValueError):
    """Mechanical control comparison failed."""

    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


# Reason code used on ledger cells that fail control verification
CONTROL_CONTRACT_FAILED = "CONTROL_CONTRACT_FAILED"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utf8_len(data: bytes) -> int:
    return len(data)


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON; no silent Unicode normalization."""
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Task-dependency annotations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldAnnotation:
    field_id: str
    classification: FieldClass
    value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field_id": self.field_id,
            "classification": self.classification.value,
            "value": self.value,
        }


@dataclass(frozen=True)
class TaskDependencyAnnotation:
    task_id: str
    version: str
    fields: tuple[FieldAnnotation, ...]

    def classified(self, cls: FieldClass) -> list[FieldAnnotation]:
        return [f for f in self.fields if f.classification is cls]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "version": self.version,
            "fields": [f.to_dict() for f in self.fields],
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "TaskDependencyAnnotation":
        fields: list[FieldAnnotation] = []
        for raw in data.get("fields") or []:
            try:
                cls = FieldClass(str(raw["classification"]))
            except ValueError as e:
                raise PacketCompileError(
                    "UNKNOWN_FIELD_CLASSIFICATION",
                    f"unknown classification: {raw.get('classification')!r}",
                ) from e
            fields.append(
                FieldAnnotation(
                    field_id=str(raw["field_id"]),
                    classification=cls,
                    value=str(raw["value"]),
                )
            )
        return TaskDependencyAnnotation(
            task_id=str(data["task_id"]),
            version=str(data.get("version") or TASK_DEP_ANNOTATION_VERSION),
            fields=tuple(fields),
        )


def validate_annotation(ann: TaskDependencyAnnotation) -> None:
    """Fail closed on unknown classes (already parsed) and empty required sets."""
    if not ann.task_id:
        raise PacketCompileError("MISSING_TASK_ID")
    if not ann.classified(FieldClass.REQUIRED_TASK_FACT):
        raise PacketCompileError("MISSING_REQUIRED_TASK_FACT_ANNOTATIONS")
    if not ann.classified(FieldClass.REQUIRED_OPERATIONAL_STATE):
        raise PacketCompileError("MISSING_REQUIRED_OPERATIONAL_STATE_ANNOTATIONS")
    # Forbidden values must be non-empty strings if present
    for f in ann.classified(FieldClass.FORBIDDEN_ANSWER_LEAKAGE):
        if not f.value:
            raise PacketCompileError("EMPTY_FORBIDDEN_LEAKAGE_VALUE", f.field_id)


# ---------------------------------------------------------------------------
# Runtime / shared instruction surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeSettings:
    model_tag: str
    temperature: float = 0.3
    seed: int = 42
    num_ctx: int = 2048
    endpoint: str = "http://127.0.0.1:11434"
    runtime_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_tag": self.model_tag,
            "temperature": self.temperature,
            "seed": self.seed,
            "num_ctx": self.num_ctx,
            "endpoint": self.endpoint,
            "runtime_version": self.runtime_version,
        }

    def fingerprint(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_dict()))


# Shared operative instructions for C1/C2/C3 (not C0 bare).
SHARED_SYSTEM_INSTRUCTIONS = (
    "Local conditioned-kernel continuity aperture. "
    "Return ONLY valid JSON matching the provided output schema. "
    "Use only closed-set identifiers supplied in the packet. "
    "Do not invent identifiers, relations, or free-form memory authority. "
    "No tools, cloud, or files."
)

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "continuity_assertions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_id": {"type": "string"},
                    "relation": {"type": "string"},
                    "object_id": {"type": "string"},
                },
                "required": ["subject_id", "relation", "object_id"],
            },
        }
    },
    "required": ["continuity_assertions"],
}


def output_schema_hash() -> str:
    return sha256_hex(canonical_json_bytes(OUTPUT_SCHEMA))


def instruction_block_hash(system_text: str) -> str:
    return sha256_hex(system_text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Packet compilation
# ---------------------------------------------------------------------------


def _sorted_fact_lines(fields: Sequence[FieldAnnotation]) -> list[str]:
    items = sorted(fields, key=lambda f: f.field_id)
    return [f"{f.field_id}={f.value}" for f in items]


def _content_body(
    *,
    condition: ConditionId,
    ann: TaskDependencyAnnotation,
    accepted_relations: Sequence[Mapping[str, str]] | None,
    include_reconstructed_state: bool,
) -> dict[str, Any]:
    required_facts = ann.classified(FieldClass.REQUIRED_TASK_FACT)
    operational = ann.classified(FieldClass.REQUIRED_OPERATIONAL_STATE)
    optional = ann.classified(FieldClass.OPTIONAL_SUPPORT)

    if not required_facts:
        raise PacketCompileError("MISSING_REQUIRED_TASK_FACT")
    if not operational:
        raise PacketCompileError("MISSING_REQUIRED_OPERATIONAL_STATE")

    body: dict[str, Any] = {
        "condition": condition.value,
        "task_id": ann.task_id,
        "packet_contract_version": PACKET_CONTRACT_VERSION,
        "task_dep_version": ann.version,
        "required_task_facts": _sorted_fact_lines(required_facts),
        "required_operational_state": _sorted_fact_lines(operational),
        "output_schema": OUTPUT_SCHEMA,
        "unknown_behavior": (
            "If no valid closed-set assertion can be formed, return "
            '{"continuity_assertions":[]} which will be rejected as incomplete.'
        ),
    }
    if optional:
        body["optional_support"] = _sorted_fact_lines(optional)
    if include_reconstructed_state:
        # C3 only: reconstructed continuity relations from verified replay.
        rels = list(accepted_relations or [])
        body["accepted_relations"] = sorted(
            [
                {
                    "subject_id": str(r["subject_id"]),
                    "relation": str(r["relation"]),
                    "object_id": str(r["object_id"]),
                }
                for r in rels
            ],
            key=lambda x: (x["subject_id"], x["relation"], x["object_id"]),
        )
    return body


def _scan_forbidden(body: Mapping[str, Any], ann: TaskDependencyAnnotation) -> None:
    """Fail if forbidden leakage values appear in model-visible body bytes."""
    blob = canonical_json_bytes(body).decode("utf-8")
    for f in ann.classified(FieldClass.FORBIDDEN_ANSWER_LEAKAGE):
        if f.value and f.value in blob:
            raise PacketCompileError(
                "FORBIDDEN_ANSWER_LEAKAGE",
                f"forbidden value for {f.field_id} present in packet",
            )


def apply_space_padding(user_content: str, target_user_utf8_len: int) -> tuple[str, int]:
    """Append deterministic U+0020 padding after PAD_DELIMITER to hit exact byte length.

    Returns (padded_user_content, padding_byte_count).
    """
    raw = user_content.encode("utf-8")
    if len(raw) > target_user_utf8_len:
        raise PacketCompileError(
            "BYTE_BUDGET_OVERFLOW",
            f"content {len(raw)} exceeds target {target_user_utf8_len}",
        )
    need = target_user_utf8_len - len(raw)
    if need == 0:
        return user_content, 0
    # Delimiter + spaces must fit exactly in `need` bytes.
    delim = PAD_DELIMITER.encode("utf-8")
    if need < len(delim):
        # Pad with pure spaces only when delimiter cannot fit.
        return user_content + (" " * need), need
    spaces = need - len(delim)
    padded = user_content + PAD_DELIMITER + (" " * spaces)
    assert len(padded.encode("utf-8")) == target_user_utf8_len
    return padded, need


def build_serialized_model_input(
    *,
    condition: ConditionId,
    system_text: str,
    user_content: str,
    runtime: RuntimeSettings,
    schema: Mapping[str, Any] | None = None,
) -> bytes:
    """Exact UTF-8 bytes of the runtime request surface (no silent NFC).

    This is the object hashed/compared by the control verifier: the JSON
    serialization of messages + format + options that would be sent to Ollama.
    """
    sch = schema if schema is not None else OUTPUT_SCHEMA
    payload = {
        "model": runtime.model_tag,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_content},
        ],
        "format": sch,
        "stream": False,
        "options": {
            "temperature": runtime.temperature,
            "seed": runtime.seed,
            "num_ctx": runtime.num_ctx,
        },
    }
    return canonical_json_bytes(payload)


@dataclass(frozen=True)
class CompiledPacket:
    condition_id: ConditionId
    task_id: str
    system_text: str
    user_content: str  # includes padding region when applied
    padding_bytes: int
    schema: dict[str, Any]
    runtime: RuntimeSettings
    body: dict[str, Any]
    complete_bytes: bytes
    packet_contract_version: str = PACKET_CONTRACT_VERSION
    task_dep_version: str = TASK_DEP_ANNOTATION_VERSION
    padding_mechanism_version: str = PADDING_MECHANISM_VERSION

    @property
    def byte_count(self) -> int:
        return len(self.complete_bytes)

    @property
    def input_sha256(self) -> str:
        return sha256_hex(self.complete_bytes)

    def to_receipt_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id.value,
            "task_id": self.task_id,
            "byte_count": self.byte_count,
            "input_sha256": self.input_sha256,
            "system_sha256": sha256_hex(self.system_text.encode("utf-8")),
            "user_sha256": sha256_hex(self.user_content.encode("utf-8")),
            "instruction_block_hash": instruction_block_hash(self.system_text),
            "output_schema_hash": sha256_hex(canonical_json_bytes(self.schema)),
            "padding_bytes": self.padding_bytes,
            "padding_mechanism_version": self.padding_mechanism_version,
            "packet_contract_version": self.packet_contract_version,
            "task_dep_version": self.task_dep_version,
            "runtime": self.runtime.to_dict(),
            "scientific_completion": False,
        }


def compile_condition_packet(
    condition: ConditionId,
    ann: TaskDependencyAnnotation,
    runtime: RuntimeSettings,
    *,
    accepted_relations: Sequence[Mapping[str, str]] | None = None,
    target_complete_bytes: int | None = None,
    bare_prompt: str | None = None,
) -> CompiledPacket:
    """Compile one condition's model-visible input. Fail closed on sufficiency."""
    validate_annotation(ann)

    if condition is ConditionId.C0_BARE:
        system_text = "Answer the task briefly."
        prompt = bare_prompt or "Complete the task."
        # C0: minimal — only required facts concatenated, no schema identity claim
        facts = "; ".join(_sorted_fact_lines(ann.classified(FieldClass.REQUIRED_TASK_FACT)))
        user_content = f"{prompt}\nFacts: {facts}"
        body = {"condition": condition.value, "user_content": user_content}
        schema: dict[str, Any] = {}  # bare may omit structured schema
        complete = build_serialized_model_input(
            condition=condition,
            system_text=system_text,
            user_content=user_content,
            runtime=runtime,
            schema=schema if schema else {"type": "object"},
        )
        return CompiledPacket(
            condition_id=condition,
            task_id=ann.task_id,
            system_text=system_text,
            user_content=user_content,
            padding_bytes=0,
            schema=schema if schema else {"type": "object"},
            runtime=runtime,
            body=body,
            complete_bytes=complete,
            task_dep_version=ann.version,
        )

    include_state = condition is ConditionId.C3_STATIC_CK
    body = _content_body(
        condition=condition,
        ann=ann,
        accepted_relations=accepted_relations,
        include_reconstructed_state=include_state,
    )
    _scan_forbidden(body, ann)

    # Shared instructions for C1/C2/C3
    system_text = SHARED_SYSTEM_INSTRUCTIONS
    # Canonical body serialization (representation region)
    representation = canonical_json_bytes(body).decode("utf-8")
    user_content = "Packet:\n" + representation
    padding_bytes = 0

    if condition is ConditionId.C1_BUDGET_MATCHED_BARE and target_complete_bytes is not None:
        # Iteratively pad user content until complete request hits target.
        # C1 user content is flat serialization of the same body without
        # accepted_relations (structure contrast lives in C3 only).
        flat_body = _content_body(
            condition=condition,
            ann=ann,
            accepted_relations=None,
            include_reconstructed_state=False,
        )
        _scan_forbidden(flat_body, ann)
        representation = canonical_json_bytes(flat_body).decode("utf-8")
        user_content = "Packet:\n" + representation
        body = flat_body
        # Binary search / linear expand padding to hit exact complete byte length.
        base = build_serialized_model_input(
            condition=condition,
            system_text=system_text,
            user_content=user_content,
            runtime=runtime,
            schema=OUTPUT_SCHEMA,
        )
        if len(base) > target_complete_bytes:
            raise PacketCompileError(
                "BYTE_BUDGET_OVERFLOW",
                f"C1 base {len(base)} > target {target_complete_bytes}",
            )
        # Adding N bytes to user content does not always add N to complete JSON
        # (escaping). Search for padding count that yields exact total.
        user_content, padding_bytes = _pad_user_to_complete_target(
            system_text=system_text,
            user_content=user_content,
            runtime=runtime,
            condition=condition,
            target=target_complete_bytes,
        )

    complete = build_serialized_model_input(
        condition=condition,
        system_text=system_text,
        user_content=user_content,
        runtime=runtime,
        schema=OUTPUT_SCHEMA,
    )
    return CompiledPacket(
        condition_id=condition,
        task_id=ann.task_id,
        system_text=system_text,
        user_content=user_content,
        padding_bytes=padding_bytes,
        schema=dict(OUTPUT_SCHEMA),
        runtime=runtime,
        body=body,
        complete_bytes=complete,
        task_dep_version=ann.version,
    )


def _pad_user_to_complete_target(
    *,
    system_text: str,
    user_content: str,
    runtime: RuntimeSettings,
    condition: ConditionId,
    target: int,
) -> tuple[str, int]:
    """Find space padding yielding exact complete request UTF-8 length."""
    # Upper bound: target spaces is more than enough (JSON escaping of spaces is 1:1).
    lo, hi = 0, target + 64
    best: tuple[str, int] | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid == 0:
            candidate = user_content
            pad_n = 0
        else:
            delim = PAD_DELIMITER
            # mid is desired extra bytes in user string UTF-8
            if mid < len(delim.encode("utf-8")):
                candidate = user_content + (" " * mid)
                pad_n = mid
            else:
                spaces = mid - len(delim.encode("utf-8"))
                candidate = user_content + delim + (" " * max(0, spaces))
                pad_n = mid
        complete = build_serialized_model_input(
            condition=condition,
            system_text=system_text,
            user_content=candidate,
            runtime=runtime,
            schema=OUTPUT_SCHEMA,
        )
        n = len(complete)
        if n == target:
            # Validate padding content
            _assert_padding_inert(candidate[len(user_content) :])
            return candidate, pad_n
        if n < target:
            lo = mid + 1
            best = (candidate, pad_n)
        else:
            hi = mid - 1
    raise PacketCompileError(
        "BYTE_MATCH_UNACHIEVABLE",
        f"could not hit exact target {target} (best={best})",
    )


def _assert_padding_inert(padding_region: str) -> None:
    """Padding may only be delimiter + U+0020 spaces."""
    if not padding_region:
        return
    # Allow optional delimiter then only spaces
    rest = padding_region
    if rest.startswith(PAD_DELIMITER):
        rest = rest[len(PAD_DELIMITER) :]
    if rest and not all(ch == " " for ch in rest):
        raise PacketCompileError(
            "PADDING_NOT_INERT",
            "padding contains non-space characters",
        )
    # No task-like tokens in delimiter itself beyond fixed PAD_DELIMITER
    if re.search(r"thread_|question_|relation|remains_open|is_answered", padding_region):
        raise PacketCompileError("PADDING_CONTAINS_IDENTIFIER")


def scan_padding_for_leaks(
    padding_region: str,
    *,
    forbidden_fragments: Iterable[str],
    relation_names: Iterable[str],
    identifiers: Iterable[str],
) -> None:
    """Adversarial scan: padding must not contain answers, relations, or ids."""
    if not padding_region:
        return
    for frag in forbidden_fragments:
        if frag and frag in padding_region:
            raise PacketCompileError("PADDING_CONTAINS_ANSWER_FRAGMENT", frag)
    for rel in relation_names:
        if rel and rel in padding_region:
            raise PacketCompileError("PADDING_CONTAINS_RELATION", rel)
    for ident in identifiers:
        if ident and ident in padding_region:
            raise PacketCompileError("PADDING_CONTAINS_IDENTIFIER", ident)


# ---------------------------------------------------------------------------
# Control verifier
# ---------------------------------------------------------------------------


@dataclass
class ControlComparisonReceipt:
    condition_pair: tuple[str, str]
    task_id: str
    verdict: ControlVerdict
    reason_codes: list[str]
    left: dict[str, Any]
    right: dict[str, Any]
    intended_differences: list[str]
    prohibited_mismatches: list[str]
    permitted_padding: dict[str, Any]
    packet_contract_version: str
    task_dep_version: str
    verifier_version: str
    repo_commit: str | None
    scientific_completion: bool = False
    headline_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_pair": list(self.condition_pair),
            "task_id": self.task_id,
            "verdict": self.verdict.value,
            "reason_codes": list(self.reason_codes),
            "left": self.left,
            "right": self.right,
            "intended_differences": list(self.intended_differences),
            "prohibited_mismatches": list(self.prohibited_mismatches),
            "permitted_padding": dict(self.permitted_padding),
            "packet_contract_version": self.packet_contract_version,
            "task_dep_version": self.task_dep_version,
            "verifier_version": self.verifier_version,
            "repo_commit": self.repo_commit,
            "scientific_completion": False,
            "headline_eligible": self.headline_eligible and self.verdict is ControlVerdict.PASS,
        }


def _task_fact_set(packet: CompiledPacket) -> list[str]:
    return list(packet.body.get("required_task_facts") or [])


def _operational_set(packet: CompiledPacket) -> list[str]:
    return list(packet.body.get("required_operational_state") or [])


def verify_control_pair(
    left: CompiledPacket,
    right: CompiledPacket,
    *,
    require_byte_equality: bool,
    require_instruction_identity: bool,
    require_task_fact_identity: bool = True,
    require_schema_identity: bool = True,
    require_runtime_identity: bool = True,
    intended_differences: Sequence[str] | None = None,
    repo_commit: str | None = None,
) -> ControlComparisonReceipt:
    """Mechanically compare two compiled runtime inputs. Fail closed on drift."""
    reasons: list[str] = []
    prohibited: list[str] = []
    intended = list(intended_differences or [])

    left_r = left.to_receipt_dict()
    right_r = right.to_receipt_dict()

    if left.task_id != right.task_id:
        prohibited.append("TASK_ID_MISMATCH")
        reasons.append("TASK_ID_MISMATCH")

    if require_runtime_identity:
        if left.runtime.model_tag != right.runtime.model_tag:
            prohibited.append("MODEL_TAG_MISMATCH")
            reasons.append("MODEL_TAG_MISMATCH")
        if left.runtime.fingerprint() != right.runtime.fingerprint():
            prohibited.append("GENERATION_PARAMETER_MISMATCH")
            reasons.append("GENERATION_PARAMETER_MISMATCH")

    if require_instruction_identity:
        if left.system_text != right.system_text:
            prohibited.append("INSTRUCTION_MISMATCH")
            reasons.append("INSTRUCTION_MISMATCH")
        if instruction_block_hash(left.system_text) != instruction_block_hash(right.system_text):
            prohibited.append("INSTRUCTION_HASH_MISMATCH")
            reasons.append("INSTRUCTION_HASH_MISMATCH")

    if require_schema_identity:
        if canonical_json_bytes(left.schema) != canonical_json_bytes(right.schema):
            prohibited.append("OUTPUT_SCHEMA_MISMATCH")
            reasons.append("OUTPUT_SCHEMA_MISMATCH")

    if require_task_fact_identity:
        if _task_fact_set(left) != _task_fact_set(right):
            prohibited.append("TASK_FACT_MISMATCH")
            reasons.append("TASK_FACT_MISMATCH")
        if _operational_set(left) != _operational_set(right):
            # C3 may add accepted_relations under operational contrast — only compare
            # required_operational_state lines from annotations.
            prohibited.append("OPERATIONAL_STATE_MISMATCH")
            reasons.append("OPERATIONAL_STATE_MISMATCH")

    if require_byte_equality:
        if left.byte_count != right.byte_count:
            prohibited.append("BYTE_COUNT_MISMATCH")
            reasons.append(
                f"BYTE_COUNT_MISMATCH:{left.byte_count}!={right.byte_count}"
            )
        if left.complete_bytes != right.complete_bytes:
            # Byte equality of complete input is the primary contract when required.
            # Structure contrast means complete bytes may differ in content even
            # when lengths match — for C1 vs C3 we require length equality and
            # same facts/instructions/schema/runtime, not identical full bytes.
            # Spec: "Treatment and byte-matched control have exact UTF-8 byte equality"
            # for the budget contract on the *budget-matched* dimension.
            # C1 is padded to match C3's complete byte *count*; content differs by design.
            pass
        if left.byte_count != right.byte_count:
            pass  # already recorded
        else:
            # Exact length match achieved
            pass

    # One-byte drift detection helper is on lengths when equality required
    if require_byte_equality and abs(left.byte_count - right.byte_count) == 1:
        prohibited.append("ONE_BYTE_DRIFT")
        reasons.append("ONE_BYTE_DRIFT")

    padding_info = {
        "left_padding_bytes": left.padding_bytes,
        "right_padding_bytes": right.padding_bytes,
        "mechanism": PADDING_MECHANISM_VERSION,
    }

    verdict = ControlVerdict.PASS if not prohibited else ControlVerdict.FAIL
    if prohibited:
        reasons.insert(0, CONTROL_CONTRACT_FAILED)

    return ControlComparisonReceipt(
        condition_pair=(left.condition_id.value, right.condition_id.value),
        task_id=left.task_id,
        verdict=verdict,
        reason_codes=reasons,
        left=left_r,
        right=right_r,
        intended_differences=intended,
        prohibited_mismatches=prohibited,
        permitted_padding=padding_info,
        packet_contract_version=PACKET_CONTRACT_VERSION,
        task_dep_version=left.task_dep_version,
        verifier_version=CONTROL_VERIFIER_VERSION,
        repo_commit=repo_commit,
        scientific_completion=False,
        headline_eligible=(verdict is ControlVerdict.PASS),
    )


def verify_c3_vs_c1(
    c3: CompiledPacket,
    c1: CompiledPacket,
    *,
    repo_commit: str | None = None,
) -> ControlComparisonReceipt:
    """Primary structure contrast: same facts/instructions/schema/runtime/byte count."""
    return verify_control_pair(
        c3,
        c1,
        require_byte_equality=True,
        require_instruction_identity=True,
        require_task_fact_identity=True,
        require_schema_identity=True,
        require_runtime_identity=True,
        intended_differences=[
            "C3 includes reconstructed accepted_relations organization",
            "C1 is flat serialization without persistent-state organization",
            "C1 may include inert space padding to match C3 UTF-8 byte count",
        ],
        repo_commit=repo_commit,
    )


def build_matched_c3_c1_pair(
    ann: TaskDependencyAnnotation,
    runtime: RuntimeSettings,
    *,
    accepted_relations: Sequence[Mapping[str, str]] | None = None,
    repo_commit: str | None = None,
) -> tuple[CompiledPacket, CompiledPacket, ControlComparisonReceipt]:
    """Compile C3 then C1 padded to C3 complete byte length; verify pair."""
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK,
        ann,
        runtime,
        accepted_relations=accepted_relations,
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE,
        ann,
        runtime,
        target_complete_bytes=c3.byte_count,
    )
    # Padding leak scan on C1 padding region
    base_user = "Packet:\n" + canonical_json_bytes(c1.body).decode("utf-8")
    pad_region = c1.user_content[len(base_user) :] if c1.user_content.startswith(base_user) else ""
    ids = [f.field_id for f in ann.fields] + [f.value for f in ann.fields]
    rels = ["remains_open", "is_answered", "depends_on", "blocked_by", "references"]
    forbidden = [f.value for f in ann.classified(FieldClass.FORBIDDEN_ANSWER_LEAKAGE)]
    scan_padding_for_leaks(
        pad_region,
        forbidden_fragments=forbidden,
        relation_names=rels,
        identifiers=ids,
    )
    receipt = verify_c3_vs_c1(c3, c1, repo_commit=repo_commit)
    return c3, c1, receipt


# ---------------------------------------------------------------------------
# Contrast documentation helpers
# ---------------------------------------------------------------------------

CONTRAST_DEFINITIONS: dict[str, dict[str, str]] = {
    "C3_vs_C0": {
        "isolates": (
            "Substrate-organized packet vs minimal bare prompt — confounded by "
            "information volume, instructions, and schema."
        ),
        "not_isolates": "Pure structure; not a clean causal control.",
    },
    "C3_vs_C1": {
        "isolates": (
            "Structure of persistent-state organization under exact UTF-8 byte "
            "budget, shared instructions, shared task facts, shared schema, "
            "shared runtime."
        ),
        "not_isolates": "Instruction wording differences (held fixed).",
    },
    "C3_vs_C2": {
        "isolates": (
            "Presence of reconstructed continuity state under shared instructions, "
            "facts, and schema; byte budget measured and disclosed, not forced equal."
        ),
        "not_isolates": "Exact byte budget (may differ).",
    },
}


# ---------------------------------------------------------------------------
# Scientific-experiment scope guard
# ---------------------------------------------------------------------------


def require_ratified_experiment_contract(
    execution_scope: str,
    experiment_contract_id: str | None,
) -> None:
    """Fail closed if scientific_experiment is selected without a ratified id."""
    if execution_scope != "scientific_experiment":
        return
    if not experiment_contract_id:
        raise ControlContractError(
            SCIENTIFIC_EXPERIMENT_GATE_REASON,
            "ExecutionScope.SCIENTIFIC_EXPERIMENT requires a ratified "
            "experiment_contract_id; candidate acceptance alone is insufficient",
        )


def assert_no_scientific_completion_in_control_receipt(
    receipt: ControlComparisonReceipt,
) -> None:
    if receipt.scientific_completion:
        raise ControlContractError(
            "CONTROL_RECEIPT_SCIENCE_LIE",
            "control receipts must not claim scientific completion",
        )


# ---------------------------------------------------------------------------
# Unicode handling (explicit; no silent normalization)
# ---------------------------------------------------------------------------


def bytes_nfc_nfd_differ(text: str) -> bool:
    """True when NFC and NFD encodings differ (adversarial fixture helper)."""
    nfc = unicodedata.normalize("NFC", text).encode("utf-8")
    nfd = unicodedata.normalize("NFD", text).encode("utf-8")
    return nfc != nfd


def hash_without_normalization(text: str) -> str:
    """Hash exact UTF-8 of the given Python str as-is (no NFC/NFD)."""
    return sha256_hex(text.encode("utf-8"))
