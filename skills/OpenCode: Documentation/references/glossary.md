# OpenCode Glossary

Complete glossary of OpenCode terminology, organized alphabetically.

---

## A

**AGENTS.md**
- **Definition**: Project-specific file containing custom instructions and rules for the AI
- **Location**: Project root directory
- **Purpose**: Similar to `CLAUDE.md` or Cursor's rules, provides context about project structure, coding standards, and workflows
- **Command**: `/init` generates this file automatically
- **Reference**: See `rules.md`

**ACP (Agent Client Protocol)**
- **Definition**: Protocol for agent communication via stdin/stdout using nd-JSON
- **Usage**: `opencode acp` command starts an ACP server
- **Reference**: See `acp.md`

**Agent**
- **Definition**: Specialized AI assistant with custom prompts, models, and tool access
- **Types**:
  - **Primary**: Main assistants you interact with directly (Build, Plan). Cycle with Tab key or `switch_agent` keybind
  - **Subagent**: Specialized helpers invoked by primary agents or via `@mention` (General, Explore)
- **Configuration**: Via `opencode.json` `agent` section or markdown files in `.opencode/agent/`
- **Reference**: See `agents.md`

**Anthropic**
- **Definition**: LLM provider offering Claude models
- **Models**: Claude Sonnet, Haiku, Opus
- **Setup**: Use `/connect` → select Anthropic → authenticate or enter API key
- **Reference**: See `providers.md`

**Auth**
- **Definition**: Authentication and credential management for providers
- **Storage**: `~/.local/share/opencode/auth.json`
- **Commands**:
  - `opencode auth login`: Configure API keys
  - `opencode auth list`: List authenticated providers
  - `opencode auth logout`: Remove credentials
- **Reference**: See `cli.md`

---

## B

**Bash**
- **Definition**: Built-in tool for executing shell commands in your project environment
- **Examples**: `npm install`, `git status`, any terminal command
- **Usage**: Automatic when LLM needs to run commands, or prefix message with `!`
- **Permission**: Can be set to `"allow"`, `"ask"`, or `"deny"` per command pattern
- **Reference**: See `tools.md`, `permissions.md`

**Build Agent**
- **Definition**: Default primary agent with all tools enabled
- **Mode**: `primary`
- **Purpose**: Standard development work with full file and system access
- **Keybind**: Tab to cycle to it
- **Reference**: See `agents.md`

---

## C

**CLI (Command Line Interface)**
- **Definition**: `opencode` command for terminal interaction
- **Default**: Starts TUI when run without arguments
- **Commands**: `run`, `agent`, `auth`, `github`, `mcp`, `models`, `serve`, `web`, `acp`, `session`, `stats`, `export`, `import`, `upgrade`, `uninstall`
- **Flags**: `--model`, `--agent`, `--continue`, `--session`, `--share`, etc.
- **Reference**: See `cli.md`

**Commands (Custom)**
- **Definition**: Reusable prompt templates triggered via `/command-name`
- **Configuration**: Via `opencode.json` `command` section or `.opencode/command/*.md` files
- **Placeholders**: `$ARGUMENTS`, `$1`, `$2`, `!`command``, `@file`
- **Examples**: Test runner, component generator, review command
- **Reference**: See `commands.md`

**Commands (Built-in TUI)**
- **Definition**: Native commands available in Terminal User Interface
- **List**:
  - `/connect`: Add provider credentials
  - `/compact`: Compact session (alias: `/summarize`)
  - `/details`: Toggle tool execution details
  - `/editor`: Open external editor for composing messages
  - `/exit`: Exit OpenCode (aliases: `/quit`, `/q`)
  - `/export`: Export conversation to Markdown
  - `/help`: Show help dialog
  - `/init`: Create/update `AGENTS.md` file
  - `/models`: List available models
  - `/new`: Start new session (alias: `/clear`)
  - `/redo`: Redo previously undone action
  - `/sessions`: List/switch sessions (aliases: `/resume`, `/continue`)
  - `/share`: Share current session
  - `/theme` or `/themes`: List available themes
  - `/undo`: Undo last message and file changes
  - `/unshare`: Unshare current session
