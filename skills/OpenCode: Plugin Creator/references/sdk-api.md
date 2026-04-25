# SDK API Reference

Complete API reference for the OpenCode SDK client (`@opencode-ai/sdk`).

## Installation

```bash
npm install @opencode-ai/sdk
```

## Creating a Client

### Start server + client

```typescript
import { createOpencode } from "@opencode-ai/sdk"

const { client } = await createOpencode({
  hostname: "127.0.0.1",
  port: 4096,
  signal: undefined,
  timeout: 5000,
  config: {
    model: "anthropic/claude-3-5-sonnet-20241022",
  },
})
```

### Client only (connect to existing server)

```typescript
import { createOpencodeClient } from "@opencode-ai/sdk"

const client = createOpencodeClient({
  baseUrl: "http://localhost:4096",
  fetch: globalThis.fetch,
  parseAs: "auto",
  responseStyle: "fields",
  throwOnError: false,
})
```

### Import Types

```typescript
import type { Session, Message, Part } from "@opencode-ai/sdk"
```

## API Categories

### Global APIs

#### `global.health()`

Check server health and version.

**Returns:** `{ healthy: true, version: string }`

```typescript
const health = await client.global.health()
console.log(health.data.version)
```

---

### App APIs

#### `app.log()`

Write a log entry.

**Parameters:**
- `body`: `{ service: string, level: "debug"|"info"|"warn"|"error", message: string, extra?: object }`

**Returns:** `boolean`

```typescript
await client.app.log({
  body: {
    service: "my-plugin",
    level: "info",
    message: "Operation completed",
    extra: { foo: "bar" },
  },
})
```

#### `app.agents()`

List all available agents.

**Returns:** `Agent[]`

```typescript
const agents = await client.app.agents()
```

---

### Project APIs

#### `project.list()`

List all projects.

**Returns:** `Project[]`

```typescript
const projects = await client.project.list()
```

#### `project.current()`

Get current project.

**Returns:** `Project`

```typescript
const currentProject = await client.project.current()
```

---

### Path APIs

#### `path.get()`

Get current path information.

**Returns:** `Path`

```typescript
const pathInfo = await client.path.get()
```

---

### Config APIs

#### `config.get()`

Get config info.

**Returns:** `Config`

```typescript
const config = await client.config.get()
```

#### `config.providers()`

List providers and default models.

**Returns:** `{ providers: Provider[], default: { [key: string]: string } }`

```typescript
const { providers, default: defaults } = await client.config.providers()
```

---

### Session APIs

#### `session.list()`

List sessions.

**Returns:** `Session[]`

```typescript
const sessions = await client.session.list()
```

#### `session.get({ path })`

Get session details.

**Parameters:**
- `path.id`: Session ID

**Returns:** `Session`

```typescript
const session = await client.session.get({ path: { id: "session-id" } })
```

#### `session.children({ path })`

List child sessions.

**Parameters:**
- `path.id`: Parent session ID

**Returns:** `Session[]`

```typescript
const children = await client.session.children({ path: { id: "parent-id" } })
```

#### `session.create({ body })`

Create session.

**Parameters:**
- `body`: `{ parentID?: string, title?: string }`

**Returns:** `Session`

```typescript
const session = await client.session.create({
  body: { title: "My session" },
})
```

#### `session.delete({ path })`

Delete session.

**Parameters:**
- `path.id`: Session ID

**Returns:** `boolean`

```typescript
await client.session.delete({ path: { id: "session-id" } })
```

#### `session.update({ path, body })`

Update session properties.

**Parameters:**
- `path.id`: Session ID
- `body`: `{ title?: string }`

**Returns:** `Session`

```typescript
const updated = await client.session.update({
  path: { id: "session-id" },
  body: { title: "New title" },
})
```

#### `session.init({ path, body })`

Analyze app and create AGENTS.md.

**Parameters:**
- `path.id`: Session ID
- `body`: `{ messageID: string, providerID: string, modelID: string }`

**Returns:** `boolean`

#### `session.abort({ path })`

Abort a running session.

**Parameters:**
- `path.id`: Session ID

**Returns:** `boolean`

```typescript
await client.session.abort({ path: { id: "session-id" } })
```

#### `session.share({ path })`

Share session.

**Parameters:**
- `path.id`: Session ID

**Returns:** `Session`

```typescript
const shared = await client.session.share({ path: { id: "session-id" } })
```

#### `session.unshare({ path })`

Unshare session.

**Parameters:**
- `path.id`: Session ID

**Returns:** `Session`

```typescript
const unshared = await client.session.unshare({ path: { id: "session-id" } })
```

#### `session.summarize({ path, body })`

Summarize session.

**Parameters:**
- `path.id`: Session ID
- `body`: `{ providerID: string, modelID: string }`

**Returns:** `boolean`

#### `session.messages({ path })`

List messages in a session.

**Parameters:**
- `path.id`: Session ID

**Returns:** `{ info: Message, parts: Part[] }[]`

```typescript
const messages = await client.session.messages({ path: { id: "session-id" } })
```

#### `session.message({ path })`

Get message details.

**Parameters:**
- `path.id`: Session ID
- `path.messageID`: Message ID

**Returns:** `{ info: Message, parts: Part[] }`

```typescript
const message = await client.session.message({
  path: { id: "session-id", messageID: "message-id" },
})
```

#### `session.prompt({ path, body })`

Send prompt message.

**Parameters:**
- `path.id`: Session ID
- `body`:
  - `model?`: `{ providerID: string, modelID: string }`
  - `noReply?: boolean` - Inject context without AI response
  - `parts`: Part[]

**Returns:** `AssistantMessage` (unless `noReply: true`)

