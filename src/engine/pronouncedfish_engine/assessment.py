"""Experimental single-substitution CTC evidence, not clinical pronunciation scores.

This is a restricted baseline, NOT a reproduction of the published GOP-SF method.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Sequence

from .analysis import analyze
from .phonetics import canonical_phone
from .recognition import AudioInput, RecognitionResult

METHOD = "ctc-single-substitution-log-support-v1"


@dataclass(frozen=True)
class CTCEvidence:
    """One utterance's T×C normalized log probabilities, kept out of public JSON.

    phone_token_ids maps COMPLETE phone spellings to SINGLE native output classes.
    Adapters exclude marks and special symbols. ignored_token_ids (word separators)
    are merged into blank for phone-only scoring. Different sounds cannot share IDs.
    """

    log_probs: Any
    phone_token_ids: Mapping[str, int]
    blank_id: int
    model_version: str
    ignored_token_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class RecognitionRun:
    recognition: RecognitionResult
    evidence: Optional[CTCEvidence]


class EvidenceRecognizer(Protocol):
    """An implemented boundary for future models, without a plugin registry.

    A non-CTC adapter can return evidence=None rather than fake CTC capability.
    """

    def recognize_with_evidence(self, audio: AudioInput) -> RecognitionRun: ...


def _phone_map(evidence, classes):
    mapping = {}
    ignored = set(evidence.ignored_token_ids)
    valid_id = lambda i: isinstance(i, int) and not isinstance(i, bool) and 0 <= i < classes
    if not valid_id(evidence.blank_id):
        raise ValueError("Invalid CTC blank ID.")
    if any(not valid_id(i) or i == evidence.blank_id for i in ignored):
        raise ValueError("Invalid ignored CTC token ID.")
    for phone, token_id in evidence.phone_token_ids.items():
        if (not isinstance(phone, str) or not phone or any(c.isspace() for c in phone)
                or not valid_id(token_id) or token_id == evidence.blank_id or token_id in ignored):
            raise ValueError("Invalid complete-phone CTC mapping.")
        normalized = canonical_phone(phone)
        if normalized in mapping and mapping[normalized] != token_id:
            raise ValueError("Conflicting normalized phone mappings.")
        mapping[normalized] = token_id
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Distinct phones cannot share a CTC output class.")
    return mapping


def score_ctc(evidence: Optional[CTCEvidence], target_phones: Sequence[str]) -> dict:
    """Contrast full-target CTC probability against single-position substitutions.

    At each position, conditional_log_support = log P_CTC(target|audio) minus
    logsumexp over sequences replacing that position with each candidate (target
    included). The margin compares the target with the best NON-target candidate.
    All CTC paths are summed; no segment boundaries are assumed. No insertions or
    deletions enter the denominator. These model-specific scores are uncalibrated.
    """
    import torch
    import torch.nn.functional as F

    if isinstance(target_phones, (str, bytes)):
        raise ValueError("Expected a sequence of complete target phones.")
    target = list(target_phones)
    if not target or any(not isinstance(p, str) or not p or any(c.isspace() for c in p) for p in target):
        raise ValueError("Target must contain nonempty complete phone tokens.")
    result = {
        "status": "unavailable", "method": METHOD,
        "model_version": evidence.model_version if evidence else None,
        "calibration_status": "unavailable", "score_unit": "natural_log",
        "target_phones": target, "candidate_phones": [],
        "target_sequence_log_probability": None, "phone_scores": [],
        "requires_review": True, "review_reason": "No compatible CTC evidence was supplied.",
    }
    if evidence is None:
        return result
    values = torch.as_tensor(evidence.log_probs).detach().to(device="cpu", dtype=torch.float64).clone()
    if values.ndim != 2 or not 0 < values.shape[0] <= 2000 or values.shape[1] < 2:
        raise ValueError("CTC evidence must be a nonempty T×C matrix with at most 2000 frames.")
    if torch.isnan(values).any() or torch.isposinf(values).any() or not torch.allclose(
        torch.logsumexp(values, dim=-1), torch.zeros(values.shape[0], dtype=values.dtype), atol=1e-4, rtol=0
    ):
        raise ValueError("CTC evidence must contain normalized log probabilities.")
    # Remove float32 log-softmax rounding residuals before summing many paths.
    values -= torch.logsumexp(values, dim=-1, keepdim=True)
    mapping = _phone_map(evidence, values.shape[1])
    candidates = sorted(mapping)
    result["candidate_phones"] = candidates
    if not 2 <= len(candidates) <= 128 or len(target) > 128:
        result["review_reason"] = "Experimental limits: 2–128 candidate classes and at most 128 target phones."
        return result
    unknown = [p for p in target if canonical_phone(p) not in mapping]
    if unknown:
        result["review_reason"] = "Target phones lack single-class CTC mappings: " + ", ".join(unknown)
        return result
    if evidence.ignored_token_ids:
        ids = [evidence.blank_id, *set(evidence.ignored_token_ids)]
        values[:, evidence.blank_id] = torch.logsumexp(values[:, ids], dim=1)
        values[:, list(set(evidence.ignored_token_ids))] = -torch.inf
    ids = torch.tensor([mapping[canonical_phone(p)] for p in target], dtype=torch.long)
    candidate_ids = torch.tensor([mapping[p] for p in candidates], dtype=torch.long)
    count, length = len(candidates), len(target)

    def sequence_log_probs(sequences):
        batch = sequences.shape[0]
        return -F.ctc_loss(
            values[:, None, :].expand(-1, batch, -1).contiguous(), sequences,
            torch.full((batch,), values.shape[0], dtype=torch.long),
            torch.full((batch,), length, dtype=torch.long),
            blank=evidence.blank_id, reduction="none", zero_infinity=False,
        )

    canonical_logp = sequence_log_probs(ids[None, :])[0]
    if not torch.isfinite(canonical_logp):
        result["review_reason"] = "No finite CTC path supports the full target sequence; no phone scores assigned."
        return result
    result["target_sequence_log_probability"] = float(canonical_logp)
    for index, phone in enumerate(target):
        sequences = ids.repeat(count, 1)
        sequences[:, index] = candidate_ids
        probabilities = sequence_log_probs(sequences)
        alternatives = probabilities.masked_fill(candidate_ids == ids[index], -torch.inf)
        best = int(alternatives.argmax())
        row = {
            "expected_index": index, "expected_phone": phone, "status": "unavailable",
            "conditional_log_support": None, "best_alternative_phone": None,
            "log_margin_vs_best_alternative": None,
            "reason": "No finite non-target alternative path exists.",
        }
        if torch.isfinite(alternatives[best]):
            row.update(status="ok",
                       conditional_log_support=min(0.0, float(canonical_logp - torch.logsumexp(probabilities, dim=0))),
                       best_alternative_phone=candidates[best],
                       log_margin_vs_best_alternative=float(canonical_logp - alternatives[best]), reason=None)
        result["phone_scores"].append(row)
    assessed = sum(row["status"] == "ok" for row in result["phone_scores"])
    result.update(
        status="ok" if assessed == length else "partial" if assessed else "unavailable",
        calibration_status="uncalibrated" if assessed else "unavailable",
        review_reason="Experimental single-substitution evidence, conditioned on the surrounding target. Not correctness, severity, distortion detection, or full GOP-SF; human review required.",
    )
    return result


def assess(recognizer: EvidenceRecognizer, audio: AudioInput, expected_phones: Sequence[str], *,
           acceptable_variants=(), supported_substitutions=()) -> dict:
    """One acoustic forward pass, followed by symbolic and acoustic comparisons.

    Symbolic analysis chooses the supplied variant; acoustic scoring uses the same
    variant. Frame matrices remain in memory and are not serialized into results.
    """
    run = recognizer.recognize_with_evidence(audio)
    comparison = analyze(run.recognition, expected_phones,
                         acceptable_variants=acceptable_variants,
                         supported_substitutions=supported_substitutions)
    evidence = run.evidence if comparison["status"] == "ok" else None
    if evidence is not None and evidence.model_version != run.recognition["model_version"]:
        raise ValueError("Recognition and acoustic evidence model versions disagree.")
    acoustic = score_ctc(evidence, comparison["selected_expected_phones"] or comparison["expected_phones"])
    if acoustic["model_version"] is None:
        acoustic["model_version"] = run.recognition["model_version"]
    if comparison["status"] != "ok":
        acoustic["review_reason"] = "Recognition is unassessable; no acoustic phone scores assigned."
    return {"recognition": run.recognition, "analysis": comparison, "acoustic_assessment": acoustic}
