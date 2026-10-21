import * as fs from "fs";
import * as vscode from "vscode";

// Runs inside VS Code. Opens a Python file, waits for the Faultline diagnostic the language server publishes, and checks what the editor
// itself holds: the file, the line, the severity and the wording. It throws (and so fails the session) when anything differs.

const SEVERITY = ["Error", "Warning", "Information", "Hint"];

export async function run(): Promise<void> {
  const file = process.env.FAULTLINE_TEST_FILE!;
  const expectLine = Number(process.env.FAULTLINE_TEST_LINE);
  const expectSeverity = process.env.FAULTLINE_TEST_SEVERITY || "Error";
  const log = process.env.FAULTLINE_EVIDENCE_LOG;
  const note = (o: object) => log && fs.appendFileSync(log, JSON.stringify({ at: new Date().toISOString(), ...o }) + "\n");

  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
  await vscode.window.showTextDocument(doc);
  note({ event: "opened in VS Code", file, language: doc.languageId, vscode: vscode.version });

  const deadline = Date.now() + 90_000;
  let found: vscode.Diagnostic[] = [];
  while (Date.now() < deadline) {
    found = vscode.languages.getDiagnostics(doc.uri).filter((d) => d.source === "faultline");
    if (found.length) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  if (!found.length) {
    note({ event: "no Faultline diagnostic arrived", file });
    throw new Error("no Faultline diagnostic arrived within 90 s");
  }
  const d = found[0];
  const seen = { line: d.range.start.line + 1, column: d.range.start.character, endColumn: d.range.end.character, severity: SEVERITY[d.severity], code: String(typeof d.code === "object" ? d.code.value : d.code), message: d.message, lineText: doc.lineAt(d.range.start.line).text };
  note({ event: "diagnostic held by VS Code", file, count: found.length, ...seen });
  if (seen.line !== expectLine) throw new Error(`the diagnostic is on line ${seen.line}, expected ${expectLine}`);
  if (seen.severity !== expectSeverity) throw new Error(`the severity is ${seen.severity}, expected ${expectSeverity}`);
  if (!/^[A-Z ]+: /.test(seen.message)) throw new Error("the message does not start with a verdict word");
  note({ event: "checks passed", file, line: seen.line, severity: seen.severity });
}
