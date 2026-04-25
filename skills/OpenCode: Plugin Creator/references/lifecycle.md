# Plugin Lifecycle Hooks

Complete reference of all available event hooks in OpenCode plugins.

## Event Hook Syntax

### Basic Hook Structure

```typescript
event: async ({ event }) => {
  // event.type: string - the event name
  // event.properties: object - event-specific data
}
```

### Named Hooks

```typescript
"hook.name": async (input, output) => {
  // input: object - hook-specific input
  // output: object - modifiable output
}
```

## Available Events

### Command Events

#### `command.executed`

Fired when a command is executed.

**Event Properties:**
```typescript
{
  type: "command.executed",
  properties: {
    command: string,      // Command that was executed
    args?: object,        // Command arguments
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "command.executed") {
    console.log("Command:", event.properties.command)
  }
}
```

---

### File Events

#### `file.edited`

Fired when a file is edited.

**Event Properties:**
```typescript
{
  type: "file.edited",
  properties: {
    path: string,         // File path
    content: string,      // New content
    timestamp: number,
  }
}
```

#### `file.watcher.updated`

Fired when the file watcher detects changes.

**Event Properties:**
```typescript
{
  type: "file.watcher.updated",
  properties: {
    path: string,
    eventType: string,    // "create" | "update" | "delete"
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "file.edited") {
    await client.app.log({
      service: "file-watcher",
      level: "info",
      message: `File edited: ${event.properties.path}`,
    })
  }
}
```

---

### Installation Events

#### `installation.updated`

Fired when installation status changes.

**Event Properties:**
```typescript
{
  type: "installation.updated",
  properties: {
    status: string,       // "installing" | "complete" | "failed"
    component: string,    // What was installed
    timestamp: number,
  }
}
```

---

### LSP Events

#### `lsp.client.diagnostics`

Fired when LSP diagnostics are updated.

**Event Properties:**
```typescript
{
  type: "lsp.client.diagnostics",
  properties: {
    language: string,     // Language server name
    diagnostics: Array<{
      path: string,
      severity: string,
      message: string,
      line: number,
      column: number,
    }>,
    timestamp: number,
  }
}
```

#### `lsp.updated`

Fired when LSP client status changes.

**Event Properties:**
```typescript
{
  type: "lsp.updated",
  properties: {
    language: string,
    status: string,       // "starting" | "running" | "stopped"
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "lsp.client.diagnostics") {
    const errors = event.properties.diagnostics.filter(d => d.severity === "error")
    if (errors.length > 0) {
      console.log(`${errors.length} errors detected`)
    }
  }
}
```

---

### Message Events

#### `message.part.removed`

Fired when a message part is removed.

**Event Properties:**
```typescript
{
  type: "message.part.removed",
  properties: {
    messageID: string,
    partID: string,
    timestamp: number,
  }
}
```

#### `message.part.updated`

Fired when a message part is updated.

**Event Properties:**
```typescript
{
  type: "message.part.updated",
  properties: {
    messageID: string,
    partID: string,
    content: string,
    timestamp: number,
  }
}
```

#### `message.removed`

Fired when a message is removed.

**Event Properties:**
```typescript
{
  type: "message.removed",
  properties: {
    messageID: string,
    timestamp: number,
  }
}
```

#### `message.updated`

Fired when a message is updated.

**Event Properties:**
```typescript
{
  type: "message.updated",
  properties: {
    messageID: string,
    content: string,
    timestamp: number,
  }
}
```

---

### Permission Events

#### `permission.replied`

Fired when a permission request is responded to.

**Event Properties:**
```typescript
{
  type: "permission.replied",
  properties: {
    permissionID: string,
    response: string,     // "allow" | "deny"
    remember: boolean,
    timestamp: number,
  }
}
```

#### `permission.updated`

Fired when permission state changes.

**Event Properties:**
```typescript
{
  type: "permission.updated",
  properties: {
    permissionID: string,
    status: string,
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "permission.replied") {
    const { response, permissionID } = event.properties
    console.log(`Permission ${permissionID}: ${response}`)
  }
}
```

---

### Server Events

#### `server.connected`

Fired when a client connects to the server.

**Event Properties:**
```typescript
{
  type: "server.connected",
  properties: {
    clientID: string,
    timestamp: number,
  }
}
```