- **Keybinds**: Most have `ctrl+x` (leader) shortcuts
- **Reference**: See `tui.md`, `keybinds.md`

**Compaction**
- **Definition**: Context reduction when conversation becomes too long
- **Configuration**: `compaction.auto` (default: `true`), `compaction.prune` (default: `true`)
- **Behavior**: Removes old tool outputs and summarizes context
- **Reference**: See `config.md`

**Connect**
- **Definition**: Command to add LLM provider API keys
- **Usage**: `/connect` in TUI
- **Process**: Select provider → enter/paste API key → credentials stored
- **Storage**: `~/.local/share/opencode/auth.json`
- **Reference**: See `providers.md`, `intro.md`

**Context7**
- **Definition**: MCP server for searching documentation
- **Configuration**:
  ```json
  "context7": {
    "type": "remote",
    "url": "https://mcp.context7.com/mcp"
  }
  ```
- **Usage**: Add `use context7` to prompts
- **Reference**: See `mcp-servers.md`

**Custom Tools**
- **Definition**: User-defined functions that LLM can call
- **Location**: Defined in `opencode.json` or via plugins
- **Configuration**: Tool name, Zod schema for args, execute function
- **Reference**: See `custom-tools.md`, `plugins.md`

---

## D

**Default Agent**
- **Definition**: Agent used when none is explicitly specified
- **Configuration**: `default_agent` in `opencode.json`
- **Requirement**: Must be a primary agent (not subagent)
- **Fallback**: `"build"` if specified agent doesn't exist or is subagent
- **Applies to**: TUI, CLI, desktop app, GitHub Action
- **Reference**: See `config.md`

**Disable (Agents/Tools)**
- **Definition**: Hide or prevent usage of agents or tools
- **Agents**: Set `disable: true` in agent config
- **Tools**: Set to `false` in `tools` config or use wildcard `mymcp_*: false`
- **Permissions**: Use `"deny"` to block, or set tool to `false`
- **Reference**: See `agents.md`, `tools.md`

**Diff Style**
- **Definition**: Control diff rendering in TUI
- **Options**: `"auto"` (adapts to terminal width), `"stacked"` (always single column)
- **Configuration**: `tui.diff_style` in `opencode.json`
- **Reference**: See `config.md`

**Directory (Config)**
- **Definition**: Custom directory for agents, commands, modes, and plugins
- **Variable**: `OPENCODE_CONFIG_DIR`
- **Priority**: Loaded after global config and `.opencode` directories
- **Structure**: Same as standard `.opencode` directory
- **Reference**: See `config.md`

**Doom Loop**
- **Definition**: Safety guard triggered when same tool call repeats 3 times with identical input
- **Permission**: `"ask"` by default
- **Purpose**: Prevent infinite loops
- **Reference**: See `permissions.md`

---

## E

**Edit**
- **Definition**: Built-in tool for modifying existing files using exact string replacements
- **Behavior**: Performs precise edits by replacing exact text matches
- **Permission**: Can be configured to `"ask"` or `"deny"` by pattern
- **Reference**: See `tools.md`, `permissions.md`

**Environment Variables**
- **Definition**: Configuration via environment variables
- **Common variables**:
  - `OPENCODE_CONFIG`: Path to config file
  - `OPENCODE_CONFIG_DIR`: Path to config directory
  - `OPENCODE_CONFIG_CONTENT`: Inline JSON config content
  - `OPENCODE_AUTO_SHARE`: Automatically share sessions
  - `OPENCODE_DISABLE_AUTOUPDATE`: Disable automatic updates
  - `OPENCODE_DISABLE_PRUNE`: Disable pruning of old data
  - `OPENCODE_DISABLE_LSP_DOWNLOAD`: Disable automatic LSP downloads
  - `OPENCODE_EXPERIMENTAL`: Enable all experimental features
  - Provider-specific: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.
- **Reference**: See `cli.md`, `config.md`

**Experimental Features**
- **Variables**: `OPENCODE_EXPERIMENTAL_*` family
- **Features**: Icon discovery, LSP tool, file watcher, output token limits, etc.
- **Warning**: Unstable, may change or be removed
- **Reference**: See `cli.md`, `config.md`

