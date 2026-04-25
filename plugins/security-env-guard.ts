/**
 * OpenCode Security Plugin: Environment Guard
 *
 * Protects .env files from being read by AI agents.
 * Returns only variable names, not values.
 *
 * YAGNI-COMPLIANT VERSION
 *
 * @author SvetlovTech (Svetlov Aleksei)
 * @telegram @SvetlovTech
 * @github https://github.com/svetlovtech
 * @email svetlovtech@outlook.com
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync } from "fs"

export function SecurityEnvGuardPlugin(): Plugin {
  return async () => {
    return {
      "tool.execute.before": async (input, output) => {
        if (input.tool !== "read") return
        if (!output.args?.filePath) return

        const filePath = output.args.filePath
        const fileName = filePath.split('/').pop() || filePath

        const isEnvFile = [
          /^\.env$/,
          /^\.env\.(local|development|production|test|staging)$/,
          /^\.env\..+\.local$/,
        ].some(pattern => pattern.test(fileName))

        if (!isEnvFile) return

        const content = readFileSync(filePath, "utf-8")
        const keys: string[] = []
        const lines = content.split('\n')

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || trimmed.startsWith('#')) continue

          const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)/)
          if (match && match[1]) {
            keys.push(match[1])
          }
        }

        const keysList = keys.length > 0
          ? keys.map(k => `  - ${k}`).join('\n')
          : '  (no variables found)'

        const message = `⚠️  Protected file detected: ${filePath}

📋 Available environment variables:
${keysList}

Values are hidden for security reasons.`

        throw new Error(message)
      },
    }
  }
}

export default SecurityEnvGuardPlugin
