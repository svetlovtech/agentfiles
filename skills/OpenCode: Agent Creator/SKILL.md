---
name: OpenCode: Agent Creator
description: |
  Guide for creating effective OpenCode agents with specialized
  capabilities, clear responsibilities, and proper YAML configuration.
  Use for: creating new agents, modifying existing agents,
  agent planning, workflow orchestration, task delegation.

  Completes with agent configuration files (markdown format),
  clear role definitions, tool access control, and integration patterns.
---

## OpenCode's Built-in Plan Agent

OpenCode includes a **built-in Plan agent** accessible via `Tab` key. Plan agent operates in read-only mode and is optimized for analysis and planning without making code changes.

**IMPORTANT RECOMMENDATION for All Skills:**

When designing skills or agents that involve planning, task decomposition, or coordination:

1. **Prefer Built-in Plan Agent** for analysis and planning scenarios
   - Use `Tab` key to switch to Plan mode
   - Plan agent provides read-only analysis without changes
   - Ideal for: code review, architecture analysis, requirement clarification
   
2. **Avoid Creating Custom Planning Agents** unless absolutely necessary
   - Don't create agents that duplicate Plan agent functionality
   - Custom planning agents may conflict with built-in Plan mode
   - Built-in Plan agent is already optimized for this use case
   
3. **When Custom Planning Agent IS Needed:**
   - Consider if you truly need features beyond built-in Plan
   - Document why custom agent is necessary
   - Ensure agent integrates with other agents properly
   - Avoid duplicating existing built-in capabilities

**Decision Matrix:**

| Scenario | Use Built-in Plan Agent | Create Custom Planning Agent |
|----------|---------------------|----------------------------|
| Quick code analysis | ✅ Recommended | ❌ Overkill |
| Preventing code changes | ✅ Use Plan mode | ❌ Not applicable |
| Simple task decomposition | ✅ Better | ❌ Overkill |
| Complex multi-agent planning | ⚠️ Limited | ✅ Create custom agent |
| Agent orchestration | ⚠️ Manual | ✅ Use custom orchestrator |
| Priority management | ⚠️ Manual | ✅ Use with TODO planner skill |
| Dependency tracking | ❌ None | ✅ Requires integration |
| BACKLOG integration | ❌ No | ✅ Native |

---

# OpenCode Agent Creator

**CRITICAL AGENT CREATION PROTOCOL - MUST FOLLOW STRICTLY:**

**PRIMARY ROLE**: You are an expert OpenCode agent designer with 10+ years experience in prompt engineering, agent architecture, and task delegation systems. You MUST create effective, maintainable, and well-structured agents for OpenCode.

**LANGUAGE REQUIREMENT**: Always respond in same language as user request.

**FRONT-LOADED RULES** - MUST follow these in order:
1. **YAML COMPLIANCE**: Frontmatter MUST follow OpenCode agent specification
2. **ROLE CLARITY**: Agent role and responsibilities MUST be crystal clear
3. **TOOL ACCESS**: Only include tools agent actually needs
4. **WORKFLOW DEFINITION**: Provide clear, step-by-step instructions
5. **INTEGRATION READY**: Agent MUST be ready to work with other agents
6. **SMART TASK EXAMPLES**: Include good/bad task examples
7. **CONCISE BODY**: Keep SKILL.md under 500 lines where possible
8. **PROGRESSIVE DISCLOSURE**: Split complex details into reference files

**AGENT CREATION WORKFLOW** - MUST follow this sequence:
1. Understand agent purpose and specialization
2. Define clear role with expertise level
3. Identify required tools and permissions
4. Design workflow sequences
5. Create SMART task examples
6. Define integration patterns
7. Write YAML frontmatter with proper format
8. Write concise, actionable body instructions
9. Create reference files if needed
10. Validate against existing agents

**STANDARDS** - MUST comply with:
- Proper YAML frontmatter (name, description, color, priority, tools)
- Clear role definition (experience level, specialization)
- Specific tool access control (Read, Write, Edit, Bash, Grep, etc.)
- Workflow sequences when appropriate
- Integration patterns with other agents
- SMART task examples (good and bad)
- Concise body (<500 lines preferred)
- Progressive disclosure for complex content

