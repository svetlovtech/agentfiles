/**
 * OpenCode Tool Confirm Plugin
 *
 * This plugin provides a 'confirm' tool that sends confirmation requests to Telegram
 * and waits for user response (blocking).
 *
 * @author SvetlovTech (Svetlov Aleksei)
 * @telegram @SvetlovTech
 * @github https://github.com/svetlovtech
 * @email svetlovtech@outlook.com
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               CONSTANTS                                    ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

const CHAT_SERVICE_URL = process.env.CHAT_SERVICE_URL || "http://57.129.81.64:8081"
const CHAT_SERVICE_TOKEN = process.env.CHAT_SERVICE_TOKEN || "sk_5bc4b36e99858f483a8aaf757574c72a94a95d9597a4d4e6b32c3204425a"
const DEFAULT_CONFIRM_TIMEOUT = parseInt(process.env.CONFIRM_TIMEOUT || "300") * 1000

const ERROR_TOKEN_NOT_CONFIGURED = "Error: CHAT_SERVICE_TOKEN not configured"

const CONFIRM_DESCRIPTION = `Request user confirmation for an operation via Telegram.

This is a BLOCKING operation that waits for user response.

Use for:
- Confirming destructive operations (deletions, overwrites)
- Approving critical changes
- Getting explicit user consent before proceeding
- Validating high-impact actions

The tool will:
1. Send a confirmation request to Telegram
2. Display an inline callout in the TUI
3. Wait for user to respond Yes/No
4. Return success or throw an error if cancelled

Returns: Success message if confirmed, throws error if cancelled or timed out.`

const MSG_CONFIRMED = "✅ Confirmed"
const MSG_CANCELLED = "❌ Operation cancelled by user"
const MSG_TIMEOUT = "⏱️ Confirmation timed out"
const MSG_STOPPED = "🛑 Operation stopped"

// ═══════════════════════════════════════════════════════════════════════════

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                          IMPLEMENTATIONS                                  ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

/**
 * HTTP Client for chat service communication
 */
class ChatHttpClient {
  constructor(
    private readonly baseUrl: string,
    private readonly authToken: string,
    private readonly defaultTimeout: number
  ) {}

  async post<T = Record<string, unknown>>(
    path: string,
    body?: Record<string, unknown>,
    timeout?: number
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${this.authToken}`,
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(timeout || this.defaultTimeout),
    })

    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error")
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    return response.json()
  }
}

/**
 * Confirmation Service - handles Telegram confirmation requests
 */
class TelegramConfirmationService {
  constructor(
    private readonly httpClient: ChatHttpClient
  ) {}

  async requestConfirmation(params: {
    message: string
    details?: string
    timeout: number
  }): Promise<{ confirmed: boolean; response_time?: number }> {
    const response = await this.httpClient.post<{
      status: string
      confirmed?: boolean
      response_time?: number
    }>(
      "/api/confirm",
      {
        session_id: `c-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`,
        message: params.message,
        details: params.details,
        timeout: Math.floor(params.timeout / 1000),
      },
      params.timeout
    )

    // Handle response status
    switch (response.status) {
      case "stopped":
        throw new Error(MSG_STOPPED)
      case "timeout":
        throw new Error(MSG_TIMEOUT)
      case "cancelled":
      case "confirmed":
        if (response.confirmed === false) {
          throw new Error(MSG_CANCELLED)
        }
        break
    }

    return {
      confirmed: response.confirmed === true,
      response_time: response.response_time,
    }
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            PLUGIN EXPORT                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

export const ToolConfirmPlugin: Plugin = async () => {
  const httpClient = new ChatHttpClient(
    CHAT_SERVICE_URL,
    CHAT_SERVICE_TOKEN,
    DEFAULT_CONFIRM_TIMEOUT
  )
  const confirmationService = new TelegramConfirmationService(httpClient)

  return {
    tool: {
      confirm: tool({
        description: CONFIRM_DESCRIPTION,
        args: {
          message: tool
            .schema
            .string()
            .describe("Confirmation message to display to user (clear and concise)"),
          details: tool
            .schema
            .string()
            .optional()
            .describe("Additional context or details about the operation"),
          timeout: tool
            .schema
            .number()
            .optional()
            .default(300)
            .describe("Timeout in seconds (default: 300 = 5 minutes)"),
        },
        async execute(args: {
          message: string
          details?: string
          timeout?: number
        }) {
          if (!CHAT_SERVICE_TOKEN) return ERROR_TOKEN_NOT_CONFIGURED

          const { message, details, timeout = 300 } = args

          const response = await confirmationService.requestConfirmation({
            message,
            details,
            timeout: timeout * 1000,
          })

          const timeInfo = response.response_time ? ` (responded in ${response.response_time}s)` : ""
          return `${MSG_CONFIRMED}: ${message}${timeInfo}`
        },
      }),
    },
  }
}

export default ToolConfirmPlugin
