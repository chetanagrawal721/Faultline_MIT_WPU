import * as fs from "fs";
import * as vscode from "vscode";
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from "vscode-languageclient/node";

// The extension only starts the Faultline language server (python -m faultline.lsp, LSP 3.17 over stdio) and shows its state.
// All analysis stays in Faultline; nothing here reads or runs the user's code.

let client: LanguageClient | undefined;
let status: vscode.StatusBarItem | undefined;

// A value the user set (workspace or user settings) wins; then the environment variable the launcher sets; then the default.
function setting(name: string, env: string, fallback = ""): string {
  const i = vscode.workspace.getConfiguration("faultline").inspect<string>(name);
  const explicit = (i?.workspaceFolderValue ?? i?.workspaceValue ?? i?.globalValue ?? "").trim();
  return explicit || process.env[env] || (i?.defaultValue ?? "").trim() || fallback;
}

async function start(context: vscode.ExtensionContext): Promise<void> {
  const python = setting("pythonPath", "FAULTLINE_PYTHON", "python");
  const backend = setting("backendPath", "FAULTLINE_BACKEND");
  const serverOptions: ServerOptions = {
    command: python,
    args: ["-m", "faultline.lsp"],
    transport: TransportKind.stdio,
    options: { env: { ...process.env, ...(backend ? { PYTHONPATH: backend } : {}) } },
  };
  if (process.env.FAULTLINE_EVIDENCE_LOG) {
    fs.appendFileSync(process.env.FAULTLINE_EVIDENCE_LOG, JSON.stringify({ at: new Date().toISOString(), event: "starting the language server", command: python, pythonpath: backend }) + "\n");
  }
  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "python" }],
    initializationOptions: {
      api: setting("api", "FAULTLINE_API", "http://127.0.0.1:8000"),
      consumer: setting("consumer", "FAULTLINE_CONSUMER"),
    },
    outputChannelName: "Faultline",
  };
  client = new LanguageClient("faultline", "Faultline", serverOptions, clientOptions);
  status ??= vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 0);
  context.subscriptions.push(status);
  status.text = "Faultline: starting";
  status.show();
  client.onNotification("faultline/status", (p: { state: string; detail?: string }) => {
    status!.text = p.state === "ready" ? "Faultline: ready" : "Faultline: unavailable";
    status!.tooltip = p.detail || "";
  });
  await client.start();
}

const SEVERITY = ["Error", "Warning", "Information", "Hint"];

// When FAULTLINE_EVIDENCE_LOG names a file, every change to the diagnostics VS Code holds for a Faultline source is appended to it as a JSON
// line: what the editor itself received (file, line, column, severity, message), used as evidence of a real editor session.
function recordDiagnostics(context: vscode.ExtensionContext): void {
  const file = process.env.FAULTLINE_EVIDENCE_LOG;
  if (!file) return;
  context.subscriptions.push(
    vscode.languages.onDidChangeDiagnostics((e) => {
      for (const uri of e.uris) {
        const ds = vscode.languages.getDiagnostics(uri).filter((d) => d.source === "faultline");
        fs.appendFileSync(
          file,
          JSON.stringify({
            at: new Date().toISOString(),
            file: uri.fsPath,
            diagnostics: ds.map((d) => ({ line: d.range.start.line + 1, column: d.range.start.character, endColumn: d.range.end.character, severity: SEVERITY[d.severity], code: String(typeof d.code === "object" ? d.code.value : d.code), message: d.message })),
          }) + "\n",
        );
      }
    }),
  );
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  recordDiagnostics(context);
  context.subscriptions.push(
    vscode.commands.registerCommand("faultline.restart", async () => {
      await client?.stop();
      await start(context);
    }),
  );
  await start(context);
}

export async function deactivate(): Promise<void> {
  await client?.stop();
}