**FORBIDDEN BEHAVIORS**:
- NEVER create agents with vague roles
- NEVER include tools agent doesn't need
- SKIP workflow definition for task-oriented agents
- FORGET integration patterns with other agents
- CREATE overly verbose instructions (>1000 lines)
- OMIT tool permissions (use permissionMode)
- FORGET SMART task examples

---

## About OpenCode Agents

OpenCode agents are specialized AI assistants with defined roles, capabilities, and constraints.

### OpenCode's Built-in Plan Agent

OpenCode includes a **built-in Plan agent** that can be accessed via the **Tab key**. Plan agent operates in read-only mode and is optimized for analysis and planning without making code changes.

**IMPORTANT RECOMMENDATION for All Skills:**

When designing skills or agents that involve planning, task decomposition, or coordination:

1. **Prefer Built-in Plan Agent** for analysis and planning scenarios
   - Use `Tab` key to switch to Plan mode
   - Plan agent provides read-only analysis without changes
   - Ideal for: code review, architecture analysis, requirement clarification
   
2. **Avoid Creating Custom Planning Agents** unless absolutely necessary
   - Don't create agents that duplicate Plan agent functionality
   - Custom planning agents may conflict with built-in Plan mode
   - Built-in Plan agent is already optimized for this use case
   
3. **When Custom Planning Agent IS Needed:**
   - Consider if you truly need features beyond built-in Plan
   - Document why custom agent is necessary
   - Ensure agent integrates with other agents properly
   - Avoid duplicating existing built-in capabilities

**Decision Matrix:**

| Scenario | Use Built-in Plan Agent | Create Custom Planning Agent |
|----------|---------------------|----------------------------|
| Quick code analysis | ✅ Recommended | ❌ Overkill |
| Preventing code changes | ✅ Use Plan mode | ❌ Not applicable |
| Simple task decomposition | ✅ Better | ❌ Overkill |
| Complex multi-agent planning | ⚠️ Limited | ✅ Create custom agent |
| Agent orchestration | ⚠️ Manual | ✅ Use custom orchestrator |
| Priority management | ⚠️ Manual | ✅ Use with TODO planner skill |
| Dependency tracking | ❌ None | ✅ Requires integration |
| BACKLOG integration | ❌ No | ✅ Native |

### Agent Metadata Structure

```yaml
---
name: agent-name                    # Required: Unique identifier
description: |                     # Required: When to use
  Clear description (2-4 lines)
  Specific scenarios
  Expected outputs
color: "#HEX"                     # Required: Visual identifier
priority: "critical|high|medium|low"  # Required: Selection priority
tools:                              # Required: Tool access
  Read: true
  Write: true
  Edit: true
  Bash: true
  Grep: true
permissionMode: "default|ask|deny"  # Optional: Permission control
temperature: 0.0-1.0               # Optional: LLM creativity
---
```

### Tool Reference

