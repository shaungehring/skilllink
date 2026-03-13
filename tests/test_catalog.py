"""Tests for skilllink/catalog.py."""

import pytest
import yaml

from skilllink.catalog import (
    ToolEntry,
    build_sample_catalog,
    filter_by_tag,
    find_tool,
    infer_tool_type,
    load_catalog,
    merge_scan_into_catalog,
    parse_md_frontmatter,
    save_catalog,
    scan_tooling_dir,
    slugify,
)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic(self):
        assert slugify("React Toolkit") == "react-toolkit"

    def test_underscores(self):
        assert slugify("my_tool_name") == "my-tool-name"

    def test_special_chars(self):
        assert slugify("My Tool!") == "my-tool"

    def test_already_slugged(self):
        assert slugify("already-slugged") == "already-slugged"

    def test_multiple_spaces(self):
        assert slugify("too   many   spaces") == "too-many-spaces"

    def test_leading_trailing(self):
        assert slugify("  trim me  ") == "trim-me"


# ---------------------------------------------------------------------------
# parse_md_frontmatter
# ---------------------------------------------------------------------------

class TestParseMdFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        md = tmp_path / "tool.md"
        md.write_text("---\nname: My Tool\ndescription: Does stuff\n---\n# Body\n")
        result = parse_md_frontmatter(md)
        assert result["name"] == "My Tool"
        assert result["description"] == "Does stuff"

    def test_no_frontmatter(self, tmp_path):
        md = tmp_path / "tool.md"
        md.write_text("# Just a heading\nNo frontmatter here.\n")
        assert parse_md_frontmatter(md) == {}

    def test_only_opening_fence(self, tmp_path):
        md = tmp_path / "tool.md"
        md.write_text("---\nname: Broken\n")
        assert parse_md_frontmatter(md) == {}

    def test_tags_list(self, tmp_path):
        md = tmp_path / "tool.md"
        md.write_text("---\nname: T\ntags:\n  - react\n  - ts\n---\n")
        result = parse_md_frontmatter(md)
        assert result["tags"] == ["react", "ts"]

    def test_invalid_yaml_in_frontmatter(self, tmp_path):
        md = tmp_path / "tool.md"
        md.write_text("---\n: invalid: yaml: :\n---\n")
        # Should not raise — returns empty dict
        result = parse_md_frontmatter(md)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# infer_tool_type
# ---------------------------------------------------------------------------

class TestInferToolType:
    def test_agent_dir(self, tmp_path):
        agent_file = tmp_path / "agents" / "my-agent" / "AGENT.md"
        agent_file.parent.mkdir(parents=True)
        agent_file.touch()
        assert infer_tool_type(agent_file, tmp_path) == "agent"

    def test_plugin_dir(self, tmp_path):
        plugin_file = tmp_path / "plugins" / "my-plugin.md"
        plugin_file.parent.mkdir()
        plugin_file.touch()
        assert infer_tool_type(plugin_file, tmp_path) == "plugin"

    def test_skills_dir(self, tmp_path):
        skill_file = tmp_path / "skills" / "react" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.touch()
        assert infer_tool_type(skill_file, tmp_path) == "skill"

    def test_default_skill(self, tmp_path):
        other_file = tmp_path / "misc" / "tool.md"
        other_file.parent.mkdir()
        other_file.touch()
        assert infer_tool_type(other_file, tmp_path) == "skill"


# ---------------------------------------------------------------------------
# load_catalog / save_catalog roundtrip
# ---------------------------------------------------------------------------

class TestLoadSaveCatalog:
    def test_roundtrip(self, tmp_path):
        catalog_path = tmp_path / "catalog.yaml"
        tools = [
            ToolEntry(name="Tool A", path="skills/a.md", type="skill",
                      tags=["python"], description="Does A", always_include=False),
            ToolEntry(name="Agent B", path="agents/b.md", type="agent",
                      tags=[], description="", always_include=True),
        ]
        save_catalog(catalog_path, tools)
        loaded = load_catalog(catalog_path)
        assert len(loaded) == 2
        assert loaded[0].name == "Tool A"
        assert loaded[0].tags == ["python"]
        assert loaded[1].name == "Agent B"
        assert loaded[1].always_include is True

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_catalog(tmp_path / "missing.yaml")

    def test_load_malformed_yaml(self, tmp_path):
        catalog_path = tmp_path / "catalog.yaml"
        catalog_path.write_text("{invalid yaml: [}\n")
        with pytest.raises(yaml.YAMLError):
            load_catalog(catalog_path)

    def test_load_empty_tools_key(self, tmp_path):
        catalog_path = tmp_path / "catalog.yaml"
        catalog_path.write_text("tools:\n")
        result = load_catalog(catalog_path)
        assert result == []

    def test_save_atomic(self, tmp_path):
        """save_catalog should not leave a .tmp file behind."""
        catalog_path = tmp_path / "catalog.yaml"
        save_catalog(catalog_path, [])
        tmp_file = catalog_path.with_suffix(".yaml.tmp")
        assert not tmp_file.exists()


# ---------------------------------------------------------------------------
# find_tool
# ---------------------------------------------------------------------------

