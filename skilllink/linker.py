"""Symlink management for skilllink."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from skilllink.catalog import slugify

Scope = Literal["project", "global"]

_TYPE_DIRS: dict[str, str] = {
    "skill": "skills",
    "agent": "agents",
    "plugin": "plugins",
}


def get_target_dir(tool_type: str, scope: Scope, cwd: Path | None = None) -> Path:
    """Resolve the directory where the symlink will be placed.

    scope='project': <cwd>/.claude/<type>s/
    scope='global':  ~/.claude/<type>s/
    """
    type_dir = _TYPE_DIRS.get(tool_type, tool_type + "s")
    if scope == "global":
        base = Path.home() / ".claude"
    else:
        base = (cwd or Path.cwd()) / ".claude"
    return base / type_dir


def ensure_target_dir(target_dir: Path) -> None:
    """Create target_dir (and parents) if it does not exist."""
    target_dir.mkdir(parents=True, exist_ok=True)


def resolve_source(tool_path: str, tooling_dir: Path) -> Path:
    """Return the absolute path of the source tool file.

    Raises FileNotFoundError if the source does not exist.
    """
    source = (tooling_dir / tool_path).resolve()
    if not source.exists():
        raise FileNotFoundError(
            f"Tool source file not found: {source}\n"
            f"Check the 'path' field in your catalog.yaml"
        )
    return source


def compute_symlink_path(tool_name: str, tool_path: str, target_dir: Path) -> Path:
    """Determine the full path of the symlink to be created.

    Name is slugified from tool_name; extension is preserved from tool_path.
    Example: 'React Toolkit', 'skills/react/SKILL.md' -> target_dir/react-toolkit.md
    """
    suffix = Path(tool_path).suffix
    slug = slugify(tool_name)
    return target_dir / (slug + suffix)


def link_tool(
    source: Path,
    symlink_path: Path,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Create a symlink at symlink_path pointing to source.

    Returns (success, message).
    - Already correctly linked: idempotent (False, 'already linked: ...')
    - Broken symlink: replaced
    - Real file/dir at target: raises FileExistsError
    - dry_run: no filesystem changes
    """
    if symlink_path.is_symlink():
        if symlink_path.resolve() == source.resolve():
            return False, f"already linked: {symlink_path}"
        # Broken or wrong target — replace it
        if not dry_run:
            symlink_path.unlink()
    elif symlink_path.exists():
        raise FileExistsError(
            f"File already exists at {symlink_path} and is not a symlink. "
            "Remove it manually before linking."
        )

    if dry_run:
        return True, f"would link: {symlink_path} -> {source}"

    symlink_path.symlink_to(source)
    return True, f"linked: {symlink_path} -> {source}"


def unlink_tool(symlink_path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """Remove the symlink at symlink_path.

    Returns (success, message).
    - Not found: (False, 'not found: ...')
    - Real file (not symlink): raises ValueError
    """
    if not symlink_path.exists() and not symlink_path.is_symlink():
        return False, f"not found: {symlink_path}"
    if not symlink_path.is_symlink():
        raise ValueError(
            f"{symlink_path} is not a symlink. Refusing to delete a real file."
        )
    if dry_run:
        return True, f"would unlink: {symlink_path}"
    symlink_path.unlink()
    return True, f"unlinked: {symlink_path}"


def find_symlink(
    tool_name: str,
    tool_path: str,
    scope: Scope,
    cwd: Path | None = None,
) -> Path | None:
    """Locate an existing symlink for the given tool in the target dir.

    Returns the Path if found by slug-matching the name, else None.
    """
    suffix = Path(tool_path).suffix
    slug = slugify(tool_name)
    expected_name = slug + suffix
    target_dir = get_target_dir(_infer_type_from_path(tool_path), scope, cwd)
    candidate = target_dir / expected_name
    if candidate.is_symlink() or candidate.exists():
        return candidate
    return None


def _infer_type_from_path(tool_path: str) -> str:
    parts = {p.lower() for p in Path(tool_path).parts}
    if "agents" in parts:
        return "agent"
    if "plugins" in parts:
        return "plugin"
    return "skill"


def get_project_status(cwd: Path | None = None) -> dict[str, list[dict]]:
    """Scan .claude/{skills,agents,plugins}/ under cwd.

    Returns dict keyed by type with symlink info dicts:
        {'name': str, 'target': str, 'broken': bool}
    Non-symlink files are ignored.
    """
    base = (cwd or Path.cwd()) / ".claude"
    result: dict[str, list[dict]] = {"skills": [], "agents": [], "plugins": []}

    for type_key in result:
        type_dir = base / type_key
        if not type_dir.is_dir():
            continue
        for entry in sorted(type_dir.iterdir()):
            if not entry.is_symlink():
                continue
            target = entry.resolve()
            broken = not entry.exists()
            result[type_key].append({
                "name": entry.name,
                "target": str(target),
                "broken": broken,
            })

    return result
