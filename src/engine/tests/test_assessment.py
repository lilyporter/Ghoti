"""Acoustic math checked against explicit CTC path enumeration, not itself."""

import itertools
import json
import math
from types import SimpleNamespace

import pytest
import torch

from pronouncedfish_engine import CTCEvidence, RecognitionRun, assess, score_ctc


def evidence(probabilities, mapping=None, blank=0, ignored=()):
    return CTCEvidence(torch.tensor(probabilities, dtype=torch.float64).log(),
                       {"a": 1, "b": 2} if mapping is None else mapping, blank, "test-model@1", ignored)


def enumerate_probability(probabilities, target, blank=0, ignored=()):
    total = 0.0
    for path in itertools.product(range(len(probabilities[0])), repeat=len(probabilities)):
        mapped = [blank if p in ignored else p for p in path]
        collapsed = [p for i, p in enumerate(mapped) if i == 0 or p != mapped[i-1]]
        collapsed = [p for p in collapsed if p != blank]
        if collapsed == target:
            total += math.prod(probabilities[t][p] for t, p in enumerate(path))
    return total


@pytest.mark.parametrize("target", [["a"], ["a", "b"], ["a", "a"]])
def test_sequence_and_substitution_scores_match_exhaustive_ctc_paths(target):
    probabilities = [[.2, .6, .2], [.5, .1, .4], [.2, .3, .5]]
    result = score_ctc(evidence(probabilities), target)
    ids = [1 if p == "a" else 2 for p in target]
    base = enumerate_probability(probabilities, ids)
    assert result["target_sequence_log_probability"] == pytest.approx(math.log(base))
    for index, row in enumerate(result["phone_scores"]):
        changed = list(ids); changed[index] = 3 - ids[index]
        alternative = enumerate_probability(probabilities, changed)
        assert row["conditional_log_support"] == pytest.approx(math.log(base / (base + alternative)))
        assert row["log_margin_vs_best_alternative"] == pytest.approx(math.log(base / alternative))
    json.dumps(result, allow_nan=False)


def test_same_decoded_label_different_audio_evidence_changes_score():
    strong = score_ctc(evidence([[.05, .9, .05]]), ["a"])
    weak = score_ctc(evidence([[.05, .50, .45]]), ["a"])
    assert strong["phone_scores"][0]["conditional_log_support"] > weak["phone_scores"][0]["conditional_log_support"]


def test_word_separators_are_marginalized_into_blank_without_mutating_evidence():
    probs = [[.1, .6, .1, .2], [.1, .1, .2, .6], [.1, .5, .2, .2]]
    source = evidence(probs, ignored=(3,))
    before = source.log_probs.clone()
    result = score_ctc(source, ["a", "a"])
    expected = enumerate_probability(probs, [1, 1], ignored=(3,))
    assert result["target_sequence_log_probability"] == pytest.approx(math.log(expected))
    assert torch.equal(before, source.log_probs)


def test_model_native_ids_and_complete_affricate_aliases_are_supported():
    # Blank need not be 0; a complete native affricate need not be one character.
    result = score_ctc(evidence([[.8, .1, .1]], {"t͡ʃ": 0, "d": 1}, blank=2), ["ʧ"])
    assert result["status"] == "ok"
    assert result["target_phones"] == ["ʧ"]
    assert result["phone_scores"][0]["best_alternative_phone"] == "d"


@pytest.mark.parametrize("target", [["ã"], ["a͡ɪ"], ["?"]])
def test_unknown_multiclass_phones_are_unavailable_not_silently_stripped(target):
    result = score_ctc(evidence([[.2, .4, .4]]), target)
    assert result["status"] == "unavailable"
    assert result["phone_scores"] == []
    assert "single-class" in result["review_reason"]