---

### Session Events

#### `session.created`

Fired when a new session is created.

**Event Properties:**
```typescript
{
  type: "session.created",
  properties: {
    sessionID: string,
    title: string,
    parentID?: string,
    timestamp: number,
  }
}
```

#### `session.compacted`

Fired when a session is compacted.

**Event Properties:**
```typescript
{
  type: "session.compacted",
  properties: {
    sessionID: string,
    messageCount: number,
    timestamp: number,
  }
}
```

#### `session.deleted`

Fired when a session is deleted.

**Event Properties:**
```typescript
{
  type: "session.deleted",
  properties: {
    sessionID: string,
    timestamp: number,
  }
}
```

#### `session.diff`

Fired when a session diff is calculated.

**Event Properties:**
```typescript
{
  type: "session.diff",
  properties: {
    sessionID: string,
    messageID?: string,
    diff: object,
    timestamp: number,
  }
}
```

#### `session.error`

Fired when a session encounters an error.

**Event Properties:**
```typescript
{
  type: "session.error",
  properties: {
    sessionID: string,
    error: string,
    timestamp: number,
  }
}
```

#### `session.idle`

Fired when a session becomes idle (no activity).

**Event Properties:**
```typescript
{
  type: "session.idle",
  properties: {
    sessionID: string,
    duration: number,     // Idle duration in ms
    timestamp: number,
  }
}
```

#### `session.status`

Fired when session status changes.

**Event Properties:**
```typescript
{
  type: "session.status",
  properties: {
    sessionID: string,
    status: string,       // "idle" | "running" | "error" | "completed"
    timestamp: number,
  }
}
```

#### `session.updated`

Fired when session properties are updated.

**Event Properties:**
```typescript
{
  type: "session.updated",
  properties: {
    sessionID: string,
    changes: object,      // Changed properties
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "session.idle") {
    await $`osascript -e 'display notification "Session completed!" with title "opencode"'`
  }
  if (event.type === "session.error") {
    await client.app.log({
      service: "session-monitor",
      level: "error",
      message: `Session error: ${event.properties.error}`,
    })
  }
}
```

---

### Todo Events

#### `todo.updated`

Fired when the todo list is updated.

**Event Properties:**
```typescript
{
  type: "todo.updated",
  properties: {
    sessionID: string,
    todos: Array<{
      id: string,
      text: string,
      done: boolean,
    }>,
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "todo.updated") {
    const completed = event.properties.todos.filter(t => t.done).length
    console.log(`Todos: ${completed}/${event.properties.todos.length} completed`)
  }
}
```

---

### Tool Events

#### `tool.execute.before`

Fired before a tool is executed. Can modify arguments.

**Hook Signature:**
```typescript
"tool.execute.before": async (input, output) => {
  // input.tool: string - tool name
  // input.args: object - tool arguments
  // output.args: object - modifiable arguments
}
```

**Example:**
```typescript
"tool.execute.before": async (input, output) => {
  if (input.tool === "bash") {
    // Escape command arguments
    output.args.command = escapeCommand(output.args.command)
  }
  if (input.tool === "read" && output.args.filePath.includes(".env")) {
    throw new Error("Do not read .env files")
  }
}
```

#### `tool.execute.after`

Fired after a tool is executed. Can modify results.

**Hook Signature:**
```typescript
"tool.execute.after": async (input, output) => {
  // input.tool: string - tool name
  // input.args: object - tool arguments
  // output.data: object - tool result (modifiable)
}
```

**Example:**
```typescript
"tool.execute.after": async (input, output) => {
  if (input.tool === "bash" && output.data.exitCode !== 0) {
    // Modify output to show error
    output.data.stdout = `Error: ${output.data.stderr}`
  }
  if (input.tool === "write") {
    // Log file writes
    await client.app.log({
      service: "file-writer",
      level: "info",
      message: `Wrote file: ${input.args.filePath}`,
    })
  }
}
```

---

### TUI Events

#### `tui.prompt.append`

Fired when text is appended to the prompt.

**Event Properties:**
```typescript
{
  type: "tui.prompt.append",
  properties: {
    text: string,
    timestamp: number,
  }
}
```

#### `tui.command.execute`

Fired when a TUI command is executed.

