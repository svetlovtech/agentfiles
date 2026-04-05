"""Tests for the ``agentfiles completion`` subcommand.

Covers:
- ``cmd_completion()`` dispatching to the correct shell generator
- Parser registration of the ``completion`` subcommand
- Bash, zsh, and fish completion script output validity
- Invalid shell rejection
- ``_COMMAND_MAP`` entry for ``completion``
"""

from __future__ import annotations

import argparse
import subprocess
import sys

import pytest

from syncode.cli import (
    _COMMAND_MAP,
    _SUBCOMMANDS,
    build_parser,
    cmd_completion,
)

# ---------------------------------------------------------------------------
# Parser registration
# ---------------------------------------------------------------------------


class TestCompletionParser:
    """Tests for the ``completion`` subcommand in the argument parser."""

    def test_completion_subcommand_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["completion", "bash"])
        assert args.command == "completion"
        assert args.shell == "bash"

    def test_completion_shell_zsh(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["completion", "zsh"])
        assert args.shell == "zsh"

    def test_completion_shell_fish(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["completion", "fish"])
        assert args.shell == "fish"

    def test_completion_invalid_shell_rejected(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["completion", "powershell"])

    def test_completion_no_shell_rejected(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["completion"])

    def test_completion_in_command_map(self) -> None:
        assert "completion" in _COMMAND_MAP
        assert _COMMAND_MAP["completion"] is cmd_completion

    def test_completion_in_subcommands_list(self) -> None:
        assert "completion" in _SUBCOMMANDS


# ---------------------------------------------------------------------------
# cmd_completion return codes
# ---------------------------------------------------------------------------


class TestCompletionReturnCodes:
    """Tests for ``cmd_completion()`` exit codes."""

    def test_bash_returns_zero(self) -> None:
        args = argparse.Namespace(shell="bash")
        assert cmd_completion(args) == 0

    def test_zsh_returns_zero(self) -> None:
        args = argparse.Namespace(shell="zsh")
        assert cmd_completion(args) == 0

    def test_fish_returns_zero(self) -> None:
        args = argparse.Namespace(shell="fish")
        assert cmd_completion(args) == 0


# ---------------------------------------------------------------------------
# Bash completion script validity
# ---------------------------------------------------------------------------


class TestBashCompletion:
    """Tests for the generated bash completion script."""

    def test_starts_with_shebang(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert output.startswith("#!/usr/bin/env bash\n")

    def test_contains_complete_function(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "_agentfiles()" in output
        assert "complete -F _agentfiles agentfiles" in output

    def test_contains_all_subcommands(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        for subcmd in _SUBCOMMANDS:
            assert subcmd in output, f"Missing subcommand '{subcmd}' in bash completion"

    def test_contains_target_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        for platform in ["opencode", "claude_code", "windsurf", "cursor", "all"]:
            assert platform in output, f"Missing platform '{platform}'"

    def test_contains_type_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        for item_type in ["agent", "skill", "command", "plugin", "all"]:
            assert item_type in output, f"Missing item type '{item_type}'"

    def test_contains_format_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert '"text json"' in output or "text json" in output

    def test_is_valid_bash_syntax(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The generated script should parse without syntax errors in bash."""
        args = argparse.Namespace(shell="bash")
        cmd_completion(args)
        output = capsys.readouterr().out
        result = subprocess.run(
            ["bash", "-n"],
            input=output,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Bash syntax error:\n{result.stderr}"


# ---------------------------------------------------------------------------
# Zsh completion script validity
# ---------------------------------------------------------------------------


class TestZshCompletion:
    """Tests for the generated zsh completion script."""

    def test_starts_with_compdef(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert output.startswith("#compdef agentfiles\n")

    def test_contains_function_definition(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "_agentfiles()" in output
        assert '_agentfiles "$@"' in output

    def test_contains_all_subcommands(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        for subcmd in _SUBCOMMANDS:
            assert f"'{subcmd}:" in output, f"Missing subcommand '{subcmd}' in zsh completion"

    def test_contains_target_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        for platform in ["opencode", "claude_code", "windsurf", "cursor", "all"]:
            assert platform in output, f"Missing platform '{platform}'"

    def test_contains_arguments_directive(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "_arguments" in output

    def test_contains_color_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "always auto never" in output

    def test_contains_completion_shell_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="zsh")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "bash zsh fish" in output


# ---------------------------------------------------------------------------
# Fish completion script validity
# ---------------------------------------------------------------------------


class TestFishCompletion:
    """Tests for the generated fish completion script."""

    def test_starts_with_comment(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert output.startswith("# agentfiles fish completion\n")

    def test_uses_complete_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "complete -c agentfiles" in output

    def test_contains_all_subcommands(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        for subcmd in _SUBCOMMANDS:
            assert f"'{subcmd}'" in output, f"Missing subcommand '{subcmd}' in fish completion"

    def test_contains_target_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        for platform in ["opencode", "claude_code", "windsurf", "cursor", "all"]:
            assert platform in output, f"Missing platform '{platform}'"

    def test_contains_type_choices(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        for item_type in ["agent", "skill", "command", "plugin", "all"]:
            assert item_type in output, f"Missing item type '{item_type}'"

    def test_contains_global_flags(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        # Fish uses -l for long options (e.g. -l version means --version)
        assert "-l version" in output
        assert "-l color" in output
        assert "-l verbose" in output
        assert "-l quiet" in output

    def test_contains_dry_run_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "-l dry-run" in output

    def test_contains_yes_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        assert "-l yes" in output

    def test_no_trailing_whitespace_on_lines(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Each line should end without trailing whitespace."""
        args = argparse.Namespace(shell="fish")
        cmd_completion(args)
        output = capsys.readouterr().out
        for i, line in enumerate(output.splitlines(), start=1):
            assert line == line.rstrip(), f"Trailing whitespace on line {i}: '{line}'"


# ---------------------------------------------------------------------------
# End-to-end via subprocess
# ---------------------------------------------------------------------------


class TestCompletionSubprocess:
    """Integration tests running ``python -m syncode completion`` via subprocess."""

    def test_bash_via_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "syncode", "completion", "bash"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "_agentfiles()" in result.stdout
        assert "complete -F _agentfiles agentfiles" in result.stdout

    def test_zsh_via_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "syncode", "completion", "zsh"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "#compdef agentfiles" in result.stdout

    def test_fish_via_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "syncode", "completion", "fish"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "complete -c agentfiles" in result.stdout

    def test_invalid_shell_exits_nonzero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "syncode", "completion", "powershell"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert result.stderr.strip()
