"""Takes screenshots of every page of the running interface and writes the screenshot document.

    python tools/fl.py script scripts/capture_ui.py                    # light theme, to docs/screenshots, and the documents docs/UI_SCREENSHOTS.md and .pdf
    python tools/fl.py script scripts/capture_ui.py --theme dark       # the dark theme
    python tools/fl.py script scripts/capture_ui.py --base http://127.0.0.1:8000 --width 1440 --height 900

The project must be running (python tools/fl.py up) and hold at least one finished analysis. The pages shown are real: the script opens the interface in a
browser, chooses the newest analysis that contains a witnessed break, opens that analysis's own finding and witness, and takes each picture from the page
as it is rendered. Nothing is drawn or edited.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (file stem, route after #/, title, what it shows and what to point at)
PAGES = [
    ("01-home", "", "Product site: home", "The public front page. It states the claim (witnesses, not warnings) before anyone logs in."),
    ("02-how-it-works", "how", "Product site: how it works", "The pipeline in plain steps: pin, relate, build two worlds, run three times each, witness, attribute, fix."),
    ("03-capabilities", "capabilities", "Product site: capabilities", "What is supported and what is not, stated openly."),
    ("10-overview", "app", "Workspace: Overview", "Counts of investigations and findings, the outcome chart, jobs by status, the Reuse and recomputation panel, the analysis funnel and what needs attention."),
    ("11-new-analysis", "app/new", "New analysis", "Paste the library and the consumer. Both are pinned to exact commits before anything runs."),
    ("12-findings", "app/findings", "Findings", "Every verdict in one list, with its mode (LIVE) and the sentence that states what was and was not shown."),
    ("13-finding", "app/finding/{finding}", "Finding detail (BREAK WITNESSED)", "The scoped verdict, what the evidence establishes, the why-path, both worlds, the dependency delta, the six runs, the scope, re-run and fix."),
    ("14-witness", "app/witness/{finding}", "Witness detail", "Three fresh passes against three fresh failures with the same signature, the six-run board and the raw output."),
    ("15-finding-inconclusive", "app/finding/{inconclusive}", "Finding detail (INCONCLUSIVE)", "An unsettled result is never shown as a pass: the reasons are listed, grouped by cause."),
    ("16-world-matrix", "app/worlds", "World matrix", "The reference world, the consumer world, and the exact delta: only the packages whose versions differ."),
    ("17-relationships", "app/relationships", "Relationships", "Why two repositories are related: the file and line in both manifests at the pinned commit."),
    ("18-inventory-graph", "app/inventory", "Inventory graph", "Repositories, manifests and packages as a graph with evidence-backed edges."),
    ("19-evidence", "app/evidence", "Evidence", "The bundle behind a witness: artifacts with their SHA-256, the manifest, integrity and replay."),
    ("20-jobs", "app/jobs", "Jobs", "Every background job with its status, run time, wait time, failure class and attempts."),
    ("21-repositories", "app/repository", "Repositories", "The pinned snapshot of each repository and its inventory."),
    ("22-capabilities-and-coverage", "app/coverage", "Capabilities and coverage", "What this deployment can do per ecosystem, which oracles exist and which features are enabled."),
    ("23-settings", "app/settings", "Settings", "Theme, access token and application information."),
]
CROPS = [
    ("30-reuse-panel", "app", "[data-testid=\"reuse-counters\"]", "Reuse and recomputation (the twist)", "Pairs reused, pairs recomputed, stored objects rejected, worlds reused and built, with the reason for each pair. Counted from the append-only event log."),
    ("31-funnel", "app", "[data-testid=\"funnel\"]", "Analysis funnel", "Every stage as a recorded count, from submitted to verdict."),
]


def get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=30) as r:        # noqa: S310
        return json.loads(r.read())


def choose(base: str) -> dict:
    """The project to show: the newest with a witnessed break that names both a library and a consumer; its finding and witness; and an inconclusive finding."""
    findings = get(base, "/api/findings")
    inconclusive = next((f["finding_id"] for f in findings if f["verdict"] == "INCONCLUSIVE"), None)
    best = None
    for p in get(base, "/api/projects"):
        try:
            view = get(base, f"/api/projects/{p['id']}/analysis")
        except Exception:      # noqa: BLE001 - a project without an analysis is skipped
            continue
        cell = next((c for c in view.get("cells", []) if c.get("verdict") == "BREAK_WITNESSED" and c.get("finding_id")), None)
        if cell and view.get("status") == "DONE" and "notify-svc" in " ".join(r["name"] for r in p["repositories"]) and (best is None or view["started_at"] > best["started"]):
            best = {"project": p["id"], "finding": cell["finding_id"], "started": view["started_at"], "name": p["name"]}
    if best is None:
        raise SystemExit("no finished analysis with a witnessed break was found: run the main example first")
    best["inconclusive"] = inconclusive or best["finding"]
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--out", default=str(ROOT / "docs" / "screenshots"))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pick = choose(a.base)
    taken: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": a.width, "height": a.height}, device_scale_factor=1, color_scheme=a.theme)
        ctx.add_init_script(f"window.localStorage.setItem('faultline-theme','{a.theme}');window.localStorage.setItem('faultline-active-project','{pick['project']}');")
        page = ctx.new_page()

        def settle() -> None:
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1200)

        for stem, route, title, note in PAGES:
            path = route.format(**pick)
            page.goto(f"{a.base}/#/{path}")
            page.reload()
            settle()
            if route.startswith("app/inventory"):
                page.wait_for_timeout(1500)
            f = out / f"{stem}-{a.theme}.png"
            # the picture is as tall as the page, so the side navigation (as tall as the window) reaches the bottom instead of stopping at the first screen
            tall = min(max(a.height, page.evaluate("document.documentElement.scrollHeight")), 4200)
            page.set_viewport_size({"width": a.width, "height": tall})
            page.wait_for_timeout(500)
            page.screenshot(path=str(f), full_page=tall >= 4200)
            page.set_viewport_size({"width": a.width, "height": a.height})
            taken.append({"file": f.name, "title": title, "note": note, "route": f"#/{path}"})
            print("  ok  ", f.name)
        page.goto(f"{a.base}/#/app")
        page.reload()
        settle()
        for stem, _route, selector, title, note in CROPS:
            el = page.locator(selector).first
            box = el.locator("xpath=ancestor::section[contains(@class,'work-panel')]").first
            target = box if box.count() else el
            f = out / f"{stem}-{a.theme}.png"
            target.screenshot(path=str(f))
            taken.append({"file": f.name, "title": title, "note": note, "route": "#/app (crop)"})
            print("  ok  ", f.name)
        browser.close()
    (out / f"index-{a.theme}.json").write_text(json.dumps({"project": pick, "theme": a.theme, "width": a.width, "height": a.height, "shots": taken}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
