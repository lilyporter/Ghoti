"""Token alignment and descriptive feature regressions, without model weights."""

import json
import socket
from copy import deepcopy

import pytest

pytest.importorskip("jiwer")
pytest.importorskip("panphon")

from pronouncedfish_engine import analyze
from pronouncedfish_engine.cli import main


def recognition(phones, status="ok"):
    return {"status": status, "recognized_phones": phones}


def test_voicing_substitution_returns_heatmap_values():
    result = analyze(recognition(["d"]), ["t"], supported_substitutions=[("t", "d")])
    row = result["alignment"][0]
    features = row["feature_comparison"]
    assert result["edit_counts"] == {"substitutions": 1, "omissions": 0, "additions": 0}
    assert row["kind"] == "substitution"
    assert row["supported_substitution"] is True
    assert features["manhattan_distance"] == 2
    differences = dict(zip(result["feature_names"], features["absolute_differences"]))
    assert differences.pop("voi") == 2
    assert set(differences.values()) == {0}
    assert result["requires_review"] is True
    assert result["distortion_status"] == "not_assessed"


@pytest.mark.parametrize("heard,expected,kind,indexes", [
    (["k", "t"], ["k", "æ", "t"], "omission", (1, None)),
    (["k", "æ", "s", "t"], ["k", "æ", "t"], "addition", (None, 2)),
])
def test_gaps_have_no_fake_zero_distance(heard, expected, kind, indexes):
    result = analyze(recognition(heard), expected)
    row = next(r for r in result["alignment"] if r["kind"] == kind)
    assert (row["expected_index"], row["recognized_index"]) == indexes
    assert row["feature_status"] == "not_applicable"
    assert row["feature_comparison"] is None


def test_accepted_variant_and_tie_breaking():
    result = analyze(recognition(["k", "ɑ", "t"]), ["k", "ɒ", "t"],
                     acceptable_variants=[["k", "ɑ", "t"]])
    assert result["matches_target"] is True
    assert result["selected_variant_index"] == 1
    assert result["expected_phones"] == ["k", "ɒ", "t"]
    assert result["selected_expected_phones"] == ["k", "ɑ", "t"]
    tied = analyze(recognition(["d"]), ["t"], acceptable_variants=[["b"]])
    assert tied["selected_variant_index"] == 0


@pytest.mark.parametrize("heard,expected", [
    (["ʧ", "g"], ["t͡ʃ", "ɡ"]),
    (["ʤ"], ["d͡ʒ"]),
    (["ã"], ["a\u0303"]),
])
def test_spelling_aliases_match_without_changing_output(heard, expected):
    result = analyze(recognition(heard), expected)
    assert result["matches_target"] is True
    assert [r["recognized_phone"] for r in result["alignment"]] == heard
    assert all(r["feature_comparison"]["manhattan_distance"] == 0
               for r in result["alignment"])


def test_distinct_sounds_and_marks_are_not_stripped():
    for heard, expected in [("ã", "a"), ("aː", "a"), ("ɹ", "r")]:
        result = analyze(recognition([heard]), [expected])
        assert result["matches_target"] is False
        assert result["edit_counts"]["substitutions"] == 1
        assert result["alignment"][0]["supported_substitution"] is False


def test_feature_lookup_never_silently_drops_or_splits_unknown_phone():
    for unknown in ["t?", "a͡ɪ", "🦈"]:
        result = analyze(recognition([unknown]), ["t"])
        row = result["alignment"][0]
        assert row["recognized_phone"] == unknown
        assert row["feature_status"] == "unavailable"
        assert row["feature_comparison"] is None


def test_repeated_tokens_and_multicodepoint_phone_indices():
    result = analyze(recognition(["ʧ", "ã", "ã"]), ["t͡ʃ", "ã"])
    assert result["edit_counts"] == {"substitutions": 0, "omissions": 0, "additions": 1}
    assert len(result["alignment"]) == 3
    assert [r["recognized_index"] for r in result["alignment"]] == [0, 1, 2]


@pytest.mark.parametrize("heard,status", [([], "ok"), ([], "unassessable"), (["d"], "unassessable")])
def test_unassessable_recognition_does_not_become_omissions(heard, status):
    result = analyze(recognition(heard, status), ["t"])
    assert result["status"] == "unassessable"
    assert result["alignment"] == []
    assert result["edit_counts"] is None
    assert result["matches_target"] is None


def test_substitution_inventory_is_directional():
    result = analyze(recognition(["t"]), ["d"], supported_substitutions=[("t", "d")])
    assert result["alignment"][0]["supported_substitution"] is False


def test_analysis_is_offline_and_preserves_inputs(monkeypatch):
    from pronouncedfish_engine.analysis import _feature_table

    def forbidden(*args, **kwargs):
        pytest.fail("Analysis must not open a network connection")

    _feature_table.cache_clear()
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    source = recognition(["ʧ", "d"])
    before = deepcopy(source)
    expected = ["t͡ʃ", "t"]
    result = analyze(source, expected)
    assert source == before
    assert expected == ["t͡ʃ", "t"]
    # Results must be serializable and cannot mutate the cached feature table.
    json.dumps(result, ensure_ascii=False)
    result["alignment"][1]["feature_comparison"]["expected_vector"][0] = 999
    fresh = analyze(source, expected)
    assert 999 not in fresh["alignment"][1]["feature_comparison"]["expected_vector"]


@pytest.mark.parametrize("target", [[], "cat", [""], ["k æ"], [1]])
def test_bad_target_rejected(target):
    with pytest.raises(ValueError):
        analyze(recognition(["t"]), target)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-be", "utf-32"])
def test_cli_analyzes_saved_unicode_json(encoding, tmp_path, monkeypatch, capsys):
    source = tmp_path / "recognition.json"
    source.write_text(json.dumps(recognition(["ð"]), ensure_ascii=False), encoding=encoding)
    monkeypatch.setattr("sys.argv", ["engine", "analyze", str(source), "--expected-phones", "θ"])
    assert main() == 0
    output = capsys.readouterr().out
    # Legacy PowerShell may decode native UTF-8 as cp437 then write UTF-16.
    # ASCII-only redirected JSON preserves IPA through that conversion.
    assert output.isascii()
    powershell_bytes = output.encode("utf-8").decode("cp437").encode("utf-16")
    result = json.loads(powershell_bytes)
    assert result["edit_counts"]["substitutions"] == 1
    assert result["alignment"][0]["recognized_phone"] == "ð"


@pytest.mark.parametrize("payload,exit_code", [
    (recognition([], "unassessable"), 2),
    ({"status": "ok", "recognized_phones": "t"}, 1),
    ({"unexpected": True}, 1),
])
def test_cli_handles_unassessable_and_malformed_results(payload, exit_code, tmp_path, monkeypatch, capsys):
    source = tmp_path / "recognition.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["engine", "analyze", str(source), "--expected-phones", "t"])
    assert main() == exit_code
    captured = capsys.readouterr()
    if exit_code == 2:
        assert json.loads(captured.out)["edit_counts"] is None
    else:
        assert "Engine error" in captured.err
