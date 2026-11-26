# Model Context Protocol (MCP) Reference: Bottom Pot

This document catalogs the MCP servers configured and available in this environment, their intended use, and boundary constraints.

---

## Available MCP Servers

| MCP Server | Status | Purpose & Boundary Rules |
|---|---|---|
| **`github-mcp-server`** | Active | Create branches, inspect files, create pull requests, manage issue comments. Respect `MERGE_POLICY`: open PRs, do NOT merge them unless explicitly directed. |
| **`playwright`** | Active | Automated browser navigation, state interaction, and full-resolution screenshot capture across target viewports. |
| **`chrome-devtools-mcp`** | Active | Performance audits, Lighthouse audits, console inspection, layout shift analysis, and accessibility checks. |
| **`shadcn`** | Active | Search, inspect, and retrieve shadcn/Base UI component patterns. Note: all installed components must adhere to the 0-radius square system. |
| **`context7`** | Active | Query current upstream documentation for libraries in use (e.g. Tailwind v4, Base UI, Lucide). |
| **`Neon`** | *Restricted (Production)* | Production serverless PostgreSQL (`DATABASE_URL` in `AGENTS.md` §2 / `CONTEXT.md`). Agents must never inspect, migrate, or mutate production Neon databases or branches without explicit owner authorization; local dev/tests run strictly offline with `:memory:` or disposable SQLite (`ADR 0030`). |
| **`Vercel`** | *Restricted (Production)* | Production unified SPA + FastAPI deployment (`vercel.json` in `AGENTS.md` §2 / `CONTEXT.md`). Agents must never deploy, promote, or alter cloud hosting configuration without explicit owner authorization. |

---

## Operational Rules

1. **Zero Credential Commits**: Never log, display, or commit API keys, tokens, or credentials.
2. **Local Configuration**: `.agents/mcp_config.json` is gitignored. The template is documented in `.agents/mcp_config.json.example`.
3. **No Unsolicited Hosting or DB Mutations**: Do not deploy, alter Vercel hosting settings, or run migrations/queries against production Neon databases without explicit owner authorization.