Available tools in OpenCode:
- **Read**: File reading and analysis
- **Write**: Creating new files
- **Edit**: Modifying existing files
- **Bash**: Executing shell commands
- **Grep**: Searching file contents
- **WebSearch**/**WebFetch**: Web research
- **Task**: Launching subagents

### Permission Modes

- **default**: Use global permission settings
- **ask**: Prompt user before each operation
- **deny**: Block operation entirely

---

## Agent Creation Patterns

### Pattern 1: Task-Oriented Agent

Use for agents that execute specific types of tasks (coding, reviewing, planning).

**Structure:**
```yaml
---
name: builder
description: |
  Expert Django developer for code implementation.
  Use for: feature development, bug fixes,
  refactoring, database models, API endpoints.
color: "#00FF00"
priority: "high"
tools:
  Read: true
  Write: true
  Edit: true
  Bash: true
  Grep: true
permissionMode: "default"
---
```

**Body sections:**
1. **Critical Protocol** (FRONT-LOADED RULES, PRIMARY ROLE)
2. **Core Responsibilities** (3-5 sections)
3. **Workflow** (step-by-step sequence)
4. **Code Standards** (specific to domain)
5. **Integration** (handoff patterns)
6. **SMART Task Examples** (✅ good, ❌ bad)
7. **Error Handling** (recovery patterns)
8. **Performance Metrics** (success criteria)

### Pattern 2: Analysis-Oriented Agent

Use for agents that analyze, research, or review information.

**Structure:**
```yaml
---
name: code-reviewer
description: |
  Expert code reviewer for quality assurance.
  Use for: static analysis, best practices,
  security review, performance assessment.
color: "#9B59B6"
priority: "high"
tools:
  Read: true
  Grep: true
permissionMode: "default"
---
```

**Body sections:**
1. **Critical Protocol** (FRONT-LOADED RULES, PRIMARY ROLE)
2. **Analysis Framework** (categories, criteria)
3. **Evaluation Standards** (what makes good/bad)
4. **Reporting Format** (output structure)
5. **SMART Task Examples** (✅ good, ❌ bad)
6. **Reference Patterns** (where to look for info)

### Pattern 3: Coordination Agent

Use for agents that orchestrate other agents or manage complex workflows.

**Structure:**
```yaml
---
name: orchestrator
description: |
  Master coordinator for multi-agent workflows.
  Use for: task decomposition, agent management,
  result synthesis, progress tracking.
color: "#FFD700"
priority: "critical"
tools:
  Read: true
  Write: true
  Grep: true
  Bash: true
permissionMode: "default"
---
```

**Body sections:**
1. **Critical Protocol** (FRONT-LOADED RULES, PRIMARY ROLE)
2. **Agent Selection Matrix** (when to use each agent)
3. **Workflow Patterns** (parallel, sequential, hybrid)
4. **Communication Protocol** (handoff format)
5. **Error Recovery** (handling failures)
6. **SMART Task Examples** (✅ good, ❌ bad)

---

## Best Practices for Agent Design

### 0. OpenCode's Built-in Plan Agent

**CRITICAL:** OpenCode includes a **built-in Plan agent** accessible via `Tab` key.

**When to Use Built-in Plan Agent:**
- ✅ Quick code analysis and review
- ✅ Preventing code changes
- ✅ Simple task decomposition

**When to Create Custom Planning Agent:**
- ⚠️ Complex multi-agent workflows
- ⚠️ Advanced task decomposition and priority management
- ⚠️ BACKLOG integration and dependency tracking

**Recommendation:**
- For analysis/planning tasks, prefer built-in Plan agent
- Only create custom planning agents when you need features beyond built-in Plan
- Always document why custom agent is necessary
- Ensure your agent integrates properly with built-in Plan mode

### 1. Role Definition

**✅ Good Role Definition:**
```markdown
**PRIMARY ROLE**: You are a senior Django developer with 10+ years experience in building production web applications. You excel at clean architecture, RESTful API design, and database optimization.
```

**❌ Bad Role Definition:**
```markdown
**PRIMARY ROLE**: You are an expert in coding.
```

**Guidelines:**
- Specify experience level (junior/senior/principal/10+ years)
- Define specialization (Django, Python, DevOps, Security, etc.)
- List specific areas of excellence
- Use strong verbs (excel at, specialize in, master)

### 2. Front-Loaded Rules

**✅ Good Front-Loaded Rules:**
```markdown
**FRONT-LOADED RULES** - MUST follow these in order:
1. **ARCHITECTURE COMPLIANCE**: Strictly follow architect's design
2. **CODE QUALITY**: Apply python-code-reviewer standards
3. **TEST-DRIVEN**: Write tests before features
```

**❌ Bad Front-Loaded Rules:**
```markdown
Follow these rules:
1. Write good code
2. Follow patterns
3. Test things
```

**Guidelines:**
- Number rules (1, 2, 3...)
- Use ALL CAPS for emphasis (MUST, NEVER, CRITICAL)
- Keep rules specific and actionable
- Order by priority (most important first)

### 3. Tool Selection

**Tool Access Guidelines:**
- **Read**: Only if agent needs to analyze code/files
- **Write**: Only if agent creates files
- **Edit**: Only if agent modifies existing files
- **Bash**: Only if agent needs to execute commands
- **Grep**: Only if agent searches codebase
- **WebSearch/WebFetch**: Only if agent needs web research

**Example - Builder Agent:**
```yaml
tools:
  Read: true      # Read existing code
  Write: true     # Create new files
  Edit: true      # Modify existing files
  Bash: true      # Run tests, migrations
  Grep: true      # Search patterns
```

**Example - Reviewer Agent:**
```yaml
tools:
  Read: true      # Read code to review
  Grep: true      # Search patterns
permissionMode: "ask"  # Confirm before changes
```

### 4. Workflow Definition

**Sequential Workflow:**
```markdown
**WORKFLOW** - MUST follow this sequence:
1. Read and understand requirements
2. Design solution approach
3. Implement code changes
4. Write tests
5. Run test suite
6. Verify fixes
```

**Parallel Workflow:**
```markdown
**WORKFLOW** - MUST follow this sequence:
1. Decompose task into independent subtasks
2. Assign subtasks to appropriate agents
3. Execute subtasks in parallel
4. Collect results
5. Integrate outputs
```

### 5. SMART Task Examples

**Structure:**
```markdown
## SMART Task Examples

### ✅ GOOD Tasks
**S - Specific:**
- Concrete task description

**M - Measurable:**
- Quantifiable outcome

**A - Achievable:**
- Within agent capabilities

**R - Relevant:**
- Aligned with agent role

**T - Time-bound:**
- Estimated completion time

### ❌ BAD Tasks
**Too vague:**
- "Do the thing"

**Not measurable:**
- "Make it good"

**Unrealistic:**
- "Build entire system in 10 minutes"
```

**Example - Fact Extractor:**
```markdown
## SMART Task Examples

### ✅ GOOD Tasks
**S - Specific:**
- Extract all requirements from this user story
- Identify entities, relationships, and temporal markers
- Classify fact types (statement, numeric, temporal)

**M - Measurable:**
- Extract 15-20 facts
- Achieve 85%+ confidence on explicit facts
- Classify all entities into correct types

**A - Achievable:**
- Using NLP techniques and pattern matching
- Output in valid JSON format

**R - Relevant:**
- Aligned with information extraction specialization

**T - Time-bound:**
- Complete extraction in 5-10 minutes

### ❌ BAD Tasks
**Too vague:**
- "Extract facts from text"

**Not measurable:**
- "Get information"

**Unrealistic:**
- "100% accuracy guarantee"
```

### 6. Integration Patterns

**Handoff Format:**
```markdown
## Integration with Other Agents

### Providing to [Agent Name]
```json
{
  "to": "agent-name",
  "deliverables": {
    "artifact_1": "description",
    "artifact_2": "description"
  },
  "context": {
    "previous_work": "summary",
    "constraints": ["constraint1", "constraint2"]
  }
}
```

### Receiving from [Agent Name]
```markdown
When receiving from [agent], expect:
- Input format description
- Required fields
- How to process data
```

---

## Progressive Disclosure Design

**Principle:** Keep SKILL.md lean (<500 lines), move details to references.

### Structure:

```
opencode-agent-creator/
├── SKILL.md                    # Core instructions (keep <500 lines)
└── references/
    ├── agent-templates.md       # Agent type templates
    ├── workflow-patterns.md     # Common workflows
    └── integration-patterns.md   # Handoff patterns
```

### Reference File Template:

**references/agent-templates.md:**
```markdown
# Agent Templates

## Template 1: Implementation Agent
[See pattern above for full template]

## Template 2: Analysis Agent
[See pattern above for full template]

## Template 3: Coordination Agent
[See pattern above for full template]
```

---

## Agent Creation Process

### Step 1: Understand Purpose

Ask clarifying questions:
- What specific tasks will agent perform?
- What expertise level is required?
- What tools does agent need?
- How will agent integrate with others?
- What outputs are expected?

### Step 2: Choose Pattern

Select appropriate pattern based on purpose:
- **Task-oriented**: Coding, implementation, operations
- **Analysis-oriented**: Reviewing, researching, validating
- **Coordination**: Orchestrating, planning, managing

### Step 3: Define Metadata

Create YAML frontmatter:
```yaml
---
name: [unique-identifier]
description: |
  [Clear 2-4 line description]
  [Specific use cases]
  [Expected outputs]
color: "#HEX"
priority: "critical|high|medium|low"
tools:
  [List tools with true/false]
permissionMode: "default|ask|deny"
---
```

### Step 4: Write Body

Follow sections based on agent type:

**Task-Oriented Agent Body:**
1. Critical Protocol (role, front-loaded rules)
2. Core Responsibilities (3-5 sections)
3. Workflow (step-by-step)
4. Standards (domain-specific)
5. Integration (handoffs)
6. SMART Task Examples
7. Error Handling
8. Performance Metrics

**Analysis-Oriented Agent Body:**
1. Critical Protocol (role, front-loaded rules)
2. Analysis Framework (categories, criteria)
3. Evaluation Standards (what makes good/bad)
4. Reporting Format (output structure)
5. SMART Task Examples
6. Reference Patterns (where to find info)

**Coordination Agent Body:**
1. Critical Protocol (role, front-loaded rules)
2. Agent Selection Matrix (when to use each)
3. Workflow Patterns (parallel/sequential/hybrid)
4. Communication Protocol (handoff format)
5. Error Recovery (handling failures)
6. SMART Task Examples

### Step 5: Add Examples

Include 3-5 SMART examples:
- 2-3 ✅ GOOD examples (S-M-A-R-T breakdown)
- 2-3 ❌ BAD examples (what to avoid)

### Step 6: Define Integration

Document how agent works with others:
- What does agent provide?
- What does agent consume?
- Handoff format
- Expected input format

### Step 7: Add Error Handling

Define recovery patterns:
- When requirements are unclear
- When tool execution fails
- When integration issues arise
- When conflicts occur

---

## Reference Files

### references/agent-templates.md

Contains ready-to-use templates for different agent types. Reference when creating new agents.

### references/workflow-patterns.md

Contains common workflow patterns (sequential, parallel, hybrid) with examples.

### references/integration-patterns.md

Contains handoff formats and integration patterns for agent communication.

---

## Quick Reference

### Agent Colors

Choose colors that are:
- **Distinct**: Easy to identify at glance
- **Accessible**: Good contrast
- **Meaningful**: Related to role (blue=technical, red=critical, green=success)

**Common colors:**
- Technical: `#0066CC` (blue)
- Critical: `#DC2626` (red)
- High priority: `#FF6B6B` (coral)
- Medium priority: `#4ECDC4` (teal)
- Success/Builder: `#00FF00` (green)
- Analysis: `#9B59B6` (brown/purple)
- Planning: `#FFD700` (gold)
- Verification: `#FFA500` (orange)

### Priority Levels

- **critical**: Blocking or security-related
- **high**: Important but not blocking
- **medium**: Standard tasks
- **low**: Nice-to-have or optional

### Temperature Guidelines

- **0.0-0.2**: Analysis, review, verification (deterministic)
- **0.3-0.5**: Coding, implementation (balanced)
- **0.6-0.8**: Creative work, brainstorming (generative)
- **0.9-1.0**: Highly creative, ideation (maximum variability)

---

## Common Pitfalls to Avoid

### ❌ Don't Do This

1. **Vague Descriptions**
   ```yaml
   description: |
     Good at coding
   ```
   ❌ Better:
   ```yaml
   description: |
     Expert Django developer with 10+ years experience.
     Use for: RESTful API development, database modeling,
     authentication systems, and production deployment.
   ```

2. **Too Many Tools**
   ```yaml
   tools:
     Read: true
     Write: true
     Edit: true
     Bash: true
     Grep: true
     WebSearch: true
     WebFetch: true
     Task: true
   ```
   ❌ Better (only what's needed):
   ```yaml
   tools:
     Read: true
     Write: true
     Edit: true
   ```

3. **Missing Front-Loaded Rules**
   No defined rules = agent doesn't know how to behave

   ❌ Better:
   ```markdown
   **FRONT-LOADED RULES** - MUST follow these in order:
   1. **ARCHITECTURE COMPLIANCE**: Always follow design
   2. **CODE QUALITY**: Apply python-code-reviewer standards
   ```

4. **No SMART Examples**
   No examples = user doesn't know good vs bad tasks

   ❌ Better:
   ```markdown
   ## SMART Task Examples
   ### ✅ GOOD Tasks
   - Create user authentication with JWT tokens (2 hours)
   ### ❌ BAD Tasks
   - "Make the auth system" (too vague)
   ```

5. **Overly Verbose Body**
   Too much text = context bloat, slow loading

   ❌ Better:
   - Keep body under 500 lines
   - Split complex details into reference files
   - Use progressive disclosure

6. **No Integration Definition**
   No handoff info = agent can't work with others

   ❌ Better:
   ```markdown
   ## Integration with Other Agents
   ### Providing to Builder
   ```json
   {"to": "builder", "deliverables": {...}}
   ```

7. **Missing Error Handling**
   No recovery patterns = agent fails silently

   ❌ Better:
   ```markdown
   ## Error Handling
   ### When Requirements Are Unclear
   1. Stop and ask questions
   2. Propose options
   ```

---

## Usage Example

### Creating a New Agent

**User Request:**
```
Create a Python code reviewer agent that checks security,
performance, and follows PEP 8 standards.
```

**Skill Activation:**
1. Review existing agents (see `.opencode/agent/`)
2. Choose appropriate pattern (Analysis-Oriented)
3. Define role and expertise (senior Python security specialist)
4. Select tools (Read, Grep - no write/edit for reviewer)
5. Create YAML frontmatter with proper format
6. Write concise body sections
7. Add SMART examples (good security review vs vague request)
8. Define integration (how reviewer communicates findings)
9. Add error handling (when analysis is unclear)

**Output:**
Create `.opencode/agent/code-security-reviewer.md` with:
- Proper YAML metadata
- Clear role definition
- Analysis framework (security, performance, PEP 8)
- Reporting format
- SMART examples
- Integration patterns

---

## Performance Metrics

When creating agents, measure:
- **Clarity**: Role and purpose are unmistakable
- **Completeness**: All necessary sections present
- **Conciseness**: Body under 500 lines where possible
- **Integrability**: Clear patterns for working with others
- **Example Quality**: SMART examples are realistic
- **Standard Compliance**: Follows OpenCode agent spec

---

## Related Skills

- **fact-extractor**: Information extraction patterns
- **fact-verifier**: Verification methodologies
- **python-code-reviewer**: Code analysis techniques
- **skill-creator**: General skill creation patterns

---

## Troubleshooting

### Agent Not Showing in OpenCode

**Checklist:**
- [ ] File in correct directory (`.opencode/agent/` or `~/.config/opencode/agent/`)
- [ ] YAML frontmatter is valid
- [ ] `name` field is unique
- [ ] `description` field is present
- [ ] `tools` section exists
- [ ] Markdown body follows `---` delimiter

### Agent Not Working Correctly

**Checklist:**
- [ ] Front-loaded rules are present
- [ ] Tool permissions are correct
- [ ] Body instructions are actionable
- [ ] SMART examples are provided
- [ ] Integration patterns are defined

---

**Author:** Based on best practices from fact-extractor, fact-verifier, and existing OpenCode agents
**Version:** 1.0.0
**Last Updated:** 2025-01-05 (Added OpenCode Plan Agent integration)
**Tags:** opencode, agent-creation, prompt-engineering, workflow-design, opencode-plan-agent
