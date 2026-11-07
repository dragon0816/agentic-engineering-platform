"""Ordinary collection must never query a person's live Outlook process."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows live Outlook collection")
def test_collecting_mail_tests_does_not_probe_outlook() -> None:
    code = """
import os, runpy, sys, types
os.environ.pop("AEP_OUTLOOK_TESTS", None)
sys.path.insert(0, "tests")
client = types.ModuleType("win32com.client")
calls = []
client.GetActiveObject = lambda name: calls.append(name)
package = types.ModuleType("win32com")
package.client = client
sys.modules["win32com"] = package
sys.modules["win32com.client"] = client
runpy.run_path("tests/test_outlook_mail_folders.py")
print(len(calls))
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=30)
    assert result.returncode == 0
    assert result.stdout.strip() == b"0"