class TestFindTool:
    def _tools(self):
        return [
            ToolEntry(name="React Toolkit", path="skills/react.md", type="skill"),
            ToolEntry(name="FastAPI Agent", path="agents/fastapi.md", type="agent"),
        ]

    def test_exact_match(self):
        result = find_tool(self._tools(), "React Toolkit")
        assert result is not None
        assert result.name == "React Toolkit"

    def test_case_insensitive(self):
        result = find_tool(self._tools(), "react toolkit")
        assert result is not None

    def test_not_found(self):
        assert find_tool(self._tools(), "Nonexistent") is None


# ---------------------------------------------------------------------------
# filter_by_tag
# ---------------------------------------------------------------------------

class TestFilterByTag:
    def _tools(self):
        return [
            ToolEntry(name="A", path="a.md", type="skill", tags=["python", "fastapi"]),
            ToolEntry(name="B", path="b.md", type="skill", tags=["react", "typescript"]),
            ToolEntry(name="C", path="c.md", type="agent", tags=["python"]),
        ]

    def test_single_match(self):
        result = filter_by_tag(self._tools(), "react")
        assert len(result) == 1
        assert result[0].name == "B"

    def test_multiple_matches(self):
        result = filter_by_tag(self._tools(), "python")
        assert len(result) == 2

    def test_no_match(self):
        result = filter_by_tag(self._tools(), "go")
        assert result == []

    def test_case_insensitive(self):
        result = filter_by_tag(self._tools(), "PYTHON")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# scan_tooling_dir
# ---------------------------------------------------------------------------

class TestScanToolingDir:
    def _make_tooling_dir(self, tmp_path):
        (tmp_path / "skills" / "react").mkdir(parents=True)
        (tmp_path / "agents" / "init").mkdir(parents=True)
        (tmp_path / "skills" / "react" / "SKILL.md").write_text(
            "---\nname: React Toolkit\ndescription: React patterns\ntags:\n  - react\n---\n# React\n"
        )
        (tmp_path / "agents" / "init" / "AGENT.md").write_text(
            "---\nname: Project Init Agent\ndescription: Scaffolds projects\n---\n"
        )
        (tmp_path / "skills" / "no-frontmatter.md").write_text("# Just docs\n")
        return tmp_path

    def test_finds_md_files(self, tmp_path):
        tooling_dir = self._make_tooling_dir(tmp_path)
        entries = scan_tooling_dir(tooling_dir)
        names = [e.name for e in entries]
        assert "React Toolkit" in names
        assert "Project Init Agent" in names

    def test_infers_types(self, tmp_path):
        tooling_dir = self._make_tooling_dir(tmp_path)
        entries = scan_tooling_dir(tooling_dir)
        types = {e.name: e.type for e in entries}
        assert types.get("React Toolkit") == "skill"
        assert types.get("Project Init Agent") == "agent"

    def test_uses_frontmatter_description(self, tmp_path):
        tooling_dir = self._make_tooling_dir(tmp_path)
        entries = scan_tooling_dir(tooling_dir)
        react = next(e for e in entries if e.name == "React Toolkit")
        assert react.description == "React patterns"

    def test_no_frontmatter_generates_name(self, tmp_path):
        tooling_dir = self._make_tooling_dir(tmp_path)
        entries = scan_tooling_dir(tooling_dir)
        names = [e.name for e in entries]
        assert "No Frontmatter" in names

    def test_skips_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("# readme\n")
        entries = scan_tooling_dir(tmp_path)
        names = [e.name for e in entries]
        assert "Readme" not in names


# ---------------------------------------------------------------------------
# merge_scan_into_catalog
# ---------------------------------------------------------------------------

class TestMergeScanIntoCatalog:
    def test_adds_new(self):
        existing = [ToolEntry(name="Old Tool", path="old.md", type="skill")]
        scanned = [
            ToolEntry(name="Old Tool", path="old.md", type="skill"),
            ToolEntry(name="New Tool", path="new.md", type="agent"),
        ]
        merged, added, skipped = merge_scan_into_catalog(existing, scanned)
        assert added == 1
        assert skipped == 1
        assert len(merged) == 2

    def test_preserves_existing(self):
        existing = [ToolEntry(name="A", path="a.md", type="skill",
                              tags=["manually-added"], description="Custom desc")]
        scanned = [ToolEntry(name="A", path="a.md", type="skill")]
        merged, _, _ = merge_scan_into_catalog(existing, scanned)
        assert merged[0].tags == ["manually-added"]
        assert merged[0].description == "Custom desc"

    def test_case_insensitive_dedup(self):
        existing = [ToolEntry(name="React Toolkit", path="r.md", type="skill")]
        scanned = [ToolEntry(name="react toolkit", path="r.md", type="skill")]
        _, added, skipped = merge_scan_into_catalog(existing, scanned)
        assert added == 0
        assert skipped == 1

    def test_empty_existing(self):
        scanned = [ToolEntry(name="X", path="x.md", type="skill")]
        merged, added, skipped = merge_scan_into_catalog([], scanned)
        assert added == 1
        assert skipped == 0
        assert len(merged) == 1


# ---------------------------------------------------------------------------
# build_sample_catalog
# ---------------------------------------------------------------------------

def test_build_sample_catalog():
    samples = build_sample_catalog()
    assert len(samples) >= 2
    types = {s.type for s in samples}
    assert "skill" in types or "agent" in types
    # At least one always_include
    assert any(s.always_include for s in samples)
