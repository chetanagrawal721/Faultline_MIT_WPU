"""TC-13.12.5 (wording) on the real twist documents, and the checker itself on text that must and must not be flagged."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_twist_docs", ROOT / "scripts" / "check_twist_docs.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)


def test_the_twist_documents_and_strings_use_no_banned_wording():
    assert chk.wording_problems() == []


def test_the_checker_flags_a_claim_and_accepts_a_disclaimer(tmp_path, monkeypatch):
    f = tmp_path / "x.md"
    f.write_text("This is a guarantee of fit.\nWe never give a guarantee.\nThe word Break Witnessed is misspelt.\nBREAK WITNESSED is right.\n", encoding="utf-8")
    monkeypatch.setattr(chk, "SCANNED", [f])
    monkeypatch.setattr(chk, "ROOT", tmp_path)
    got = chk.wording_problems()
    assert any(":1:" in p and "guarantee" in p for p in got)
    assert not any(":2:" in p for p in got)
    assert any(":3:" in p and "Break Witnessed" in p for p in got)
    assert not any(":4:" in p for p in got)
