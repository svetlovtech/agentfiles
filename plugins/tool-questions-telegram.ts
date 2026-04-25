/**
 * OpenCode Questions Telegram Plugin
 *
 * This plugin provides a 'question' tool that sends questions to Telegram
 * and waits for user response (blocking).
 *
 * REFACTORED for YAGNI Principle Compliance
 */

import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               TYPES                                       ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

interface QuestionOption {
  label: string
  description: string
}

interface Question {
  question: string
  header: string
  options: QuestionOption[]
  multiple?: boolean
}

interface QuestionResponse {
  status: string
  answer?: string
  results?: Array<{
    question_index: number
    status: string
    answer?: string
  }>
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                         CORE FUNCTIONALITY                                ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

async function askQuestions(questions: Question[]): Promise<string[]> {
  const sessionId = `q-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`

  const questionsFormatted = questions.map((q) => ({
    header: q.header,
    question: q.question,
    options: q.options.map((opt) => ({
      label: opt.label,
      description: opt.description || "",
    })),
    multiple: q.multiple || false,
  }))

  const url = `${Configuration.CHAT_SERVICE_URL}/api/question`
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${Configuration.CHAT_SERVICE_TOKEN}`,
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ session_id: sessionId, questions: questionsFormatted }),
    signal: AbortSignal.timeout(Configuration.CHAT_SERVICE_TIMEOUT),
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error")
    throw new Error(`HTTP ${response.status}: ${errorText}`)
  }

  const result: QuestionResponse = await response.json()

  // Handle status errors
  if (result.status === "stopped") {
    throw new Error("User cancelled the operation via Telegram")
  }
  if (result.status === "timeout") {
    throw new Error("Question timed out waiting for Telegram response")
  }

  // Parse answer
  const parseAnswer = (answerStr: string, options: QuestionOption[]): string[] => {
    // Handle comma-separated numeric answers (multiple selection)
    if (answerStr.includes(",") && /^\d/.test(answerStr)) {
      const indices = answerStr.split(", ")
        .map((s) => parseInt(s.trim()) - 1)
        .filter((idx) => idx >= 0 && idx < options.length)
      return indices.map((idx) => options[idx]?.label || `Option ${idx + 1}`)
    }

    // Handle single numeric answer
    const numAnswer = parseInt(answerStr)
    if (!isNaN(numAnswer) && numAnswer >= 1 && numAnswer <= options.length) {
      return [options[numAnswer - 1]?.label || answerStr]
    }

    // Default: return raw answer
    return [answerStr]
  }

  // Single question response
  if (result.answer !== undefined && result.answer !== null) {
    return parseAnswer(String(result.answer), questions[0].options)
  }

  // Batch response
  if (result.results && result.results.length > 0) {
    const allLabels: string[] = []
    for (const r of result.results) {
      if (r.status !== "success" || !r.answer) continue
      const labels = parseAnswer(
        String(r.answer),
        questions[r.question_index].options
      )
      allLabels.push(...labels)
    }
    return allLabels
  }

  return []
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            CONFIGURATION                                  ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

class Configuration {
  static readonly CHAT_SERVICE_URL = process.env.CHAT_SERVICE_URL || "http://57.129.81.64:8081"
  static readonly CHAT_SERVICE_TOKEN = process.env.CHAT_SERVICE_TOKEN || "sk_5bc4b36e99858f483a8aaf757574c72a94a95d9597a4d4e6b32c3204425a"
  static readonly CHAT_SERVICE_TIMEOUT = parseInt(process.env.CHAT_SERVICE_TIMEOUT || "3600") * 1000

  static readonly QUESTION_DESCRIPTION = `Use this tool when you need to ask the user questions during execution. This allows you to:
1. Gather user preferences or requirements
2. Clarify ambiguous instructions
3. Get decisions on implementation choices as you work
4. Offer choices to the user about what direction to take.

Usage notes:
- When \`custom\` is enabled (default), a "Type your own answer" option is added automatically; don't include "Other" or catch-all options
- Answers are returned as arrays of labels; set \`multiple: true\` to allow selecting more than one
- If you recommend a specific option, make that the first option in the list and add "(Recommended)" at the end of the label
- Pass multiple questions in the array for batch mode`
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                  ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const QuestionsTelegramPlugin: Plugin = async () => {
  return {
    tool: {
      question: tool({
        description: Configuration.QUESTION_DESCRIPTION,
        args: {
          questions: tool.schema
            .array(
              tool.schema.object({
                question: tool.schema.string().describe("Complete question"),
                header: tool.schema.string().describe("Very short label (max 30 chars)"),
                options: tool.schema
                  .array(
                    tool.schema.object({
                      label: tool.schema.string().describe("Display text (1-5 words, concise)"),
                      description: tool.schema.string().describe("Explanation of choice"),
                    })
                  )
                  .describe("Available choices"),
                multiple: tool.schema.boolean().optional().describe("Allow selecting multiple choices"),
              })
            )
            .describe("Questions to ask (1 or more)"),
        },
        async execute(args: { questions: Question[] }) {
          if (!Configuration.CHAT_SERVICE_TOKEN) {
            return "Error: CHAT_SERVICE_TOKEN not configured"
          }

          try {
            const labels = await askQuestions(args.questions)
            return JSON.stringify(labels)
          } catch (error) {
            return `Error: ${error instanceof Error ? error.message : String(error)}`
          }
        },
      }),
    },
  }
}

export default QuestionsTelegramPlugin
