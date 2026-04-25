#!/bin/bash

# OpenCode Plugin Scaffolder (Bash version)

set -e

echo -e "\033[1m🚀 OpenCode Plugin Scaffolder\033[0m\n"

# Prompt for plugin details
read -p "Plugin name (e.g., my-awesome-plugin): " PLUGIN_NAME
read -p "Plugin description: " DESCRIPTION
read -p "Author name: " AUTHOR
read -p "Use TypeScript? (y/n): " USE_TYPESCRIPT

# Normalize plugin name
PLUGIN_SLUG=$(echo "$PLUGIN_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
PASCAL_NAME=$(echo "$PLUGIN_NAME" | sed -r 's/(^|[-\s])(\w)/\U\2/g')

echo -e "\033[1m📦 Creating plugin...\033[0m\n"

# Create directories
mkdir -p "$PLUGIN_SLUG"
mkdir -p ".opencode/plugin/$PLUGIN_SLUG"

# Determine file extension
EXT="${USE_TYPESCRIPT^^" == "Y" ? "ts" : "js"}"

# Create package.json
cat > "$PLUGIN_SLUG/package.json" <<EOF
{
  "name": "$PLUGIN_SLUG",
  "version": "0.1.0",
  "description": "$DESCRIPTION",
  "type": "module",
  "main": "./plugin.$EXT",
  "exports": "./plugin.$EXT",
  "keywords": ["opencode", "plugin"],
  "author": "$AUTHOR",
  "license": "MIT",
  "peerDependencies": {
    "@opencode-ai/plugin": "*"
  },
  "dependencies": {
    "@opencode-ai/plugin": "latest"
  }
}
EOF

# Create plugin file
if [ "$USE_TYPESCRIPT" = "y" ] || [ "$USE_TYPESCRIPT" = "Y" ]; then
  # TypeScript version
  cat > ".opencode/plugin/$PLUGIN_SLUG/plugin.$EXT" <<'TSPLUGIN'
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

export const {{pluginName}}: Plugin = async ({ client, $, directory, worktree, project }) => {
  // Plugin initialization
  await client.app.log({
    service: "{{pluginName}}",
    level: "info",
    message: "Plugin initialized",
  })

  console.log("{{pluginName}} loaded!")

  return {
    event: async ({ event }) => {
      console.log("Event:", event.type, event.properties)
    },

    "tool.execute.before": async (input, output) => {
      console.log(`Before tool: ${input.tool}`)
    },

    "tool.execute.after": async (input, output) => {
      console.log(`After tool: ${input.tool}`)
    },

    tool: {
      myTool: tool({
        description: "My custom tool",
        args: {
          input: tool.schema.string(),
        },
        async execute({ input }) {
          return `Processed: ${input}`
        },
      }),
    },
  }
}
TSPLUGIN
else
  # JavaScript version
  cat > ".opencode/plugin/$PLUGIN_SLUG/plugin.$EXT" <<'JSPLUGIN'
export const {{pluginName}} = async ({ client, $, directory, worktree, project }) => {
  // Plugin initialization
  await client.app.log({
    service: "{{pluginName}}",
    level: "info",
    message: "Plugin initialized",
  })

  console.log("{{pluginName}} loaded!")

  return {
    event: async ({ event }) => {
      console.log("Event:", event.type, event.properties)
    },

    "tool.execute.before": async (input, output) => {
      console.log(`Before tool: ${input.tool}`)
    },

    "tool.execute.after": async (input, output) => {
      console.log(`After tool: ${input.tool}`)
    },

    tool: {
      myTool: {
        description: "My custom tool",
        args: {
          input: { type: "string" },
        },
        async execute(args) {
          return `Processed: ${args.input}`
        },
      },
    },
  }
}
JSPLUGIN
fi

# Replace placeholders in plugin file
sed -i "s/{{pluginName}}/$PASCAL_NAME/g" ".opencode/plugin/$PLUGIN_SLUG/plugin.$EXT"

# Create README
cat > "$PLUGIN_SLUG/README.md" <<EOF
# $PLUGIN_NAME

$DESCRIPTION

## Installation

### Local Installation

1. Copy the plugin:
\`\`\`bash
cp -r .opencode/plugin/$PLUGIN_SLUG ~.config/opencode/plugin/
\`\`\`

2. Restart OpenCode

### NPM Installation

1. Publish to npm:
\`\`\`bash
cd $PLUGIN_SLUG
npm publish
\`\`\`

2. Add to \`opencode.json\`:
\`\`\`json
{
  "plugin": ["$PLUGIN_SLUG"]
}
\`\`\`

## Usage

The plugin is now loaded and ready to use with OpenCode.

## Features

- $DESCRIPTION
- Custom hooks and tools
- Event handling
- SDK integration

## Development

Edit: \`.opencode/plugin/$PLUGIN_SLUG/plugin.$EXT\`

## Author

$AUTHOR

## License

MIT
EOF

echo -e "\033[32m✅ Plugin created successfully!\033[0m"
echo -e "\033[1m📁 Location:\033[0m $PLUGIN_SLUG"
echo -e "\033[1m📁 OpenCode plugin:\033[0m .opencode/plugin/$PLUGIN_SLUG"
echo -e "\n\033[1m📝 Next steps:\033[0m"
echo "  1. Edit: .opencode/plugin/$PLUGIN_SLUG/plugin.$EXT"
echo "  2. Restart OpenCode"
echo "  3. Test your plugin"
echo ""
