# NexAlfa Agent Instructions

## Workspace
This is NexAlfa's workspace. All files the agent creates, reads, or edits live here unless specified otherwise.

## Skills
Skills live in `./skills/<skill-name>/SKILL.md`. The agent can create, edit, and invoke skills.

## Memory
- `MEMORY.md` — auto-maintained knowledge base (facts, patterns, decisions)
- `USER.md` — what the agent knows about the user (preferences, projects, style)

## Tools Available
- **filesystem** — read, write, edit files
- **process** — execute shell commands
- **browser** — web automation via Playwright
- **cron** — schedule recurring tasks
- **mcp** — connect to MCP servers for external tools
- **webhooks** — handle incoming webhook events
- **sessions** — list, history, send, spawn conversations

## Dev Mode
Everything is allowed. No permission gates. Raw config visible. Thinking messages shown.
