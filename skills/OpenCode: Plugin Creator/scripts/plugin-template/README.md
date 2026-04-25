# OpenCode Plugin Template

A starter template for creating OpenCode plugins.

## Quick Start

1. **Copy the template**
   ```bash
   cp -r scripts/plugin-template .opencode/plugin/my-plugin
   cd .opencode/plugin/my-plugin
   ```

2. **Install dependencies** (if needed)
   ```bash
   bun install
   ```

3. **Edit the plugin**
   - Open `plugin.ts` or `plugin.js`
   - Modify the plugin name and implementation
   - Add your custom tools and hooks

4. **Test locally**
   - Restart OpenCode
   - The plugin will load automatically

## Plugin Structure

```
plugin-template/
├── plugin.ts         # TypeScript plugin
├── plugin.js         # JavaScript plugin
├── package.json      # Dependencies
└── README.md        # This file
```

## Available Hooks

### Event Handlers
- `session.created` - New session created
- `session.idle` - Session became idle
- `session.error` - Session encountered error
- `file.edited` - File was edited
- And many more (see `references/lifecycle.md`)

### Tool Hooks
- `tool.execute.before` - Before tool execution
- `tool.execute.after` - After tool execution

### Custom Tools
Define tools the LLM can call using the `tool` helper.

### Experimental Hooks
- `experimental.session.compacting` - Customize compaction

## TypeScript vs JavaScript

Choose the appropriate file:
- **TypeScript** (`plugin.ts`) - Type safety, better IDE support
- **JavaScript** (`plugin.js`) - Simpler, no compilation needed

## Publishing to NPM

1. Update `package.json`:
   ```json
   {
     "name": "@your-org/your-plugin",
     "version": "1.0.0"
   }
   ```

2. Build if needed (TypeScript)
3. Publish:
   ```bash
   npm publish
   ```

4. Add to `opencode.json`:
   ```json
   {
     "plugin": ["@your-org/your-plugin"]
   }
   ```

## Resources

- Main workflow: `SKILL.md`
- SDK API: `references/sdk-api.md`
- Architecture: `references/plugin-architecture.md`
- Lifecycle hooks: `references/lifecycle.md`
- Examples: `references/examples.md`

## Examples

### Add a Custom Tool

```typescript
tool: {
  myTool: tool({
    description: "My custom tool",
    args: {
      input: tool.schema.string(),
    },
    async execute({ input }) {
      return `Processed: ${input}`
    },
  })
}
```

### Intercept Tool Execution

```typescript
"tool.execute.before": async (input, output) => {
  if (input.tool === "bash") {
    // Modify arguments
    output.args.command = sanitize(output.args.command)
  }
}
```

### Send Notifications

```typescript
event: async ({ event }) => {
  if (event.type === "session.idle") {
    await $`osascript -e 'display notification "Done!" with title "Plugin"'`
  }
}
```

## Testing

Test your plugin:

```typescript
// test/plugin.test.ts
import { describe, it, expect } from "bun:test"
import { MyPlugin } from "../plugin"

describe("MyPlugin", () => {
  it("should initialize", async () => {
    const plugin = await MyPlugin({})
    expect(plugin).toBeDefined()
  })
})
```

## Support

- OpenCode Docs: https://opencode.ai/docs
- Community Discord: https://opencode.ai/discord
- Report issues: https://github.com/anomalyco/opencode/issues
