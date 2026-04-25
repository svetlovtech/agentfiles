---
name: OpenCode: Plugin Creator
description: Guide developers through creating, building, and distributing OpenCode plugins. Covers SDK API, plugin architecture, lifecycle hooks, custom tools, best practices, and distribution.
---

# OpenCode Plugin Creator

Start here to create OpenCode plugins that extend functionality with event hooks, custom tools, and SDK integrations.

## Quick Start

**Choose your approach:**

1. **Local Plugin** - Place `.ts` or `.js` files in `.opencode/plugin/`
2. **Global Plugin** - Place files in `~/.config/opencode/plugin/`
3. **NPM Package** - Publish to npm and add to `opencode.json` config

**Basic plugin structure:**

```typescript
export const MyPlugin = async ({ project, client, $, directory, worktree }) => {
  console.log("Plugin initialized!")

  return {
    // Hook implementations
  }
}
```

**Use TypeScript for type safety:**

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async (ctx) => {
  return {
    // Type-safe hook implementations
  }
}
```

## Core Concepts

**Plugin Function Context:**
- `project` - Current project information
- `directory` - Current working directory
- `worktree` - Git worktree path
- `client` - SDK client for AI interaction
- `$` - Bun shell API for commands

**Return Object Structure:**
```typescript
{
  "hook.name": async (input, output) => { /* implementation */ },
  event: async ({ event }) => { /* event handler */ },
  tool: { /* custom tools */ }
}
```

## Workflow Steps

### 1. Choose Event Hooks

See `references/lifecycle.md` for complete hook list.

Common hooks:
- `tool.execute.before` - Intercept before tool execution
- `tool.execute.after` - Modify tool output
- `session.created` - Respond to new sessions
- `file.edited` - Track file changes
- `event` - Catch all events

### 2. Add Custom Tools (Optional)

Tools extend LLM capabilities:

```typescript
import { tool } from "@opencode-ai/plugin"

export const CustomToolsPlugin: Plugin = async (ctx) => {
  return {
    tool: {
      mytool: tool({
        description: "This is a custom tool",
        args: {
          foo: tool.schema.string(),
        },
        async execute(args, ctx) {
          return `Hello ${args.foo}!`
        },
      }),
    },
  }
}
```

### 3. Use SDK API

Client methods available in `references/sdk-api.md`:

```typescript
// Logging
await client.app.log({
  service: "my-plugin",
  level: "info",
  message: "Plugin initialized",
})

// Session management
const session = await client.session.create({
  body: { title: "My session" }
})

