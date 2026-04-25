# Plugin Examples

Collection of code examples for OpenCode plugins.

## Basic Plugin Examples

### Simple Logging Plugin

```typescript
export const LoggingPlugin = async ({ client }) => {
  await client.app.log({
    service: "logging-plugin",
    level: "info",
    message: "Plugin initialized",
  })

  return {
    "tool.execute.after": async (input, output) => {
      await client.app.log({
        service: "logging-plugin",
        level: "info",
        message: `Executed tool: ${input.tool}`,
      })
    },
  }
}
```

### Session Tracker Plugin

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const SessionTracker: Plugin = async ({ client }) => {
  const sessions = new Map()

  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        sessions.set(event.properties.sessionID, {
          started: Date.now(),
          title: event.properties.title,
        })
      }

      if (event.type === "session.idle") {
        const session = sessions.get(event.properties.sessionID)
        if (session) {
          const duration = Date.now() - session.started
          console.log(`Session ${session.title} took ${duration}ms`)
        }
      }

      if (event.type === "session.deleted") {
        sessions.delete(event.properties.sessionID)
      }
    },
  }
}
```

## Tool Interception Examples

### .env File Protection

```typescript
export const EnvProtection = async ({ client }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath.includes(".env")) {
        await client.app.log({
          service: "env-protection",
          level: "warn",
          message: "Blocked attempt to read .env file",
        })
        throw new Error("Do not read .env files")
      }

      if (input.tool === "write" && output.args.filePath.includes(".env")) {
        throw new Error("Do not write to .env files")
      }
    },
  }
}
```

### Command Sanitization

```typescript
import { escape } from "shescape"

export const CommandSanitizer = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash") {
        // Sanitize command arguments
        output.args.command = escape(output.args.command)
      }
    },
  }
}
```

### Error Message Enhancement

```typescript
export const ErrorEnhancer = async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "bash" && output.data.exitCode !== 0) {
        // Enhance error output
        const errorMsg = output.data.stderr || output.data.stdout || "Unknown error"
        output.data.stdout = `❌ Command failed:\n${errorMsg}`
      }
    },
  }
}
```

## Notification Examples

### Desktop Notifications (macOS)

```typescript
export const NotificationPlugin = async ({ $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        await $`osascript -e 'display notification "Session completed!" with title "opencode"'`
      }

      if (event.type === "session.error") {
        await $`osascript -e 'display notification "Session error: ${event.properties.error}" with title "opencode"'`
      }
    },
  }
}
```

### Toast Notifications

```typescript
export const ToastPlugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        await client.tui.showToast({
          body: {
            message: `Session "${event.properties.title}" created`,
            variant: "success",
          },
        })
      }

      if (event.type === "session.error") {
        await client.tui.showToast({
          body: {
            message: `Error: ${event.properties.error}`,
            variant: "error",
          },
        })
      }
    },
  }
}
```

## Custom Tool Examples

### Database Query Tool

```typescript
import { tool } from "@opencode-ai/plugin"

export const DatabasePlugin = async () => {
  return {
    tool: {
      query: tool({
        description: "Execute SQL queries on the project database",
        args: {
          query: tool.schema.string().describe("SQL query to execute"),
        },
        async execute({ query }) {
          // Simulate database execution
          console.log(`Executing: ${query}`)
          return `Results for: ${query}`
        },
      }),
    },
  }
}
```

### HTTP Request Tool

```typescript
import { tool } from "@opencode-ai/plugin"

export const HttpPlugin = async () => {
  return {
    tool: {
      httpGet: tool({
        description: "Make an HTTP GET request",
        args: {
          url: tool.schema.string().url().describe("URL to fetch"),
        },
        async execute({ url }) {
          const response = await fetch(url)
          const text = await response.text()
          return {
            status: response.status,
            body: text,
          }
        },
      }),
    },
  }
}
```

### File Stats Tool

```typescript
import { tool } from "@opencode-ai/plugin"