**Export**
- **Definition**: Export session data as JSON or conversation as Markdown
- **Commands**:
  - `/export`: Export conversation to Markdown (opens in editor)
  - `opencode export [sessionID]`: Export session as JSON
- **Reference**: See `tui.md`, `cli.md`

**External Directory**
- **Definition**: Safety guard triggered when a tool touches paths outside project working directory
- **Permission**: `"ask"` by default
- **Purpose**: Prevent accidental modifications outside project
- **Reference**: See `permissions.md`

---

## F

**File References (@)**
- **Definition**: Syntax to include file content in messages
- **Usage**: `@path/to/file.ts` in prompt
- **Behavior**: Fuzzy search finds file, content added to conversation
- **Example**: "How is auth handled in @packages/functions/src/api/index.ts?"
- **Reference**: See `tui.md`

**Formatters**
- **Definition**: Code formatting tools applied after file edits
- **Configuration**: `formatter` section in `opencode.json`
- **Built-in**: Prettier, ESLint, Black, etc.
- **Custom**: Define with `command` and `extensions`
- **Reference**: See `formatters.md`

---

## G

**General Agent**
- **Definition**: Built-in subagent for researching complex questions, searching code, executing multi-step tasks
- **Mode**: `subagent`
- **Usage**: Invoke via `@general` or automatically by primary agents
- **Purpose**: When unsure you'll find right match in first few tries
- **Reference**: See `agents.md`

**GitHub Integration**
- **Definition**: Automate tasks via GitHub Actions and comments
- **Triggers**: Issue comments, PR comments, schedule events, workflow_dispatch
- **Commands**: `/opencode` or `/oc` in comments
- **Features**: Triage issues, fix and implement, review PRs, secure execution
- **Setup**: `opencode github install` or manual workflow configuration
- **Workflow file**: `.github/workflows/opencode.yml`
- **Reference**: See `github.md`

**Glob**
- **Definition**: Built-in tool for finding files by pattern matching
- **Usage**: Patterns like `**/*.js` or `src/**/*.ts`
- **Behavior**: Returns matching file paths sorted by modification time
- **Internal**: Uses ripgrep with `.gitignore` respect
- **Ignore**: Use `.ignore` file to include files normally ignored
- **Reference**: See `tools.md`

**Google / Google Vertex AI**
- **Definition**: LLM provider offering Gemini models
- **Models**: Gemini 3 Pro, Gemini 3 Flash, GLM 4.x
- **Setup**: Requires `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`, or `gcloud auth`
- **Reference**: See `providers.md`

**Grep**
- **Definition**: Built-in tool for searching file contents using regular expressions
- **Usage**: Fast content search across codebase with full regex syntax
- **Behavior**: Supports file pattern filtering via `include` parameter
- **Internal**: Uses ripgrep under the hood, respects `.gitignore`
- **Ignore**: Use `.ignore` file to search in ignored directories
- **Reference**: See `tools.md`

**Groq / Grok Code**
- **Definition**: LLM provider offering Grok and Qwen models
- **Models**: Grok Code Fast 1, Qwen 3 Coder
- **Setup**: `opencode mcp add` for Groq, or `/connect` → select Groq
- **Reference**: See `providers.md`, `mcp-servers.md`

---

## H

**Help**
- **Definition**: Show available commands, keybinds, and documentation
- **Command**: `/help`
- **Keybind**: `ctrl+x h`
- **Reference**: See `tui.md`

---

## I

**IDE Integration**
- **Definition**: OpenCode support for code editors
- **Supported**: VS Code, Cursor, JetBrains, Neovim, etc.
- **Setup**: Via desktop app or browser-based web interface
- **Reference**: See `ide.md`

**Import**
- **Definition**: Import session data from JSON file or OpenCode share URL
- **Command**: `opencode import <file>` or `opencode import https://opncd.ai/s/abc123`
- **Reference**: See `cli.md`

**Instructions**
- **Definition**: Custom instruction files for the LLM
- **Configuration**: `instructions` array in `opencode.json`
- **Formats**: Paths and glob patterns to instruction files
- **Examples**: `["CONTRIBUTING.md", "docs/guidelines.md", ".cursor/rules/*.md"]`
- **Integration**: Combined with `AGENTS.md` files
- **Reference**: See `config.md`, `rules.md`

