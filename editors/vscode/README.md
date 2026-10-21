# Faultline for VS Code

Shows Faultline findings on the lines of a consumer's Python source, through the Faultline language server (`python -m faultline.lsp`,
LSP 3.17 over stdio). The extension only starts the server; the server reads findings from the Faultline API.

Run it from the repository root, with the stack up (`python tools/fl.py up --detach`) and an analysis done:

    python tools/fl.py vscode <folder of the consumer repository>

That builds the extension, then opens the folder in an Extension Development Host. Settings: `faultline.api`, `faultline.consumer`
(owner/name; empty reads the folder's git origin), `faultline.pythonPath`, `faultline.backendPath` (the launcher sets the last two through
`FAULTLINE_PYTHON` and `FAULTLINE_BACKEND`).
