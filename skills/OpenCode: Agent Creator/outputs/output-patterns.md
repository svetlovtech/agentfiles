# Output Patterns

This file contains output format patterns and templates for different agent types and workflows.

---

## Agent Output Patterns

### Pattern 1: Code Implementation Output

**When to use:** Builder/implementation agents completing coding tasks.

**Structure:**
```markdown
## Implementation Summary

### Files Created
- `path/to/file1.py` - Description
- `path/to/file2.py` - Description

### Changes Made
- Modified: `path/to/existing_file.py`
  - Change description
  - Lines affected: X-Y

### Testing
- Tests written: `path/to/test_file.py`
- Coverage achieved: X%
- All tests passing: Yes/No

### Documentation
- Docstrings added: Yes/No
- API docs updated: Yes/No
```

### Pattern 2: Analysis Output

**When to use:** Reviewer/analysis agents completing assessments.

**Structure:**
```markdown
## Analysis Report

### Overall Assessment
- Category scores: [score breakdown]
- Overall rating: [stars] (⭐⭐⭐⭐⭐⭐)
- Critical issues: [count]
- High priority issues: [count]

### Detailed Analysis by Category

### 1. Functionality and Correctness
- Score: X/10
- Findings:
  - [Finding 1]
  - [Finding 2]

[... other categories ...]

### Recommendations

### Priority 1 (Critical)
- [ ] [Recommendation 1]
- [ ] [Recommendation 2]

### Priority 2 (Important)
- [ ] [Recommendation 3]
- [ ] [Recommendation 4]

### Positive Aspects
- [ ] [Positive aspect 1]
- [ ] [Positive aspect 2]
```

### Pattern 3: Extracted Data Output

**When to use:** Information extraction agents (fact-extractor, data miners).

**Structure:**
```json
{
  "metadata": {
    "extraction_timestamp": "ISO_8601",
    "total_facts": 42,
    "total_entities": 15
  },
  "entities": [
    {
      "id": "entity_1",
      "name": "Entity Name",
      "type": "organization|person|location|product",
      "attributes": {},
      "confidence": 0.95
    }
  ],
  "facts": [
    {
      "id": "fact_1",
      "type": "statement|numeric_data|temporal",
      "content": "Fact description",
      "confidence": 0.92,
      "source_location": "paragraph_2 sentence_3"
    }
  ],
  "relationships": [
    {
      "id": "rel_1",
      "source_entity": "entity_1",
      "target_entity": "entity_2",
      "relationship_type": "works_for|located_in|created_by"
    }
  ]
}
```

### Pattern 4: Verification Output

**When to use:** Fact verification agents (fact-verifier, validators).

**Structure:**
```json
{
  "verification_result": {
    "status": "VERIFIED_CORRECT|TYPO_DETECTED|OUTDATED|WRONG_VALUE|HALLUCINATION",
    "status_code": "VC|TD|OD|WV|HL",
    "confidence": 0.95,
    "is_correct": true/false
  },
  "correction_details": {
    "correct_fact": "Corrected version if applicable",
    "claimed_value": "Original incorrect value",
    "correct_value": "Correct value",
    "explanation": "Why correction is needed"
  },
  "sources": [
    {
      "type": "primary|secondary|official",
      "url": "https://source.com",
      "title": "Source Title",
      "credibility": 0.95,
      "relevant_quote": "Supporting quote"
    }
  ]
}
```

### Pattern 5: Coordination Output

**When to use:** Orchestrator/coordination agents managing workflows.

**Structure:**
```markdown
## Orchestration Report

### Task Decomposition
- Total subtasks: 15
- Parallel tasks: 8
- Sequential tasks: 7
- Dependencies identified: 12

### Agent Assignments
- architect: System design (2 hours)
- builder: Implementation (6 hours)
- validator: Testing (3 hours)
- fact-extractor: Requirements analysis (1 hour)

### Progress Tracking

#### Phase 1: Planning ✅
- Status: Completed
- Duration: 45 minutes
- Deliverable: Architecture design document

#### Phase 2: Implementation 🔄
- Status: In Progress (60%)
- Started: 2025-01-05 14:30
- Estimated completion: 2025-01-05 18:00

#### Phase 3: Testing ⏳
- Status: Not Started
- Scheduled: After implementation phase

### Quality Gates
- Gate 1 (Architecture): Passed ✅
- Gate 2 (Implementation): In Progress 🔄
- Gate 3 (Testing): Not Started ⏳

### Blockers
- [ ] Blocked by [resource]
- [ ] Blocked by [dependency]

### Next Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

```

---

## Document Output Patterns

### Pattern 1: ADR (Architecture Decision Record)

```markdown
# ADR-[number]: [Decision Title]

## Status
[Proposed/Approved/Implemented/Deprecated]

## Context
[What is the problem we're trying to solve?]

## Decision
[What are we doing and why? Include design principles rationale.]

## Design Principles Applied

### SOLID Principles:
- **Single Responsibility**: How each component has one clear purpose
- **Open/Closed**: How system is extensible without modification
- **Liskov Substitution**: Proper inheritance and substitutability
- **Interface Segregation**: Focused, cohesive interfaces
- **Dependency Inversion**: Abstraction dependencies

### DRY/KISS Principles:
- **DRY**: How duplication is eliminated through abstraction
- **KISS**: How simplicity is maintained and over-engineering avoided

## Consequences
[What becomes easier/harder as a result?]

## Implementation Notes
[Specific guidance for developers including design pattern compliance]

## Alternatives Considered
- [Alternative 1]: [Why not chosen]
- [Alternative 2]: [Why not chosen]
```

