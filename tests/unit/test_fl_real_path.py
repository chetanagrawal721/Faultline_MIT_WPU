"""tools/fl.py: a path written by the packaged Claude app under AppData/Roaming is found where an ordinary terminal sees it."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fl_tool", ROOT / "tools" / "fl.py")
fl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fl)


def test_a_redirected_roaming_path_is_found_under_the_package_cache(tmp_path):
    real = tmp_path / "AppData" / "Local" / "Packages" / "Claude_abc123" / "LocalCache" / "Roaming" / "uv" / "python" / "cpython-3.12.15"
    real.mkdir(parents=True)
    asked = tmp_path / "AppData" / "Roaming" / "uv" / "python" / "cpython-3.12.15"
    assert not asked.exists() and fl.real_path(asked) == real


def test_an_existing_path_and_an_unknown_path_are_returned_as_they_are(tmp_path):
    here = tmp_path / "x"
    here.mkdir()
    assert fl.real_path(here) == here
    gone = tmp_path / "AppData" / "Roaming" / "nothing"
    assert fl.real_path(gone) == gone