export const FileStatsPlugin = async ({ $ }) => {
  return {
    tool: {
      fileStats: tool({
        description: "Get file statistics",
        args: {
          path: tool.schema.string().describe("File path"),
        },
        async execute({ path }) {
          const result = await $`wc -l ${path}`.text()
          const lines = parseInt(result.trim().split(/\s+/)[0])
          return {
            path,
            lines,
          }
        },
      }),
    },
  }
}
```

### Math Operations (Multiple Tools)

```typescript
import { tool } from "@opencode-ai/plugin"

export const MathPlugin = async () => {
  return {
    tool: {
      add: tool({
        description: "Add two numbers",
        args: {
          a: tool.schema.number().describe("First number"),
          b: tool.schema.number().describe("Second number"),
        },
        async execute({ a, b }) {
          return a + b
        },
      }),

      multiply: tool({
        description: "Multiply two numbers",
        args: {
          a: tool.schema.number().describe("First number"),
          b: tool.schema.number().describe("Second number"),
        },
        async execute({ a, b }) {
          return a * b
        },
      }),
    },
  }
}
```

## Multi-Language Tool Examples

### Python Tool Wrapper

```typescript
import { tool } from "@opencode-ai/plugin"

export const PythonToolPlugin = async () => {
  return {
    tool: {
      pythonAdd: tool({
        description: "Add two numbers using Python",
        args: {
          a: tool.schema.number(),
          b: tool.schema.number(),
        },
        async execute({ a, b }) {
          // Assumes .opencode/tool/add.py exists
          const result = await Bun.$`python3 .opencode/tool/add.py ${a} ${b}`.text()
          return result.trim()
        },
      }),
    },
  }
}
```

### Shell Script Tool

```typescript
import { tool } from "@opencode-ai/plugin"

export const ShellToolPlugin = async () => {
  return {
    tool: {
      listFiles: tool({
        description: "List files in a directory",
        args: {
          directory: tool.schema.string().optional().describe("Directory to list"),
        },
        async execute({ directory = "." }) {
          const result = await Bun.$`ls -la ${directory}`.text()
          return result
        },
      }),
    },
  }
}
```

## Integration Examples

### GitHub Integration

```typescript
import { tool } from "@opencode-ai/plugin"

export const GitHubPlugin = async () => {
  const GITHUB_API = "https://api.github.com"

  return {
    tool: {
      createIssue: tool({
        description: "Create a GitHub issue",
        args: {
          owner: tool.schema.string().describe("Repository owner"),
          repo: tool.schema.string().describe("Repository name"),
          title: tool.schema.string().describe("Issue title"),
          body: tool.schema.string().optional().describe("Issue body"),
        },
        async execute({ owner, repo, title, body }) {
          const response = await fetch(`${GITHUB_API}/repos/${owner}/${repo}/issues`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `token ${process.env.GITHUB_TOKEN}`,
            },
            body: JSON.stringify({ title, body }),
          })

          const data = await response.json()
          return data
        },
      }),
    },
  }
}
```

### External Service Integration

```typescript
import { tool } from "@opencode-ai/plugin"

export const ServicePlugin = async () => {
  return {
    tool: {
      checkStatus: tool({
        description: "Check external service status",
        args: {
          service: tool.schema.string().describe("Service name"),
        },
        async execute({ service }) {
          // Simulate API call
          await new Promise(resolve => setTimeout(resolve, 100))
          return {
            service,
            status: "operational",
            uptime: "99.9%",
          }
        },
      }),
    },
  }
}
```

## Compaction Hooks Examples

### Custom Compaction Context

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const CompactionPlugin: Plugin = async () => {
  return {
    "experimental.session.compacting": async (input, output) => {
      // Add project-specific context
      output.context.push(`
        ## Project Context
        - Framework: React
        - Build system: Vite
        - Testing: Vitest
      `)

      output.context.push(`
        ## Recent Activity
        - Modified 5 files
        - Created 2 new components
        - Fixed 3 bugs
      `)
    },
  }
}
```

### Domain-Specific Compaction

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const DomainCompactionPlugin: Plugin = async ({ project, directory }) => {
  return {
    "experimental.session.compacting": async (input, output) => {
      // Inject domain-specific knowledge
      const context = getDomainContext(project, directory)
      output.context.push(`
        ## Domain Knowledge
        ${context}
      `)
    },
  }
}

