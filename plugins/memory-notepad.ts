/**
 * OpenCode Notepad Plugin
 *
 * Survives compaction — a markdown notepad for working context that
 * persists across session compaction events.
 *
 * Storage: .opencode/notepad.md
 *
 * Sections:
 *   ## Priority — important context, decisions, goals
 *   ## Working  — current task state, active files, in-progress work
 *   ## Manual   — user-authored notes (never auto-modified)
 *
 * Tools: notepad_read, notepad_write, notepad_append
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

type NotepadSection = "priority" | "working" | "manual"

interface NotepadContent {
  priority: string
  working: string
  manual: string
}

const SECTION_HEADERS: Record<NotepadSection, string> = {
  priority: "## Priority",
  working: "## Working",
  manual: "## Manual",
}

const SECTION_ORDER: NotepadSection[] = ["priority", "working", "manual"]

const SERVICE_NAME = "notepad"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                         NOTEPAD STORE CLASS                               ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

class NotepadStore {
  private filePath: string
  private content: NotepadContent
  private dirty = false

  constructor(private readonly projectDir: string) {
    const openCodeDir = join(projectDir, ".opencode")
    if (!existsSync(openCodeDir)) {
      mkdirSync(openCodeDir, { recursive: true })
    }
    this.filePath = join(openCodeDir, "notepad.md")
    this.content = this.load()
  }

  private load(): NotepadContent {
    if (existsSync(this.filePath)) {
      try {
        const raw = readFileSync(this.filePath, "utf-8")
        return this.parse(raw)
      } catch {
        // corrupted
      }
    }
    return { priority: "", working: "", manual: "" }
  }

  private parse(raw: string): NotepadContent {
    const content: NotepadContent = { priority: "", working: "", manual: "" }
    const lines = raw.split("\n")
    let currentSection: NotepadSection | null = null
    const sectionBuffers: Record<NotepadSection, string[]> = {
      priority: [],
      working: [],
      manual: [],
    }

    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed === SECTION_HEADERS.priority) {
        currentSection = "priority"
        continue
      }
      if (trimmed === SECTION_HEADERS.working) {
        currentSection = "working"
        continue
      }
      if (trimmed === SECTION_HEADERS.manual) {
        currentSection = "manual"
        continue
      }
      if (currentSection) {
        sectionBuffers[currentSection].push(line)
      }
    }

    for (const section of SECTION_ORDER) {
      const buf = sectionBuffers[section]
      content[section] = buf
        .join("\n")
        .replace(/^\n+/, "")
        .replace(/\n+$/, "")
    }

    return content
  }

  persist(): void {
    if (!this.dirty) return
    const lines: string[] = ["# Notepad", `> Auto-managed. Sections survive compaction.`, ""]

    for (const section of SECTION_ORDER) {
      const text = this.content[section].trim()
      lines.push(SECTION_HEADERS[section])
      lines.push("")
      if (text) {
        lines.push(text)
      } else {
        lines.push("*No entries.*")
      }
      lines.push("")
    }

    writeFileSync(this.filePath, lines.join("\n"), "utf-8")
    this.dirty = false
  }

  read(section?: NotepadSection): string {
    if (section) {
      return this.content[section] || ""
    }

    const sections = SECTION_ORDER
      .filter((s) => this.content[s].trim())
      .map((s) => {
        return `${SECTION_HEADERS[s]}\n\n${this.content[s]}`
      })

    if (sections.length === 0) {
      return "Notepad is empty."
    }

    return sections.join("\n\n---\n\n")
  }

  write(section: NotepadSection, text: string): void {
    this.content[section] = text.replace(/\n+$/, "")
    this.dirty = true
    this.persist()
  }

  append(section: NotepadSection, text: string): void {
    const existing = this.content[section].trim()
    const separator = existing ? "\n\n" : ""
    this.content[section] = `${existing}${separator}${text.replace(/\n+$/, "")}`
    this.dirty = true
    this.persist()
  }

  clear(section?: NotepadSection): void {
    if (section) {
      this.content[section] = ""
    } else {
      this.content = { priority: "", working: "", manual: "" }
    }
    this.dirty = true
    this.persist()
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const NotepadPlugin: Plugin = async ({ client, directory }) => {
  const store = new NotepadStore(directory)

  await client.app.log({
    service: SERVICE_NAME,
    level: "info",
    message: "Initialized",
  })

  return {
    event: async ({ event }) => {
      if (event.type === "session.compacted") {
        await client.app.log({
          service: SERVICE_NAME,
          level: "debug",
          message: `Session ${event.properties.sessionID} compacted. Notepad preserved.`,
        })
      }
    },

    "experimental.session.compacting": async (_input, output) => {
      const content = store.read()
      if (content === "Notepad is empty.") return

      const priority = store.read("priority")
      const working = store.read("working")

      const sections: string[] = []

      if (priority.trim()) {
        sections.push(`### Priority Notes\n${priority}`)
      }
      if (working.trim()) {
        sections.push(`### Working Context\n${working}`)
      }

      if (sections.length > 0) {
        output.context.push(
          `## Notepad (survived compaction)\n\n${sections.join("\n\n")}`
        )
      }
    },

    tool: {
      notepad_read: tool({
        description: `Read the notepad — working context that survives compaction.

Sections:
- priority: important decisions, goals, critical context
- working: current task state, active files, in-progress work
- manual: user-authored notes (never auto-modified by plugins)

Call without args to read all non-empty sections.`,
        args: {
          section: tool.schema
            .enum(["priority", "working", "manual"] as const)
            .optional()
            .describe("Read a specific section only"),
        },
        async execute(args) {
          const section = args.section as NotepadSection | undefined
          return store.read(section)
        },
      }),

      notepad_write: tool({
        description: `Write (replace) content in a notepad section.

Replaces the entire section content. Use notepad_append for additive writes.

Sections:
- priority: important decisions, goals, critical context
- working: current task state, active files, in-progress work  
- manual: user-authored notes (preserved across auto-operations)`,
        args: {
          section: tool.schema
            .enum(["priority", "working", "manual"] as const)
            .describe("Target section"),
          content: tool.schema
            .string()
            .describe("Content to write (replaces existing)"),
        },
        async execute(args) {
          store.write(args.section, args.content)
          return `Written to [${args.section}] section.`
        },
      }),

      notepad_append: tool({
        description: `Append content to a notepad section.

Adds to existing content with a blank line separator.

Sections:
- priority: important decisions, goals, critical context
- working: current task state, active files, in-progress work
- manual: user-authored notes (preserved across auto-operations)`,
        args: {
          section: tool.schema
            .enum(["priority", "working", "manual"] as const)
            .describe("Target section"),
          content: tool.schema
            .string()
            .describe("Content to append"),
        },
        async execute(args) {
          store.append(args.section, args.content)
          return `Appended to [${args.section}] section.`
        },
      }),
    },
  }
}

export default NotepadPlugin
