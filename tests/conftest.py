"""Fixtures for House Chat tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def daytime(monkeypatch):
    """The tests run in the daytime: a machine done at night rings no phone (watch.NIGHT_FROM/NIGHT_TO)."""
    monkeypatch.setattr("custom_components.hus_chat.watch.NIGHT_FROM", 24)
    monkeypatch.setattr("custom_components.hus_chat.watch.NIGHT_TO", 0)
