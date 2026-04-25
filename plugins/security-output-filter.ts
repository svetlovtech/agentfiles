/**
 * OpenCode Security Plugin: Output Filter
 * 
 * Scans ALL tool outputs and redacts secrets before LLM sees them.
 * Works with: bash, read, edit, glob, grep, and any other tool that might expose secrets.
 * 
 * @author SvetlovTech (Svetlov Aleksei)
 * @telegram @SvetlovTech
 * @github https://github.com/svetlovtech
 * @email svetlovtech@outlook.com
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                          SECRET PATTERNS                                   ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

/**
 * Secret pattern definition
 */
interface SecretPattern {
  /** Human-readable pattern name */
  name: string
  /** Regex pattern to detect secret */
  pattern: RegExp
  /** Replacement text for detected secret */
  replacement: string
}

/**
 * Comprehensive list of secret patterns
 * Covers: Database URLs, API Keys, Private Keys, JWT Tokens, Generic Secrets
 */
const SECRET_PATTERNS: SecretPattern[] = [
  // ═══════════════════════════════════════════════════════════════════════
  // Database Connection Strings (4 patterns)
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: "PostgreSQL URL",
    pattern: /postgres(?:ql)?:\/\/[^:]+:([^@]+)@[^\s]+/gi,
    replacement: "postgres://***:***REDACTED***@***"
  },
  {
    name: "MySQL URL",
    pattern: /mysql:\/\/[^:]+:([^@]+)@[^\s]+/gi,
    replacement: "mysql://***:***REDACTED***@***"
  },
  {
    name: "MongoDB URL",
    pattern: /mongodb(?:\+srv)?:\/\/[^:]+:([^@]+)@[^\s]+/gi,
    replacement: "mongodb://***:***REDACTED***@***"
  },
  {
    name: "Redis URL",
    pattern: /redis:\/\/[^:]*:([^@]+)@[^\s]+/gi,
    replacement: "redis://***:***REDACTED***@***"
  },
  
  // ═══════════════════════════════════════════════════════════════════════
  // API Keys (9 patterns)
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: "OpenAI API Key",
    pattern: /sk-[a-zA-Z0-9]{48,}/g,
    replacement: "sk-***REDACTED***"
  },
  {
    name: "OpenAI Project Key",
    pattern: /sk-proj-[a-zA-Z0-9]{48,}/g,
    replacement: "sk-proj-***REDACTED***"
  },
  {
    name: "Anthropic API Key",
    pattern: /sk-ant-api03-[a-zA-Z0-9-]{80,}/g,
    replacement: "sk-ant-api03-***REDACTED***"
  },
  {
    name: "AWS Access Key",
    pattern: /AKIA[A-Z0-9]{16}/g,
    replacement: "AKIA***REDACTED***"
  },
  {
    name: "GitHub Token",
    pattern: /ghp_[a-zA-Z0-9]{36}/g,
    replacement: "ghp_***REDACTED***"
  },
  {
    name: "GitHub OAuth",
    pattern: /gho_[a-zA-Z0-9]{36}/g,
    replacement: "gho_***REDACTED***"
  },
  {
    name: "GitHub App Token",
    pattern: /ghu_[a-zA-Z0-9]{36}/g,
    replacement: "ghu_***REDACTED***"
  },
  {
    name: "Slack Token",
    pattern: /xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}/g,
    replacement: "xox***-***REDACTED***"
  },
  
  // ═══════════════════════════════════════════════════════════════════════
  // Private Keys (3 patterns) - Multiline support
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: "RSA Private Key",
    pattern: /-----BEGIN RSA PRIVATE KEY-----[\s\S]*?-----END RSA PRIVATE KEY-----/g,
    replacement: "-----BEGIN RSA PRIVATE KEY-----\n***REDACTED***\n-----END RSA PRIVATE KEY-----"
  },
  {
    name: "EC Private Key",
    pattern: /-----BEGIN EC PRIVATE KEY-----[\s\S]*?-----END EC PRIVATE KEY-----/g,
    replacement: "-----BEGIN EC PRIVATE KEY-----\n***REDACTED***\n-----END EC PRIVATE KEY-----"
  },
  {
    name: "OpenSSH Private Key",
    pattern: /-----BEGIN OPENSSH PRIVATE KEY-----[\s\S]*?-----END OPENSSH PRIVATE KEY-----/g,
    replacement: "-----BEGIN OPENSSH PRIVATE KEY-----\n***REDACTED***\n-----END OPENSSH PRIVATE KEY-----"
  },
  
  // ═══════════════════════════════════════════════════════════════════════
  // Authentication Tokens (1 pattern)
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: "JWT Token",
    pattern: /eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*/g,
    replacement: "eyJ***REDACTED***"
  },
  
  // ═══════════════════════════════════════════════════════════════════════
  // Generic Secrets (2 patterns) - Conservative settings
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: "Password in connection string",
    pattern: /(?:password|passwd|pwd)\s*[=:]\s*['"]?[^'"\s\n]{8,}['"]?/gi,
    replacement: "password=***REDACTED***"
  },
  {
    name: "Secret key assignment",
    pattern: /(?:secret_key|secretkey|api_key|apikey|access_token|private_key)\s*[=:]\s*['"]?[a-zA-Z0-9_\-]{32,}['"]?/gi,
    replacement: "***REDACTED***"
  },
]

const PLUGIN_NAME = "Security::OutputFilter"

// Tools that require secret filtering
const FILTERED_TOOLS = new Set([
  "bash",   // Command output
  "read",   // File contents
  "edit",   // Edit diff
  "glob",   // File paths
  "grep",   // Search results
])

// ═══════════════════════════════════════════════════════════════════════════

/**
 * Scan text and redact all secrets
 */
function redactSecrets(text: string): { redacted: string; hasSecrets: boolean } {
  let redacted = text
  let hasSecrets = false

  for (const { pattern, replacement } of SECRET_PATTERNS) {
    const matches = text.match(pattern)
    if (matches) {
      hasSecrets = true
      redacted = redacted.replace(pattern, replacement)
    }
  }

  return { redacted, hasSecrets }
}

// ═══════════════════════════════════════════════════════════════════════════

/**
 * Security Output Filter Plugin
 * 
 * This plugin intercepts tool outputs AFTER execution and redacts secrets.
 * It scans output from bash, read, edit, glob, and grep tools.
 * 
 * @example
 * // Before filtering:
 * "Database URL: postgres://admin:secret123@localhost/db"
 * 
 * // After filtering:
 * "Database URL: postgres://***:***REDACTED***@***"
 */
export const SecurityOutputFilterPlugin: Plugin = async ({ client }) => {
  await client.app.log({
    service: PLUGIN_NAME,
    level: "info",
    message: "Plugin initialized - scanning all tool outputs for secrets",
  })

  return {
    /**
     * Intercept tool execution AFTER it runs
     * Scans output and redacts secrets
     */
    "tool.execute.after": async (input, output) => {
      const toolName = input.tool
      const outputContent = output.output

      // Skip if tool not in filter list or output is invalid
      if (!FILTERED_TOOLS.has(toolName) || !outputContent || typeof outputContent !== "string") {
        return
      }

      const { redacted, hasSecrets } = redactSecrets(outputContent)

      // Replace output if secrets found
      if (hasSecrets) {
        await client.app.log({
          service: PLUGIN_NAME,
          level: "warn",
          message: `Secrets detected and redacted in ${toolName} output`,
        })
        output.output = redacted
      }
    },
  }
}

export default SecurityOutputFilterPlugin
