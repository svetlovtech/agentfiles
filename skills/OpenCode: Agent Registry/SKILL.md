---
name: OpenCode: Agent Registry
description: |
  OpenCode agent registry with all available agents, their roles, and capabilities.
  Use when: Orchestrating tasks, selecting appropriate agents, understanding agent capabilities.
  
  Contains: 21 agents across categories (Critical, Fast Lane, Deep Lane, Specialists)
---

# OpenCode Agent Registry

## Overview

This registry contains all available OpenCode agents organized by their role and capabilities. Use this reference when:
- **Orchestrating tasks** — Select the right agent for each job
- **Understanding capabilities** — Know what each agent can do
- **Planning workflows** — Design agent collaboration patterns
- **Debugging delegation** — Verify correct agent selection

## Agent Categories

### 🔴 CRITICAL (Always Available)

These agents are essential and always available in the system.

#### 🎯 Orchestrator
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: Critical
- **Description**: Pure delegating orchestrator that analyzes tasks and delegates to specialized agents
- **Use when**: Entry point for ANY complex task, task coordination, multi-agent workflows
- **Tools**: Task, todowrite
- **Returns**: Aggregated results and status reports (in Russian to user)

#### 👨‍💻 Coder
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: Critical
- **Description**: Production-quality code writing and refactoring
- **Use when**: Write code, implement features, refactor, bug fixes
- **Tools**: Read, Write, Edit, Grep, Glob, Bash
- **Returns**: Modified files + implementation summary

#### 🔒 SecurityAuditor
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: Critical
- **Description**: Deep security analysis covering OWASP Top 10, injection vulnerabilities, authentication
- **Use when**: Security audit, vulnerability scanning, penetration testing
- **Tools**: Read, Grep, Glob, Bash
- **Returns**: JSON findings with severity, remediation steps, CWE references

#### ✅ FactVerifier
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: Critical
- **Description**: Independent fact-checking and verification system
- **Use when**: Verify claims, detect hallucinations, cross-reference sources
- **Tools**: Read, Grep, Bash, webfetch
- **Returns**: Verification results with confidence scores and source citations

---

### 🚀 FAST LANE — GLM-4.7

Fast operations agents optimized for quick response times.

#### 🔍 Explorer
- **Model**: GLM-4.7
- **Priority**: High
- **Description**: Instant code search, finds patterns, functions, classes across codebase
- **Use when**: "Where is X used?", "Find all API endpoints", "Show TODO/FIXME"
- **Tools**: Read, Grep, Glob
- **Returns**: List of files with relevant lines and context

#### 👁️ CodeReviewer
- **Model**: GLM-4.7
- **Priority**: High
- **Description**: Quick code review with best practices validation
- **Use when**: Code review, quality checks, Clean Code verification, SOLID/DRY compliance
- **Tools**: Read, Grep, Glob, Bash
- **Returns**: Markdown report with prioritized findings and recommendations

#### 🎨 StyleEnforcer
- **Model**: GLM-4.7
- **Priority**: Medium
- **Description**: Automatic linting and code formatting
- **Use when**: Format code, fix linting errors, enforce coding standards
- **Tools**: Bash, Read, Edit
- **Returns**: Report of applied changes and fixes

#### 📊 DepWatcher
- **Model**: GLM-4.7
- **Priority**: Medium
- **Description**: Dependency monitoring and vulnerability tracking
- **Use when**: Check dependencies, npm audit, pip-audit, security advisories
- **Tools**: Bash, Read, Write
- **Returns**: JSON dependency report with vulnerabilities and recommendations

---

### 🧠 DEEP LANE — GLM-5

Complex task agents for deep analysis and generation.

#### 🧪 TestGenerator
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: High
- **Description**: Generate comprehensive unit/integration/e2e tests
- **Use when**: Generate tests, improve coverage, TDD approach, test automation
- **Tools**: Read, Write, Grep, Glob, Bash
- **Returns**: Created test files + coverage report