---

## K

**Keybinds**
- **Definition**: Customizable keyboard shortcuts for TUI
- **Configuration**: `keybinds` section in `opencode.json`
- **Leader key**: Default `ctrl+x`, most actions require leader + key
- **Disable**: Set to `"none"` to disable specific keybind
- **Categories**:
  - App control: `app_exit`, `editor_open`, `theme_list`
  - Session: `session_new`, `session_list`, `session_export`, `session_compact`
  - Messages: `messages_page_up`, `messages_undo`, `messages_redo`
  - Models: `model_list`, `model_cycle_recent`, `variant_cycle`
  - Input: `input_clear`, `input_paste`, `input_newline`, `input_move_left/right`
- **Reference**: See `keybinds.md`

---

## L

**Leader Key**
- **Definition**: Modifier key for TUI shortcuts to avoid terminal conflicts
- **Default**: `ctrl+x`
- **Usage**: Press leader key, then press action key (e.g., `ctrl+x n` for new session)
- **Configuration**: `keybinds.leader` in `opencode.json`
- **Reference**: See `keybinds.md`

**LSP (Language Server Protocol)**
- **Definition**: Integration with LSP servers for code intelligence
- **Tool**: `lsp` tool (experimental, requires `OPENCODE_EXPERIMENTAL_LSP_TOOL=true`)
- **Operations**: `goToDefinition`, `findReferences`, `hover`, `documentSymbol`, `callHierarchy`, etc.
- **Configuration**: `lsp` section in `opencode.json` or `.opencode/lsp.json`
- **Reference**: See `tools.md`, `lsp.md`

**LM Studio**
- **Definition**: Local model runner, can be used as OpenCode provider
- **Setup**: Configure as custom OpenAI-compatible provider
- **Example**:
  ```json
  "lmstudio": {
    "npm": "@ai-sdk/openai-compatible",
    "name": "LM Studio (local)",
    "options": {
      "baseURL": "http://127.0.0.1:1234/v1"
    }
  }
  ```
- **Reference**: See `providers.md`

**List**
- **Definition**: Built-in tool for listing files and directories
- **Usage**: Accepts glob patterns to filter results
- **Internal**: Uses ripgrep under the hood
- **Reference**: See `tools.md`

**Local Models**
- **Definition**: Models running locally instead of via API
- **Providers**: Ollama, LM Studio, llama.cpp, etc.
- **Configuration**: Custom provider setup with `baseURL` pointing to local server
- **Reference**: See `providers.md`

---

## M

**MCP (Model Context Protocol)**
- **Definition**: Protocol for integrating external tools and services
- **Types**:
  - **Local**: Run command to start server
  - **Remote**: Connect to HTTP endpoint
- **Configuration**: `mcp` section in `opencode.json`
- **OAuth**: Automatic OAuth flow for remote servers requiring authentication
- **Commands**: `opencode mcp add`, `opencode mcp list`, `opencode mcp auth`, `opencode mcp logout`
- **Examples**: Context7, Grep by Vercel, Sentry, GitHub
- **Warning**: MCP servers add to context, can exceed limit
- **Reference**: See `mcp-servers.md`

**Max Steps**
- **Definition**: Maximum number of agentic iterations before forced text-only response
- **Purpose**: Control costs by limiting tool calls
- **Configuration**: `maxSteps` in agent config
- **Behavior**: When reached, agent receives special system prompt to summarize work
- **Reference**: See `agents.md`

**Model**
- **Definition**: Specific LLM instance for generating responses
- **Format**: `provider/model-id` (e.g., `anthropic/claude-sonnet-4-5`)
- **Configuration**: `model` in `opencode.json`, or per-agent
- **Loading priority**: CLI flag → config → last used → internal priority
- **Variants**: Different configurations of same model (e.g., high/low reasoning)
- **Reference**: See `models.md`