def test_unalignable_and_zero_probability_paths_never_produce_json_nan_or_infinity():
    for source, target in [(evidence([[.2, .4, .4]]), ["a", "a"]),
                           (evidence([[0, 1, 0]]), ["a"])]:
        result = score_ctc(source, target)
        assert result["status"] == "unavailable"
        json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("source", [
    CTCEvidence([[0, 0, 0]], {"a": 1, "b": 2}, 0, "test"),
    CTCEvidence([[float("nan"), -1, -2]], {"a": 1, "b": 2}, 0, "test"),
    evidence([[.2, .4, .4]], {"a": 1, "b": 1}),
    evidence([[.2, .4, .4]], {"a": 0, "b": 1}),
    evidence([[.2, .4, .4]], ignored=(1,)),
    evidence([[.2, .4, .4]], {"g": 1, "ɡ": 2}),
])
def test_incompatible_evidence_is_rejected(source):
    with pytest.raises(ValueError):
        score_ctc(source, ["a"])


def test_no_ctc_capability_has_an_explicit_unavailable_result():
    result = score_ctc(None, ["a"])
    assert result["status"] == "unavailable"
    assert result["calibration_status"] == "unavailable"


def test_partial_result_and_resource_limits_are_explicit():
    result = score_ctc(evidence([[0, 1, 0], [1, 0, 0], [0, .5, .5]]), ["a", "a"])
    assert result["status"] == "partial"
    assert [r["status"] for r in result["phone_scores"]] == ["unavailable", "ok"]
    assert score_ctc(evidence([[.2, .4, .4]]), ["a"] * 129)["status"] == "unavailable"
    assert score_ctc(evidence([[.2, .4, .4]], {}), ["a"])["status"] == "unavailable"
    json.dumps(result, allow_nan=False)


def test_model_adapter_replacement_and_single_pass():
    pytest.importorskip("jiwer"); pytest.importorskip("panphon")
    class OwnModel:
        calls = 0
        def recognize_with_evidence(self, audio):
            self.calls += 1
            return RecognitionRun(
                {"status": "ok", "recognized_phones": ["a"], "model_version": "test-model@1"},
                evidence([[.1, .8, .1]]),
            )
    model = OwnModel()
    result = assess(model, None, ["b"], acceptable_variants=[["a"]])
    assert model.calls == 1
    assert result["analysis"]["selected_variant_index"] == 1
    assert result["acoustic_assessment"]["target_phones"] == ["a"]
    assert result["acoustic_assessment"]["status"] == "ok"
    assert "log_probs" not in json.dumps(result)


def test_unassessable_recognition_never_receives_acoustic_scores():
    model = SimpleNamespace(recognize_with_evidence=lambda audio: RecognitionRun(
        {"status": "unassessable", "recognized_phones": [], "model_version": "test-model@1"},
        evidence([[.1, .8, .1]]),
    ))
    result = assess(model, None, ["a"])
    assert result["acoustic_assessment"]["status"] == "unavailable"
    assert result["acoustic_assessment"]["phone_scores"] == []


def test_model_version_mismatch_is_rejected():
    pytest.importorskip("jiwer"); pytest.importorskip("panphon")
    model = SimpleNamespace(recognize_with_evidence=lambda audio: RecognitionRun(
        {"status": "ok", "recognized_phones": ["a"], "model_version": "different-model"},
        evidence([[.1, .8, .1]]),
    ))
    with pytest.raises(ValueError, match="versions disagree"):
        assess(model, None, ["a"])


def test_assess_cli_preserves_the_combined_result(monkeypatch, capsys):
    pytest.importorskip("jiwer"); pytest.importorskip("panphon")
    from pronouncedfish_engine.cli import main
    class OwnModel:
        def __init__(self, *args, **kwargs): pass
        def recognize_with_evidence(self, audio):
            return RecognitionRun(
                {"status": "ok", "recognized_phones": ["a"], "model_version": "test-model@1"},
                evidence([[.1, .8, .1]]),
            )
    monkeypatch.setattr("pronouncedfish_engine.pasketti.PaskettiRecognizer", OwnModel)
    monkeypatch.setattr("pronouncedfish_engine.audio.load_audio", lambda _: None)
    monkeypatch.setattr("sys.argv", ["engine", "assess", "sample.wav", "--expected-phones", "b"])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert set(output) == {"recognition", "analysis", "acoustic_assessment"}
    assert output["acoustic_assessment"]["status"] == "ok"
