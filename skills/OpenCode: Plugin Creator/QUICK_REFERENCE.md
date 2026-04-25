# Quick Reference

## Plugin Structure

```typescript
export const MyPlugin = async (ctx) => {
  return {
    event: async ({ event }) => { /* handle events */ },
    "tool.execute.before": async (input, output) => { /* before tool */ },
    "tool.execute.after": async (input, output) => { /* after tool */ },
    tool: { /* custom tools */ },
    "experimental.session.compacting": async (input, output) => { /* compact */ },
  }
}
```

## Context Object

```typescript
{
  project: Project,      // Project info
  directory: string,      // Working directory
  worktree: string,       // Git worktree
  client: SDKClient,      // API client
  $: ShellAPI,            // Bun shell
}
```

## Common Hooks

**Events:**
- `session.created` - New session
- `session.idle` - Session completed
- `session.error` - Session error
- `file.edited` - File changed
- `lsp.client.diagnostics` - LSP diagnostics

**Tool Hooks:**
- `tool.execute.before` - Intercept before execution
- `tool.execute.after` - Modify after execution

## Custom Tool

```typescript
import { tool } from "@opencode-ai/plugin"

tool: {
  myTool: tool({
    description: "Tool description",
    args: {
      param: tool.schema.string(),
    },
    async execute({ param }) {
      return `Result: ${param}`
    },
  }),
}
```

## SDK Client

```typescript
// Logging
await client.app.log({ service: "plugin", level: "info", message: "..." })

// Sessions
await client.session.create({ body: { title: "New" } })
await client.session.prompt({ path: { id }, body: { parts: [...] } })

// Files
await client.file.read({ query: { path: "file.ts" } })
await client.find.text({ query: { pattern: "..." } })

// TUI
await client.tui.showToast({ body: { message: "Done!", variant: "success" } })
```

## Scaffolding

```bash
# Bash version
bun run /path/to/skill/scripts/scaffold.sh

# TypeScript version (if available)
bun run /path/to/skill/scripts/scaffold.ts
```

## Plugin Locations

- Project: `.opencode/plugin/`
- Global: `~/.config/opencode/plugin/`
- NPM: Add to `opencode.json` → `plugin` array

## Dependencies

```json
// .opencode/package.json
{
  "dependencies": {
    "axios": "^1.6.0"
  }
}
```

```typescript
// Import and use
import axios from "axios"
```

## TypeScript Support

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async (ctx) => {
  // Type-safe implementation
}
```

## All Event Types

**Command:** `command.executed`
**File:** `file.edited`, `file.watcher.updated`
**Installation:** `installation.updated`
**LSP:** `lsp.client.diagnostics`, `lsp.updated`
**Message:** `message.part.removed`, `message.part.updated`, `message.removed`, `message.updated`
**Permission:** `permission.replied`, `permission.updated`
**Server:** `server.connected`
**Session:** `session.created`, `session.compacted`, `session.deleted`, `session.diff`, `session.error`, `session.idle`, `session.status`, `session.updated`
**Todo:** `todo.updated`
**Tool:** `tool.execute.before`, `tool.execute.after`
**TUI:** `tui.prompt.append`, `tui.command.execute`, `tui.toast.show`

**Experimental:** `experimental.session.compacting`

## See Also

- **SDK API:** `references/sdk-api.md`
- **Architecture:** `references/plugin-architecture.md`
- **Lifecycle:** `references/lifecycle.md`
- **Examples:** `references/examples.md`
- **Template:** `scripts/plugin-template/`
