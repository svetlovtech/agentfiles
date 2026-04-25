import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async ({ client, $, directory, worktree, project }) => {
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
      switch (event.type) {
        case "session.created":
          console.log("Session created:", event.properties.sessionID)
          break
        case "session.idle":
          console.log("Session idle:", event.properties.sessionID)
          break
        case "session.error":
          console.error("Session error:", event.properties.error)
          break
      }
    },

    // ============================================
    // Tool Interception Hooks
    // ============================================

    "tool.execute.before": async (input, output) => {
      console.log(`Before tool: ${input.tool}`)
      console.log("  Args:", input.args)

      // Example: Modify arguments
      // if (input.tool === "bash") {
      //   output.args.command = sanitize(output.args.command)
      // }

      // Example: Block sensitive operations
      // if (input.tool === "read" && output.args.filePath.includes(".env")) {
      //   throw new Error("Do not read .env files")
      // }
    },

    "tool.execute.after": async (input, output) => {
      console.log(`After tool: ${input.tool}`)

      // Example: Modify output
      // if (input.tool === "bash" && output.data.exitCode !== 0) {
      //   output.data.stdout = `Error: ${output.data.stderr}`
      // }

      // Example: Log operations
      // await client.app.log({
      //   service: "my-plugin",
      //   level: "info",
      //   message: `Executed ${input.tool}`,
      // })
    },

    // ============================================
    // Custom Tools
    // ============================================

    tool: {
      myTool: tool({
        description: "Describe what this tool does",
        args: {
          input: tool.schema.string().describe("Input parameter description"),
        },
        async execute({ input }, context) {
          console.log("myTool called with:", input)
          console.log("Context:", context)

          // Tool implementation
          return `Result: ${input}`
        },
      }),

      // Add more tools here
      // anotherTool: tool({
      //   description: "Another tool",
      //   args: {
      //     param: tool.schema.number(),
      //   },
      //   async execute({ param }) {
      //     return param * 2
      //   },
      // }),
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
