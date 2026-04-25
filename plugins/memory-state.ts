/**
 * OpenCode State Tools Plugin
 *
 * Session-scoped key-value store with optional persistence.
 * Useful for tracking task progress, flags, intermediate results
 * within a session that survive tool boundaries.
 *
 * Storage:
 *   - In-memory Map (session-scoped, fast)
 *   - Optional file persist to .opencode/state-{sessionId}.json
 *
 * Tools: state_get, state_set, state_delete, state_list
 *
 * @author OpenCode Memory System
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync, mkdirSync, unlinkSync, readdirSync } from "node:fs"
import { join } from "node:path"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               TYPES                                      ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

interface StateEntry {
  key: string
  value: string
  type: "string" | "number" | "boolean" | "json"
  created: number
  updated: number
  persist: boolean
}

interface StateFile {
  version: number
  session_id: string
  entries: StateEntry[]
}

const SERVICE_NAME = "state-tools"
const STATE_DIR = ".opencode"
const STATE_FILE_PREFIX = "state-"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                        STATE MANAGER CLASS                                ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

class StateManager {
  private store = new Map<string, StateEntry>()
  private sessionID: string
  private stateDir: string
  private persistPath: string
  private hasPersistedEntries = false

  constructor(sessionID: string, projectDir: string) {
    this.sessionID = sessionID
    this.stateDir = join(projectDir, STATE_DIR)
    this.persistPath = join(this.stateDir, `${STATE_FILE_PREFIX}${sessionID}.json`)

    if (!existsSync(this.stateDir)) {
      mkdirSync(this.stateDir, { recursive: true })
    }

    this.loadFromFile()
  }

  private loadFromFile(): void {
    if (!existsSync(this.persistPath)) return

    try {
      const raw = readFileSync(this.persistPath, "utf-8")
      const data = JSON.parse(raw) as StateFile
      if (data.version !== 1) return

      for (const entry of data.entries) {
        this.store.set(entry.key, entry)
        if (entry.persist) {
          this.hasPersistedEntries = true
        }
      }
    } catch {
      // corrupted or missing
    }
  }

  private persistToFile(): void {
    if (!this.hasPersistedEntries) return

    const entries = Array.from(this.store.values()).filter((e) => e.persist)
    const data: StateFile = {
      version: 1,
      session_id: this.sessionID,
      entries,
    }

    writeFileSync(this.persistPath, JSON.stringify(data, null, 2), "utf-8")
  }

  set(key: string, value: string, persist = false): StateEntry {
    const now = Date.now()
    let type: StateEntry["type"] = "string"

    if (value === "true" || value === "false") {
      type = "boolean"
    } else if (!isNaN(Number(value)) && value.trim() !== "") {
      type = "number"
    } else {
      try {
        JSON.parse(value)
        type = "json"
      } catch {
        type = "string"
      }
    }

    const existing = this.store.get(key)

    const entry: StateEntry = {
      key,
      value,
      type,
      created: existing?.created ?? now,
      updated: now,
      persist,
    }

    this.store.set(key, entry)

    if (persist) {
      this.hasPersistedEntries = true
      this.persistToFile()
    }

    return entry
  }

  get(key: string): StateEntry | null {
    return this.store.get(key) ?? null
  }

  delete(key: string): boolean {
    const entry = this.store.get(key)
    if (!entry) return false

    this.store.delete(key)
    if (entry.persist) {
      this.persistToFile()
    }

    const remaining = Array.from(this.store.values()).some((e) => e.persist)
    if (!remaining) {
      this.hasPersistedEntries = false
      try { unlinkSync(this.persistPath) } catch { /* ignore */ }
    }

    return true
  }

  list(): StateEntry[] {
    return Array.from(this.store.values()).sort((a, b) => b.updated - a.updated)
  }

  getStats(): { total: number; persisted: number; types: Record<string, number> } {
    const entries = this.list()
    const types: Record<string, number> = {}
    let persisted = 0

    for (const e of entries) {
      types[e.type] = (types[e.type] || 0) + 1
      if (e.persist) persisted++
    }

    return { total: entries.length, persisted, types }
  }

  cleanup(): void {
    if (existsSync(this.persistPath)) {
      try { unlinkSync(this.persistPath) } catch { /* ignore */ }
    }
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                     GARBAGE COLLECTOR                                     ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

function cleanupOldStateFiles(projectDir: string, maxAgeMs = 24 * 3600 * 1000): number {
  const stateDir = join(projectDir, STATE_DIR)
  if (!existsSync(stateDir)) return 0

  let cleaned = 0
  const now = Date.now()

  try {
    const files = readdirSync(stateDir)
    for (const file of files) {
      if (!file.startsWith(STATE_FILE_PREFIX) || !file.endsWith(".json")) continue

      const filePath = join(stateDir, file)
      try {
        const stat = readFileSync(filePath, "utf-8")
        const data = JSON.parse(stat) as StateFile
        // Check first entry's updated time or use file mtime
        const lastActivity = data.entries.length > 0
          ? Math.max(...data.entries.map((e) => e.updated))
          : 0

        if (lastActivity > 0 && now - lastActivity > maxAgeMs) {
          unlinkSync(filePath)
          cleaned++
        }
      } catch {
        // skip corrupted files
      }
    }
  } catch {
    // ignore
  }

  return cleaned
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const StateToolsPlugin: Plugin = async ({ client, directory }) => {
  const activeManagers = new Map<string, StateManager>()
  let currentSessionID: string | null = null
  let currentManager: StateManager | null = null

  const cleaned = cleanupOldStateFiles(directory)
  if (cleaned > 0) {
    await client.app.log({
      service: SERVICE_NAME,
      level: "info",
      message: `Cleaned up ${cleaned} old state files (>24h)`,
    })
  }

  await client.app.log({
    service: SERVICE_NAME,
    level: "info",
    message: "Initialized",
  })

  function getManager(sessionID: string): StateManager {
    let mgr = activeManagers.get(sessionID)
    if (!mgr) {
      mgr = new StateManager(sessionID, directory)
      activeManagers.set(sessionID, mgr)
    }
    return mgr
  }

  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        const sid = event.properties.sessionID
        currentSessionID = sid
        currentManager = getManager(sid)

        await client.app.log({
          service: SERVICE_NAME,
          level: "debug",
          message: `Session ${sid}: state manager ready`,
        })
      }

      if (event.type === "session.deleted") {
        const sid = event.properties.sessionID
        const mgr = activeManagers.get(sid)
        if (mgr) {
          mgr.cleanup()
          activeManagers.delete(sid)
          if (currentSessionID === sid) {
            currentSessionID = null
            currentManager = null
          }
        }
      }
    },

    "experimental.session.compacting": async (input, output) => {
      const mgr = getManager(input.sessionID as string)
      const entries = mgr.list()

      if (entries.length === 0) return

      const lines = entries.map((e) => {
        const persistMark = e.persist ? " [persisted]" : ""
        return `- **${e.key}** = \`${e.value}\` (${e.type}${persistMark})`
      })

      output.context.push(
        `## Session State (${entries.length} entries)\n\n${lines.join("\n")}`
      )
    },

    tool: {
      state_set: tool({
        description: `Set a session-scoped key-value state.

Use for tracking task progress, flags, intermediate results.
Values are stored as strings but auto-typed (string/number/boolean/json).

Options:
- persist: save to file (survives process restart within same session dir)
- Session-scoped: each session has its own state namespace`,
        args: {
          key: tool.schema
            .string()
            .describe("State key (use dot-notation for namespacing, e.g. 'task.current')"),
          value: tool.schema
            .string()
            .describe("State value (any string, will be auto-typed)"),
          persist: tool.schema
            .boolean()
            .optional()
            .default(false)
            .describe("Persist to file (survives restart, default: false)"),
        },
        async execute(args, ctx) {
          const manager = getManager(ctx.sessionID)
          const entry = manager.set(args.key, args.value, args.persist ?? false)
          const persistStr = entry.persist ? " [persisted]" : ""
          return `Set "${entry.key}" = "${entry.value}" (${entry.type}${persistStr})`
        },
      }),

      state_get: tool({
        description: `Get a session state value by key.

Returns the value and metadata (type, age, persistence status).`,
        args: {
          key: tool.schema
            .string()
            .describe("State key to retrieve"),
        },
        async execute(args, ctx) => {
          const manager = getManager(ctx.sessionID)
          const entry = manager.get(args.key)

          if (!entry) {
            return `State "${args.key}" not found.`
          }

          const age = Math.round((Date.now() - entry.updated) / 1000)
          const ageStr = age < 60 ? `${age}s ago` : `${Math.round(age / 60)}m ago`
          const persistStr = entry.persist ? " [persisted]" : ""

          return `"${entry.key}" = "${entry.value}" (${entry.type}, updated ${ageStr}${persistStr})`
        },
      }),

      state_delete: tool({
        description: `Delete a session state key.`,
        args: {
          key: tool.schema
            .string()
            .describe("State key to delete"),
        },
        async execute(args, ctx) => {
          const manager = getManager(ctx.sessionID)
          const deleted = manager.delete(args.key)

          if (!deleted) {
            return `State "${args.key}" not found.`
          }

          return `Deleted "${args.key}".`
        },
      }),

      state_list: tool({
        description: `List all session state entries.

Returns all keys, values, types, and metadata.`,
        args: {},
        async execute(_args, ctx) => {
          const manager = getManager(ctx.sessionID)
          const entries = manager.list()
          const stats = manager.getStats()

          if (entries.length === 0) {
            return "No state entries."
          }

          const lines = entries.map((e) => {
            const age = Math.round((Date.now() - e.updated) / 1000)
            const ageStr = age < 60 ? `${age}s` : `${Math.round(age / 60)}m`
            const p = e.persist ? " P" : ""
            return `  ${e.key} = ${e.value}  (${e.type}, ${ageStr}${p})`
          })

          const statsStr = `${stats.total} entries (${stats.persisted} persisted)`
          const typeStr = Object.entries(stats.types)
            .map(([t, c]) => `${t}: ${c}`)
            .join(", ")

          return `Session State [${statsStr} | types: ${typeStr}]\n${lines.join("\n")}`
        },
      }),
    },
  }
}

export default StateToolsPlugin
