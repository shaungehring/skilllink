"""CLI entry point for skilllink."""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

from skilllink import __version__
from skilllink import catalog as cat
from skilllink import linker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skilllink",
        description="Manage Claude Code skill/agent symlinks from a master library.",
    )
    parser.add_argument("--version", action="version", version=f"skilllink {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Walk tooling dir and generate catalog stubs")
    p_scan.add_argument("--dry-run", action="store_true", help="Preview without writing")

    # init
    p_init = sub.add_parser("init", help="Create a sample catalog.yaml")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing catalog.yaml")

    # list
    p_list = sub.add_parser("list", help="List tools in the catalog")
    p_list.add_argument("--tag", metavar="TAG", help="Filter by tag")
    p_list.add_argument("--type", choices=["skill", "agent", "plugin"], dest="tool_type",
                        help="Filter by type")

    # status
    sub.add_parser("status", help="Show symlinks in current project's .claude/")

    # link
    p_link = sub.add_parser("link", help="Create a symlink for one tool")
    p_link.add_argument("name", help="Tool name (as in catalog)")
    p_link.add_argument("--scope", choices=["project", "global"], default="project")

    # unlink
    p_unlink = sub.add_parser("unlink", help="Remove a symlink")
    p_unlink.add_argument("name", help="Tool name to unlink")
    p_unlink.add_argument("--scope", choices=["project", "global"], default="project")

    # apply
    p_apply = sub.add_parser("apply", help="Create symlinks for multiple tools")
    p_apply.add_argument("names", nargs="+", metavar="NAME")
    p_apply.add_argument("--scope", choices=["project", "global"], default="project")
    p_apply.add_argument("--dry-run", action="store_true")

    # update
    sub.add_parser("update", help="Update skilllink and the slash command from GitHub")

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace, tooling_dir: Path) -> None:
    catalog_path = cat.get_catalog_path(tooling_dir)
    scanned = cat.scan_tooling_dir(tooling_dir)

    if not scanned:
        print("No .md files found in tooling directory.")
        return

    existing: list[cat.ToolEntry] = []
    if catalog_path.exists():
        try:
            existing = cat.load_catalog(catalog_path)
        except (FileNotFoundError, yaml.YAMLError):
            pass

    merged, added, skipped = cat.merge_scan_into_catalog(existing, scanned)

    if args.dry_run:
        print(f"Would add {added} tool(s), skip {skipped} existing.")
        for e in scanned:
            status = "EXISTS" if cat.find_tool(existing, e.name) else "NEW"
            print(f"  [{status}] {e.name} ({e.type}) — {e.path}")
        return

    cat.save_catalog(catalog_path, merged)
    print(f"Catalog updated: {added} added, {skipped} already present → {catalog_path}")