**Model List**
- **Definition**: Command to display all available models from configured providers
- **Command**: `/models` in TUI, `opencode models [provider]` in CLI
- **Flags**: `--refresh`, `--verbose`
- **Purpose**: Find exact model name for configuration
- **Reference**: See `cli.md`, `models.md`

---

## N

**New Session**
- **Definition**: Start fresh conversation in current session
- **Command**: `/new` (alias: `/clear`)
- **Keybind**: `ctrl+x n`
- **Behavior**: Clears chat history but keeps config and tools
- **Reference**: See `tui.md`

---

## O

**Ollama**
- **Definition**: Local model runner, can be used as OpenCode provider
- **Setup**: Configure as custom OpenAI-compatible provider
- **Example**:
  ```json
  "ollama": {
    "npm": "@ai-sdk/openai-compatible",
    "name": "Ollama (local)",
    "options": {
      "baseURL": "http://localhost:11434/v1"
    }
  }
  ```
- **Tip**: Increase `num_ctx` if tool calls aren't working (start around 16k-32k)
- **Reference**: See `providers.md`

**OpenAI**
- **Definition**: LLM provider offering GPT models
- **Models**: GPT 5.2, GPT 5.1, GPT 5, GPT 5 Codex, etc.
- **Setup**: Use `/connect` → select OpenAI → enter API key
- **Reference**: See `providers.md`

**OpenCode Zen**
- **Definition**: Curated list of tested and verified models provided by OpenCode team
- **Purpose**: Benchmark models/providers for coding agents, ensure consistent quality
- **Models**: GPT 5.x, Claude Sonnet 4.x, Kimi K2, Qwen3 Coder, MiniMax M2.1, etc.
- **Benefits**:
  - Tested for coding agent use
  - Consistent performance
  - Price drops passed along at cost
  - No lock-in (works with any coding agent)
- **Setup**: Sign in at opencode.ai/auth, get API key, `/connect` → select opencode
- **Pricing**: Pay-as-you-go, per 1M tokens, auto-reload below $5
- **Free models**: Big Pickle, Grok Code Fast 1, GLM 4.7, MiniMax M2.1 (limited time)
- **Reference**: See `zen.md`

**Options (Agent)**
- **Definition**: Additional configuration passed directly to LLM provider
- **Examples**: `reasoningEffort`, `textVerbosity`, `thinking.budgetTokens`, etc.
- **Usage**: Provider-specific parameters for features like reasoning modes
- **Reference**: See `agents.md`, `models.md`

---

## P

**Patch**
- **Definition**: Built-in tool for applying patch files to codebase
- **Usage**: Apply diffs and patches from various sources
- **Reference**: See `tools.md`

**Permissions**
- **Definition**: Control over which agent actions require approval
- **Actions**:
  - `"allow"` - Run automatically without approval
  - `"ask"` - Prompt user for approval
  - `"deny"` - Block the action entirely
- **Types**: Tools, bash commands, files, skills, external directories, doom loops
- **Configuration**: `permission` section in `opencode.json` (globally or per-agent)
- **Granular**: Use object syntax for pattern-based rules (e.g., specific bash commands)
- **Defaults**: Most permissions default to `"allow"`, `doom_loop` and `external_directory` default to `"ask"`
- **Ask approval options**:
  - `once` - Approve just this request
  - `always` - Approve future requests matching patterns for current session
  - `reject` - Deny request
- **Reference**: See `permissions.md`

**Plan Agent**
- **Definition**: Restricted primary agent for planning and analysis without making changes
- **Mode**: `primary`
- **Default permissions**: `file edits`: `"ask"`, `bash`: `"ask"`
- **Purpose**: Analyze code, suggest changes, create plans
- **Keybind**: Tab to cycle to it
- **Reference**: See `agents.md`

**Plugins**
- **Definition**: Extend OpenCode by hooking into events and customizing behavior
- **Types**:
  - **Local**: Files in `.opencode/plugin/` or `~/.config/opencode/plugin/`
  - **NPM**: Packages in `plugin` array in `opencode.json`
- **Load order**: Global config → Project config → Global plugin directory → Project plugin directory
- **Events**: Command, File, Installation, LSP, Message, Permission, Server, Session, Todo, Tool, TUI
- **Dependencies**: Add `package.json` in config directory for external packages
- **Reference**: See `plugins.md`

