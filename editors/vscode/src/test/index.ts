import * as fs from "fs";
import * as vscode from "vscode";

// Runs inside VS Code. Two modes:
//   * one check (FAULTLINE_TEST_FILE, FAULTLINE_TEST_LINE, FAULTLINE_TEST_SEVERITY): open a Python file, wait for the Faultline diagnostic the language
//     server publishes and check the line and the severity the editor itself holds;
//   * steps (FAULTLINE_TEST_STEPS, a JSON file): open and check diagnostics, apply the verified fix through the editor's own code action, switch the API
//     the server reads (as after a new analysis) and check that the diagnostic is gone.
// It throws (and so fails the session) when anything differs. Every step is appended to FAULTLINE_EVIDENCE_LOG as a JSON line.

const SEVERITY = ["Error", "Warning", "Information", "Hint"];
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const note = (o: object) => process.env.FAULTLINE_EVIDENCE_LOG && fs.appendFileSync(process.env.FAULTLINE_EVIDENCE_LOG, JSON.stringify({ at: new Date().toISOString(), ...o }) + "\n");

type Step = {
  open?: string;
  expect?: { line: number; severity: string };
  expect_none?: boolean;
  apply_fix?: string;
  target?: string;
  expect_last_line?: string;
  set_api?: string;
};

function faultlineDiagnostics(uri: vscode.Uri): vscode.Diagnostic[] {
  return vscode.languages.getDiagnostics(uri).filter((d) => d.source === "faultline");
}

function describe(d: vscode.Diagnostic, doc: vscode.TextDocument) {
  return { line: d.range.start.line + 1, column: d.range.start.character, endColumn: d.range.end.character, severity: SEVERITY[d.severity], code: String(typeof d.code === "object" ? d.code.value : d.code), message: d.message, lineText: doc.lineAt(d.range.start.line).text };
}

async function waitDiagnostic(doc: vscode.TextDocument, seconds = 90): Promise<vscode.Diagnostic[]> {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    const found = faultlineDiagnostics(doc.uri);
    if (found.length) return found;
    await sleep(500);
  }
  return [];
}

async function open(file: string): Promise<vscode.TextDocument> {
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
  await vscode.window.showTextDocument(doc);
  note({ event: "opened in VS Code", file, language: doc.languageId, vscode: vscode.version });
  return doc;
}

function check(doc: vscode.TextDocument, found: vscode.Diagnostic[], want: { line: number; severity: string }) {
  if (!found.length) {
    note({ event: "no Faultline diagnostic arrived", file: doc.fileName });
    throw new Error(`no Faultline diagnostic arrived for ${doc.fileName}`);
  }
  const seen = describe(found[0], doc);
  note({ event: "diagnostic held by VS Code", file: doc.fileName, count: found.length, ...seen });
  if (seen.line !== want.line) throw new Error(`the diagnostic is on line ${seen.line}, expected ${want.line}`);
  if (seen.severity !== want.severity) throw new Error(`the severity is ${seen.severity}, expected ${want.severity}`);
  if (!/^[A-Z ]+: /.test(seen.message)) throw new Error("the message does not start with a verdict word");
  note({ event: "checks passed", file: doc.fileName, line: seen.line, severity: seen.severity });
}

async function runStep(s: Step): Promise<void> {
  if (s.open && s.expect) {
    const doc = await open(s.open);
    check(doc, await waitDiagnostic(doc), s.expect);
  } else if (s.open && s.expect_none) {
    const g = globalThis as unknown as { __faultline?: { seq: number; state: string } };
    const doc = await open(s.open);
    const until = Date.now() + 60_000;
    while (Date.now() < until && g.__faultline?.state !== "ready") await sleep(500);
    await sleep(6000);                                           // the server answers on open; give it time to publish before looking
    const found = faultlineDiagnostics(doc.uri);
    note({ event: "diagnostics after the new analysis", file: doc.fileName, count: found.length, serverState: g.__faultline?.state });
    if (found.length) throw new Error(`a Faultline diagnostic is still shown after the new analysis: ${found[0].message}`);
    note({ event: "checks passed", file: doc.fileName, diagnosticGone: true });
  } else if (s.apply_fix && s.target) {
    const doc = await open(s.apply_fix);
    const found = await waitDiagnostic(doc);
    if (!found.length) throw new Error("no diagnostic to fix");
    const actions = (await vscode.commands.executeCommand<vscode.CodeAction[]>("vscode.executeCodeActionProvider", doc.uri, found[0].range, vscode.CodeActionKind.QuickFix.value)) || [];
    const mine = actions.filter((a) => a.title.startsWith("Faultline: add "));
    note({ event: "code actions offered by VS Code", file: doc.fileName, titles: actions.map((a) => a.title) });
    if (mine.length !== 1 || !mine[0].edit) throw new Error(`expected exactly one Faultline code action with an edit, got ${mine.length}`);
    const targetUri = vscode.Uri.file(s.target);
    const touched = mine[0].edit.entries().map(([u]) => u.fsPath.toLowerCase());
    if (touched.length !== 1 || touched[0] !== targetUri.fsPath.toLowerCase()) throw new Error(`the edit touches ${touched.join(", ")}, expected only ${targetUri.fsPath}`);
    const before = fs.readFileSync(s.target, "utf8");
    if (!(await vscode.workspace.applyEdit(mine[0].edit))) throw new Error("the editor refused the edit");
    const tdoc = await vscode.workspace.openTextDocument(targetUri);
    await tdoc.save();
    const after = fs.readFileSync(s.target, "utf8");
    note({ event: "fix applied by VS Code and saved", file: s.target, title: mine[0].title, addedLine: after.slice(before.length) });
    const eol = after.includes("\r\n") ? "\r\n" : "\n";
    if (!after.startsWith(before) || after.slice(before.length) !== s.expect_last_line + eol) throw new Error(`unexpected content added: ${JSON.stringify(after.slice(before.length))}`);
    note({ event: "checks passed", file: s.target, appended: s.expect_last_line });
  } else if (s.set_api) {
    await vscode.workspace.getConfiguration("faultline").update("api", s.set_api, vscode.ConfigurationTarget.Global);
    note({ event: "api switched (as after a new analysis)", api: s.set_api });
    await vscode.commands.executeCommand("faultline.restart");
  } else {
    throw new Error("unknown step: " + JSON.stringify(s));
  }
}

export async function run(): Promise<void> {
  const stepsFile = process.env.FAULTLINE_TEST_STEPS;
  if (stepsFile) {
    const steps: Step[] = JSON.parse(fs.readFileSync(stepsFile, "utf8"));
    for (const s of steps) await runStep(s);
    note({ event: "all steps passed", steps: steps.length });
    return;
  }
  await runStep({ open: process.env.FAULTLINE_TEST_FILE!, expect: { line: Number(process.env.FAULTLINE_TEST_LINE), severity: process.env.FAULTLINE_TEST_SEVERITY || "Error" } });
}
