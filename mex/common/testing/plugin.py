"""Pytest plugin with common MEx-specific fixtures.

Activate by adding `pytest_plugins = ("mex.common.testing.plugin",)`
to the `conftest.py` in your root test folder.
"""
import os
from enum import Enum
from pathlib import Path
from typing import Generator, Protocol

import pytest
from langdetect import DetectorFactory
from pydantic import AnyUrl
from pytest import FixtureRequest, MonkeyPatch

from mex.common.connector import reset_connector_context
from mex.common.settings import BaseSettings, SettingsContext, SettingsType


class SettingLoader(Protocol):
    """Protocol for settings loader function."""

    def __call__(
        self, settings_cls: type[SettingsType]
    ) -> Generator[SettingsType, None, None]:
        """Load the settings of the given class configured for testing."""
        ...


@pytest.fixture(autouse=True)
def patch_reprs(monkeypatch: MonkeyPatch) -> None:
    """Allow for easier copying of expected output by patching __repr__ methods."""
    monkeypatch.setattr(
        Enum, "__repr__", lambda self: f"{self.__class__.__name__}.{self.name}"
    )
    monkeypatch.setattr(
        AnyUrl, "__repr__", lambda self: f'AnyUrl("{self}", scheme="{self.scheme}")'
    )


@pytest.fixture(autouse=True)
def isolate_assets_dir(is_integration_test: bool, monkeypatch: MonkeyPatch) -> None:
    """Disable the `MEX_ASSETS_DIR` environment variable for unit testing."""
    if not is_integration_test:  # pragma: no cover
        monkeypatch.delenv("MEX_ASSETS_DIR", raising=False)


@pytest.fixture(autouse=True)
def isolate_work_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Set the `MEX_WORK_DIR` environment variable to a temp path for all tests."""
    monkeypatch.setenv("MEX_WORK_DIR", str(tmp_path))


@pytest.fixture(autouse=True)
def settings() -> BaseSettings:
    """Load the settings for this pytest session."""
    return BaseSettings.get()


@pytest.fixture(autouse=True)
def isolate_settings_context() -> Generator[None, None, None]:
    """Automatically close all connectors and remove from context variable."""
    yield
    SettingsContext.set(None)


@pytest.fixture(autouse=True)
def isolate_connector_context() -> Generator[None, None, None]:
    """Automatically close all connectors and remove from context variable."""
    yield
    reset_connector_context()


@pytest.fixture(autouse=True)
def is_integration_test(request: FixtureRequest) -> bool:
    """Check the markers of a test to see if this is an integration test."""
    return any(m.name == "integration" for m in request.keywords.get("pytestmark", ()))


@pytest.fixture(autouse=True)
def skip_integration_test_in_ci(is_integration_test: bool) -> None:
    """Automatically skip all tests marked as integration when the CI env var is set."""
    if is_integration_test and os.environ.get("CI") == "true":  # pragma: no cover
        pytest.skip("Skip integration test in CI")


@pytest.fixture(autouse=True)
def isolate_langdetect() -> None:
    """Automatically set the language detection seed to a stable value during tests."""
    DetectorFactory.seed = 0


@pytest.fixture(scope="session", autouse=True)
def faker_session_locale() -> list[str]:
    """Configure the default locales used for localizing fake data."""
    return ["de_DE", "en_US"]