**Provider**
- **Definition**: LLM service or API offering models
- **Examples**: Anthropic, OpenAI, Google, Groq, OpenCode Zen, etc.
- **Configuration**: `provider` section in `opencode.json`
- **Custom**: Add OpenAI-compatible providers
- **Credentials**: Stored in `~/.local/share/opencode/auth.json`
- **Setup**: `/connect` command or environment variables
- **Reference**: See `providers.md`

**Provider Options**
- **Definition**: Global provider configuration
- **Options**: `timeout`, `setCacheKey`, `baseURL`, `apiKey`, `headers`
- **Example**:
  ```json
  "provider": {
    "anthropic": {
      "options": {
        "timeout": 600000,
        "setCacheKey": true
      }
    }
  }
  ```
- **Reference**: See `config.md`, `providers.md`

---

## R

**Read**
- **Definition**: Built-in tool for reading file contents from codebase
- **Behavior**: Returns file contents, supports reading specific line ranges
- **Permission**: Default `"allow"` for all files except `.env` files (`"deny"`)
- **Reference**: See `tools.md`, `permissions.md`

**Redo**
- **Definition**: Restore previously undone message and file changes
- **Command**: `/redo`
- **Keybind**: `ctrl+x r`
- **Requirements**: Project must be a Git repository
- **Reference**: See `tui.md`

**Rules**
- **Definition**: Custom instructions for OpenCode via `AGENTS.md` file
- **Purpose**: Customize LLM behavior for specific project (similar to CLAUDE.md)
- **Types**:
  - **Project**: `AGENTS.md` in project root, applies when working in directory
  - **Global**: `~/.config/opencode/AGENTS.md`, applies across all sessions
- **Custom instructions**: `instructions` array in `opencode.json` can reference external files
- **Reference**: See `rules.md`

---

## S

**Scroll Acceleration**
- **Definition**: macOS-style smooth, natural scrolling in TUI
- **Configuration**: `tui.scroll_acceleration.enabled` in `opencode.json`
- **Behavior**: Increases speed with rapid gestures, precise with slow movements
- **Priority**: Takes precedence over `scroll_speed` when enabled
- **Reference**: See `config.md`

**Scroll Speed**
- **Definition**: Control how fast TUI scrolls when using scroll commands
- **Configuration**: `tui.scroll_speed` in `opencode.json` (default: `1` on Unix, `3` on Windows, minimum: `1`)
- **Ignored**: When `scroll_acceleration.enabled` is `true`
- **Reference**: See `config.md`

**SDK**
- **Definition**: OpenCode software development kit for plugin and integration development
- **Package**: `@opencode-ai/plugin`
- **Features**: `client` for AI interaction, typed interfaces, logging
- **Reference**: See `sdk.md`

**Sentry MCP**
- **Definition**: MCP server for interacting with Sentry projects and issues
- **Configuration**:
  ```json
  "sentry": {
    "type": "remote",
    "url": "https://mcp.sentry.dev/mcp",
    "oauth": {}
  }
  ```
- **Auth**: `opencode mcp auth sentry`
- **Usage**: Add `use sentry` to prompts to query issues, projects, error data
- **Reference**: See `mcp-servers.md`

**Server**
- **Definition**: Headless OpenCode server for API access
- **Commands**:
  - `opencode serve`: Start HTTP server without web interface
  - `opencode web`: Start HTTP server with web interface
- **Configuration**: `server` section in `opencode.json` (port, hostname, mdns, cors)
- **Reference**: See `server.md`, `config.md`

**Sessions**
- **Definition**: Conversation history and state
- **Management**:
  - `/sessions` or `/resume` or `/continue`: List and switch between sessions
  - `/new` or `/clear`: Start new session
  - `/compact`: Compress context
- **CLI**: `opencode session list`, `opencode session [command]`
- **Storage**: Stored locally in OpenCode data directory
- **Reference**: See `tui.md`, `cli.md`

**Share**
- **Definition**: Create public links to OpenCode conversations for collaboration
- **Modes**:
  - `"manual"` (default): Explicitly share with `/share` command
  - `"auto"`: Automatically share new conversations
  - `"disabled"`: Disable sharing entirely
