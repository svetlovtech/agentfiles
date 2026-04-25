/**
 * OpenCode Remember Tags Plugin
 *
 * Parses <remember> and <remember priority> tags from LLM text output
 * and persists them to project memory.
 *
 * Tags:
 *   <remember>content</remember>           → temp category, 7 days TTL
 *   <remember priority>content</remember>  → decision category, permanent
 *
 * Hook: tool.execute.after — scans text output for tags
 * Auto-cleanup: removes expired remember entries on write
 *
 * @author OpenCode Memory System
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs"
import { join } from "node:path"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               TYPES                                      ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

interface RememberEntry {
  id: string
  content: string
  priority: boolean
  category: "decision" | "temp"
  created: number
  expires: number
  session_id?: string
  source_tool?: string
}

interface RememberStore {
  version: number
  entries: RememberEntry[]
}

const STORE_VERSION = 1
const SERVICE_NAME = "remember-tags"

const REGEX_NORMAL = /<remember>([\s\S]*?)<\/remember>/g
const REGEX_PRIORITY = /<remember\s+priority>([\s\S]*?)<\/remember>/g

const TTL_NORMAL_DAYS = 7
const TTL_NORMAL_MS = TTL_NORMAL_DAYS * 24 * 3600 * 1000
const TTL_PRIORITY_MS = 0

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                        REMEMBER STORE CLASS                               ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

class RememberStoreManager {
  private store: RememberStore
  private filePath: string

  constructor(private readonly projectDir: string) {
    const openCodeDir = join(projectDir, ".opencode")
    if (!existsSync(openCodeDir)) {
      mkdirSync(openCodeDir, { recursive: true })
    }
    this.filePath = join(openCodeDir, "remember-tags.json")
    this.store = this.load()
  }

  private load(): RememberStore {
    if (existsSync(this.filePath)) {
      try {
        const raw = readFileSync(this.filePath, "utf-8")
        const parsed = JSON.parse(raw) as RememberStore
        if (parsed.version === STORE_VERSION) {
          return parsed
        }
      } catch {
        // corrupted
      }
    }
    return { version: STORE_VERSION, entries: [] }
  }

  private persist(): void {
    this.cleanup()
    writeFileSync(this.filePath, JSON.stringify(this.store, null, 2), "utf-8")
  }

  private cleanup(): void {
    const now = Date.now()
    this.store.entries = this.store.entries.filter((e) => e.expires > now)
  }

  add(params: {
    content: string
    priority: boolean
    session_id?: string
    source_tool?: string
  }): RememberEntry {
    const now = Date.now()
    const isPriority = params.priority

    const entry: RememberEntry = {
      id: `rem_${now.toString(36)}_${Math.random().toString(36).substring(2, 8)}`,
      content: params.content.trim(),
      priority: isPriority,
      category: isPriority ? "decision" : "temp",
      created: now,
      expires: isPriority ? now + 365 * 24 * 3600 * 1000 : now + TTL_NORMAL_MS,
      session_id: params.session_id,
      source_tool: params.source_tool,
    }

    this.store.entries.push(entry)
    this.persist()
    return entry
  }

  getAll(): RememberEntry[] {
    this.cleanup()
    return [...this.store.entries].sort((a, b) => b.created - a.created)
  }

  getSummary(): string {
    this.cleanup()
    const priority = this.store.entries.filter((e) => e.priority).length
    const normal = this.store.entries.filter((e) => !e.priority).length
    return `${priority} priority, ${normal} temporary (${this.store.entries.length} total)`
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const RememberTagsPlugin: Plugin = async ({ client, directory }) => {
  const rememberStore = new RememberStoreManager(directory)

  await client.app.log({
    service: SERVICE_NAME,
    level: "info",
    message: `Initialized. Remember tags: ${rememberStore.getSummary()}`,
  })

  function parseTags(text: string): { content: string; priority: boolean }[] {
    const results: { content: string; priority: boolean }[] = []

    let match: RegExpExecArray | null
    const priorityRegex = new RegExp(REGEX_PRIORITY.source, "g")
    while ((match = priorityRegex.exec(text)) !== null) {
      const content = match[1].trim()
      if (content) {
        results.push({ content, priority: true })
      }
    }

    const normalRegex = new RegExp(REGEX_NORMAL.source, "g")
    while ((match = normalRegex.exec(text)) !== null) {
      const content = match[1].trim()
      if (content) {
        results.push({ content, priority: false })
      }
    }

    return results
  }

  function stripTags(text: string): string {
    return text
      .replace(/<remember\s+priority>[\s\S]*?<\/remember>/g, "")
      .replace(/<remember>[\s\S]*?<\/remember>/g, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim()
  }

  return {
    "tool.execute.after": async (input, output, ctx) => {
      if (typeof output.data !== "object" || output.data === null) return

      const textFields = extractTextFromOutput(output.data)
      let foundAny = false

      for (const field of textFields) {
        if (typeof field.value !== "string") continue
        const tags = parseTags(field.value)
        if (tags.length === 0) continue

        for (const tag of tags) {
          const entry = rememberStore.add({
            content: tag.content,
            priority: tag.priority,
            session_id: ctx?.sessionID,
            source_tool: input.tool,
          })

          await client.app.log({
            service: SERVICE_NAME,
            level: "info",
            message: `Captured ${tag.priority ? "priority" : ""} remember: "${tag.content.substring(0, 80)}..."`,
            extra: { entryId: entry.id, priority: tag.priority, tool: input.tool },
          })
        }

        field.value = stripTags(field.value)
        foundAny = true
      }
    },

    "experimental.session.compacting": async (_input, output) => {
      const entries = rememberStore.getAll()
      if (entries.length === 0) return

      const priority = entries.filter((e) => e.priority)
      const recent = entries
        .filter((e) => !e.priority)
        .slice(0, 10)

      const lines: string[] = []

      if (priority.length > 0) {
        lines.push("### Priority Remembers (permanent)")
        lines.push(...priority.map((e) => `- ${e.content}`))
      }

      if (recent.length > 0) {
        lines.push("### Recent Remembers (7-day TTL)")
        lines.push(
          ...recent.map((e) => {
            const daysLeft = Math.max(
              0,
              Math.round((e.expires - Date.now()) / (24 * 3600 * 1000))
            )
            return `- ${e.content} (${daysLeft}d left)`
          })
        )
      }

      if (lines.length > 0) {
        output.context.push(
          `## Remember Tags (auto-captured)\n\n${lines.join("\n")}`
        )
      }
    },
  }
}

function extractTextFromOutput(
  data: Record<string, unknown>,
  parentKey = ""
): { value: unknown; parentKey: string }[] {
  const results: { value: unknown; parentKey: string }[] = []

  for (const [key, value] of Object.entries(data)) {
    const fullKey = parentKey ? `${parentKey}.${key}` : key
    if (typeof value === "string" && (value.includes("<remember") || value.includes("</remember>"))) {
      results.push({ value, parentKey: fullKey })
    } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      results.push(...extractTextFromOutput(value as Record<string, unknown>, fullKey))
    }
  }

  return results
}

export default RememberTagsPlugin
