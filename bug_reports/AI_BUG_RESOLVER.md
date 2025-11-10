# AI Bug Resolver Workflow

## Overview

This document describes how AI assistants can automatically fix bugs in the system using the streamlined AI workflow functions.

## AI Workflow (3 Simple Steps)

### 1. Get Bugs to Fix

```python
bugs = await get_bugs_for_ai(status="Assigned", severity="Critical", limit=10)
```

**Parameters:**
- `status` - Filter by status (default: "Assigned")
  - Options: New, Triaged, Assigned, In Progress, Good-to-Test, Resolved, Dismissed
- `severity` - Filter by severity (optional)
  - Options: Critical, High, Medium, Low
- `limit` - Max bugs to return (default: 10)

**Returns:** Array of bugs with all details (JSON, no HTML)

```json
[
  {
    "bug_id": "uuid-here",
    "title": "Null pointer exception in login",
    "description": "App crashes when user clicks login...",
    "reproduction_steps": "1. Open app\n2. Click login\n3. Crash",
    "severity": "Critical",
    "category": "Backend",
    "status": "Assigned",
    "assigned_to": "AI_Assistant",
    "progress_notes": null,
    "reported_at": "2025-01-08 10:30:00"
  }
]
```

### 2. Get Full Bug Details (Optional)

```python
bug = await get_bug_details(bug_id)
```

**Returns:** Complete bug data including:
- Description and reproduction steps
- System info and log context
- Screenshot path (if available)
- All progress notes and history

### 3. Fix Bug and Mark for Testing

```python
await ai_fix_bug(bug_id, "Fixed null pointer in user_service.py:142 by adding null check before user.getName() call")
```

**Parameters:**
- `bug_id` - The bug to mark as fixed
- `fix_notes` - Detailed description of what you changed
  - Be specific: mention files, line numbers, what was changed

**What Happens:**
- ✅ Status automatically changes to "Good-to-Test"
- ✅ Fix notes appended with timestamp and AI name
- ✅ Bug appears in human testing queue (`bugs_ready_for_testing()`)
- ✅ Human can verify, resolve, or send back with notes

## Complete Example

```python
# Get critical bugs assigned to me
bugs = await get_bugs_for_ai(status="Assigned", severity="Critical")

if not bugs:
    print("No critical bugs to fix!")
    return

# Pick the first bug
bug = bugs[0]
print(f"Working on: {bug['title']}")

# Get full details if needed
details = await get_bug_details(bug["bug_id"])
print(f"Reproduction steps:\n{details['reproduction_steps']}")

# AI analyzes the code, finds the issue, makes fixes...
# Example: Read file, edit file, test changes

# Mark as fixed
await ai_fix_bug(
    bug["bug_id"],
    """Fixed null pointer exception in user_service.py:142

    Changes made:
    - Added null check before user.getName() call
    - Added error logging for debugging
    - Added unit test to prevent regression

    Files changed:
    - src/user_service.py (line 142)
    - tests/test_user_service.py (added test_login_null_user)
    """
)
```

## Human Testing Workflow

After AI marks bug as "Good-to-Test":

1. **Human calls** `bugs_ready_for_testing()`
   - Sees all bugs marked as "Good-to-Test"
   - Sees AI's fix notes

2. **Human tests the fix:**
   - ✅ **Works?** → Click "Resolve" → Bug marked as Resolved
   - ❌ **Broken?** → Click "Send Back" → Bug returns to Assigned with tester notes

3. **If sent back:**
   - AI sees updated progress_notes with tester feedback
   - AI can fix again and re-submit for testing

## Why This Works

- **No intermediate statuses** - AI either fixes it or doesn't (no "In Progress" needed)
- **Fast iteration** - AI fixes → Human tests → Feedback loop
- **Clear communication** - Fix notes show exactly what changed
- **Automatic routing** - "Good-to-Test" status auto-populates testing queue
- **Human verification** - Humans always verify AI fixes before marking resolved

## Tips for AI

1. **Be specific in fix_notes** - Mention exact files and line numbers
2. **Include context** - Explain WHY you made the change
3. **Test your fix** - Run the code before marking as fixed
4. **Read repro steps** - Follow the exact steps to reproduce before fixing
5. **Check system_info** - Some bugs are environment-specific

## Integration with Human Workflow

Humans use these functions:
- `assign_bugs_interactive()` - Manager assigns bugs to AI or humans
- `my_assigned_bugs_html()` - Devs see their assigned bugs
- `update_my_bug_progress()` - Humans update status manually
- `bugs_ready_for_testing()` - Testers verify AI and human fixes
- `team_bug_dashboard()` - Manager sees all bug assignments

AI uses these functions:
- `get_bugs_for_ai()` - Get bugs to fix
- `get_bug_details()` - Read full bug details
- `ai_fix_bug()` - Mark as fixed and ready for testing

Both workflows converge at **"Good-to-Test"** status where humans verify all fixes!
