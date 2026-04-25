# Plugin Architecture

Deep dive into OpenCode plugin architecture, patterns, and extensibility points.

## What Are Plugins?

Plugins are JavaScript/TypeScript modules that extend OpenCode by hooking into various events and customizing behavior. They can:
- Add new features
- Integrate with external services
- Modify OpenCode's default behavior
- Add custom tools for the LLM
- Intercept and modify tool execution

## Plugin Structure

### Basic Plugin Function

Every plugin exports a function that receives a context object and returns a hooks object:

```typescript
export const MyPlugin = async (context) => {
  // Initialization logic

  return {
    // Hook implementations
  }
}
```

### Context Object

The plugin function receives this context:

```typescript
{
  project: Project,      // Current project information
  directory: string,      // Current working directory
  worktree: string,       // Git worktree path
  client: SDKClient,      // SDK client for AI interaction
  $: ShellAPI,            // Bun shell API for commands
}
```

### Hooks Object

The return object defines which hooks the plugin implements:

```typescript
return {
  "tool.execute.before": async (input, output) => { /* ... */ },
  "tool.execute.after": async (input, output) => { /* ... */ },
  event: async ({ event }) => { /* ... */ },
  tool: { /* custom tools */ }
}
```

## Extensibility Points

### 1. Event Hooks

Events are fired throughout OpenCode's lifecycle. Plugins can subscribe to specific events.

**Event hook signature:**
```typescript
event: async ({ event }) => {
  // event.type: string
  // event.properties: object
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "session.idle") {
    console.log("Session completed!")
  }
}
```

### 2. Tool Interception Hooks

Modify tool execution before or after it runs.

**Before hook:**
```typescript
"tool.execute.before": async (input, output) => {
  // input.tool: string - tool name
  // input.args: object - tool arguments
  // output.args: object - modify arguments
}
```

**After hook:**
```typescript
"tool.execute.after": async (input, output) => {
  // input.tool: string - tool name
  // input.args: object - tool arguments
  // output.data: object - tool result (modify this)
}
```

### 3. Custom Tools

Add new tools that the LLM can call.

```typescript
tool: {
  mytool: tool({
    description: "Tool description",
    args: { /* Zod schema */ },
    async execute(args, context) {
      // Return result
    },
  })
}
```

### 4. Experimental Hooks

Special hooks for advanced use cases.

**Compaction hooks:**
```typescript
"experimental.session.compacting": async (input, output) => {
  // output.context: string[] - add context
  // output.prompt: string - replace entire prompt
}
```

## Plugin Loading System

### Load Order

Plugins are loaded in this sequence:
1. Global config plugins (`~/.config/opencode/opencode.json`)
2. Project config plugins (`opencode.json`)
3. Global plugin directory (`~/.config/opencode/plugin/`)
4. Project plugin directory (`.opencode/plugin/`)

### Plugin Sources

#### Local Files

Place `.js` or `.ts` files in:
- `.opencode/plugin/` (project-level)
- `~/.config/opencode/plugin/` (global)

Files are automatically loaded at startup.

#### NPM Packages

Add to `opencode.json`:
```json
{
  "plugin": ["opencode-helicone-session", "@my-org/custom-plugin"]
}
```

Both regular and scoped packages are supported.

### Caching

NPM plugins are cached in `~/.cache/opencode/node_modules/` after installation with Bun.

### Duplicate Handling

- Duplicate npm packages with same name and version loaded once
- Local and npm plugins with similar names both loaded separately

## Dependencies Management

### Local Plugin Dependencies

Create `.opencode/package.json`:

```json
{
  "dependencies": {
    "shescape": "^2.1.0",
    "axios": "^1.6.0"
  }
}
```

OpenCode runs `bun install` at startup to install these.

### Using Dependencies

```typescript
import { escape } from "shescape"
import axios from "axios"

export const MyPlugin = async ({ client }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash") {
        output.args.command = escape(output.args.command)
      }
    },
  }
}
```

### Best Practices for Dependencies

1. Minimize external dependencies
2. Prefer built-in Node.js APIs
3. Use Bun's built-in utilities
4. Pin versions in package.json
5. Check compatibility with Bun runtime

## Custom Tools Architecture

### Tool Definition Pattern

Tools use the `tool()` helper from `@opencode-ai/plugin`:

```typescript
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Tool description",
  args: {
    param: tool.schema.string().describe("Parameter description"),
  },
  async execute(args, context) {
    // Implementation
    return "result"
  },
})
```

### Tool Naming

**Single export:**
- Filename: `database.ts`
- Tool name: `database`

