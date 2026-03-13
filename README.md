# skilllink

> AI-powered skill and agent symlink manager for Claude Code.

Stop stuffing every skill and agent into `~/.claude` and blowing up your context window. **skilllink** lets you maintain a master library of Skills, Agents, and Plugins in any folder you want, then intelligently symlinks only what makes sense for each project — guided by Claude.

---

## How it works

```
~/AITools/          ← your master library (hundreds of tools)
  catalog.yaml        ← index with tags and descriptions
  skills/
  agents/
  plugins/

myproject/.claude/    ← only the tools this project needs
  skills/ → symlinks
  agents/ → symlinks
```

1. **Run `/skill-this-project`** in Claude Code — if you don't have a project description yet, Claude will ask and create one for you
2. **Claude reads your catalog** and recommends matching tools
3. **Confirm the list**, then run the generated `skilllink apply` command
4. **Symlinks are created** — Claude Code only loads what's relevant

---

## Install

One-liner (macOS / Linux):

```bash
curl -fsSL https://raw.githubusercontent.com/shaungehring/skilllink/main/install.sh | bash
```

Or directly from GitHub:

```bash
pip install git+https://github.com/shaungehring/skilllink
```

Or from PyPI (once published):

```bash
pip install skilllink
```

Or from source:

```bash
git clone https://github.com/shaungehring/skilllink
cd skilllink
pip install -e .
```

---

## Setup

### 1. Point skilllink at your tooling directory

By default it looks at `~/.AITools`. Override with an env var:

```bash
export SKILLLINK_TOOLING_DIR=/path/to/your/AITooling
```

Add this to your `~/.zshrc` or `~/.bashrc`.

### 2. Build your catalog

If you already have tools organized in `~/.AITools`:

```bash
skilllink scan
```

This walks your directory, finds all `.md` files, and generates `catalog.yaml` with stub entries. It reads YAML frontmatter from each file to pre-populate names, descriptions, and tags. Then edit `catalog.yaml` to refine — that's what the AI uses to match tools to your project.

#### Example agent frontmatter

```yaml
---
name: accessibility-tester
description: "Use this agent when you need comprehensive accessibility testing, WCAG compliance verification, or assessment of assistive technology support."
tools: Read, Grep, Glob, Bash
model: haiku
---
```

#### Example skill frontmatter

```yaml
---
name: ai-agent-development
description: "AI agent development workflow for building autonomous agents, multi-agent systems, and agent orchestration with CrewAI, LangGraph, and custom agents."
category: granular-workflow-bundle
risk: safe
source: personal
date_added: "2026-02-27"
---
```

If you're starting fresh:

```bash
skilllink init
```

This drops a sample `catalog.yaml` you can adapt.

### 3. Install the slash command

Copy the slash command into your global Claude Code config:

```bash
mkdir -p ~/.claude/commands
cp .claude/commands/skill-this-project.md ~/.claude/commands/
```

### 4. Mark always-on tools

In `catalog.yaml`, set `always_include: true` for tools that should exist in every project (project scaffolding agent, git workflow agent, etc.). The `skilllink apply` command links these automatically — no need to name them explicitly.

---

## Usage

### Starting a new project

```bash
mkdir myproject && cd myproject

# Open Claude Code
code .
# Then in Claude Code: /skill-this-project
```

If the project doesn't have a `PLAN.md`, `CLAUDE.md`, or `README.md` yet, Claude will ask you to describe it and write the file for you. Then it reads your catalog, recommends tools, and outputs:

```bash
skilllink apply "React Toolkit" "TypeScript Strict Mode" "FastAPI Agent" "PostgreSQL Patterns" "AWS CDK Agent" --scope project
```

Run that command and your `.claude/` is set up.

### Manual commands

```bash
# See everything in your catalog
skilllink list

# Filter by tag or type
skilllink list --tag python
skilllink list --type agent

# See what's linked in current project
skilllink status

# Link a tool manually
skilllink link "React Toolkit" --scope project

# Remove a symlink
skilllink unlink "React Toolkit"

# Preview without changing anything
skilllink apply "React Toolkit" "FastAPI Agent" --dry-run

# Apply for real
skilllink apply "React Toolkit" "FastAPI Agent" --scope project
```

---

## catalog.yaml schema

```yaml
tools:
  - name: React Toolkit          # Display name — used in CLI and slash command
    path: skills/react/SKILL.md  # Relative to your tooling directory
    type: skill                  # skill | agent | plugin
    tags:                        # Keywords matched against your project stack
      - react
      - frontend
      - typescript
    description: React component patterns and hooks best practices
    always_include: false        # true = linked in every project automatically
```

**Good tags** are specific: `react`, `fastapi`, `aws`, `postgres`, `langgraph`. Claude matches these against words it detects in your `PLAN.md` or `CLAUDE.md`.

---

## Project structure after setup

```
myproject/
  PLAN.md
  CLAUDE.md
  .claude/
    skills/
      react-toolkit.md  -> ~/AITools/skills/react/SKILL.md
      typescript-strict.md -> ~/AITools/skills/typescript/SKILL.md
    agents/
      project-scaffolding-agent.md -> ~/AITools/agents/project-init/AGENT.md   ★ always
      fastapi-agent.md -> ~/AITools/agents/fastapi/AGENT.md
```

Claude Code loads skills and agents from `.claude/` — only the symlinks that are there get loaded.

---

## Sharing with the community

The catalog schema is the standard. If you publish a skill or agent:

1. Include a `catalog-entry.yaml` with your recommended tags and description
2. Users drop your tool into their `~/.AITools/` folder
3. They add your `catalog-entry.yaml` content to their `catalog.yaml`
4. Done — your tool is discoverable by `/skill-this-project`

---

## Contributing

PRs welcome. The core is four files:

- `skilllink/catalog.py` — catalog read/write/scan and `ToolEntry` dataclass
- `skilllink/linker.py` — symlink management
- `skilllink/cli.py` — CLI commands (argparse)
- `.claude/commands/skill-this-project.md` — the Claude Code slash command

Run the test suite:

```bash
pip install -e ".[dev]"
pytest
```

---

## License

MIT
