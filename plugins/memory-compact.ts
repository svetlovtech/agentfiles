/**
 * OpenCode Smart Compact Plugin
 *
 * Captures critical session state before compaction and injects it
 * into the compaction context so the agent retains working awareness.
 *
 * Extracts:
 *   - Active files (recently read/edited)
 *   - Tool usage pattern
 *   - Working directory
 *   - Session age / duration
 *
 * Hook: experimental.session.compacting
 *
 * @author OpenCode Memory System
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                          SESSION TRACKER                                  ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

interface FileEvent {
  path: string
  action: "read" | "edited" | "write"
  timestamp: number
}

interface ToolUsage {
  tool: string
  count: number
  lastUsed: number
}

class SessionTracker {
  private readonly fileEvents: FileEvent[] = []
  private readonly toolUsage = new Map<string, { count: number; lastUsed: number }>()
  private sessionStart = Date.now()
  private lastDecisionNote: string | null = null
  private readonly sessionMessages: { role: string; summary: string; timestamp: number }[] = []

  trackFile(path: string, action: "read" | "edited" | "write"): void {
    this.fileEvents.push({ path, action, timestamp: Date.now() })
    if (this.fileEvents.length > 500) {
      this.fileEvents.shift()
    }
  }

  trackTool(tool: string): void {
    const existing = this.toolUsage.get(tool)
    if (existing) {
      existing.count++
      existing.lastUsed = Date.now()
    } else {
      this.toolUsage.set(tool, { count: 1, lastUsed: Date.now() })
    }
  }

  setDecisionNote(note: string): void {
    this.lastDecisionNote = note
  }

  addMessage(role: string, summary: string): void {
    this.sessionMessages.push({ role, summary, timestamp: Date.now() })
    if (this.sessionMessages.length > 50) {
      this.sessionMessages.shift()
    }
  }

  getActiveFiles(windowMs = 10 * 60 * 1000): FileEvent[] {
    const cutoff = Date.now() - windowMs
    const recent = this.fileEvents.filter((e) => e.timestamp >= cutoff)

    const byPath = new Map<string, FileEvent & { _score: number }>()
    for (const event of recent) {
      const existing = byPath.get(event.path)
      if (existing) {
        existing._score += event.action === "edited" ? 3 : event.action === "write" ? 2 : 1
        if (event.timestamp > existing.timestamp) {
          existing.action = event.action
          existing.timestamp = event.timestamp
        }
      } else {
        byPath.set(event.path, {
          ...event,
          _score: event.action === "edited" ? 3 : event.action === "write" ? 2 : 1,
        })
      }
    }

    return Array.from(byPath.values())
      .sort((a, b) => b._score - a._score)
      .slice(0, 20)
  }

  getToolStats(): ToolUsage[] {
    return Array.from(this.toolUsage.entries())
      .map(([tool, data]) => ({ tool, ...data }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 15)
  }

  getSessionDuration(): string {
    const ms = Date.now() - this.sessionStart
    const minutes = Math.floor(ms / 60000)
    if (minutes < 60) return `${minutes}m`
    const hours = Math.floor(minutes / 60)
    const remaining = minutes % 60
    return `${hours}h ${remaining}m`
  }

  getDecisionNote(): string | null {
    return this.lastDecisionNote
  }

  getRecentMessages(count = 5): string[] {
    return this.sessionMessages
      .slice(-count)
      .map((m) => `[${m.role}] ${m.summary}`)
  }

  reset(): void {
    this.fileEvents.length = 0
    this.toolUsage.clear()
    this.sessionMessages.length = 0
    this.lastDecisionNote = null
    this.sessionStart = Date.now()
  }
}

const SERVICE_NAME = "smart-compact"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const SmartCompactPlugin: Plugin = async ({ client }) => {
  const tracker = new SessionTracker()

  await client.app.log({
    service: SERVICE_NAME,
    level: "info",
    message: "Initialized",
  })

  return {
    event: async ({ event }) => {
      switch (event.type) {
        case "session.created":
          tracker.reset()
          break

        case "file.edited":
          tracker.trackFile(event.properties.path, "edited")
          break

        case "session.compacted":
          await client.app.log({
            service: SERVICE_NAME,
            level: "debug",
            message: `Session ${event.properties.sessionID} compacted (${event.properties.messageCount} messages)`,
          })
          break
      }
    },

    "tool.execute.before": async (input) => {
      tracker.trackTool(input.tool)

      if (input.tool === "read" && input.args?.filePath) {
        tracker.trackFile(input.args.filePath, "read")
      }
    },

    "tool.execute.after": async (input, output) => {
      if (input.tool === "write" && input.args?.filePath) {
        tracker.trackFile(input.args.filePath, "write")
      }
      if (input.tool === "edit" && input.args?.filePath) {
        tracker.trackFile(input.args.filePath, "edited")
      }
    },

    "experimental.session.compacting": async (input, output) => {
      const activeFiles = tracker.getActiveFiles()
      const toolStats = tracker.getToolStats()
      const duration = tracker.getSessionDuration()
      const decisionNote = tracker.getDecisionNote()

      const sections: string[] = []

      // Session overview
      sections.push(`### Session Overview\n- Duration: ${duration}`)

      // Active files
      if (activeFiles.length > 0) {
        const edited = activeFiles.filter((f) => f.action === "edited" || f.action === "write")
        const read = activeFiles.filter((f) => f.action === "read")

        const fileLines: string[] = []
        if (edited.length > 0) {
          fileLines.push(`**Modified files:**\n${edited.map((f) => `- \`${f.path}\``).join("\n")}`)
        }
        if (read.length > 0) {
          fileLines.push(`**Recently read:**\n${read.map((f) => `- \`${f.path}\``).join("\n")}`)
        }
        sections.push(`### Active Files\n${fileLines.join("\n\n")}`)
      }

      // Tool usage pattern
      if (toolStats.length > 0) {
        const topTools = toolStats
          .slice(0, 8)
          .map((t) => `- ${t.tool}: ${t.count}x`)
          .join("\n")
        sections.push(`### Tool Usage Pattern\n${topTools}`)
      }

      // Last decision
      if (decisionNote) {
        sections.push(`### Last Recorded Decision\n${decisionNote}`)
      }

      if (sections.length > 0) {
        output.context.push(
          `## Session State (smart-compact)\n\n${sections.join("\n\n")}`
        )
      }
    },
  }
}

export default SmartCompactPlugin
