/**
 * OpenCode Damage Control Plugin
 *
 * Comprehensive security plugin that prevents dangerous operations:
 * - Blocks 237+ dangerous bash commands (rm -rf, git push --force, etc.)
 * - Protects files and directories at three security levels:
 *   * zeroAccessPaths: No access at all (secrets, credentials)
 *   * readOnlyPaths: Read-only (config files, lock files)
 *   * noDeletePaths: No deletion allowed (README, .git, etc.)
 *
 * Features:
 * - Loads patterns from patterns.yaml (editable by user)
 * - Uses glob patterns for path matching
 * - Uses regex for command matching
 * - Logs all blocked attempts
 * - Supports temporary disable via /dc-disable command (5 minutes)
 *
 * Original implementation: https://github.com/disler/claude-code-damage-control
 *
 * @author disler (IndyDevDan)
 * @github https://github.com/disler
 *
 * @author SvetlovTech (Svetlov Aleksei) - OpenCode port and enhancements
 * @telegram @SvetlovTech
 * @github https://github.com/svetlovtech
 * @email svetlovtech@outlook.com
 * @license MIT
 */

import type { Plugin } from "@opencode-ai/plugin"
import { parse as parseYaml } from "yaml"
import * as path from "path"
import * as fs from "fs"
import { fileURLToPath } from "url"

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               TYPES                                         ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

interface BashPattern {
  pattern: string
  reason: string
}

interface PathPatterns {
  zeroAccessPaths: string[]
  readOnlyPaths: string[]
  noDeletePaths: string[]
}

interface PatternsConfig {
  bashToolPatterns: BashPattern[]
  zeroAccessPaths: string[]
  readOnlyPaths: string[]
  noDeletePaths: string[]
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            ABSTRACTIONS                                     ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

/**
 * Abstract logger interface for dependency inversion (DIP)
 */
interface ILogger {
  log(service: string, level: string, message: string): Promise<void>
}

/**
 * Abstract config loader interface for dependency inversion (DIP)
 */
interface IConfigLoader {
  load(): PatternsConfig
}

/**
 * Abstract security checker interface for dependency inversion (DIP)
 */
interface ISecurityChecker {
  isPathProtected(filePath: string, patterns: PathPatterns, checkReadOnly: boolean): { isProtected: boolean; reason?: string }
  isCommandDangerous(command: string, patterns: BashPattern[]): { isDangerous: boolean; reason?: string }
  isDeleteProtected(command: string, noDeletePaths: string[]): { isProtected: boolean; path?: string }
  commandContainsProtectedPath(command: string, zeroAccessPaths: string[]): boolean
}

/**
 * Abstract plugin state manager interface for dependency inversion (DIP)
 */
interface IPluginStateManager {
  isDisabled(): boolean
  disable(): void
  getRemainingDisableTime(): number
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                               CONSTANTS                                     ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

const PLUGIN_NAME = "DamageControl"
const DISABLE_DURATION_MINUTES = 5
const DISABLE_DURATION_MS = DISABLE_DURATION_MINUTES * 60 * 1000

// Get current directory
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PATTERNS_FILE = path.join(__dirname, "patterns.yaml")

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                            IMPLEMENTATIONS                                  ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

/**
 * Client logger implementation
 * Adapts the client's logging interface to ILogger abstraction
 */
class ClientLogger implements ILogger {
  constructor(private client: any) {}

