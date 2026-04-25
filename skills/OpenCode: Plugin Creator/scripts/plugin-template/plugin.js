export const MyPlugin = async ({ client, $, directory, worktree, project }) => {
  // Plugin initialization
  await client.app.log({
    service: "my-plugin",
    level: "info",
    message: "Plugin initialized",
  })

  console.log("MyPlugin loaded!")
  console.log("Project:", project)
  console.log("Directory:", directory)
  console.log("Worktree:", worktree)

  return {
    // ============================================
    // Event Handlers
    // ============================================

    event: async ({ event }) => {
      console.log("Event:", event.type, event.properties)

      // Example: Send notification on session completion
      if (event.type === "session.idle") {
        await $`osascript -e 'display notification "Session completed!" with title "opencode"'`
      }

      // Example: Handle errors
      if (event.type === "session.error") {
        console.error("Session error:", event.properties.error)
      }
    },

    // ============================================
    // Tool Interception Hooks
    // ============================================

    "tool.execute.before": async (input, output) => {
      console.log(`Before tool: ${input.tool}`)
      console.log("  Args:", input.args)

      // Example: Sanitize commands
      if (input.tool === "bash") {
        // output.args.command = sanitize(output.args.command)
      }

      // Example: Block sensitive files
      if (input.tool === "read" && output.args.filePath.includes(".env")) {
        throw new Error("Do not read .env files")
      }
    },

    "tool.execute.after": async (input, output) => {
      console.log(`After tool: ${input.tool}`)

      // Example: Enhance error messages
      if (input.tool === "bash" && output.data.exitCode !== 0) {
        output.data.stdout = `Error: ${output.data.stderr}`
      }

      // Example: Log all tool executions
      await client.app.log({
        service: "my-plugin",
        level: "info",
        message: `Executed tool: ${input.tool}`,
      })
    },

    // ============================================
    // Custom Tools
    // ============================================

    tool: {
      myTool: {
        description: "Describe what this tool does",
        args: {
          input: { type: "string", description: "Input parameter description" },
        },
        async execute(args, context) {
          console.log("myTool called with:", args)
          console.log("Context:", context)

          return `Result: ${args.input}`
        },
      },

      // Add more tools here
      // anotherTool: {
      //   description: "Another tool",
      //   args: {
      //     param: { type: "number", description: "A number" },
      //   },
      //   async execute(args) {
      //     return args.param * 2
      //   },
      // },
    },

    // ============================================
    // Experimental Hooks
    // ============================================

    "experimental.session.compacting": async (input, output) => {
      // Add custom context during session compaction
      output.context.push(`
        ## MyPlugin Context
        - Add any context that should persist across compaction
        - Current task status
        - Important decisions
        - Active files
      `)

      // Or replace the entire compaction prompt:
      // output.prompt = `Custom compaction prompt...`
    },
  }
}
