---
name: OpenCode: Documentation
description: Comprehensive glossary and terminology reference for OpenCode AI coding agent. Use when encountering unfamiliar OpenCode terms, concepts, or need clarification on configuration options, commands, agents, tools, providers, models, or integration patterns.
---

# OpenCode Glossary

**Purpose**: Reference for OpenCode terminology, concepts, and configuration options.

**Usage**: Load this skill when you encounter unfamiliar terms or need clarification on OpenCode concepts.

## Quick Reference

Core concepts are organized alphabetically. For detailed definitions, see `references/glossary.md`.

### Key Categories

**Agents & Tools**
- **Agent**: Specialized AI assistant with specific permissions and tools
- **Primary Agent**: Main assistants you interact with (Build, Plan)
- **Subagent**: Specialized helpers invoked by primary agents
- **Tool**: Function LLM can execute (bash, read, edit, write, etc.)

**Configuration**
- **opencode.json**: Main configuration file
- **AGENTS.md**: Project-specific rules and instructions
- **SKILL.md**: Reusable behavior definitions
- **Provider**: LLM service (Anthropic, OpenAI, Zen, etc.)
- **Model**: Specific LLM instance (claude-sonnet-4-5, gpt-5.1, etc.)

**Interface & Commands**
- **TUI**: Terminal User Interface
- **CLI**: Command Line Interface
- **Slash Command**: Commands starting with `/` (/init, /share, etc.)
- **Leader Key**: Default `ctrl+x` for keybind combinations

**Integration**
- **MCP Server**: Model Context Protocol for external tools
- **GitHub Integration**: Workflow automation via comments
- **Plugin**: Custom extensions and hooks
- **Permission**: Control over agent actions (allow/ask/deny)

## Common Patterns

**Model ID format**: `provider/model-id` (e.g., `anthropic/claude-sonnet-4-5`)

**Permission modes**:
- `"allow"` - Run automatically
- `"ask"` - Prompt for approval
- `"deny"` - Block action

**Agent modes**:
- `"primary"` - Directly accessible via Tab
- `"subagent"` - Invoked via @mention or automatically
- `"all"` - Available in both modes

## Configuration Locations

**Global**: `~/.config/opencode/`
**Project**: `.opencode/` in project root
**Priority**: Local overrides global, project overrides global

## File References

| File | Purpose |
|------|---------|
| `opencode.json` | Main configuration |
| `AGENTS.md` | Project rules and instructions |
| `.opencode/agent/*.md` | Custom agent definitions |
| `.opencode/command/*.md` | Custom commands |
| `.opencode/skill/*/SKILL.md` | Reusable skills |
| `.opencode/plugin/*` | Local plugins |

## Quick Start

1. **Connect provider**: `/connect` → select provider → paste API key
2. **Initialize project**: `/init` → generates `AGENTS.md`
3. **Select model**: `/models` → choose from list
4. **Customize**: Edit `opencode.json` for settings

---

## When to Use

- **When learning OpenCode**: Review core concepts first
- **When configuring**: Reference permission and agent options
- **When troubleshooting**: Check MCP, tools, and provider sections
- **When extending**: Review skills, commands, and plugins patterns

See `references/glossary.md` for complete terminology.
