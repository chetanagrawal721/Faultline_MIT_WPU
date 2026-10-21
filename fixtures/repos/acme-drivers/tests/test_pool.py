import importlib.util

import pytest

# The driver is optional. Neither world installs it, so these tests are skipped and nothing is observed.
pytestmark = pytest.mark.skipif(importlib.util.find_spec("acme_missing_driver") is None, reason="database driver not installed")


def test_connect():
    from acme_drivers.pool import connect

    assert connect