- **Command**: `/share` to generate link (copied to clipboard)
- **Unshare**: `/unshare` to remove link and delete data
- **Privacy**: Conversations are public until unshared
- **Reference**: See `share.md`

**Skill**
- **Definition**: Reusable behavior definition via SKILL.md files
- **Format**: Markdown with YAML frontmatter (name, description, license, compatibility, metadata)
- **Locations**: `.opencode/skill/<name>/SKILL.md` or `~/.config/opencode/skill/<name>/SKILL.md`
- **Loading**: Discovered from current working directory up to git worktree, plus global
- **Usage**: Agents can load skills via `skill` tool
- **Permissions**: Control skill access with `permission.skill` using patterns
- **Reference**: See `skills.md`, `permissions.md`

**Skills Directory**
- **Definition**: Locations where OpenCode searches for skill definitions
- **Paths**:
  - Project: `.opencode/skill/`
  - Global: `~/.config/opencode/skill/`
  - Claude-compatible project: `.claude/skills/`
  - Claude-compatible global: `~/.claude/skills/`
- **Discovery**: Walks up from CWD to git worktree for project-local
- **Reference**: See `skills.md`

**Small Model**
- **Definition**: Separate model for lightweight tasks like title generation
- **Configuration**: `small_model` in `opencode.json`
- **Default**: Cheaper model from provider if available, otherwise falls back to main model
- **Reference**: See `config.md`

**Stats**
- **Definition**: Show token usage and cost statistics for sessions
- **Command**: `opencode stats`
- **Flags**: `--days`, `--tools`, `--models`, `--project`
- **Reference**: See `cli.md`

**Subagent**
- **Definition**: Specialized agent invoked by primary agents for specific tasks
- **Built-in**: General (research, multi-step), Explore (fast codebase exploration)
- **Invocation**:
  - **Automatic**: Primary agents invoke based on descriptions
  - **Manual**: `@agent-name` in messages
- **Navigation**: Cycle between parent and child sessions with `<leader>+right/left`
- **Tool access**: Can be restricted compared to primary agents
- **Reference**: See `agents.md`

**Switch Agent**
- **Definition**: Cycle between primary agents during a session
- **Methods**:
  - Tab key
  - `switch_agent` keybind (default: Tab)
  - `/agent` command or `agent_cycle` keybind
- **Reference**: See `agents.md`, `keybinds.md`

**System Theme**
- **Definition**: Theme that adapts to your terminal's color scheme
- **Features**:
  - Generates custom gray scale based on terminal background
  - Uses ANSI colors (0-15) for syntax highlighting
  - Preserves terminal defaults (none for text/background)
- **Purpose**: Match terminal's appearance without fixed colors
- **Reference**: See `themes.md`

---

## T

**Temperature**
- **Definition**: Control randomness and creativity of LLM responses
- **Configuration**: `temperature` in agent config
- **Values**:
  - `0.0-0.2`: Very focused and deterministic (code analysis, planning)
  - `0.3-0.5`: Balanced with some creativity (general development)
  - `0.6-1.0`: More creative and varied (brainstorming, exploration)
- **Defaults**: Model-specific (typically 0 for most, 0.55 for Qwen)
- **Reference**: See `agents.md`

**Themes**
- **Definition**: Visual appearance customization for TUI
- **Built-in**: system, tokyonight, everforest, ayu, catppuccin, gruvbox, kanagawa, nord, matrix, one-dark, etc.
- **Custom**: JSON files in `~/.config/opencode/themes/*.json` or `.opencode/themes/*.json`
- **Requirements**: Terminal must support truecolor (24-bit color) for full color palette
- **Format**: JSON with `defs` for reusable colors, dark/light variants, hex/ANSI color references
- **Configuration**: `theme` in `opencode.json`
- **Reference**: See `themes.md`

**Todo (TodoRead/TodoWrite)**
- **Definition**: Tools for managing todo lists during coding sessions
- **Usage**:
  - `todowrite`: Create and update task lists
  - `todoread`: Read current todo list state
