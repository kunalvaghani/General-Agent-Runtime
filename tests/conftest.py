"""Keep developer environment settings out of tests."""

import os

import pytest


def pytest_addoption(parser):
    parser.addoption("--docker", action="store_true", help="Run live container tool tests")


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path):
    for key in os.environ:
        if key.startswith("GAR_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
