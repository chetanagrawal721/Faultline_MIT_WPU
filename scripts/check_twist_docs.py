"""Checks the twist documents (TC-13.12.4 and TC-13.12.5).

    python scripts/check_twist_docs.py            # both checks; exit 1 if either fails

Claims: every row of the verified list in docs/INCREMENTAL_WITNESS_REPORT.md names at least one evidence file, and every file the report names exists.
Wording: the twist documents, the guides and the strings the twist added to the interface and the language server contain none of the words the product never
uses ("compatible", "proof", "guarantee", "AI detected") except where the line says it is not claiming them, and no verdict word is written in another case.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "INCREMENTAL_WITNESS_REPORT.md"
BANNED = re.compile(r"\b(compatible|compatibility|proof|proofs|guarantee|guarantees|guaranteed|AI[- ]detected)\b", re.IGNORECASE)
DISCLAIMED = re.compile(r"\b(never|not|no|nothing|avoid|without|banned|cannot|does not|do not)\b", re.IGNORECASE)
VERDICTS = ["BREAK WITNESSED", "SILENT DIVERGENCE WITNESSED", "NO DIVERGENCE OBSERVED", "NOT EXPOSED", "EXPOSED", "POTENTIAL", "INCONCLUSIVE", "HYGIENE"]
SCANNED = [*sorted((ROOT / "docs").glob("INCREMENTAL_WITNESS_*.md")), ROOT / "docs" / "DEMO_GUIDE.md", ROOT / "docs" / "DEMO_GUIDE_SIMPLE.md", ROOT / "docs" / "DEMO_COMPLETE.md",
           ROOT / "docs" / "adr" / "0008-incremental-witness.md", ROOT / "frontend" / "src" / "app" / "views" / "Reuse.tsx",
           ROOT / "backend" / "faultline" / "analysis" / "static.py", ROOT / "backend" / "faultline" / "analysis" / "incremental.py",
           *sorted((ROOT / "backend" / "faultline" / "lsp").glob("*.py"))]
PATH = re.compile(r"`((?:evidence|tests|scripts|docs|backend|frontend|editors|fixtures)/[^`\s]+?)`")


def claim_problems() -> list[str]:
    text = REPORT.read_text(encoding="utf-8")
    problems = []
    verified = text.split("## 1. Verified", 1)[1].split("## 2.", 1)[0]
    for line in verified.splitlines():
        if re.match(r"\| V\d+ \|", line):
            paths = PATH.findall(line)
            if not paths:
                problems.append(f"claim without evidence: {line[:90]}")
    for p in sorted(set(PATH.findall(text))):
        if "*" in p or p.endswith("/"):
            continue
        if not (ROOT / p).exists():
            problems.append(f"named file does not exist: {p}")
    return problems


def wording_problems() -> list[str]:
    problems = []
    for f in SCANNED:
        if not f.exists():
            problems.append(f"missing: {f.relative_to(ROOT)}")
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in BANNED.finditer(line):
                if not DISCLAIMED.search(line):
                    problems.append(f"{f.relative_to(ROOT)}:{n}: '{m.group(0)}' without saying it is not claimed")
            if f.suffix == ".md":
                for v in VERDICTS:
                    for m in re.finditer(re.escape(v), line, re.IGNORECASE):
                        if m.group(0) != v and not m.group(0).islower() and m.group(0) != v.capitalize():
                            problems.append(f"{f.relative_to(ROOT)}:{n}: verdict word written as '{m.group(0)}', exact form is '{v}'")
    return problems


def main() -> int:
    c, w = claim_problems(), wording_problems()
    for p in c:
        print("CLAIMS  ", p)
    for p in w:
        print("WORDING ", p)
    print(f"claims: {'ok' if not c else str(len(c)) + ' problem(s)'}; wording: {'ok' if not w else str(len(w)) + ' problem(s)'}")
    return 1 if c or w else 0


if __name__ == "__main__":
    sys.exit(main())
