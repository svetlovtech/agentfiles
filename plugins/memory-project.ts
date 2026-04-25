/**
 * OpenCode Project Memory Plugin
 *
 * Cross-session persistent memory for project decisions, conventions,
 * architecture notes, debug info, and temporary context.
 *
 * Storage: .opencode/project-memory.json
 * TTL: configurable per entry, auto-cleanup on read/search
 *
 * Tools: memory_read, memory_write, memory_search, memory_delete
 *
 * @author OpenCode Memory System
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs"
import { join } from "node:path"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               TYPES                                      ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

interface MemoryEntry {
  id: string
  category: "decision" | "convention" | "architecture" | "debug" | "temp"
  key: string
  value: string
  tags: string[]
  created: number
  updated: number
  ttl?: number
  expires?: number
  session_id?: string
}

interface MemoryStore {
  version: number
  project: string
  entries: MemoryEntry[]
  metadata: {
    created: number
    last_modified: number
    total_entries: number
  }
}

type MemoryCategory = MemoryEntry["category"]

const CATEGORIES: { value: MemoryCategory; description: string }[] = [
  { value: "decision", description: "Architectural or design decisions made" },
  { value: "convention", description: "Coding conventions, patterns, or style rules" },
  { value: "architecture", description: "System architecture notes and documentation" },
  { value: "debug", description: "Debug findings, bug fixes, and solutions" },
  { value: "temp", description: "Temporary notes (auto-expire, short TTL)" },
]

const TTL_DEFAULTS: Record<MemoryCategory, number> = {
  decision: 0,
  convention: 0,
  architecture: 0,
  debug: 30 * 24 * 3600 * 1000,
  temp: 7 * 24 * 3600 * 1000,
}

const STORE_VERSION = 1
const SERVICE_NAME = "project-memory"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                         MEMORY STORE CLASS                                ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

class ProjectMemoryStore {
  private store: MemoryStore
  private filePath: string

  constructor(private readonly projectDir: string) {
    const openCodeDir = join(projectDir, ".opencode")
    if (!existsSync(openCodeDir)) {
      mkdirSync(openCodeDir, { recursive: true })
    }
    this.filePath = join(openCodeDir, "project-memory.json")
    this.store = this.load()
  }

  private load(): MemoryStore {
    if (existsSync(this.filePath)) {
      try {
        const raw = readFileSync(this.filePath, "utf-8")
        const parsed = JSON.parse(raw) as MemoryStore
        if (parsed.version === STORE_VERSION) {
          return parsed
        }
      } catch {
        // corrupted, start fresh
      }
    }
    return this.createFresh()
  }

  private createFresh(): MemoryStore {
    return {
      version: STORE_VERSION,
      project: this.projectDir,
      entries: [],
      metadata: {
        created: Date.now(),
        last_modified: Date.now(),
        total_entries: 0,
      },
    }
  }

  private persist(): void {
    this.cleanupExpired()
    this.store.metadata.last_modified = Date.now()
    this.store.metadata.total_entries = this.store.entries.length
    writeFileSync(this.filePath, JSON.stringify(this.store, null, 2), "utf-8")
  }

  private cleanupExpired(): void {
    const now = Date.now()
    const before = this.store.entries.length
    this.store.entries = this.store.entries.filter(
      (e) => !e.expires || e.expires > now
    )
    if (this.store.entries.length < before) {
      // expired entries removed
    }
  }

  private generateId(): string {
    const ts = Date.now().toString(36)
    const rand = Math.random().toString(36).substring(2, 8)
    return `mem_${ts}_${rand}`
  }

  write(params: {
    category: MemoryCategory
    key: string
    value: string
    tags?: string[]
    ttl?: number
    session_id?: string
  }): MemoryEntry {
    const now = Date.now()
    const ttlMs = params.ttl ?? TTL_DEFAULTS[params.category]

    const existing = this.store.entries.find(
      (e) => e.category === params.category && e.key === params.key
    )

    if (existing) {
      existing.value = params.value
      existing.tags = params.tags ?? []
      existing.updated = now
      existing.session_id = params.session_id
      if (ttlMs > 0) {
        existing.ttl = ttlMs
        existing.expires = now + ttlMs
      } else {
        existing.ttl = undefined
        existing.expires = undefined
      }
      this.persist()
      return existing
    }

    const entry: MemoryEntry = {
      id: this.generateId(),
      category: params.category,
      key: params.key,
      value: params.value,
      tags: params.tags ?? [],
      created: now,
      updated: now,
      session_id: params.session_id,
    }

    if (ttlMs > 0) {
      entry.ttl = ttlMs
      entry.expires = now + ttlMs
    }

    this.store.entries.push(entry)
    this.persist()
    return entry
  }

  read(params: {
    category?: MemoryCategory
    key?: string
    tags?: string[]
    include_expired?: boolean
  }): MemoryEntry[] {
    this.cleanupExpired()
    let results = [...this.store.entries]

    if (params.category) {
      results = results.filter((e) => e.category === params.category)
    }
    if (params.key) {
      const keyLower = params.key.toLowerCase()
      results = results.filter((e) => e.key.toLowerCase().includes(keyLower))
    }
    if (params.tags?.length) {
      const tagSet = new Set(params.tags.map((t) => t.toLowerCase()))
      results = results.filter((e) =>
        e.tags.some((t) => tagSet.has(t.toLowerCase()))
      )
    }

    results.sort((a, b) => b.updated - a.updated)
    return results
  }

  search(query: string): MemoryEntry[] {
    this.cleanupExpired()
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean)

    return this.store.entries
      .map((entry) => {
        const searchable = [
          entry.key,
          entry.value,
          entry.category,
          ...entry.tags,
        ]
          .join(" ")
          .toLowerCase()

        const score = terms.filter((term) => searchable.includes(term)).length
        return { entry, score }
      })
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score || b.entry.updated - a.entry.updated)
      .map((r) => r.entry)
  }

  delete(params: { category?: MemoryCategory; key?: string; id?: string }): number {
    let count = 0

    this.store.entries = this.store.entries.filter((entry) => {
      let match = true

      if (params.id) {
        match = entry.id === params.id
      } else {
        if (params.category) match = entry.category === params.category
        if (params.key) {
          const keyLower = params.key.toLowerCase()
          match = match && entry.key.toLowerCase().includes(keyLower)
        }
      }

      if (match) {
        count++
        return false
      }
      return true
    })

    this.persist()
    return count
  }

  getSummary(): string {
    this.cleanupExpired()
    const byCategory = CATEGORIES.map((c) => {
      const count = this.store.entries.filter(
        (e) => e.category === c.value
      ).length
      return `${c.value}: ${count}`
    }).join(", ")

    return `Project Memory: ${this.store.entries.length} entries (${byCategory})`
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const ProjectMemoryPlugin: Plugin = async ({ client, directory }) => {
  const store = new ProjectMemoryStore(directory)

  await client.app.log({
    service: SERVICE_NAME,
    level: "info",
    message: `Initialized. ${store.getSummary()}`,
  })

  const categoryDesc = CATEGORIES.map((c) => `- "${c.value}": ${c.description}`).join("\n")

  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        const summary = store.getSummary()
        await client.app.log({
          service: SERVICE_NAME,
          level: "debug",
          message: `Session ${event.properties.sessionID} started. ${summary}`,
        })
      }
    },

    "experimental.session.compacting": async (_input, output) => {
      const entries = store.read({})
      if (entries.length === 0) return

      const decisions = entries.filter((e) => e.category === "decision")
      const conventions = entries.filter((e) => e.category === "convention")
      const architecture = entries.filter((e) => e.category === "architecture")

      const sections: string[] = []

      if (decisions.length > 0) {
        sections.push(
          "### Key Decisions\n" +
            decisions.map((d) => `- **${d.key}**: ${d.value}`).join("\n")
        )
      }

      if (conventions.length > 0) {
        sections.push(
          "### Project Conventions\n" +
            conventions.map((c) => `- **${c.key}**: ${c.value}`).join("\n")
        )
      }

      if (architecture.length > 0) {
        sections.push(
          "### Architecture Notes\n" +
            architecture.map((a) => `- **${a.key}**: ${a.value}`).join("\n")
        )
      }

      if (sections.length > 0) {
        output.context.push(
          `## Project Memory (auto-injected)\n\n${sections.join("\n\n")}`
        )
      }
    },

    tool: {
      memory_write: tool({
        description: `Write a persistent memory entry for cross-session retention.

Use this to save important project knowledge that should survive across sessions:
- Architectural decisions and their rationale
- Coding conventions and patterns
- Architecture documentation
- Debug findings and solutions
- Temporary working notes

Categories:\n${categoryDesc}

Entries without explicit TTL use defaults: decision/convention/architecture = permanent, debug = 30 days, temp = 7 days.`,
        args: {
          category: tool.schema
            .enum(["decision", "convention", "architecture", "debug", "temp"] as const)
            .describe("Memory category"),
          key: tool.schema
            .string()
            .describe("Short identifier for this memory (e.g. 'use-redis-cache')"),
          value: tool.schema
            .string()
            .describe("The content to remember (detailed description, rationale, etc.)"),
          tags: tool.schema
            .array(tool.schema.string())
            .optional()
            .describe("Tags for searchability (e.g. ['performance', 'backend'])"),
          ttl_days: tool.schema
            .number()
            .optional()
            .describe("Days until auto-expiry (0 = permanent, overrides category default)"),
        },
        async execute(args, ctx) {
          const ttlMs = args.ttl_days !== undefined
            ? args.ttl_days * 24 * 3600 * 1000
            : undefined

          const entry = store.write({
            category: args.category,
            key: args.key,
            value: args.value,
            tags: args.tags,
            ttl: ttlMs,
            session_id: ctx.sessionID,
          })

          const ttlInfo = entry.ttl
            ? ` (TTL: ${Math.round(entry.ttl! / (24 * 3600 * 1000))}d)`
            : " (permanent)"

          const action = entry.created === entry.updated ? "Created" : "Updated"
          return `${action} memory [${entry.category}] "${entry.key}"${ttlInfo} (id: ${entry.id})`
        },
      }),

      memory_read: tool({
        description: `Read project memory entries.

Retrieve saved memories by category, key, or tags.
Use on session start to recover project context.`,
        args: {
          category: tool.schema
            .enum(["decision", "convention", "architecture", "debug", "temp"] as const)
            .optional()
            .describe("Filter by category"),
          key: tool.schema
            .string()
            .optional()
            .describe("Filter by key (substring match)"),
          tags: tool.schema
            .array(tool.schema.string())
            .optional()
            .describe("Filter by tags (entry must have at least one matching tag)"),
        },
        async execute(args) {
          const entries = store.read({
            category: args.category as MemoryCategory | undefined,
            key: args.key,
            tags: args.tags,
          })

          if (entries.length === 0) {
            return "No matching memory entries found."
          }

          const formatted = entries.map((e) => {
            const age = Math.round((Date.now() - e.updated) / (24 * 3600 * 1000))
            const ageStr = age === 0 ? "today" : `${age}d ago`
            const ttlStr = e.expires
              ? ` (expires: ${Math.round((e.expires - Date.now()) / (24 * 3600 * 1000))}d)`
              : ""
            const tagsStr = e.tags.length > 0 ? ` [${e.tags.join(", ")}]` : ""
            return `[${e.category}] ${e.key}${tagsStr} (${ageStr}${ttlStr})\n${e.value}`
          })

          return `Found ${entries.length} entries:\n\n${formatted.join("\n\n---\n\n")}`
        },
      }),

      memory_search: tool({
        description: `Full-text search across all project memory entries.

Searches keys, values, categories, and tags.
Returns results ranked by relevance.`,
        args: {
          query: tool.schema
            .string()
            .describe("Search query (space-separated terms, all must match)"),
        },
        async execute(args) {
          const entries = store.search(args.query)

          if (entries.length === 0) {
            return `No results for "${args.query}".`
          }

          const formatted = entries.map((e) => {
            const tagsStr = e.tags.length > 0 ? ` [${e.tags.join(", ")}]` : ""
            return `[${e.category}] ${e.key}${tagsStr}\n${e.value}`
          })

          return `Found ${entries.length} results for "${args.query}":\n\n${formatted.join("\n\n---\n\n")}`
        },
      }),

      memory_delete: tool({
        description: `Delete project memory entries.

Can delete by specific ID, or by category+key filter.`,
        args: {
          id: tool.schema
            .string()
            .optional()
            .describe("Delete by specific entry ID (takes precedence over other filters)"),
          category: tool.schema
            .enum(["decision", "convention", "architecture", "debug", "temp"] as const)
            .optional()
            .describe("Filter by category"),
          key: tool.schema
            .string()
            .optional()
            .describe("Filter by key (substring match)"),
        },
        async execute(args) {
          if (!args.id && !args.category && !args.key) {
            return "Error: provide at least one of id, category, or key."
          }

          const count = store.delete({
            id: args.id,
            category: args.category as MemoryCategory | undefined,
            key: args.key,
          })

          if (count === 0) {
            return "No matching entries found to delete."
          }

          return `Deleted ${count} memory entr${count === 1 ? "y" : "ies"}.`
        },
      }),
    },
  }
}

export default ProjectMemoryPlugin
