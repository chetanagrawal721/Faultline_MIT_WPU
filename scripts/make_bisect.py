"""Generate the DDMin recovery fixture (M13.6): a producer and a consumer whose worlds differ by exactly eight packages.

    python scripts/make_bisect.py

Seven of the eight changes are harmless. One, Werkzeug 2.2.3 -> 3.0.6 under Flask 2.2.2, breaks `import acme_bisect.web` (Werkzeug 3 removed
`werkzeug.urls.url_quote`, which Flask 2.2.2 imports; this is the fact scenario D rests on, verified by scripts/verify_fixture_facts.py).
The expected result is written down before any run in fixtures/twist/bisect.yaml.

Lock files are produced like the other fixtures: `uv pip compile --generate-hashes --python-platform linux --python-version 3.12
--exclude-newer 2024-10-30 --only-binary :all:`. The consumer's pins are the reference lock's pins with the eight overrides below, so
nothing else differs between the two worlds.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOS = ROOT / "fixtures" / "repos"
CUTOFF = "2024-10-30T00:00:00Z"

REFERENCE_PINS = {"flask": "2.2.2", "werkzeug": "2.2.3", "itsdangerous": "2.1.2", "click": "8.1.3", "idna": "3.4", "pyparsing": "3.0.9",
                  "packaging": "23.0", "certifi": "2023.7.22", "charset-normalizer": "3.2.0"}
CONSUMER_OVERRIDES = {"werkzeug": "3.0.6", "itsdangerous": "2.2.0", "click": "8.1.7", "idna": "3.10", "pyparsing": "3.2.0", "packaging": "24.1",
                      "certifi": "2024.8.30", "charset-normalizer": "3.4.0"}
CAUSE = "werkzeug"
assert len(CONSUMER_OVERRIDES) == 8 and CAUSE in CONSUMER_OVERRIDES

FILES: dict[str, str] = {}


def put(rel: str, text: str) -> None:
    FILES[rel] = text.lstrip("\n")


put("acme-bisect/pyproject.toml", '''
[project]
name = "acme-bisect"
version = "1.0.0"
description = "A small library with several dependencies, for the Faultline minimisation recovery demonstration"
requires-python = ">=3.9"
dependencies = ["flask>=2.2", "idna", "pyparsing", "packaging", "certifi", "charset-normalizer"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/acme_bisect"]
''')
put("acme-bisect/README.md", '''
# acme-bisect

A Faultline fixture for the minimisation recovery demonstration (the Incremental Witness twist).

The reference world pins nine packages. The consumer `bisect-svc` pins the same set with **eight** of them at other versions. Seven of
those changes are harmless; Werkzeug 2.2.3 -> 3.0.6 under Flask 2.2.2 breaks `import acme_bisect.web`. Finding that one package among the
eight is what the delta-debugging search does, and the demonstration interrupts it part of the way and resumes it.

Expected result: `fixtures/twist/bisect.yaml`.
''')
put("acme-bisect/src/acme_bisect/__init__.py", '''
"""A library whose web module needs Flask. Only pure Python, so it can be mounted without a build step."""
__version__ = "1.0.0"
''')
put("acme-bisect/src/acme_bisect/util.py", '''
"""Uses six small packages at import time; none of their version changes in this fixture affects it."""
import certifi
import charset_normalizer
import idna
import packaging.version
import pyparsing

NAMES = (certifi.__name__, charset_normalizer.__name__, idna.__name__, packaging.version.__name__, pyparsing.__name__)
''')
put("acme-bisect/src/acme_bisect/web.py", '''
"""HTTP helpers. Flask 2.2.2 imports werkzeug.urls.url_quote when it is imported, and Werkzeug 3 removed it."""
from flask import Flask, jsonify


def make_app() -> Flask:
    app = Flask(__name__)

    @app.get("/ping")
    def ping():
        return jsonify({"ok": True})

    return app
''')
put("bisect-svc/README.md", '''
# bisect-svc

The consumer for the Faultline minimisation recovery demonstration. Its world differs from the producer `acme-bisect` by eight packages
(see that repository's README). It imports `acme_bisect.web` and `acme_bisect.util`.
''')
put("bisect-svc/app/main.py", '''
from acme_bisect.util import NAMES
from acme_bisect.web import make_app

app = make_app()
''')
put("bisect-svc/requirements.txt", "")                          # filled below: the pins plus the producer as a git dependency
put("fixtures_twist/bisect.yaml", f'''
# Expected result of analysing bisect-svc against acme-bisect, written before the first run.
id: BISECT
title: Eight differing packages, one breaks the import (minimisation recovery demonstration)
producer: acme-bisect
consumer: bisect-svc
delta: {sorted(CONSUMER_OVERRIDES)}
expect:
  verdict: BREAK_WITNESSED
  entry_point: acme_bisect.web
  signature: {{exc_type: ImportError, message_contains: url_quote}}
  attribution:
    minimal_set: [{CAUSE}]
    status: COMPLETE
    sidedness: two_sided
  search:
    singleton_tests: 8              # each of the eight packages alone
    full_set_tests: 1               # the whole delta must reproduce it too
    necessity_tests: 1              # the consumer world with the cause reverted must not fail
    total_sandbox_tests: 10
''')


def compile_lock(src: Path, out: Path) -> None:
    cmd = [sys.executable, "-m", "uv", "pip", "compile", str(src), "--generate-hashes", "--no-header", "--python-version", "3.12",
           "--python-platform", "x86_64-unknown-linux-gnu", "--exclude-newer", CUTOFF, "--only-binary", ":all:", "--no-annotate", "-q", "-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"uv compile failed for {src}:\n{r.stderr}")
    banner = (f"# Resolved by: uv pip compile --generate-hashes --python-version 3.12 --python-platform x86_64-unknown-linux-gnu "
              f"--exclude-newer {CUTOFF} --only-binary :all:\n# Source: {src.name}\n")
    out.write_text(banner + out.read_text(encoding="utf-8"), encoding="utf-8")


def pins_of(lock: Path) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)", lock.read_text(encoding="utf-8"), re.M)}


def main() -> int:
    for rel, text in FILES.items():
        p = (ROOT / "fixtures" / ("twist" if rel.startswith("fixtures_twist/") else "repos") / rel.removeprefix("fixtures_twist/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    art, svc = REPOS / "acme-bisect", REPOS / "bisect-svc"
    (art / "requirements.in").write_text("# Reference world: the pins the producer's own CI resolves\n" + "".join(f"{k}=={v}\n" for k, v in REFERENCE_PINS.items()), encoding="utf-8", newline="\n")
    compile_lock(art / "requirements.in", art / "requirements.lock.txt")
    ref = pins_of(art / "requirements.lock.txt")
    for k, v in REFERENCE_PINS.items():
        assert ref.get(k) == v, (k, ref.get(k))
    cons = {**ref, **CONSUMER_OVERRIDES}                      # every other package, including the transitive ones, is exactly the reference's
    (svc / "requirements.in").write_text("# The consumer's world: the reference pins with eight packages at other versions\n" + "".join(f"{k}=={v}\n" for k, v in sorted(cons.items())),
                                         encoding="utf-8", newline="\n")
    compile_lock(svc / "requirements.in", svc / "requirements.lock.txt")
    got = pins_of(svc / "requirements.lock.txt")
    delta = sorted(k for k in set(ref) | set(got) if ref.get(k) != got.get(k))
    assert delta == sorted(CONSUMER_OVERRIDES), f"the worlds must differ by exactly the eight packages, not {delta}"
    (svc / "requirements.txt").write_text("".join(f"{k}=={v}\n" for k, v in sorted(got.items() )) + "acme-bisect @ git+https://github.com/faultline-demo/acme-bisect@main\n",
                                          encoding="utf-8", newline="\n")
    print(f"wrote the fixture; the worlds differ by {len(delta)} packages: {', '.join(delta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