**Event Properties:**
```typescript
{
  type: "tui.command.execute",
  properties: {
    command: string,
    timestamp: number,
  }
}
```

#### `tui.toast.show`

Fired when a toast notification is shown.

**Event Properties:**
```typescript
{
  type: "tui.toast.show",
  properties: {
    message: string,
    variant: string,      // "success" | "error" | "warning" | "info"
    timestamp: number,
  }
}
```

**Example:**
```typescript
event: async ({ event }) => {
  if (event.type === "tui.toast.show") {
    console.log(`Toast: ${event.properties.message} (${event.properties.variant})`)
  }
}
```

---

## Experimental Hooks

### `experimental.session.compacting`

Fired before a session is compacted. Can inject context or replace prompt.

**Hook Signature:**
```typescript
"experimental.session.compacting": async (input, output) => {
  // input.sessionID: string
  // output.context: string[] - array of context strings to add
  // output.prompt: string - replacement prompt (if set, context is ignored)
}
```

**Example - Add context:**
```typescript
"experimental.session.compacting": async (input, output) => {
  output.context.push(`
    ## Custom Context
    - Current task: ${getCurrentTask()}
    - Active files: ${getActiveFiles()}
    - Important decisions: ${getDecisions()}
  `)
}
```

**Example - Replace prompt:**
```typescript
"experimental.session.compacting": async (input, output) => {
  output.prompt = `
    You are generating a continuation prompt for a multi-agent swarm session.

    Summarize:
    1. The current task and its status
    2. Which files are being modified and by whom
    3. Any blockers or dependencies between agents
    4. The next steps to complete the work

    Format as a structured prompt that a new agent can use to resume work.
  `
}
```

---

## Hook Execution Order

### Event Flow

1. Plugin initialization
2. Event occurs
3. All `event` hooks run (in load order)
4. Named hooks for that event run (if any)

### Example Flow

For a `bash` command execution:

1. Event: `command.executed`
2. Hook: `tool.execute.before`
3. Tool executes
4. Hook: `tool.execute.after`
5. Event: `file.edited` (if file was modified)

---

## Best Practices

### Event Handling

**Use event type check:**
```typescript
event: async ({ event }) => {
  switch (event.type) {
    case "session.created":
      // Handle session creation
      break
    case "session.error":
      // Handle errors
      break
  }
}
```

### Tool Interception

**Be specific about tools:**
```typescript
"tool.execute.before": async (input, output) => {
  if (input.tool !== "bash") return
  // Only process bash commands
}
```

### Error Handling

**Catch and log errors:**
```typescript
event: async ({ event }) => {
  try {
    await handleEvent(event)
  } catch (error) {
    await client.app.log({
      service: "plugin",
      level: "error",
      message: error.message,
    })
  }
}
```

### Performance

**Avoid blocking:**
```typescript
event: async ({ event }) => {
  // Process asynchronously
  processEventAsync(event).catch(console.error)
}
```

---

## Common Use Cases

### Notifications

```typescript
event: async ({ event }) => {
  if (event.type === "session.idle") {
    await sendNotification("Session completed!")
  }
}
```

### Logging

```typescript
"tool.execute.after": async (input, output) => {
  await client.app.log({
    service: "tool-tracker",
    level: "info",
    message: `Tool ${input.tool} executed`,
  })
}
```

### Security

```typescript
"tool.execute.before": async (input, output) => {
  if (input.tool === "read" && isSensitivePath(output.args.filePath)) {
    throw new Error("Access denied")
  }
}
```

### Data Transformation

```typescript
"tool.execute.after": async (input, output) => {
  if (input.tool === "bash") {
    output.data.stdout = formatOutput(output.data.stdout)
  }
}
```

### Custom Context

```typescript
"experimental.session.compacting": async (input, output) => {
  output.context.push(`## Project Context\n${getProjectContext()}`)
}
```

---

## Event Payloads

### Common Properties

Most events include:
- `type`: string - Event name
- `properties`: object - Event-specific data
- `timestamp`: number - Unix timestamp

### Type Safety

Use TypeScript for better type safety:

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async (ctx) => {
  return {
    event: async ({ event }) => {
      // TypeScript will infer event types
      if (event.type === "session.created") {
        const sessionID = event.properties.sessionID
        // Type-safe access
      }
    },
  }
}
```