**Multiple exports:**
- Filename: `math.ts`
- Exports: `add`, `multiply`
- Tool names: `math_add`, `math_multiply`

### Tool Context

Tools receive context about the current session:

```typescript
async execute(args, context) {
  const { agent, sessionID, messageID } = context
  // Use context to access session info
}
```

### Multi-Language Tools

Tools can invoke scripts in any language:

```typescript
async execute(args) {
  // Run Python script
  const result = await Bun.$`python3 .opencode/tool/script.py ${args.a} ${args.b}`.text()
  return result.trim()
}
```

## Hook Execution Model

### Sequential Execution

Hooks run in the order plugins are loaded. All hooks run for each event.

### Input/Output Pattern

Most hooks follow an input/output pattern:

```typescript
"hook.name": async (input, output) => {
  // Read from input
  // Modify output
  // Return is ignored
}
```

### Error Propagation

Errors in hooks propagate up and can halt execution:

```typescript
"tool.execute.before": async (input, output) => {
  if (isSensitive(input.args.filePath)) {
    throw new Error("Access denied")
  }
}
```

### Async/Await Support

All hooks support async operations:

```typescript
"tool.execute.after": async (input, output) => {
  const data = await fetchData()
  output.data.extra = data
}
```

## Communication Patterns

### Plugin to Server

Use SDK client to communicate with the server:

```typescript
const session = await client.session.create({ body: { title: "New" } })
await client.tui.showToast({ body: { message: "Done!" } })
```

### Plugin to Shell

Use Bun's shell API:

```typescript
await $`git status`
const output = await $`echo hello`.text()
```

### Plugin to External Services

Use any HTTP client or service SDK:

```typescript
import { fetch } from "bun"

const response = await fetch("https://api.example.com/data")
const data = await response.json()
```

## State Management

### No Persistent State

Plugins are stateless between calls. Use the server for persistence:

```typescript
// Store state in session metadata
await client.session.update({
  path: { id: sessionID },
  body: { title: "Updated" },
})
```

### Context-Based State

Use the context object for transient state during a single request:

```typescript
let localCache = new Map()

"tool.execute.after": async (input, output) => {
  localCache.set(input.tool, output.data)
}
```

### Session-Based State

For multi-operation state, consider using session metadata or external storage.

## Isolation and Security

### Plugin Isolation

Plugins run in the same process as OpenCode but with controlled access.

### Permissions

Plugins inherit OpenCode's permissions. They can:
- Access all files the user can access
- Make network requests
- Execute shell commands
- Interact with OpenCode APIs

### Best Practices

1. Validate all inputs
2. Sanitize user data
3. Use parameterized commands
4. Avoid eval/exec of untrusted code
5. Log suspicious activity

## Performance Considerations

### Blocking Operations

Avoid blocking operations in hooks:

```typescript
// Bad
"tool.execute.before": async (input, output) => {
  while (true) { /* blocking */ }
}

// Good
"tool.execute.before": async (input, output) => {
  await asyncOperation()
}
```

### Caching

Cache expensive operations:

```typescript
let cache = new Map()

async fetchWithCache(key) {
  if (cache.has(key)) return cache.get(key)
  const data = await expensiveFetch(key)
  cache.set(key, data)
  return data
}
```

### Debouncing/Throttling

For high-frequency events, implement debouncing:

```typescript
let debounceTimer

"file.edited": async (input, output) => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    // Process file change
  }, 500)
}
```

## TypeScript Support

### Type Import

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async (ctx) => {
  return {
    // Type-safe implementations
  }
}
```

### Type Benefits

- Auto-completion for hooks
- Type checking for context
- Better IDE support
- Catch errors at compile time

## Architecture Patterns

### Observer Pattern

Subscribe to events and react:

```typescript
event: async ({ event }) => {
  if (event.type === "session.completed") {
    // Notify external service
  }
}
```

### Middleware Pattern

Intercept and modify operations:

```typescript
"tool.execute.before": async (input, output) => {
  // Pre-process
  output.args = preprocess(output.args)
}

