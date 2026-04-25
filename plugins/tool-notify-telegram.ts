/**
 * Notify Telegram Plugin
 * Sends notifications to Telegram and waits for response (blocking pattern)
 */

import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

export type NotificationLevel = "info" | "success" | "warning" | "error"

interface NotificationResponse {
  status: string
  message_id?: number
}

async function sendNotification(
  title: string,
  body: string,
  level: NotificationLevel
): Promise<string> {
  const serviceUrl = process.env.CHAT_SERVICE_URL || "http://57.129.81.64:8081"
  const token = process.env.CHAT_SERVICE_TOKEN || "sk_5bc4b36e99858f483a8aaf757574c72a94a95d9597a4d4e6b32c3204425a"
  const timeout = parseInt(process.env.CHAT_SERVICE_TIMEOUT || "3600") * 1000

  if (!token) {
    return "Error: CHAT_SERVICE_TOKEN not configured"
  }

  const url = `${serviceUrl}/api/notify`
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
  }

  const payload = { title, body, level }

  try {
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(timeout),
    })

    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error")
      return `Error: HTTP ${response.status}: ${errorText}`
    }

    const data: NotificationResponse = await response.json()
    const { status, message_id } = data

    return status === "sent" && message_id
      ? `📤 Уведомление отправлено (msg: ${message_id})`
      : `📤 Статус: ${status}`
  } catch (error) {
    return `Error: ${(error as Error).message || String(error)}`
  }
}

export const NotifyTelegramPlugin: Plugin = async () => {
  return {
    tool: {
      notify: tool({
        description: "Sends a notification to Telegram and waits for response.\n\nUse for:\n- Progress updates\n- Task completion notifications\n- Alerts and warnings\n\nReturns actual status and message_id from the service.",
        args: {
          title: tool.schema.string().describe("Заголовок уведомления"),
          body: tool.schema.string().describe("Основной текст уведомления"),
          level: tool.schema
            .enum(["info", "success", "warning", "error"])
            .optional()
            .default("info")
            .describe("Уровень: info, success, warning, error"),
        },
        async execute(args: {
          title: string
          body: string
          level?: NotificationLevel
        }) {
          const { title, body, level = "info" } = args
          return sendNotification(title, body, level)
        },
      }),
    },
  }
}

export default NotifyTelegramPlugin