#### 🚀 DevOpsAgent
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: High
- **Description**: CI/CD, Docker, Kubernetes, deployment automation
- **Use when**: Deploy, build Docker, configure CI/CD, K8s manifests, infrastructure
- **Tools**: Read, Write, Bash, Glob
- **Returns**: Deploy logs + status + configuration files

#### 🔌 APIArchitect
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: High
- **Description**: REST/GraphQL API design and documentation
- **Use when**: Design API, OpenAPI specs, API documentation, versioning
- **Tools**: Read, Write, Glob, Bash
- **Returns**: OpenAPI specs + documentation + examples

#### 📝 DocWriter
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: Medium
- **Description**: Documentation generation and maintenance
- **Use when**: Write README, API docs, code comments, user guides
- **Tools**: Read, Write, Glob
- **Returns**: Created documentation with structure and examples

#### 🔄 MigrationManager
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: Medium
- **Description**: Code and database migration management
- **Use when**: Migrate code, upgrade dependencies, DB migrations, version upgrades
- **Tools**: Read, Write, Edit, Bash, Glob
- **Returns**: Migration report + logs + rollback procedures

---

### 🔧 SPECIALISTS

Narrow-focus experts for specific domains.

#### 🗃️ SQLOptimizer
- **Model**: GLM-4.7
- **Priority**: Medium
- **Description**: SQL query optimization and performance analysis
- **Use when**: Optimize queries, analyze query plans, indexing strategies
- **Tools**: Read, Bash, Write, Grep
- **Returns**: Optimized queries + performance report + execution plans

#### 🎯 TaskDecomposer
- **Model**: GLM-4.7
- **Priority**: Medium
- **Description**: Break down complex tasks into manageable subtasks
- **Use when**: Break down complex tasks, create task hierarchy, work breakdown
- **Tools**: Read, Grep, Glob
- **Returns**: Structured list of subtasks with dependencies

#### 🧪 APITester
- **Model**: zai-coding-plan/glm-5-turbo
- **Priority**: High
- **Description**: API integration testing, contract testing, mock servers
- **Use when**: Generate API tests, create mocks, validate OpenAPI contracts
- **Tools**: Read, Write, Edit, Grep, Glob, Bash
- **Returns**: Test files + mock servers + coverage report

#### 🔍 FactExtractor
- **Model**: GLM-4.7
- **Priority**: Medium
- **Description**: Extract and structure facts from unstructured text
- **Use when**: NER, knowledge graph construction, data structuring, entity extraction
- **Tools**: Read, Write, Grep, Bash
- **Returns**: Structured JSON with entities, facts, relationships

#### 📝 DocumentationUpdater
- **Model**: GLM-4.7
- **Priority**: Medium
- **Description**: Keep documentation synchronized with code changes
- **Use when**: Update README, sync API docs, maintain CHANGELOG
- **Tools**: Read, Write, Edit, Grep, Glob
- **Returns**: Updated documentation files with change summaries

#### 👁️ VisualAnalyzer
- **Model**: Vision-capable model
- **Priority**: Medium
- **Description**: Analyze images, screenshots, diagrams, UI/UX elements
- **Use when**: UI review, OCR, diagram understanding, error diagnosis, screenshot analysis
- **Tools**: 8 vision tools (ui_to_artifact, extract_text, diagnose_error, understand_technical_diagram, analyze_data_visualization, ui_diff_check, analyze_image, analyze_video)
- **Returns**: Structured analysis reports with visual insights

---

## Quick Selection Guide

Use this table to quickly find the right agent for your task:

| Task Type | Recommended Agent | Alternative |
|-----------|------------------|-------------|
| **Orchestration** | Orchestrator | - |
| **Code Writing** | Coder | - |
| **Code Review** | CodeReviewer | Coder |
| **Security Audit** | SecurityAuditor | - |
| **Testing** | TestGenerator | Coder |
| **Code Search** | Explorer | Grep/Glob |
| **Deployment** | DevOpsAgent | - |
| **API Design** | APIArchitect | Coder |
| **Documentation** | DocWriter | Coder |
| **Dependency Check** | DepWatcher | - |
| **Code Formatting** | StyleEnforcer | - |
| **SQL Optimization** | SQLOptimizer | - |
| **Task Breakdown** | TaskDecomposer | Orchestrator |
| **API Testing** | APITester | TestGenerator |
| **Fact Extraction** | FactExtractor | - |
| **Fact Verification** | FactVerifier | - |
| **Visual Analysis** | VisualAnalyzer | - |
| **Documentation Sync** | DocumentationUpdater | DocWriter |
| **Migration** | MigrationManager | DevOpsAgent |