// File operations
const content = await client.file.read({
  query: { path: "src/index.ts" }
})
```

### 4. Add Dependencies

Create `.opencode/package.json`:

```json
{
  "dependencies": {
    "shescape": "^2.1.0"
  }
}
```

Import in plugin:

```typescript
import { escape } from "shescape"
```

### 5. Test Plugin

Local plugins auto-load at startup. For npm plugins:

```json
{
  "plugin": ["opencode-helicone-session", "@my-org/custom-plugin"]
}
```

**Load order:**
1. Global config plugins
2. Project config plugins
3. Global plugin directory
4. Project plugin directory

### 6. Distribute

**As npm package:**
```bash
npm init
npm publish
```

**As local file:**
Copy to `.opencode/plugin/` or `~/.config/opencode/plugin/`

## Common Patterns

**Block sensitive files:**
```typescript
"tool.execute.before": async (input, output) => {
  if (input.tool === "read" && output.args.filePath.includes(".env")) {
    throw new Error("Do not read .env files")
  }
}
```

**Send notifications:**
```typescript
event: async ({ event }) => {
  if (event.type === "session.idle") {
    await $`osascript -e 'display notification "Session completed!" with title "opencode"'`
  }
}
```

**Modify tool output:**
```typescript
"tool.execute.after": async (input, output) => {
  if (input.tool === "bash" && output.data.exitCode !== 0) {
    output.data.stdout = `Error: ${output.data.stderr}`
  }
}
```

## Key Resources

- **SDK API Reference** - `references/sdk-api.md`
- **Plugin Architecture** - `references/plugin-architecture.md`
- **Lifecycle Hooks** - `references/lifecycle.md`
- **Code Examples** - `references/examples.md`
- **Plugin Template** - `scripts/plugin-template/`

## Best Practices

1. **TypeScript** - Use `import type { Plugin } from "@opencode-ai/plugin"`
2. **Logging** - Use `client.app.log()` instead of `console.log()` (see **TUI-Safe Logging** below)
3. **Error handling** - Always catch and handle errors gracefully
4. **Dependencies** - Minimize external deps, prefer built-in APIs
5. **Performance** - Avoid blocking operations, use async/await
6. **Testing** - Test locally before publishing
7. **Documentation** - Document hooks used and expected behavior

### TUI-Safe Logging

**IMPORTANT:** Never use `console.log()` or `console.error()` in plugins when running OpenCode with the TUI (Terminal User Interface). These outputs will break the TUI rendering.

**Always use `client.app.log()` for all logging:**

```typescript
export const MyPlugin: Plugin = async ({ client }) => {
  // ❌ BAD - This will break TUI
  console.log("Plugin initialized")

  // ✅ GOOD - Structured logging that doesn't break TUI
  await client.app.log({
    service: "my-plugin",
    level: "info",
    message: "Plugin initialized",
  })

  return {
    event: async ({ event }) => {
      // ❌ BAD
      console.log("Event received:", event.type)

      // ✅ GOOD
      await client.app.log({
        service: "my-plugin",
        level: "info",
        message: `Event received: ${event.type}`,
        extra: { eventType: event.type },
      })
    },
  }
}
```

**Why?**
- `console.log()` writes directly to stdout/stderr, which corrupts the TUI's terminal rendering
- `client.app.log()` sends structured logs to OpenCode's logging system that handles them properly without interfering with TUI
- Logs from `client.app.log()` appear in the log files (`~/.local/share/opencode/logs/`) without breaking the interface

**Log levels:** `debug`, `info`, `warn`, `error`

 **Debugging plugins:**
 ```bash
 # View plugin logs
 tail -f ~/.local/share/opencode/logs/$(date +%Y-%m-%d)*.log | grep my-plugin
 ```

 **Logging in helper classes:**
 When using helper classes, pass `client` to the constructor to enable proper logging:

 ```typescript
 class MyHelper {
   private client: any

   constructor(client: any) {
     this.client = client
   }

   async doWork() {
     await this.client.app.log({
       service: "my-plugin",
       level: "info",
       message: "Work completed",
     })
   }
 }

 export const MyPlugin: Plugin = async ({ client }) => {
   const helper = new MyHelper(client)

   return {
     event: async ({ event }) => {
       await helper.doWork()
     },
   }
 }
 ```

 **Getting session details from events:**
 Events like `session.idle` provide `sessionID` but not full session data. Use the SDK to fetch session info:

 ```typescript
 event: async ({ event, client }) => {
   if (event.type === "session.idle") {
     const sessionID = event.properties.sessionID

     // Fetch session details
     const session = await client.session.get({
       path: { id: sessionID }
     })

     const title = session.title ?? "Unknown session"

     // Check if this is a subagent session (has parentID)
     if (session.parentID) {
       await client.app.log({
         service: "my-plugin",
         level: "debug",
         message: "Skipping subagent session",
       })
       return
     }

     await client.app.log({
       service: "my-plugin",
       level: "info",
       message: `Session completed: ${title}`,
     })
   }
 }
 ```

Available session properties: `title`, `created`, `modified`, `parentID`, etc. See SDK docs for complete reference.

**Detecting subagent sessions:**
 Sessions spawned by `@mentions` or agent commands have a `parentID` property pointing to the parent session. Check this to distinguish main sessions from subagents:
- Main session: `session.parentID` is `undefined` or `null`
- Subagent session: `session.parentID` contains the parent session ID
 ```

## Advanced Topics

**Custom compaction hooks:**
```typescript
"experimental.session.compacting": async (input, output) => {
  // Inject additional context
  output.context.push(`
    ## Custom Context
    - Current task status
    - Important decisions
    - Active files
  `)
}
```

**Multi-tool files:**
Filename: `math.ts` → Tools: `math_add`, `math_multiply`

**Shell integration:**
```typescript
const result = await Bun.$`command args`.text()
```

## Getting Help

- Browse community plugins: `references/examples.md`
- Check OpenAPI spec: `http://localhost:4096/doc`
- Community Discord: https://opencode.ai/discord
