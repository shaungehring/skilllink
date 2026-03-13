"""Catalog read/write/scan for skilllink."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml

ToolType = Literal["skill", "agent", "plugin"]


@dataclass
class ToolEntry:
    name: str
    path: str
    type: ToolType
    tags: list[str] = field(default_factory=list)
    description: str = ""
    always_include: bool = False


# ---------------------------------------------------------------------------
# Environment / paths
# ---------------------------------------------------------------------------

def get_tooling_dir() -> Path:
    """Return the master tooling directory.

    Reads SKILLLINK_TOOLING_DIR env var; falls back to ~/.skilllink.
    Raises FileNotFoundError if the directory does not exist.
    """
    raw = os.environ.get("SKILLLINK_TOOLING_DIR", "")
    tooling_dir = Path(raw).expanduser() if raw else Path.home() / ".skilllink"
    if not tooling_dir.is_dir():
        raise FileNotFoundError(
            f"Tooling directory not found: {tooling_dir}\n"
            "Set SKILLLINK_TOOLING_DIR or create ~/.skilllink"
        )
    return tooling_dir


def get_catalog_path(tooling_dir: Path) -> Path:
    """Return the path to catalog.yaml inside tooling_dir."""
    return tooling_dir / "catalog.yaml"


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _entry_to_dict(entry: ToolEntry) -> dict:
    """Convert a ToolEntry to a dict, dropping default/empty fields."""
    d = asdict(entry)
    if not d["tags"]:
        del d["tags"]
    if not d["description"]:
        del d["description"]
    if not d["always_include"]:
        del d["always_include"]
    return d


def _dict_to_entry(d: dict) -> ToolEntry:
    return ToolEntry(
        name=d["name"],
        path=d["path"],
        type=d.get("type", "skill"),
        tags=d.get("tags") or [],
        description=d.get("description", ""),
        always_include=bool(d.get("always_include", False)),
    )


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_catalog(catalog_path: Path) -> list[ToolEntry]:
    """Parse catalog.yaml and return a list of ToolEntry objects.

    Returns an empty list if the file is absent or the 'tools' key is missing.
    Raises yaml.YAMLError on parse failure.
    """
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}\nRun 'skilllink init' or 'skilllink scan' to create it.")
    try:
        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise yaml.YAMLError(f"Failed to parse {catalog_path}: {exc}") from exc
    tools = (data or {}).get("tools") or []
    return [_dict_to_entry(t) for t in tools]


def save_catalog(catalog_path: Path, tools: list[ToolEntry]) -> None:
    """Serialize tools to catalog.yaml atomically."""
    payload = {"tools": [_entry_to_dict(t) for t in tools]}
    tmp = catalog_path.with_suffix(".yaml.tmp")
    tmp.write_text(
        yaml.dump(payload, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    os.replace(tmp, catalog_path)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def find_tool(tools: list[ToolEntry], name: str) -> ToolEntry | None:
    """Case-insensitive lookup by tool name."""
    needle = name.lower()
    for t in tools:
        if t.name.lower() == needle:
            return t
    return None


def filter_by_tag(tools: list[ToolEntry], tag: str) -> list[ToolEntry]:
    """Return tools whose tags list contains tag (case-insensitive)."""
    needle = tag.lower()
    return [t for t in tools if needle in (x.lower() for x in t.tags)]


# ---------------------------------------------------------------------------
# Frontmatter / scan
# ---------------------------------------------------------------------------

def parse_md_frontmatter(md_path: Path) -> dict:
    """Extract YAML frontmatter from a .md file.

    Frontmatter is the block between the first '---' and second '---'.
    Returns an empty dict if no valid frontmatter block is found.
    """
    text = md_path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    try:
        result = yaml.safe_load(match.group(1))
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def infer_tool_type(md_path: Path, tooling_dir: Path) -> ToolType:
    """Guess tool type from the file's ancestor directory names."""
    try:
        relative = md_path.relative_to(tooling_dir)
    except ValueError:
        return "skill"
    parts = {p.lower() for p in relative.parts}
    if "agents" in parts:
        return "agent"
    if "plugins" in parts:
        return "plugin"
    return "skill"


def slugify(name: str) -> str:
    """Convert a display name to a filesystem-safe slug.

    'React Toolkit' -> 'react-toolkit'
    """
    slug = name.lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def scan_tooling_dir(tooling_dir: Path) -> list[ToolEntry]:
    """Walk tooling_dir recursively, collect all .md files, build ToolEntry stubs."""
    entries: list[ToolEntry] = []
    for md_path in sorted(tooling_dir.rglob("*.md")):
        # Skip catalog docs
        if md_path.stem.lower() in ("catalog", "readme"):
            continue
        fm = parse_md_frontmatter(md_path)
        name = fm.get("name") or md_path.stem.replace("-", " ").replace("_", " ").title()
        description = fm.get("description", "")
        raw_tags = fm.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        tags = list(raw_tags) if raw_tags else []
        tool_type = infer_tool_type(md_path, tooling_dir)
        rel_path = str(md_path.relative_to(tooling_dir))
        entries.append(ToolEntry(
            name=name,
            path=rel_path,
            type=tool_type,
            tags=tags,
            description=description,
        ))
    return sorted(entries, key=lambda e: (e.type, e.name.lower()))


def merge_scan_into_catalog(
    existing: list[ToolEntry],
    scanned: list[ToolEntry],
) -> tuple[list[ToolEntry], int, int]:
    """Merge scanned stubs into existing catalog.

    Existing entries are preserved unchanged.
    New entries (by name, case-insensitive) are appended.
    Returns (merged_list, added_count, skipped_count).
    """
    existing_names = {e.name.lower() for e in existing}
    added = 0
    skipped = 0
    merged = list(existing)
    for entry in scanned:
        if entry.name.lower() in existing_names:
            skipped += 1
        else:
            merged.append(entry)
            existing_names.add(entry.name.lower())
            added += 1
    return merged, added, skipped


# ---------------------------------------------------------------------------
# Sample catalog
# ---------------------------------------------------------------------------

def build_sample_catalog() -> list[ToolEntry]:
    """Return example ToolEntry objects for 'skilllink init'."""
    return [
        ToolEntry(
            name="Project Scaffolding Agent",
            path="agents/project-init/AGENT.md",
            type="agent",
            tags=["setup", "init", "scaffold"],
            description="Initialize new project structures with standard boilerplate.",
            always_include=True,
        ),
        ToolEntry(
            name="React Toolkit",
            path="skills/react/SKILL.md",
            type="skill",
            tags=["react", "frontend", "typescript", "javascript"],
            description="React component patterns, hooks best practices, and performance tips.",
        ),
        ToolEntry(
            name="FastAPI Agent",
            path="agents/fastapi/AGENT.md",
            type="agent",
            tags=["fastapi", "python", "backend", "api"],
            description="Build and document FastAPI endpoints with async patterns.",
        ),
        ToolEntry(
            name="PostgreSQL Patterns",
            path="skills/postgres/SKILL.md",
            type="skill",
            tags=["postgres", "sql", "database"],
            description="SQL query patterns, migrations, and indexing best practices.",
        ),
    ]