function getDomainContext(project, directory) {
  // Extract domain-specific context
  return "This is a finance application handling transactions..."
}
```

### Complete Compaction Prompt Replacement

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const CustomCompactionPlugin: Plugin = async () => {
  return {
    "experimental.session.compacting": async (input, output) => {
      // Replace entire compaction prompt
      output.prompt = `
        You are generating a continuation prompt for a multi-agent swarm session.

        Analyze the conversation and create a concise summary that includes:

        1. **Current Objective**
           - What is being worked on
           - What has been completed

        2. **Active Work**
           - Which files are being modified
           - Who is working on what (if multi-agent)

        3. **Key Decisions**
           - Important architectural decisions
           - Design patterns chosen

        4. **Blockers & Dependencies**
           - What's blocking progress
           - What needs to be done next

        5. **Next Steps**
           - Immediate actions required
           - Long-term goals

        Format as a clear, actionable prompt that a new agent can use to resume work seamlessly.
      `
    },
  }
}
```

## Advanced Examples

### File Change Tracker

```typescript
export const FileChangeTracker = async ({ client }) => {
  const fileChanges = new Map()

  return {
    event: async ({ event }) => {
      if (event.type === "file.edited") {
        const path = event.properties.path
        const changes = fileChanges.get(path) || []

        changes.push({
          timestamp: Date.now(),
          content: event.properties.content,
        })

        fileChanges.set(path, changes)

        await client.app.log({
          service: "file-tracker",
          level: "info",
          message: `File edited: ${path} (Total changes: ${changes.length})`,
        })
      }
    },

    tool: {
      getFileChanges: {
        description: "Get change history for a file",
        args: {
          path: tool.schema.string().describe("File path"),
        },
        async execute({ path }) {
          return fileChanges.get(path) || []
        },
      },
    },
  }
}
```

### LSP Diagnostics Monitor

```typescript
export const LSPMonitor = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "lsp.client.diagnostics") {
        const { language, diagnostics } = event.properties

        const errors = diagnostics.filter(d => d.severity === "error")
        const warnings = diagnostics.filter(d => d.severity === "warning")

        if (errors.length > 0) {
          await client.tui.showToast({
            body: {
              message: `${errors.length} errors in ${language}`,
              variant: "error",
            },
          })
        }

        await client.app.log({
          service: "lsp-monitor",
          level: "info",
          message: `${language}: ${errors.length} errors, ${warnings.length} warnings`,
          extra: { diagnostics },
        })
      }
    },
  }
}
```

### Session Analytics Plugin

```typescript
export const SessionAnalytics = async ({ client }) => {
  const analytics = {
    totalSessions: 0,
    totalDuration: 0,
    errors: 0,
    toolUsage: new Map(),
  }

  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        analytics.totalSessions++
      }

      if (event.type === "session.idle") {
        analytics.totalDuration += event.properties.duration
      }

      if (event.type === "session.error") {
        analytics.errors++
      }
    },

    "tool.execute.after": async (input, output) => {
      const count = analytics.toolUsage.get(input.tool) || 0
      analytics.toolUsage.set(input.tool, count + 1)
    },

    tool: {
      getAnalytics: {
        description: "Get session analytics",
        args: {},
        async execute() {
          return {
            ...analytics,
            toolUsage: Object.fromEntries(analytics.toolUsage),
            avgDuration: analytics.totalSessions
              ? analytics.totalDuration / analytics.totalSessions
              : 0,
          }
        },
      },
    },
  }
}
```

## TypeScript Examples

### Type-Safe Plugin

```typescript
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

export const TypeScriptPlugin: Plugin = async ({ client, $, directory, worktree }) => {
  return {
    // Type-safe hooks
    event: async ({ event }) => {
      if (event.type === "session.created") {
        console.log("Session created:", event.properties.sessionID)
      }
    },

    // Type-safe tool
    tool: {
      typeSafeTool: tool({
        description: "A type-safe tool",
        args: {
          input: tool.schema.string(),
        },
        async execute({ input }) {
          return `Processed: ${input}`
        },
      }),
    },
  }
}
```

## Error Handling Examples

### Robust Error Handling

