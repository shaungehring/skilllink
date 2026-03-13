"""Tests for skilllink/linker.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from skilllink.linker import (
    compute_symlink_path,
    get_project_status,
    get_target_dir,
    link_tool,
    unlink_tool,
)


# ---------------------------------------------------------------------------
# get_target_dir
# ---------------------------------------------------------------------------

class TestGetTargetDir:
    def test_project_skill(self, tmp_path):
        result = get_target_dir("skill", "project", cwd=tmp_path)
        assert result == tmp_path / ".claude" / "skills"

    def test_project_agent(self, tmp_path):
        result = get_target_dir("agent", "project", cwd=tmp_path)
        assert result == tmp_path / ".claude" / "agents"

    def test_project_plugin(self, tmp_path):
        result = get_target_dir("plugin", "project", cwd=tmp_path)
        assert result == tmp_path / ".claude" / "plugins"

    def test_global_skill(self, tmp_path):
        with patch("skilllink.linker.Path.home", return_value=tmp_path):
            result = get_target_dir("skill", "global")
        assert result == tmp_path / ".claude" / "skills"


# ---------------------------------------------------------------------------
# compute_symlink_path
# ---------------------------------------------------------------------------

class TestComputeSymlinkPath:
    def test_basic(self, tmp_path):
        result = compute_symlink_path("React Toolkit", "skills/react/SKILL.md", tmp_path)
        assert result == tmp_path / "react-toolkit.md"

    def test_preserves_extension(self, tmp_path):
        result = compute_symlink_path("My Agent", "agents/agent.md", tmp_path)
        assert result.suffix == ".md"

    def test_slug_from_name(self, tmp_path):
        result = compute_symlink_path("FastAPI Agent!", "agents/fastapi/AGENT.md", tmp_path)
        assert result.name == "fastapi-agent.md"


# ---------------------------------------------------------------------------
# link_tool
# ---------------------------------------------------------------------------

class TestLinkTool:
    def _make_source(self, tmp_path: Path, name: str = "tool.md") -> Path:
        source = tmp_path / "source" / name
        source.parent.mkdir(exist_ok=True)
        source.write_text("# Tool")
        return source

    def test_happy_path(self, tmp_path):
        source = self._make_source(tmp_path)
        symlink = tmp_path / "target" / "tool.md"
        symlink.parent.mkdir()

        changed, msg = link_tool(source, symlink)
        assert changed is True
        assert "linked:" in msg
        assert symlink.is_symlink()
        assert symlink.resolve() == source.resolve()

    def test_dry_run_no_file_created(self, tmp_path):
        source = self._make_source(tmp_path)
        symlink = tmp_path / "target" / "tool.md"
        symlink.parent.mkdir()

        changed, msg = link_tool(source, symlink, dry_run=True)
        assert changed is True
        assert "would link" in msg
        assert not symlink.exists()

    def test_idempotent_already_linked(self, tmp_path):
        source = self._make_source(tmp_path)
        symlink = tmp_path / "tool.md"
        symlink.symlink_to(source)

        changed, msg = link_tool(source, symlink)
        assert changed is False
        assert "already linked" in msg

    def test_replaces_broken_symlink(self, tmp_path):
        broken_target = tmp_path / "gone.md"
        symlink = tmp_path / "tool.md"
        symlink.symlink_to(broken_target)  # broken — gone.md doesn't exist

        source = self._make_source(tmp_path)
        changed, msg = link_tool(source, symlink)
        assert changed is True
        assert symlink.resolve() == source.resolve()

    def test_real_file_conflict_raises(self, tmp_path):
        source = self._make_source(tmp_path)
        real_file = tmp_path / "tool.md"
        real_file.write_text("I am a real file")

        with pytest.raises(FileExistsError):
            link_tool(source, real_file)


# ---------------------------------------------------------------------------
# unlink_tool
# ---------------------------------------------------------------------------

class TestUnlinkTool:
    def test_happy_path(self, tmp_path):
        source = tmp_path / "source.md"
        source.write_text("source")
        symlink = tmp_path / "link.md"
        symlink.symlink_to(source)

        success, msg = unlink_tool(symlink)
        assert success is True
        assert "unlinked" in msg
        assert not symlink.exists()

    def test_dry_run(self, tmp_path):
        source = tmp_path / "source.md"
        source.write_text("source")
        symlink = tmp_path / "link.md"
        symlink.symlink_to(source)

        success, msg = unlink_tool(symlink, dry_run=True)
        assert success is True
        assert "would unlink" in msg
        assert symlink.is_symlink()  # still there

    def test_not_found(self, tmp_path):
        success, msg = unlink_tool(tmp_path / "missing.md")
        assert success is False
        assert "not found" in msg

    def test_real_file_raises(self, tmp_path):
        real_file = tmp_path / "real.md"
        real_file.write_text("real")

        with pytest.raises(ValueError):
            unlink_tool(real_file)


# ---------------------------------------------------------------------------
# get_project_status
# ---------------------------------------------------------------------------

class TestGetProjectStatus:
    def test_empty_project(self, tmp_path):
        status = get_project_status(cwd=tmp_path)
        assert status == {"skills": [], "agents": [], "plugins": []}

    def test_valid_symlinks(self, tmp_path):
        source = tmp_path / "real-tool.md"
        source.write_text("# Tool")
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        symlink = skills_dir / "my-tool.md"
        symlink.symlink_to(source)

        status = get_project_status(cwd=tmp_path)
        assert len(status["skills"]) == 1
        assert status["skills"][0]["name"] == "my-tool.md"
        assert status["skills"][0]["broken"] is False

    def test_broken_symlink_flagged(self, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        symlink = skills_dir / "broken.md"
        symlink.symlink_to(tmp_path / "nonexistent.md")

        status = get_project_status(cwd=tmp_path)
        assert len(status["skills"]) == 1
        assert status["skills"][0]["broken"] is True

    def test_real_files_ignored(self, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        real_file = skills_dir / "real.md"
        real_file.write_text("not a symlink")

        status = get_project_status(cwd=tmp_path)
        assert status["skills"] == []

    def test_multiple_types(self, tmp_path):
        source = tmp_path / "s.md"
        source.write_text("s")
        for type_dir in ["skills", "agents", "plugins"]:
            d = tmp_path / ".claude" / type_dir
            d.mkdir(parents=True)
            (d / "tool.md").symlink_to(source)

        status = get_project_status(cwd=tmp_path)
        assert len(status["skills"]) == 1
        assert len(status["agents"]) == 1
        assert len(status["plugins"]) == 1
