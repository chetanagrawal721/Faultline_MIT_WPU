"""Builds the screenshot document from the pictures that scripts/capture_ui.py took.

    python tools/fl.py script scripts/build_ui_doc.py

Writes docs/UI_SCREENSHOTS.md (pictures linked from docs/screenshots) and docs/UI_SCREENSHOTS.pdf (the same pages with the pictures inside).
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"
INTRO = ("These pictures were taken from the running application, in LIVE mode, by `scripts/capture_ui.py`. Nothing is drawn or edited: the script opens each page in a "
         "browser, shows the real analysis of the main example (the library `faultline-fixture-acme-models` against the consumer `faultline-fixture-notify-svc`), and saves what is rendered. "
         "Each picture is the whole page. The light theme is shown here; the dark theme of every page is in the same folder with the suffix `-dark`.")
GROUPS = [("The product site", ("01", "02", "03")), ("The workspace", ("10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23")),
          ("Close-ups used in the demo", ("30", "31"))]


def load(theme: str) -> dict:
    f = SHOTS / f"index-{theme}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"shots": []}


def main() -> int:
    light, dark = load("light"), load("dark")
    if not light["shots"]:
        print("no screenshots: run scripts/capture_ui.py first")
        return 1
    by_prefix = {s["file"][:2]: s for s in light["shots"]}
    dark_files = {s["file"][:2]: s["file"] for s in dark["shots"]}
    md = ["# Faultline: the interface, page by page", "", INTRO, "",
          f"Window size {light['width']} x {light['height']} px; each picture is as tall as its page. The full-size files are in `docs/screenshots/`.", "", "## Contents", ""]
    for title, prefixes in GROUPS:
        md.append(f"- **{title}**: " + ", ".join(f"[{by_prefix[p]['title']}](#{by_prefix[p]['file'][:-10]})" for p in prefixes if p in by_prefix))
    md.append("")
    page_html = []
    for title, prefixes in GROUPS:
        md += [f"## {title}", ""]
        page_html.append(f"<h2>{html.escape(title)}</h2>")
        for p in prefixes:
            s = by_prefix.get(p)
            if not s:
                continue
            anchor = s["file"][:-10]
            md += [f'<a id="{anchor}"></a>', f"### {s['title']}", "", f"{s['note']}", "", f"Route: `{s['route']}`", "", f"![{s['title']}](screenshots/{s['file']})", ""]
            if p in dark_files:
                md += [f"Dark theme: [`{dark_files[p]}`](screenshots/{dark_files[p]})", ""]
            page_html.append(f'<section><h3>{html.escape(s["title"])}</h3><p>{html.escape(s["note"])}</p><p class="route">{html.escape(s["route"])}</p>'
                             f'<img src="{(SHOTS / s["file"]).as_uri()}" alt="{html.escape(s["title"])}"></section>')
    (ROOT / "docs" / "UI_SCREENSHOTS.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    doc = ("<!doctype html><meta charset='utf-8'><title>Faultline: the interface</title><style>"
           "@page{size:1100px 1500px;margin:36px}body{font:15px/1.5 'Segoe UI',system-ui,sans-serif;color:#1f1e1b}h1{font-size:30px;margin:0 0 8px}"
           "h2{font-size:22px;margin:28px 0 6px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:18px;margin:20px 0 2px}p{margin:4px 0 8px}.route{color:#6a665c;font:13px Consolas,monospace}"
           "img{width:100%;border:1px solid #d8d4c8;border-radius:6px}section{margin-bottom:26px}</style>"
           f"<h1>Faultline: the interface, page by page</h1><p>{html.escape(INTRO.replace('`', ''))}</p>" + "".join(page_html))
    tmp = SHOTS / "_ui_doc.html"
    tmp.write_text(doc, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto(tmp.as_uri())
        pg.wait_for_load_state("networkidle")
        pg.pdf(path=str(ROOT / "docs" / "UI_SCREENSHOTS.pdf"), prefer_css_page_size=True, print_background=True)
        b.close()
    tmp.unlink()
    print("wrote docs/UI_SCREENSHOTS.md and docs/UI_SCREENSHOTS.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
