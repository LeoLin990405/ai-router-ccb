# Hivemind Long-Running Agent Harness

This directory contains the harness system for continuous iteration of Hivemind, based on [Anthropic's effective harness patterns](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).

## 📁 Files

- **`features.json`**: Structured feature list with explicit completion status
- **`claude-progress.txt`**: Session-by-session progress tracking and institutional memory
- **`init.sh`**: Environment initialization script for each session
- **`session-template.md`**: Template for structured development sessions

## 🎯 Philosophy

Long-running projects require structure to maintain productivity across multiple AI sessions. This harness prevents common failure modes:

- ❌ **Over-ambition**: Trying to do too much in one session
- ❌ **Premature completion**: Marking work done without thorough testing
- ❌ **Environmental confusion**: Wasting tokens understanding project state
- ❌ **Context loss**: Forgetting decisions and progress between sessions

## 🔄 Session Workflow

### 1. Session Start
```bash
.harness/init.sh
```

This script:
- Shows current working directory
- Displays git status and latest commit
- Checks Gateway API status
- Reviews recent progress
- Shows next priority feature

### 2. Feature Selection

Open `features.json` and pick the **highest priority** feature where `passes: false`.

Each feature has:
- **Steps**: Detailed implementation checklist
- **Acceptance criteria**: What "done" means
- **Dependencies**: Other features that must complete first
- **Estimated sessions**: Planning guideline

### 3. Development

**Key principles:**
- ✅ Work on **ONE feature** per session maximum
- ✅ Make **incremental progress** with clean git commits
- ✅ Write **tests before** marking complete
- ✅ Leave code in **merge-ready state**

### 4. Testing

Before marking `passes: true`:
- Run all existing tests
- Write new tests for your feature
- Test manually via browser/CLI
- Verify acceptance criteria

### 5. Session End

```bash
# 1. Commit your work
git add -A
git commit -m "feat(F00X): [clear description]"

# 2. Update features.json
# Set passes: true if feature is complete
# Or add notes to description if incomplete

# 3. Update claude-progress.txt
# Add session notes with timestamp
# Document decisions and next steps

# 4. Push to GitHub
git push origin main
```

## 📋 Feature Template

When adding new features to `features.json`:

```json
{
  "id": "F00X",
  "name": "Clear, actionable title",
  "priority": "high|medium|low",
  "description": "What this feature does and why it matters",
  "steps": [
    "Concrete step 1",
    "Concrete step 2",
    "..."
  ],
  "passes": false,
  "estimated_sessions": 2,
  "dependencies": ["F001"],
  "acceptance_criteria": [
    "Specific, testable criterion 1",
    "Specific, testable criterion 2"
  ]
}
```

## 🧪 Testing Strategy

### Current Testing
- Unit tests: Jest
- Integration tests: Jest
- Manual testing: Required

### Planned (F006)
- E2E tests: Playwright
- Visual regression: Playwright snapshots
- Browser automation: Full user flows

## 📊 Progress Tracking

### features.json
- Source of truth for what needs to be built
- Updated when features complete
- Reviewed at start of each session

### claude-progress.txt
- Chronological log of all sessions
- Institutional memory for decision context
- Prevents redundant work

### Git History
- Code-level progress tracking
- Recovery points for mistakes
- Documentation of implementation choices

## 🎓 Best Practices

1. **Start every session with init.sh**
   - Orients you to project state
   - Prevents wasted tokens on confusion

2. **One feature per session**
   - Prevents over-ambition
   - Ensures clean handoffs

3. **Test before marking complete**
   - Use browser automation when possible
   - Write E2E tests for critical flows

4. **Clean git commits**
   - Descriptive messages
   - Merge-ready code
   - No half-finished work

5. **Update progress.txt**
   - Future sessions need context
   - Document "why" not just "what"

## 🚀 Next Session Preparation

At end of each session, prepare for next agent:

```markdown
=== CURRENT STATUS ===
Active Feature: F00X - [Name]
Progress: [Brief status]
Blockers: [Any issues]

Next Session TODO:
1. [Specific next step]
2. [Specific next step]

=== CONTEXT FOR NEXT AGENT ===
[Anything important for continuity]
```

## 📚 References

- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Hivemind GitHub Repository](https://github.com/LeoLin990405/Hivemind)

## 🤝 Contributing

When adding features:
1. Add to `features.json` with detailed steps
2. Update dependencies if needed
3. Set realistic priority
4. Write clear acceptance criteria

When completing features:
1. Set `passes: true` in features.json
2. Move to `completed_features` array
3. Document in progress.txt
4. Commit with "feat(F00X):" prefix

---

**Remember**: This is a marathon, not a sprint. Quality over speed. Clean handoffs matter.
