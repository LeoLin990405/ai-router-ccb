# Development Session Template

**Date**: [YYYY-MM-DD]
**Agent**: [Claude/Codex/Gemini/etc]
**Session Goal**: [One sentence goal]

## 🚀 Session Start

### 1. Environment Check
```bash
.harness/init.sh
```

**Working Directory**:
**Git Status**:
**Latest Commit**:
**Gateway API**: ☐ Running / ☐ Not Running

### 2. Progress Review

**Last Session Summary**:
[Read from claude-progress.txt]

**Active Features**:
- [ ] None (starting fresh)
- [ ] F00X - [Feature name] - [Status]

### 3. Feature Selection

**Selected Feature**: F00X - [Name]

**Priority**: High / Medium / Low

**Why this feature**:
[Reasoning for selecting this over others]

**Estimated effort**: X sessions

---

## 📝 Implementation Plan

### Steps (from features.json)
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
- [ ] ...

### Additional Considerations
- [Any technical concerns]
- [Any dependencies to verify]
- [Any unknowns to investigate]

---

## 💻 Development Work

### Investigation Phase
**Goal**: Understand current codebase and identify integration points

**Files to review**:
- [ ] [file1.ts]
- [ ] [file2.ts]
- [ ] ...

**Findings**:
[Notes from code review]

### Implementation Phase

#### Change 1: [Description]
**Files modified**:
- [file1.ts] - [what changed]
- [file2.ts] - [what changed]

**Commit**:
```bash
git commit -m "feat(F00X): [description]"
```

#### Change 2: [Description]
[Repeat structure]

---

## 🧪 Testing

### Manual Testing
- [ ] Test case 1: [Description]
  - Expected: [result]
  - Actual: [result]
  - Status: ✅ / ❌

- [ ] Test case 2: [Description]
  - Expected: [result]
  - Actual: [result]
  - Status: ✅ / ❌

### Automated Testing
- [ ] Unit tests written
- [ ] Integration tests written
- [ ] E2E tests written (if applicable)
- [ ] All tests passing

**Test Coverage**: [X%]

### Acceptance Criteria Review
From features.json:

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

**Feature Complete?**: ☐ Yes / ☐ No / ☐ Partial

---

## 📊 Session Summary

### What Was Completed
- ✅ [Accomplishment 1]
- ✅ [Accomplishment 2]
- ✅ [Accomplishment 3]

### What Was Not Completed
- ⏸️ [Incomplete work 1] - [Reason]
- ⏸️ [Incomplete work 2] - [Reason]

### Blockers Encountered
- [Blocker 1] - [How resolved or why still blocked]
- [Blocker 2] - [How resolved or why still blocked]

### Technical Decisions
1. **Decision**: [What was decided]
   - **Rationale**: [Why this choice]
   - **Alternatives considered**: [What else was considered]

2. **Decision**: [What was decided]
   - **Rationale**: [Why this choice]
   - **Alternatives considered**: [What else was considered]

### Learnings
- [Something learned about the codebase]
- [Something learned about the feature]
- [Something that didn't work as expected]

---

## 🔄 Handoff to Next Session

### Git State
**Branch**: main
**Commits this session**: [X]
**Git status**: ☐ Clean / ☐ Uncommitted changes
**Pushed to GitHub**: ☐ Yes / ☐ No

### Feature Status Update

**features.json updated**: ☐ Yes / ☐ No
**passes field**: ☐ true / ☐ false

If incomplete:
- **Completion estimate**: [X% or X more sessions]
- **Notes added to description**: ☐ Yes / ☐ No

### Next Session TODO
1. [Specific next step]
2. [Specific next step]
3. [Specific next step]

### Context for Next Agent
[Critical information that next agent needs to know]
[Any gotchas or non-obvious aspects]
[Where to pick up if continuing this feature]

---

## 📝 Progress File Update

**claude-progress.txt updated**: ☐ Yes / ☐ No

**Content added**:
```
Session X (YYYY-MM-DD):
- [Brief summary of work]
- [Key decisions]
- [Next steps]
```

---

## ✅ Pre-Push Checklist

Before ending session:

- [ ] All code committed with clear messages
- [ ] features.json updated
- [ ] claude-progress.txt updated
- [ ] Code is in merge-ready state (no TODOs, no broken functionality)
- [ ] Tests passing (or noted why not)
- [ ] README updated if needed
- [ ] No sensitive data in commits
- [ ] Git pushed to GitHub

---

## 📈 Metrics

**Time spent**: [Approximate]
**Tokens used**: [If tracked]
**Commits made**: [X]
**Tests added**: [X]
**Lines changed**: [+X / -Y]

---

**Session End Time**: [HH:MM]

**Overall Session Rating**: ⭐⭐⭐⭐⭐ (1-5)

**Notes for Future Sessions**:
[Any process improvements or lessons learned]
