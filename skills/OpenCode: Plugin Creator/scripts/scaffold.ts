#!/usr/bin/env bun

import { readdir, readFile, writeFile, mkdir } from "fs/promises"
import { join } from "path"

// ANSI color codes
const colors = {
  reset: "\x1b[0m",
  bright: "\x1b[1m",
  green: "\x1b[32m",
  blue: "\x1b[34m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
}

function colorize(text: string, color: keyof typeof colors) {
  return `${colors[color]}${text}${colors.reset}`
}

async function readTemplateFiles() {
  const templateDir = new URL(".", import.meta.url).pathname
  const files = await readdir(templateDir)

  const templates: Record<string, string> = {}
  for (const file of files) {
    if (file === "scaffold.ts" || file === "README.md") continue
    const content = await readFile(join(templateDir, file), "utf-8")
    templates[file] = content
  }
  return templates
}

async function prompt(question: string): Promise<string> {
  process.stdout.write(colorize(question, "cyan") + " ")
  const input = await new Promise<string>((resolve) => {
    process.stdin.once("data", (data) => resolve(data.toString().trim()))
  )
  return input
}

function replacePlaceholders(content: string, replacements: Record<string, string>) {
  let result = content
  for (const [key, value] of Object.entries(replacements)) {
    result = result.replace(new RegExp(`{{${key}}}`, "g"), value)
  }
  return result
}

async function main() {
  console.log(colorize("\n🚀 OpenCode Plugin Scaffolder\n", "bright"))

  const pluginName = await prompt("Plugin name (e.g., my-awesome-plugin):")
  const description = await prompt("Plugin description:")
  const author = await prompt("Author name:")
  const useTypeScript = (await prompt("Use TypeScript? (y/n):")).toLowerCase() === "y"

  const pluginSlug = pluginName.toLowerCase().replace(/\s+/g, "-")
  const pascalName = pluginName
    .split(/[-\s]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join("")

  console.log(colorize("\n📦 Creating plugin...\n", "bright"))

  // Create plugin directory
  const pluginDir = join(process.cwd(), pluginSlug)
  await mkdir(pluginDir, { recursive: true })

  // Create .opencode/plugin directory
  const opencodeDir = join(process.cwd(), ".opencode", "plugin", pluginSlug)
  await mkdir(opencodeDir, { recursive: true })

  // Read template files
  const templateDir = new URL(".", import.meta.url).pathname
  const templates = await readTemplateFiles()

  // Generate package.json
  const packageJson = {
    name: pluginSlug,
    version: "0.1.0",
    description,
    type: "module",
    main: `./plugin.${useTypeScript ? "ts" : "js"}`,
    exports: `./plugin.${useTypeScript ? "ts" : "js"}`,
    keywords: ["opencode", "plugin"],
    author,
    license: "MIT",
    peerDependencies: {
      "@opencode-ai/plugin": "*",
    },
    dependencies: {
      "@opencode-ai/plugin": "latest",
    },
  }

  await writeFile(join(pluginDir, "package.json"), JSON.stringify(packageJson, null, 2))

  // Generate plugin file
  const pluginContent = useTypeScript
    ? templates["plugin.ts"] || templates["plugin.js"]
    : templates["plugin.js"] || templates["plugin.ts"]

  const replacements: Record<string, string> = {
    pluginName: pascalName,
    pluginDescription: description,
    pluginAuthor: author,
  }

  const processedContent = replacePlaceholders(pluginContent, replacements)
  await writeFile(join(opencodeDir, `plugin.${useTypeScript ? "ts" : "js"}`), processedContent)

  // Generate README
  const readmeContent = `# ${pluginName}

${description}

## Installation

### Local Installation

1. Copy the plugin to your project:
   \`\`\`bash
   cp -r ${pluginSlug}/.opencode/plugin .
   \`\`\`

2. Restart OpenCode

### NPM Installation

1. Publish to npm:
   \`\`\`bash
   cd ${pluginSlug}
   npm publish
   \`\`\`

2. Add to \`opencode.json\`:
   \`\`\`json
   {
     "plugin": ["${pluginSlug}"]
   }
   \`\`\`

## Usage

The plugin is now loaded and ready to use with OpenCode.

## Features

- ${description}
- Custom hooks and tools
- Event handling
- SDK integration

## Development

Edit the plugin file in \`.opencode/plugin/${pluginSlug}/plugin.${useTypeScript ? "ts" : "js"}\`.

## Author

${author}

## License

MIT
`

  await writeFile(join(pluginDir, "README.md"), readmeContent)

  console.log(colorize("✅ Plugin created successfully!\n", "green"))
  console.log(colorize("📁 Location:", "bright"), pluginDir)
  console.log(colorize("📁 OpenCode plugin:", "bright"), opencodeDir)
  console.log(colorize("\n📝 Next steps:", "bright"))
  console.log(`  1. Edit: ${opencodeDir}/plugin.${useTypeScript ? "ts" : "js"}`)
  console.log(`  2. Restart OpenCode`)
  console.log(`  3. Test your plugin\n`)
}

main().catch((error) => {
  console.error(colorize("❌ Error:", "red"), error.message)
  process.exit(1)
})