```typescript
export const RobustPlugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      try {
        await handleEvent(event)
      } catch (error) {
        await client.app.log({
          service: "robust-plugin",
          level: "error",
          message: error.message,
          extra: { event: event.type },
        })
      }
    },
  }
}

async function handleEvent(event) {
  // Event handling logic
}
```

### Graceful Degradation

```typescript
export const GracefulPlugin = async ({ client }) => {
  return {
    "tool.execute.after": async (input, output) => {
      try {
        // Try to enhance output
        output.data = enhanceOutput(output.data)
      } catch (error) {
        // Fall back to original output
        await client.app.log({
          service: "graceful-plugin",
          level: "warn",
          message: "Failed to enhance output, using original",
        })
      }
    },
  }
}
```

## Testing Examples

### Testable Plugin

```typescript
export const TestablePlugin = async ({ client, $ }) => {
  return {
    tool: {
      addNumbers: {
        description: "Add two numbers",
        args: {
          a: tool.schema.number(),
          b: tool.schema.number(),
        },
        async execute({ a, b }) {
          return a + b
        },
      },
    },
  }
}
```

### Test File

```typescript
import { describe, it, expect } from "bun:test"
import { TestablePlugin } from "./testable-plugin"

describe("TestablePlugin", () => {
  it("should add two numbers", async () => {
    const plugin = await TestablePlugin({})
    const result = await plugin.tool.addNumbers.execute({ a: 2, b: 3 })
    expect(result).toBe(5)
  })
})
```

## Community Plugin Examples

Based on real community plugins from the ecosystem:

### Helicone Session Headers

```typescript
export const HeliconePlugin = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "prompt" || input.tool === "command") {
        // Inject Helicone session headers
        const sessionId = generateSessionId()
        output.args.headers = {
          ...output.args.headers,
          "Helicone-Session-Id": sessionId,
        }
      }
    },
  }
}
```

### WakaTime Integration

```typescript
export const WakaTimePlugin = async ({ $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        const duration = Math.floor(event.properties.duration / 1000)
        await $`wakatime-cli --write --entity-file opencode.session --duration ${duration}`
      }
    },
  }
}
```

### Dynamic Context Pruning

```typescript
export const ContextPruner = async () => {
  const toolOutputs = new Map()

  return {
    "tool.execute.after": async (input, output) => {
      // Cache tool outputs
      toolOutputs.set(input.tool, {
        timestamp: Date.now(),
        output: output.data,
      })
    },

    "experimental.session.compacting": async (input, output) => {
      // Remove old tool outputs from context
      const now = Date.now()
      const maxAge = 5 * 60 * 1000 // 5 minutes

      for (const [tool, data] of toolOutputs.entries()) {
        if (now - data.timestamp > maxAge) {
          toolOutputs.delete(tool)
        }
      }

      output.context.push(`
        ## Cached Tool Outputs
        ${Array.from(toolOutputs.entries())
          .map(([tool, data]) => `${tool}: ${JSON.stringify(data.output)}`)
          .join("\n")}
      `)
    },
  }
}
```

## Template Examples

### Plugin Template with All Features

```typescript
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async ({ client, $, directory, worktree, project }) => {
  // Initialization
  await client.app.log({
    service: "my-plugin",
    level: "info",
    message: "Plugin initialized",
  })

  return {
    // Event handlers
    event: async ({ event }) => {
      console.log("Event:", event.type)
    },

    // Tool hooks
    "tool.execute.before": async (input, output) => {
      console.log("Before:", input.tool)
    },

    "tool.execute.after": async (input, output) => {
      console.log("After:", input.tool)
    },

    // Custom tools
    tool: {
      myTool: tool({
        description: "My custom tool",
        args: {
          input: tool.schema.string(),
        },
        async execute({ input }) {
          return `Result: ${input}`
        },
      }),
    },

    // Experimental hooks
    "experimental.session.compacting": async (input, output) => {
      output.context.push("Custom compaction context")
    },
  }
}
```

## More Examples

See the OpenCode ecosystem for more community plugins:
- https://opencode.ai/docs/ecosystem#plugins
- https://github.com/awesome-opencode/awesome-opencode
