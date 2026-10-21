"""EXEC zone, no network: the static public API surface of one package inside a wheel of the read-only wheelhouse.

The wheel is read as a zip and its Python files are parsed with `ast`; nothing in it is imported or executed. The surface is returned compressed
(zlib, base64) because a large package does not fit the result frame uncompressed.
"""
import base64
import json
import os
import zlib

from common import emit, read_spec


def main() -> None:
    args = read_spec().get("args", {})
    name, package = args.get("file", ""), args.get("package", "")
    if "/" in name or "\\" in name or name.startswith(".") or not name.endswith(".whl") or not package.isidentifier():
        emit({"error": "unsafe wheel or package name"})
        return
    try:
        import surface
        files = surface.read_wheel(os.path.join("/wheelhouse", name))
        s = surface.extract(files, package)
        body = json.dumps(s.to_json(), sort_keys=True).encode()
    except Exception as e:  # noqa: BLE001 - reported, never a guess
        emit({"error": f"{type(e).__name__}: {e}"})
        return
    emit({"surface_z": base64.b64encode(zlib.compress(body, 9)).decode(), "symbols": len(s.symbols), "files": len(files)})


if __name__ == "__main__":
    main()
