"""Unit-тесты CLI: upgrade."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


from infrastructure.cli import (
    _find_pip,
    _get_local_version,
    _parse_python_bounds,
    _parse_requires_python,
    _parse_version,
    upgrade,
)


class TestParseVersion:
    def test_standard(self):
        text = 'version = "1.2.3"'
        assert _parse_version(text) == (1, 2, 3)

    def test_two_parts(self):
        text = 'version = "0.5"'
        assert _parse_version(text) == (0, 5)

    def test_missing(self):
        text = 'name = "foo"'
        assert _parse_version(text) is None


class TestParseRequiresPython:
    def test_ge_only(self):
        assert _parse_requires_python('requires-python = ">=3.10"') == ">=3.10"

    def test_range(self):
        assert _parse_requires_python('requires-python = ">=3.10,<4"') == ">=3.10,<4"

    def test_missing(self):
        assert _parse_requires_python("name = 'foo'") is None


class TestParsePythonBounds:
    def test_ge_only(self):
        low, high = _parse_python_bounds(">=3.10")
        assert low == 3

    def test_ge_only_high(self):
        _, high = _parse_python_bounds(">=3.10")
        assert high is None

    def test_ge_and_lt(self):
        low, high = _parse_python_bounds(">=3.10,<4")
        assert low == 3
        assert high == 3

    def test_exact(self):
        low, high = _parse_python_bounds("==3.12")
        assert low == 3
        assert high == 3


class TestGetLocalVersion:
    def test_returns_string(self):
        v = _get_local_version()
        assert isinstance(v, str)
        parts = v.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts)


class TestFindPip:
    @patch("infrastructure.cli.shutil.which")
    def test_pip_in_path(self, mock_which):
        mock_which.return_value = "/usr/bin/pip"
        assert _find_pip() == ["pip"]

    @patch("infrastructure.cli.subprocess.run")
    @patch("infrastructure.cli.shutil.which")
    def test_python_m_pip(self, mock_which, mock_run):
        mock_which.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        assert _find_pip() == [sys.executable, "-m", "pip"]

    @patch("infrastructure.cli.subprocess.run")
    @patch("infrastructure.cli.shutil.which")
    def test_not_found(self, mock_which, mock_run):
        mock_which.return_value = None
        mock_run.return_value = MagicMock(returncode=1)
        assert _find_pip() is None


class TestUpgrade:
    def test_uptodate(self, capsys):
        with patch("infrastructure.cli._get_local_version", return_value="1.0.0"):
            toml = 'version = "1.0.0"\nrequires-python = ">=3.10"'
            with patch("infrastructure.cli._fetch_remote_pyproject", return_value=toml):
                upgrade([])
        out = capsys.readouterr().out
        assert "обновление не требуется" in out.lower() or "не требуется" in out.lower()

    def test_newer_available_incompatible_python(self, capsys):
        toml = 'version = "2.0.0"\nrequires-python = ">=4.0"'
        with patch("infrastructure.cli._get_local_version", return_value="1.0.0"):
            with patch("infrastructure.cli._fetch_remote_pyproject", return_value=toml):
                with patch("infrastructure.cli._confirm", return_value=False):
                    upgrade([])
        out = capsys.readouterr().out
        assert "несовместимость" in out.lower() or "отмена" in out.lower()

    def test_newer_available_pip_not_found(self, capsys):
        toml = 'version = "2.0.0"\nrequires-python = ">=3.10"'
        with patch("infrastructure.cli._get_local_version", return_value="1.0.0"):
            with patch("infrastructure.cli._fetch_remote_pyproject", return_value=toml):
                with patch("infrastructure.cli._find_pip", return_value=None):
                    upgrade(["-y"])
        out = capsys.readouterr().out
        assert "pip не найден" in out.lower()

    def test_newer_available_pip_runs(self, capsys):
        toml = 'version = "2.0.0"\nrequires-python = ">=3.10"'
        with patch("infrastructure.cli._get_local_version", return_value="1.0.0"):
            with patch("infrastructure.cli._fetch_remote_pyproject", return_value=toml):
                with patch("infrastructure.cli._find_pip", return_value=["pip"]):
                    with patch("infrastructure.cli.subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0)
                        upgrade(["-y"])
        out = capsys.readouterr().out
        assert "2.0.0" in out

    def test_fetch_fails(self, capsys):
        with patch("infrastructure.cli._get_local_version", return_value="1.0.0"):
            with patch("infrastructure.cli._fetch_remote_pyproject", return_value=None):
                upgrade([])
        out = capsys.readouterr().out
        assert "не удалось" in out.lower()