```typescript
// Send prompt and get AI response
const result = await client.session.prompt({
  path: { id: session.id },
  body: {
    model: { providerID: "anthropic", modelID: "claude-3-5-sonnet-20241022" },
    parts: [{ type: "text", text: "Hello!" }],
  },
})

// Inject context without triggering AI response
await client.session.prompt({
  path: { id: session.id },
  body: {
    noReply: true,
    parts: [{ type: "text", text: "You are a helpful assistant." }],
  },
})
```

#### `session.command({ path, body })`

Send command to session.

**Parameters:**
- `path.id`: Session ID
- `body`: `{ messageID?, agent?, model?, command: string, arguments?: object }`

**Returns:** `{ info: AssistantMessage, parts: Part[] }`

#### `session.shell({ path, body })`

Run a shell command.

**Parameters:**
- `path.id`: Session ID
- `body`: `{ agent: string, model?: { providerID: string, modelID: string }, command: string }`

**Returns:** `AssistantMessage`

```typescript
const result = await client.session.shell({
  path: { id: session.id },
  body: { agent: "default", command: "ls -la" },
})
```

#### `session.revert({ path, body })`

Revert a message.

**Parameters:**
- `path.id`: Session ID
- `body`: `{ messageID: string, partID?: string }`

**Returns:** `Session`

#### `session.unrevert({ path })`

Restore reverted messages.

**Parameters:**
- `path.id`: Session ID

**Returns:** `Session`

#### `postSessionByIdPermissionsByPermissionId({ path, body })`

Respond to a permission request.

**Parameters:**
- `path.id`: Session ID
- `path.permissionID`: Permission ID
- `body`: `{ response: "allow"|"deny", remember?: boolean }`

**Returns:** `boolean`

---

### File APIs

#### `find.text({ query })`

Search for text in files.

**Parameters:**
- `query.pattern`: Search pattern

**Returns:** Array of match objects with `path`, `lines`, `line_number`, `absolute_offset`, `submatches`

```typescript
const results = await client.find.text({
  query: { pattern: "function.*opencode" },
})
```

#### `find.files({ query })`

Find files and directories by name.

**Parameters:**
- `query.query`: Search string (fuzzy match)
- `query.type?`: `"file"` or `"directory"`
- `query.directory?`: Override project root
- `query.limit?`: Max results (1-200)

**Returns:** `string[]` (paths)

```typescript
const files = await client.find.files({
  query: { query: "*.ts", type: "file" },
})

const directories = await client.find.files({
  query: { query: "packages", type: "directory", limit: 20 },
})
```

#### `find.symbols({ query })`

Find workspace symbols.

**Parameters:**
- `query.query`: Symbol search query

**Returns:** `Symbol[]`

```typescript
const symbols = await client.find.symbols({ query: "MyFunction" })
```

#### `file.read({ query })`

Read a file.

**Parameters:**
- `query.path`: File path

**Returns:** `{ type: "raw" | "patch", content: string }`

```typescript
const content = await client.file.read({
  query: { path: "src/index.ts" },
})
```

#### `file.status({ query? })`

Get status for tracked files.

**Parameters:**
- `query?`: Optional filter parameters

**Returns:** `File[]`

```typescript
const files = await client.file.status()
```

---

### TUI APIs

#### `tui.appendPrompt({ body })`

Append text to the prompt.

**Parameters:**
- `body.text`: Text to append

**Returns:** `boolean`

```typescript
await client.tui.appendPrompt({ body: { text: "Add this to prompt" } })
```

#### `tui.openHelp()`

Open the help dialog.

**Returns:** `boolean`

#### `tui.openSessions()`

Open the session selector.

**Returns:** `boolean`

#### `tui.openThemes()`

Open the theme selector.

**Returns:** `boolean`

#### `tui.openModels()`

Open the model selector.

**Returns:** `boolean`

#### `tui.submitPrompt()`

Submit the current prompt.

**Returns:** `boolean`

#### `tui.clearPrompt()`

Clear the prompt.

**Returns:** `boolean`

#### `tui.executeCommand({ body })`

Execute a command.

**Parameters:**
- `body.command`: Command string

**Returns:** `boolean`

#### `tui.showToast({ body })`

Show toast notification.

**Parameters:**
- `body.message`: Message text
- `body.variant?`: `"success"` | `"error"` | `"warning"` | `"info"`

**Returns:** `boolean`

```typescript
await client.tui.showToast({
  body: { message: "Task completed", variant: "success" },
})
```

---

### Auth APIs

#### `auth.set({ ... })`

Set authentication credentials.

**Parameters:**
- `path.id`: Provider ID (e.g., "anthropic")
- `body`: `{ type: "api" | "oauth", key?: string, ... }`

**Returns:** `boolean`

```typescript
await client.auth.set({
  path: { id: "anthropic" },
  body: { type: "api", key: "your-api-key" },
})
```

---

### Event APIs

#### `event.subscribe()`

Server-sent events stream.

**Returns:** Async generator of events

```typescript
const events = await client.event.subscribe()
for await (const event of events.stream) {
  console.log("Event:", event.type, event.properties)
}
```

---

## Error Handling

```typescript
try {
  await client.session.get({ path: { id: "invalid-id" } })
} catch (error) {
  console.error("Failed to get session:", (error as Error).message)
}
```

## Type Definitions

See the full type definitions at:
https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts

Key types:
- `Session` - Session object
- `Message` - Message object
- `Part` - Message part (text, tool call, etc.)
- `Project` - Project information
- `File` - File information
- `Agent` - Agent definition
- `Config` - Configuration object
- `Provider` - Provider information