  async log(service: string, level: string, message: string): Promise<void> {
    await this.client.app.log({ service, level, message })
  }
}

/**
 * File-based config loader implementation
 * Handles reading and parsing YAML configuration
 */
class FileConfigLoader implements IConfigLoader {
  load(): PatternsConfig {
    try {
      const content = this.readConfigFile()
      const config = this.parseConfig(content)
      this.validateConfig(config)
      return config
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to load patterns.yaml:`, error)
      return this.getFallbackConfig()
    }
  }

  private readConfigFile(): string {
    return fs.readFileSync(PATTERNS_FILE, "utf-8")
  }

  private parseConfig(content: string): PatternsConfig {
    return parseYaml(content) as PatternsConfig
  }

  private validateConfig(config: PatternsConfig): void {
    if (!config.bashToolPatterns || !config.zeroAccessPaths ||
        !config.readOnlyPaths || !config.noDeletePaths) {
      throw new Error("Invalid patterns.yaml structure")
    }
  }

  private getFallbackConfig(): PatternsConfig {
    return {
      bashToolPatterns: [],
      zeroAccessPaths: [],
      readOnlyPaths: [],
      noDeletePaths: [],
    }
  }
}

/**
 * Pattern-based security checker implementation
 * Handles all security validation logic
 */
class PatternSecurityChecker implements ISecurityChecker {
  isPathProtected(filePath: string, patterns: PathPatterns, checkReadOnly: boolean): { isProtected: boolean; reason?: string } {
    if (this.matchesAnySecurityPattern(filePath, patterns.zeroAccessPaths)) {
      return {
        isProtected: true,
        reason: "Zero-access path (secrets/credentials)"
      }
    }

    if (checkReadOnly && this.matchesAnySecurityPattern(filePath, patterns.readOnlyPaths)) {
      return {
        isProtected: true,
        reason: "Read-only path (system files, lock files, etc.)"
      }
    }

    return { isProtected: false }
  }

  isCommandDangerous(command: string, patterns: BashPattern[]): { isDangerous: boolean; reason?: string } {
    for (const pattern of patterns) {
      try {
        const regex = new RegExp(pattern.pattern, "i")
        if (regex.test(command)) {
          return { isDangerous: true, reason: pattern.reason }
        }
      } catch {
        // Invalid regex, skip
      }
    }
    return { isDangerous: false }
  }

  isDeleteProtected(command: string, noDeletePaths: string[]): { isProtected: boolean; path?: string } {
    const rmMatch = command.match(/\brm\s+(?:-[rf]+\s+)*([^\s;|&]+)/g)
    if (!rmMatch) return { isProtected: false }

    for (const match of rmMatch) {
      const filePath = match.replace(/\brm\s+(?:-[rf]+\s+)*/, "").trim()
      if (this.matchesAnySecurityPattern(filePath, noDeletePaths)) {
        return { isProtected: true, path: filePath }
      }
    }

    return { isProtected: false }
  }

  commandContainsProtectedPath(command: string, zeroAccessPaths: string[]): boolean {
    return this.matchesAnySecurityPattern(command, zeroAccessPaths)
  }

  private matchesAnySecurityPattern(filePath: string, patterns: string[]): boolean {
    const normalizedPath = path.normalize(this.expandHome(filePath))
    const fileName = path.basename(normalizedPath)

    for (const pattern of patterns) {
      if (this.matchesGlobPattern(filePath, pattern)) return true

      if (pattern.includes("*") && !pattern.includes("/") && this.matchesGlobPattern(fileName, pattern)) {
        return true
      }
    }

    return false
  }

  private matchesGlobPattern(filePath: string, pattern: string): boolean {
    const normalizedPath = path.normalize(this.expandHome(filePath))
    const normalizedPattern = path.normalize(this.expandHome(pattern))

    if (normalizedPath === normalizedPattern) return true

    if (normalizedPattern.endsWith("/") && normalizedPath.startsWith(normalizedPattern)) {
      return true
    }

    if (normalizedPattern.includes("*")) {
      try {
        const regexPattern = normalizedPattern
          .replace(/[.+^${}()|[\]\\]/g, "\\$&")
          .replace(/\*/g, ".*")
        return new RegExp(`^${regexPattern}$`).test(normalizedPath)
      } catch {
        // Invalid pattern, treat as no match
      }
    }

    return false
  }

  private expandHome(filePath: string): string {
    if (filePath.startsWith("~/")) {
      return path.join(process.env.HOME || "", filePath.slice(2))
    }
    return filePath
  }
}

/**
 * In-memory plugin state manager implementation
 * Handles plugin disable/enable state
 */
class PluginStateManager implements IPluginStateManager {
  private disabledUntil: number | null = null

  isDisabled(): boolean {
    if (this.disabledUntil === null) return false

    const now = Date.now()
    if (now >= this.disabledUntil) {
      this.disabledUntil = null
      return false
    }

    return true
  }

  disable(): void {
    this.disabledUntil = Date.now() + DISABLE_DURATION_MS
  }

  getRemainingDisableTime(): number {
    if (this.disabledUntil === null) return 0
    const remaining = Math.ceil((this.disabledUntil - Date.now()) / 1000)
    return Math.max(0, remaining)
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                          TOOL VALIDATORS (OCP)                               ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

/**
 * Abstract tool validator interface for strategy pattern (OCP)
 */
interface IToolValidator {
  canValidate(toolName: string): boolean
  validate(toolName: string, args: unknown, context: ValidationContext): Promise<void>
}

/**
 * Validation context passed to validators
 */
interface ValidationContext {
  logger: ILogger
  securityChecker: ISecurityChecker
  stateManager: IPluginStateManager
  patterns: PatternsConfig
}

/**
 * Bash tool validator implementation
 * Handles bash command validation
 */
class BashToolValidator implements IToolValidator {
  canValidate(toolName: string): boolean {
    return toolName === "bash"
  }

  async validate(toolName: string, args: unknown, context: ValidationContext): Promise<void> {
    const command = (args as Record<string, unknown>)?.command as string
    if (!command) return

    // Handle /dc-disable command
    if (command.trim() === "/dc-disable") {
      await this.handleDisableCommand(context)
    }

    // Check dangerous patterns
    const dangerousResult = context.securityChecker.isCommandDangerous(
      command,
      context.patterns.bashToolPatterns
    )

    if (dangerousResult.isDangerous) {
      await this.throwBlockedCommand(context, "Bash command", dangerousResult.reason!, command)
    }

    // Check delete operations
    const deleteResult = context.securityChecker.isDeleteProtected(
      command,
      context.patterns.noDeletePaths
    )

    if (deleteResult.isProtected) {
      await this.throwBlockedDelete(context, deleteResult.path!)
    }

    // Check zero-access paths
    if (context.securityChecker.commandContainsProtectedPath(command, context.patterns.zeroAccessPaths)) {
      await this.throwBlockedAccess(context, command)
    }
  }

  private async handleDisableCommand(context: ValidationContext): Promise<void> {
    context.stateManager.disable()
    await context.logger.log(
      PLUGIN_NAME,
      "warn",
      `Plugin DISABLED for ${DISABLE_DURATION_MINUTES} minutes`
    )
    throw new Error(`🛡️ [${PLUGIN_NAME}] Plugin disabled for ${DISABLE_DURATION_MINUTES} minutes`)
  }

  private async throwBlockedCommand(context: ValidationContext, operation: string, reason: string, command: string): Promise<never> {
    await context.logger.log(PLUGIN_NAME, "warn", `Blocked dangerous command: ${reason}`)
    throw new Error(this.formatBlockMessage(operation, reason, `Command: ${command}`))
  }

  private async throwBlockedDelete(context: ValidationContext, filePath: string): Promise<never> {
    await context.logger.log(PLUGIN_NAME, "warn", `Blocked delete operation on protected path: ${filePath}`)
    throw new Error(this.formatBlockMessage(
      "Delete operation",
      "Attempting to delete protected file/directory",
      `Path: ${filePath}`
    ))
  }

  private async throwBlockedAccess(context: ValidationContext, command: string): Promise<never> {
    await context.logger.log(PLUGIN_NAME, "warn", `Blocked access to zero-access path in command`)
    throw new Error(this.formatBlockMessage(
      "Bash command",
      "Attempting to access zero-access path (secrets/credentials)",
      `Command: ${command}`
    ))
  }

  private formatBlockMessage(operation: string, reason: string, details: string): string {
    return `🚫 [${PLUGIN_NAME}] BLOCKED: ${operation}\n   Reason: ${reason}\n   ${details}\n`
  }
}

/**
 * File tool validator implementation
 * Handles file operation validation (edit/write/read)
 */
class FileToolValidator implements IToolValidator {
  canValidate(toolName: string): boolean {
    return ["edit", "write", "read"].includes(toolName)
  }

  async validate(toolName: string, args: unknown, context: ValidationContext): Promise<void> {
    const filePath = this.getFilePathFromArgs(toolName, args)
    if (!filePath) return

    const checkReadOnly = toolName === "edit" || toolName === "write"
    const pathPatterns: PathPatterns = {
      zeroAccessPaths: context.patterns.zeroAccessPaths,
      readOnlyPaths: context.patterns.readOnlyPaths,
      noDeletePaths: context.patterns.noDeletePaths
    }

    const result = context.securityChecker.isPathProtected(filePath, pathPatterns, checkReadOnly)

    if (result.isProtected) {
      await this.throwBlockedFile(context, toolName, filePath, result.reason!)
    }
  }

  private getFilePathFromArgs(tool: string, args: unknown): string | null {
    if (!args || typeof args !== "object") return null

    const argsObj = args as Record<string, unknown>

    if (argsObj.filePath) return String(argsObj.filePath)
    if (argsObj.path) return String(argsObj.path)
    if (argsObj.file) return String(argsObj.file)

    return null
  }

  private async throwBlockedFile(context: ValidationContext, operation: string, filePath: string, reason: string): Promise<never> {
    await context.logger.log(PLUGIN_NAME, "warn", `Blocked ${operation} on protected path: ${filePath}`)
    throw new Error(this.formatBlockMessage(
      `${operation} operation`,
      reason,
      `Path: ${filePath}`
    ))
  }

  private formatBlockMessage(operation: string, reason: string, details: string): string {
    return `🚫 [${PLUGIN_NAME}] BLOCKED: ${operation}\n   Reason: ${reason}\n   ${details}\n`
  }
}

/**
 * Tool validator registry (OCP - Open for extension, closed for modification)
 * Allows adding new validators without modifying core logic
 */
class ToolValidatorRegistry {
  private validators: IToolValidator[] = []

  register(validator: IToolValidator): void {
    this.validators.push(validator)
  }

  getValidator(toolName: string): IToolValidator | null {
    return this.validators.find(v => v.canValidate(toolName)) || null
  }
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║                              PLUGIN                                         ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

/**
 * Damage Control Plugin
 *
 * Protects against dangerous operations by intercepting tool calls
 * and blocking operations that match security patterns.
 *
 * SOLID Principles Applied:
 * - SRP: Separate classes for logging, config loading, security checking, state management
 * - OCP: Tool validator registry allows adding new validators without modification
 * - LSP: All validators implement the same interface
 * - ISP: Separate, focused interfaces for each responsibility
 * - DIP: Dependencies injected through constructor parameters
 */
export const DamageControlPlugin: Plugin = async ({ client }) => {
  // Dependency injection container (DIP)
  const logger: ILogger = new ClientLogger(client)
  const configLoader: IConfigLoader = new FileConfigLoader()
  const securityChecker: ISecurityChecker = new PatternSecurityChecker()
  const stateManager: IPluginStateManager = new PluginStateManager()

  // Load patterns
  const patterns: PatternsConfig = configLoader.load()

  const patternCount = patterns.bashToolPatterns.length
  const zeroAccessCount = patterns.zeroAccessPaths.length
  const readOnlyCount = patterns.readOnlyPaths.length
  const noDeleteCount = patterns.noDeletePaths.length

  await logger.log(
    PLUGIN_NAME,
    "info",
    `Plugin initialized - ${patternCount} command patterns, ${zeroAccessCount} zero-access, ${readOnlyCount} read-only, ${noDeleteCount} no-delete paths`
  )

  // Register validators (OCP - Open for extension)
  const validatorRegistry = new ToolValidatorRegistry()
  validatorRegistry.register(new BashToolValidator())
  validatorRegistry.register(new FileToolValidator())

  return {
    /**
     * Intercept tool execution BEFORE it runs
     * Delegates to appropriate validator based on tool type
     */
    "tool.execute.before": async (input, output) => {
      // Check if disabled
      if (stateManager.isDisabled()) {
        const remaining = stateManager.getRemainingDisableTime()
        await logger.log(
          PLUGIN_NAME,
          "info",
          `Plugin temporarily disabled (${remaining}s remaining)`
        )
        return
      }

      const toolName = input.tool
      const args = output.args

      // Find and execute appropriate validator
      const validator = validatorRegistry.getValidator(toolName)
      if (validator) {
        const context: ValidationContext = {
          logger,
          securityChecker,
          stateManager,
          patterns
        }
        await validator.validate(toolName, args, context)
      }
    },
  }
}

export default DamageControlPlugin
