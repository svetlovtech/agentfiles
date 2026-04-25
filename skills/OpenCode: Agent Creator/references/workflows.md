# Workflow Patterns

This file contains common workflow patterns for agent orchestration and coordination.

---

## Pattern 1: Sequential Workflow

Use when tasks must be completed in order, each task depends on previous completion.

**Example:**
```yaml
workflow: "sequential"
steps:
  - agent: architect
    task: Design system architecture
  - agent: builder
    task: Implement based on architecture
  - agent: validator
    task: Test implementation
  - agent: orchestrator
    task: Integrate and deliver
```

**When to use:**
- Tasks with strict dependencies
- Quality gates between phases
- Need for structured progression

---

## Pattern 2: Parallel Workflow

Use when independent tasks can be executed simultaneously.

**Example:**
```yaml
workflow: "parallel"
steps:
  - agent: researcher
    task: Investigate option A
  - agent: researcher
    task: Investigate option B
  - agent: researcher
    task: Investigate option C
  - agent: orchestrator
    task: Synthesize findings
```

**When to use:**
- Independent research tasks
- Speed optimization
- Multiple investigation paths

---

## Pattern 3: Hybrid Workflow

Combination of sequential and parallel execution.

**Example:**
```yaml
workflow: "hybrid"
parallel_phase:
  - agent: architect
    task: Design architecture
  - agent: fact-extractor
    task: Extract requirements
sequential_phase:
  - agent: builder
    task: Implement architecture
  - agent: validator
    task: Test implementation
```

**When to use:**
- Complex tasks with both independent and dependent components
- Need for research before implementation
- Quality gates after parallel phases

---

## Pattern 4: Branching Workflow

Use when multiple paths may be chosen based on conditions.

**Example:**
```yaml
workflow: "branching"
branches:
  condition_A:
    agent: agent-a
    task: Implement option A
  condition_B:
    agent: agent-b
    task: Implement option B
  condition_C:
    agent: orchestrator
    task: Manual decision point
```

**When to use:**
- Multiple valid approaches exist
- User choice required
- Different technical paths

---

## Pattern 5: Iterative Refinement

Use when output requires multiple rounds of improvement.

**Example:**
```yaml
workflow: "iterative"
cycles:
  - cycle: 1
    agent: builder
    task: Draft implementation
  - cycle: 2
    agent: validator
    task: Review draft
  - cycle: 3
    agent: builder
    task: Refine based on feedback
```

**When to use:**
- Quality requirements evolve
- Need for expert review
- Progressive improvement

---

## Communication Patterns

### Handoff Format

**From Agent to Agent:**
```json
{
  "to": "agent-name",
  "task_id": "unique-identifier",
  "context": {
    "previous_output": "summary",
    "requirements": ["req1", "req2"],
    "constraints": ["constraint1", "constraint2"]
  },
  "expected_output": {
    "format": "markdown|json|yaml",
    "content_requirements": ["requirement1", "requirement2"]
  }
}
```

### Status Updates

**Progress Report:**
```json
{
  "from": "agent-name",
  "status": "in_progress|completed|blocked",
  "progress_percentage": 75,
  "completed_steps": ["step1", "step2"],
  "current_phase": "implementation",
  "next_phase": "testing",
  "blockers": ["blocker1"],
  "deliverables_created": ["artifact1", "artifact2"]
}
```

---

## Quality Gates

Common quality checkpoints between workflow phases:

### Gate 1: Architecture Approval
- [ ] ADR documented
- [ ] Technical feasibility confirmed
- [ ] Performance requirements met
- [ ] Security considerations addressed

### Gate 2: Implementation Complete
- [ ] Code follows design
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] No critical bugs

### Gate 3: Testing Approved
- [ ] Test coverage >85%
- [ ] All critical paths tested
- [ ] Performance benchmarks met
- [ ] Security tests passed

### Gate 4: Production Ready
- [ ] All quality gates passed
- [ ] Deployment documentation complete
- [ ] Monitoring configured
- [ ] Rollback plan documented

---

## Error Handling in Workflows

### Handling Blockers

**When agent is blocked:**
```yaml
on_blocker:
  action: escalate
  target: orchestrator
  message: "Blocked due to: [reason]"
  suggested_alternatives: ["alt1", "alt2"]
  requires_human_input: true/false
```

### Handling Failures

**When task fails:**
```yaml
on_failure:
  action: retry|fallback|escalate
  retry_count: 3
  fallback_strategy: "alternate_approach"
  escalation_target: orchestrator
```

---

## Backlog Integration

### Backlog.md Format

**Update Pattern:**
```markdown
## Backlog

### In Progress
- [ ] [TASK-1] - assigned to [agent] - priority: [high|medium|low]
- [ ] [TASK-2] - assigned to [agent] - priority: [high|medium|low]

### Completed
- [x] [TASK-3] - completed by [agent] - [date]

### Blocked
- [ ] [TASK-4] - blocked on [agent] - reason: [reason]

### Dependencies
- TASK-5 depends on TASK-1
- TASK-6 depends on TASK-2, TASK-3
```

---

## Best Practices

### 1. Clear Dependencies
- Explicitly state task dependencies
- Use task IDs for tracking
- Don't start tasks until prerequisites met

### 2. Parallel Execution
- Only parallelize truly independent tasks
- Identify shared resources
- Coordinate access to shared data

### 3. Quality Gates
- Define success criteria upfront
- Don't proceed until gates passed
- Document gate decisions

### 4. Communication
- Use structured formats (JSON preferred)
- Include context with handoffs
- Report blockers immediately

### 5. Recovery
- Have fallback strategies
- Document retry policies
- Define escalation paths