def cmd_init(args: argparse.Namespace, tooling_dir: Path) -> None:
    catalog_path = cat.get_catalog_path(tooling_dir)
    if catalog_path.exists() and not args.force:
        print(f"Error: {catalog_path} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)
    sample = cat.build_sample_catalog()
    cat.save_catalog(catalog_path, sample)
    print(f"Created sample catalog: {catalog_path}")
    print("Edit it to add meaningful tags and descriptions, then run 'skilllink list'.")


def cmd_list(args: argparse.Namespace, tooling_dir: Path) -> None:
    catalog_path = cat.get_catalog_path(tooling_dir)
    tools = cat.load_catalog(catalog_path)

    if args.tag:
        tools = cat.filter_by_tag(tools, args.tag)
    if args.tool_type:
        tools = [t for t in tools if t.type == args.tool_type]

    if not tools:
        print("No tools found matching your filters.")
        return

    # Column widths
    w_name = max(len(t.name) for t in tools)
    w_type = 6
    w_tags = 30
    header = f"{'NAME':<{w_name}}  {'TYPE':<{w_type}}  {'TAGS':<{w_tags}}  DESCRIPTION"
    print(header)
    print("-" * len(header))

    for t in sorted(tools, key=lambda x: (x.type, x.name.lower())):
        tags_str = ", ".join(t.tags)[:w_tags]
        desc = t.description[:60]
        always = " ★" if t.always_include else ""
        print(f"{t.name + always:<{w_name}}  {t.type:<{w_type}}  {tags_str:<{w_tags}}  {desc}")

    print(f"\n{len(tools)} tool(s)")


def cmd_status(args: argparse.Namespace, tooling_dir: Path) -> None:
    status = linker.get_project_status()
    total = sum(len(v) for v in status.values())

    if total == 0:
        print("No tools linked in this project.")
        return

    for type_key, entries in status.items():
        if not entries:
            continue
        print(f"\n{type_key.upper()}")
        for e in entries:
            broken = " [BROKEN]" if e["broken"] else ""
            print(f"  {e['name']}{broken} -> {e['target']}")

    print(f"\n{total} symlink(s) total")


def _do_link(
    tool: cat.ToolEntry,
    tooling_dir: Path,
    scope: str,
    dry_run: bool,
) -> tuple[bool, str]:
    """Resolve, ensure dir, and link a single tool. Returns (changed, message)."""
    source = linker.resolve_source(tool.path, tooling_dir)
    target_dir = linker.get_target_dir(tool.type, scope)  # type: ignore[arg-type]
    linker.ensure_target_dir(target_dir)
    symlink_path = linker.compute_symlink_path(tool.name, tool.path, target_dir)
    return linker.link_tool(source, symlink_path, dry_run=dry_run)


def cmd_link(args: argparse.Namespace, tooling_dir: Path) -> None:
    catalog_path = cat.get_catalog_path(tooling_dir)
    tools = cat.load_catalog(catalog_path)
    tool = cat.find_tool(tools, args.name)
    if tool is None:
        print(f"Error: Tool not found in catalog: {args.name!r}", file=sys.stderr)
        sys.exit(1)
    _changed, msg = _do_link(tool, tooling_dir, args.scope, dry_run=False)
    print(msg)


def cmd_unlink(args: argparse.Namespace, tooling_dir: Path) -> None:
    catalog_path = cat.get_catalog_path(tooling_dir)
    tools = cat.load_catalog(catalog_path)
    tool = cat.find_tool(tools, args.name)
    if tool is None:
        print(f"Error: Tool not found in catalog: {args.name!r}", file=sys.stderr)
        sys.exit(1)

    target_dir = linker.get_target_dir(tool.type, args.scope)  # type: ignore[arg-type]
    symlink_path = linker.compute_symlink_path(tool.name, tool.path, target_dir)
    _success, msg = linker.unlink_tool(symlink_path)
    print(msg)


def cmd_apply(args: argparse.Namespace, tooling_dir: Path) -> None:
    catalog_path = cat.get_catalog_path(tooling_dir)
    all_tools = cat.load_catalog(catalog_path)

    # Resolve all names first — fail fast if any are missing
    resolved: list[cat.ToolEntry] = []
    errors: list[str] = []
    for name in args.names:
        tool = cat.find_tool(all_tools, name)
        if tool is None:
            errors.append(f"  not found: {name!r}")
        else:
            resolved.append(tool)

    if errors:
        print("Error: Some tools not found in catalog:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)

    # Add always_include tools not already in the list
    named_names = {t.name.lower() for t in resolved}
    for tool in all_tools:
        if tool.always_include and tool.name.lower() not in named_names:
            resolved.append(tool)
            named_names.add(tool.name.lower())

    linked = 0
    already = 0
    failed = 0

    for tool in resolved:
        try:
            changed, msg = _do_link(tool, tooling_dir, args.scope, dry_run=args.dry_run)
            print(msg)
            if changed:
                linked += 1
            else:
                already += 1
        except (FileNotFoundError, FileExistsError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            failed += 1

    verb = "Would link" if args.dry_run else "Linked"
    print(f"\n{verb} {linked}, already linked {already}, errors {failed}")
    if failed:
        sys.exit(1)


_REPO = "https://github.com/shaungehring/skilllink"
_SLASH_CMD_URL = (
    "https://raw.githubusercontent.com/shaungehring/skilllink/main"
    "/.claude/commands/skill-this-project.md"
)


def cmd_update(_args: argparse.Namespace, _tooling_dir: Path) -> None:
    print(f"Updating skilllink from {_REPO} ...")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", f"git+{_REPO}.git"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Retry with --user
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--user",
             f"git+{_REPO}.git"],
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        print("Error: pip upgrade failed.", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    print("skilllink upgraded successfully.")

    # Refresh the slash command
    commands_dir = Path.home() / ".claude" / "commands"
    if commands_dir.parent.exists():
        commands_dir.mkdir(parents=True, exist_ok=True)
        dest = commands_dir / "skill-this-project.md"
        try:
            with urllib.request.urlopen(_SLASH_CMD_URL, timeout=10) as resp:  # noqa: S310
                dest.write_bytes(resp.read())
            print(f"Slash command updated: {dest}")
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: could not update slash command: {exc}")
    else:
        print("Warning: ~/.claude not found — skipping slash command update.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        tooling_dir = cat.get_tooling_dir()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    dispatch = {
        "scan": cmd_scan,
        "init": cmd_init,
        "list": cmd_list,
        "status": cmd_status,
        "link": cmd_link,
        "unlink": cmd_unlink,
        "apply": cmd_apply,
        "update": cmd_update,
    }

    try:
        dispatch[args.command](args, tooling_dir)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