"tool.execute.after": async (input, output) => {
  // Post-process
  output.data = postprocess(output.data)
}
```

### Facade Pattern

Provide simplified interfaces:

```typescript
tool: {
  simpleOperation: tool({
    description: "Simplified operation",
    args: { /* minimal args */ },
    async execute(args) {
      // Complex logic hidden
      return complexOperation(args)
    },
  })
}
```

### Strategy Pattern

Different implementations based on context:

```typescript
"tool.execute.before": async (input, output) => {
  const strategy = getStrategyForTool(input.tool)
  strategy.execute(input, output)
}
```

## Common Plugin Types

### Authentication Plugins

```typescript
"tool.execute.before": async (input, output) => {
  if (input.tool === "auth-sensitive") {
    output.args.token = getToken()
  }
}
```

### Logging Plugins

```typescript
"tool.execute.after": async (input, output) => {
  await client.app.log({
    service: "logger",
    level: "info",
    message: `Executed ${input.tool}`,
  })
}
```

### Transformation Plugins

```typescript
"tool.execute.after": async (input, output) => {
  if (input.tool === "bash") {
    output.data.stdout = transformOutput(output.data.stdout)
  }
}
```

### Integration Plugins

```typescript
event: async ({ event }) => {
  if (event.type === "session.created") {
    await notifyExternalService(event.properties)
  }
}
```

### Utility Plugins

```typescript
tool: {
  formatDate: tool({
    description: "Format a date",
    args: { date: tool.schema.string() },
    async execute({ date }) {
      return new Date(date).toISOString()
    },
  })
}
```

## Testing Plugins

### Local Plugin Testing

Local plugins are auto-loaded from these directories:
- **Project-level**: `.opencode/plugin/` (relative to project root)
- **Global-level**: `~/.config/opencode/plugin/`

**Steps to test a local plugin:**

1. **Create plugin file** (e.g., `.opencode/plugin/my-plugin.ts`):

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async ({ client, directory }) => {
  console.log("[MyPlugin] Loaded!")

  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        console.log("[MyPlugin] Session created")
      }
    }
  }
}

export default MyPlugin
```

2. **Test the plugin**:

```bash
# Run opencode with your plugin
opencode run "test message"

# Check logs for errors
tail -f ~/.local/share/opencode/log/*.log

# Look for plugin loading messages
grep "plugin" ~/.local/share/opencode/log/*.log
```

3. **Common issues and fixes**:

| Error | Cause | Solution |
|-------|-------|----------|
| `BunInstallFailedError` | Plugin name in `opencode.json` | Remove plugin from config, local plugins don't need config |
| `404` on npm registry | Trying to install as npm package | Use local file instead, don't add to config |
| Plugin not loading | Wrong file location | Place in `.opencode/plugin/` or `~/.config/opencode/plugin/` |
| Type errors | Missing types | Ensure `@opencode-ai/plugin` is installed |

4. **Debug with console logs**:

```typescript
export const MyPlugin: Plugin = async ({ client, directory }) => {
  console.log("[MyPlugin] 🚀 Initializing...")
  console.log("[MyPlugin] 📁 Directory:", directory)
  console.log("[MyPlugin] 🔧 Client available:", !!client)

  return {
    "tool.execute.before": async (input, output) => {
      console.log("[MyPlugin] ⚡ Hook: tool.execute.before")
      console.log("[MyPlugin] 📦 Tool:", input.tool)
    }
  }
}
```

5. **Check logs location**:

```bash
# Current log (today's date)
cat ~/.local/share/opencode/log/$(date +%Y-%m-%d)*.log

# Search for plugin-related logs
grep -i "myplugin\|plugin loading" ~/.local/share/opencode/log/*.log

# Follow logs in real-time
tail -f ~/.local/share/opencode/log/$(date +%Y-%m-%d)*.log
```

**Important Notes:**
- Local plugins do NOT need to be listed in `opencode.json`
- They are auto-discovered at startup
- Only `.ts` and `.js` files are loaded
- Plugin must export a function returning event handlers

### Unit Testing

Test hook functions in isolation:

```typescript
import { describe, it, expect } from "bun:test"

describe("MyPlugin", () => {
  it("should block .env files", async () => {
    const plugin = await MyPlugin({})
    const output = { args: { filePath: ".env" } }
    await expect(plugin["tool.execute.before"]({ tool: "read" }, output)).rejects.toThrow()
  })
})
```

### Integration Testing

Test with actual OpenCode instance:

```typescript
import { createOpencode } from "@opencode-ai/sdk"

const { client } = await createOpencode()
// Test plugin behavior through client APIs
```

## Debugging

### Console Logging

```typescript
console.log("Plugin initialized!")
console.log("Context:", context)
```

### Structured Logging

```typescript
await client.app.log({
  service: "my-plugin",
  level: "debug",
  message: "Hook triggered",
  extra: { hook: "tool.execute.before", tool: input.tool },
})
```

### Error Handling

```typescript
try {
  await riskyOperation()
} catch (error) {
  await client.app.log({
    service: "my-plugin",
    level: "error",
    message: error.message,
  })
}
```