---

## Agent Model Distribution

### GLM-4.7 (Fast Lane)
- Explorer
- CodeReviewer
- StyleEnforcer
- DepWatcher
- SQLOptimizer
- TaskDecomposer
- FactExtractor
- DocumentationUpdater

### GLM-5 (Deep Lane & Critical)
- Orchestrator
- Coder
- SecurityAuditor
- FactVerifier
- TestGenerator
- DevOpsAgent
- APIArchitect
- DocWriter
- MigrationManager
- APITester

### Vision-Capable
- VisualAnalyzer

---

## Common Workflow Patterns

### Pattern 1: Code Feature Implementation
```
1. Explorer → Find existing patterns
2. Coder → Implement feature
3. TestGenerator → Write tests
4. CodeReviewer → Review quality
```

### Pattern 2: Security Hardening
```
1. SecurityAuditor → Identify vulnerabilities
2. Coder → Fix security issues
3. TestGenerator → Add security tests
4. DepWatcher → Check dependency vulnerabilities
```

### Pattern 3: API Development
```
1. APIArchitect → Design API structure
2. Coder → Implement endpoints
3. APITester → Generate API tests
4. DocWriter → Create API documentation
```

### Pattern 4: Full Project Review
```
1. Explorer → Scan codebase structure
2. CodeReviewer → Review code quality
3. SecurityAuditor → Security analysis
4. DepWatcher → Check dependencies
5. TestGenerator → Identify test gaps
```

### Pattern 5: Deployment Pipeline
```
1. TestGenerator → Ensure test coverage
2. StyleEnforcer → Format and lint
3. DevOpsAgent → Setup CI/CD
4. MigrationManager → Handle migrations
5. DocWriter → Update deployment docs
```

---

## Agent Coordination Tips

### Sequential Execution (Dependent Tasks)
- Use when: Task B depends on Task A results
- Example: Coder → TestGenerator (tests depend on code)

### Parallel Execution (Independent Tasks)
- Use when: Tasks don't depend on each other
- Example: SecurityAuditor + DepWatcher (independent checks)
- Speed boost: 2-5x faster than sequential

### Batch Parallel (Research/Analysis)
- Use when: Processing multiple items (files, URLs, components)
- Rule: 1-3 items → 1 agent, 4-10 → 2-3 agents, 11-20 → 4-5 agents
- Example: Research 20 websites → 5 agents (4 URLs each)

### Critical Path Priority
- Always prioritize: Security > Tests > Code > Docs
- SecurityAuditor should run early to catch issues
- TestGenerator should follow Coder immediately

---

## Agent Tool Access Matrix

| Agent | Read | Write | Edit | Grep | Glob | Bash | Task | todowrite | Web | Vision |
|-------|------|-------|------|------|------|------|------|-----------|-----|--------|
| Orchestrator | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Coder | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| SecurityAuditor | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| FactVerifier | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Explorer | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| CodeReviewer | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| TestGenerator | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| VisualAnalyzer | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

*Note: This matrix shows primary tool access. Some agents may have additional specialized tools.*

---

## Version Information

- **Registry Version**: 2.0
- **Total Agents**: 21
- **Categories**: 4 (Critical, Fast Lane, Deep Lane, Specialists)
- **Last Updated**: 2026-03-04
- **Source**: /home/ubuntu/.config/opencode/agent/orchestrator.md

---

**Registry Maintainer**: Orchestrator Agent System  
**Purpose**: Agent Discovery, Selection, and Coordination