- **Default**: Disabled for subagents, can be enabled manually
- **Purpose**: Track progress during complex multi-step tasks
- **Reference**: See `tools.md`

**TUI (Terminal User Interface)**
- **Definition**: Interactive terminal interface for working with LLM
- **Default**: Starts when running `opencode` without arguments
- **Features**:
  - File references with `@` symbol (fuzzy search)
  - Bash commands with `!` prefix
  - Slash commands for actions
  - Keybinds for navigation
  - Diff viewing
- **Configuration**: `tui` section in `opencode.json` (scroll_speed, scroll_acceleration, diff_style)
- **Reference**: See `tui.md`

---

## U

**Undo**
- **Definition**: Remove last message, subsequent responses, and any file changes
- **Command**: `/undo`
- **Keybind**: `ctrl+x u`
- **Behavior**: Uses Git to manage file changes, so project must be a Git repository
- **Redo**: Can be undone with `/redo`
- **Reference**: See `tui.md`

**Upgrade**
- **Definition**: Update OpenCode to latest or specific version
- **Command**: `opencode upgrade [target]`
- **Flags**: `--method` (installation method: curl, npm, pnpm, bun, brew)
- **Auto-update**: Enabled by default, disable with `autoupdate: false` or `OPENCODE_DISABLE_AUTOUPDATE=true`
- **Reference**: See `cli.md`, `config.md`

---

## V

**Variants (Model)**
- **Definition**: Different configurations of same model
- **Built-in**: Many providers have default variants (Anthropic: high/max, OpenAI: none/minimal/low/medium/high/xhigh)
- **Custom**: Define in agent or model config
- **Examples**: High reasoning effort, low reasoning effort, disabled variants
- **Cycle**: Use `variant_cycle` keybind (default: `ctrl+t`) to switch between variants
- **Reference**: See `models.md`

**Variables (Config)**
- **Definition**: Environment variable substitution in config files
- **Types**:
  - `{env:VARIABLE_NAME}`: Substitute environment variable
  - `{file:path/to/file}`: Substitute file contents
- **File paths**: Relative to config file, or absolute paths starting with `/` or `~`
- **Uses**: Keep sensitive data separate, include large instruction files, share config snippets
- **Reference**: See `config.md`

---

## W

**Watcher**
- **Definition**: File watcher for monitoring project changes
- **Configuration**: `watcher.ignore` in `opencode.json`
- **Purpose**: Exclude noisy directories from file watching
- **Experimental**: Enable with `OPENCODE_EXPERIMENTAL_FILEWATCHER=true`
- **Reference**: See `config.md`

**Webfetch**
- **Definition**: Built-in tool for fetching and reading web pages
- **Usage**: Look up documentation or research online resources
- **Permission**: Can be configured to `"ask"` or `"deny"` by URL pattern
- **Reference**: See `tools.md`, `permissions.md`

**Write**
- **Definition**: Built-in tool for creating new files or overwriting existing ones
- **Behavior**: Creates new files, overwrites if exists
- **Permission**: Can be configured to `"ask"` or `"deny"` by pattern
- **Reference**: See `tools.md`, `permissions.md`

---

## Z

**Zen (OpenCode Zen)**
- **Definition**: Curated list of tested and verified models provided by OpenCode team
- **Purpose**: Ensure consistent quality and performance for coding agents
- **Models**: GPT 5.x, Claude Sonnet/Opus/Haiku, Kimi K2, Qwen3 Coder, MiniMax M2.1, Gemini 3 Pro/Flash, GLM 4.x, Grok Code, Big Pickle
- **Benefits**:
  - Tested for coding agent use
  - No lock-in (works with any coding agent)
  - Price drops passed along at cost
- **Setup**: Sign in at opencode.ai/auth, get API key, `/connect` → select opencode
- **Pricing**: Pay-as-you-go, per 1M tokens, free models available
- **Features**:
  - Auto-reload below $5 balance
  - Monthly usage limits
  - Team workspaces with roles (Admin, Member)
  - Model access control
  - Bring your own keys option
- **Privacy**: US-hosted, zero-retention policy (with some exceptions for free models)
- **Reference**: See `zen.md`
