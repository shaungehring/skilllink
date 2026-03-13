---
description: Analyze this project and recommend tools from your skilllink catalog
---

# skill-this-project

You are helping set up a Claude Code project by recommending the right tools from the user's skilllink catalog.

## Your Task

### Step 1 — Get project context

Look for files in the current working directory that describe the project the user is working on or creating (sample file names):
- `PLAN.md` or `PLAN.MD`
- `CLAUDE.md` or `CLAUDE.MD`
- `README.md`

**If a context file exists**, read it now.

**If no context file exists**, ask the user:

> "I don't see a PLAN.md, CLAUDE.md, or README.md in this project. To recommend the right tools, I need to understand your project. Please describe:
>
> 1. **What are you building?** (app type, purpose)
> 2. **What's your tech stack?** (languages, frameworks, databases)
> 3. **Where does it run?** (cloud provider, container, local)
> 4. **Any special requirements?** (auth, real-time, ML, etc.)"

Once the user responds, generate and write a `PLAN.md` in the current directory using this template:

```markdown
# [Project Name]

## Overview
[1-2 sentence description of what this project does]

## Stack
[Bullet list of languages, frameworks, databases, and services]

## Deployment
[Where and how it runs]

## Notes
[Any special requirements or constraints]
```

Tell the user: "I've created PLAN.md for you. You can edit it at any time."

### Step 2 — Read the catalog

Run this command to get all available tools:

```bash
skilllink list
```

If the command fails or returns no tools:
- If `skilllink` is not installed: tell the user to run `curl -fsSL https://raw.githubusercontent.com/shaungehring/skilllink/main/install.sh | bash`
- If `skilllink` is installed but has no catalog: tell the user to run `skilllink init` or `skilllink scan`
- Do not proceed until you have a tool list

### Step 3 — Analyze and match

Compare the project context against each tool's name, type, description, and tags. Consider:

- Languages and frameworks mentioned (e.g., "React" → react-tagged tools)
- Deployment targets (e.g., "AWS" → aws-tagged tools)
- Testing, quality, or compliance requirements
- Tools marked `★` in the list are `always_include: true` — recommend these unconditionally

### Step 4 — Present recommendations

Show your recommendations in a table:

| Tool | Type | Reason |
|------|------|--------|
| React Toolkit | skill | Project uses React frontend |
| FastAPI Agent | agent | Backend is FastAPI |
| Project Scaffolding Agent ★ | agent | Always included |

Keep the list focused — recommend what the project clearly needs, not everything that might be tangentially relevant.

### Step 5 — Output the apply command

After the table, output the exact command for the user to run:

```bash
skilllink apply "Tool Name 1" "Tool Name 2" "Tool Name 3" --scope project
```

Use the **exact tool names** as they appear in `skilllink list` output (names are case-sensitive).

### Step 6 — Ask for confirmation

End with:

> "Shall I run this command for you, or would you like to adjust the list first?"

If the user says yes, run the `skilllink apply` command. If they want changes, update the command accordingly and run it.

## Rules

- Only recommend tools that appear in `skilllink list` — never invent tool names
- Always include tools marked `★` (always_include) without asking
- If the project context is ambiguous, lean toward fewer tools — the user can always add more with `skilllink link`
- If a tool is already linked (shown by `skilllink status`), note it as already active rather than re-recommending it