### Pattern 2: API Documentation

```markdown
# API Endpoint: [Endpoint Name]

## Description
[Clear description of endpoint purpose]

## Endpoint Details

- **URL**: `[METHOD] /api/resource/{id}`
- **Method**: `GET|POST|PUT|DELETE|PATCH`
- **Authentication**: Required/Optional
- **Authorization**: `[role]` required
- **Content-Type**: `application/json`

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| param1 | string | Yes | Description |
| param2 | integer | No | Description |
| param3 | object | Yes | Description |

## Response

### Success Response (200)
```json
{
  "id": "uuid",
  "attribute1": "value",
  "attribute2": "value"
}
```

### Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Missing or invalid credentials |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 500 | Internal Server Error | Server error |

## Example Request

```bash
curl -X POST https://api.example.com/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com"
  }'
```

```

---

## File Naming Conventions

### Agents
- Use kebab-case: `fact-extractor`, `security-reviewer`
- Avoid underscores: `fact_extractor`
- Be descriptive: `django-api-builder`, not just `builder`

### Skills
- Use kebab-case: `python-code-reviewer`, `git-branch-rus`
- Match functionality: `code-solid-principles`, not `solid`

### Reference Files
- Use kebab-case: `agent-templates.md`, `workflow-patterns.md`
- Be descriptive: `integration-patterns.md`, not just `patterns.md`

---

## Code Structure Patterns

### Django Application Agent
```python
django-builder/
├── SKILL.md
└── references/
    ├── models/              # Model examples
    ├── views/              # View patterns
    ├── serializers/         # DRF serializers
    ├── urls/               # URL configuration
    └── tests/              # Testing patterns
```

### DevOps Agent
```python
devops-engineer/
├── SKILL.md
└── references/
    ├── docker/              # Docker configurations
    ├── ansible/             # Playbook examples
    ├── ci-cd/               # Pipeline configs
    └── monitoring/           # Monitoring setups
```

---

## Template Patterns

### Agent Body Template

```markdown
[FRONT-LOADED RULES section]

## Core Responsibilities
[Responsibility 1]
[Responsibility 2]
[Responsibility 3]

## Workflow
[Step 1]
[Step 2]
[Step 3]

## Standards
[Standard 1]
[Standard 2]

## SMART Task Examples

### ✅ GOOD Tasks
[Good example]

### ❌ BAD Tasks
[Bad example]

## Integration with Other Agents

### Providing to [Agent]
[Handoff format]

### Receiving from [Agent]
[Input format]

## Error Handling
[Error scenario handling]

## Performance Metrics
[Metrics list]
```

---

## Quality Checklist for Skills/Agents

### Agent Quality Checklist
- [ ] YAML frontmatter is valid
- [ ] `name` field is unique
- [ ] `description` is clear and comprehensive
- [ ] `color` is specified
- [ ] `priority` is set appropriately
- [ ] `tools` section is complete
- [ ] `permissionMode` is set (if needed)
- [ ] Front-loaded rules are numbered
- [ ] Workflow is defined
- [ ] SMART task examples included
- [ ] Integration patterns documented
- [ ] Error handling described
- [ ] Performance metrics defined
- [ ] Body is concise (<1000 lines)
- [ ] Language requirements specified

### Skill Quality Checklist
- [ ] YAML frontmatter is valid
- [ ] `name` field is unique
- [ ] `description` is clear and comprehensive
- [ ] Front-loaded rules are defined
- [ ] Progressive disclosure is used
- [ ] References are properly structured
- [ ] Examples are included where appropriate
- [ ] Workflow is clear
- [ ] Body is concise (<500 lines)
- [ ] License is specified (if applicable)

---

## Common Templates

### Quick Start Template
```markdown
## Quick Start

```bash
@agent-name <task description>
```

**What happens:**
1. Agent activates based on task
2. Follows workflow defined in agent
3. Produces output using defined patterns
4. Integrates with other agents if needed
```

### Error Recovery Template
```markdown
## Error Handling

### When [Error Type]

1. **Stop**: Halt execution
2. **Analyze**: Understand root cause
3. **Recover**: Apply recovery strategy
4. **Report**: Document what happened
5. **Continue**: Resume or escalate

**Recovery Strategies:**
- [Strategy 1]
- [Strategy 2]
- [Strategy 3]
```

### Task Progress Template
```markdown
## Progress Report

### Current Status
- **Phase**: [Planning|Implementation|Testing|Completed]
- **Progress**: [X]%
- **ETA**: [Estimated completion time]

### Completed Work
- [x] [Task 1]
- [x] [Task 2]
- [ ] [Task 3]

### Current Work
- [ ] [In-progress task 1]
- [ ] [In-progress task 2]

### Next Steps
1. [Next step 1]
2. [Next step 2]
3. [Next step 3]

### Blockers
- [ ] [Blocker 1]
- [ ] [Blocker 2]

### Notes
[Additional context or observations]
```
