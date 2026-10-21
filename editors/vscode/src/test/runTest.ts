import * as path from "path";
import { runTests } from "@vscode/test-electron";

// Starts a pinned VS Code build with the extension loaded and runs ./index.ts inside it. Everything is read from the environment, which
// `python tools/fl.py vscode-test` sets: FAULTLINE_TEST_FOLDER, FAULTLINE_TEST_FILE, FAULTLINE_TEST_LINE, FAULTLINE_TEST_SEVERITY and the
// FAULTLINE_* variables the extension itself reads (FAULTLINE_API, FAULTLINE_CONSUMER, FAULTLINE_PYTHON, FAULTLINE_BACKEND, FAULTLINE_EVIDENCE_LOG).
async function main(): Promise<void> {
  const folder = process.env.FAULTLINE_TEST_FOLDER;
  if (!folder) throw new Error("FAULTLINE_TEST_FOLDER is not set");
  await runTests({
    version: "1.95.3",
    extensionDevelopmentPath: path.resolve(__dirname, "../.."),
    extensionTestsPath: path.resolve(__dirname, "./index"),
    launchArgs: [folder, "--disable-workspace-trust", "--disable-extensions", "--user-data-dir", path.resolve(__dirname, "../../.vscode-test/user-data")],
    extensionTestsEnv: { ...process.env } as Record<string, string>,
  });
}

main().catch((e) => {
  console.error("The VS Code session failed:", e);
  process.exit(1);
});
