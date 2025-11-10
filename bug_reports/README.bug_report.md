# Bug Report System - Complete Documentation

## Overview

Comprehensive bug tracking and resolution system with workflows for:
- **Users** - Report bugs with screenshots and system info
- **Managers** - Triage, assign, and track bugs
- **Developers** - Work on assigned bugs and update progress
- **Testers** - Verify fixes and provide feedback
- **AI Assistants** - Automatically fix bugs

## Table of Contents

1. [Bug Lifecycle](#bug-lifecycle)
2. [User Functions](#user-functions)
3. [Manager Functions](#manager-functions)
4. [Developer Functions](#developer-functions)
5. [Tester Functions](#tester-functions)
6. [AI Functions](#ai-functions)
7. [Database Schema](#database-schema)
8. [Status Flow](#status-flow)

---

## Bug Lifecycle

```
┌─────────────┐
│   Report    │ User reports bug
│   (New)     │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│   Triage    │ Manager categorizes/prioritizes
│  (Triaged)  │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│   Assign    │ Manager assigns to dev/AI
│ (Assigned)  │
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  Fix Bug    │ Dev/AI makes code changes
│(In Progress)│
└─────┬───────┘
      │
      ▼
┌──────────────┐
│ Ready to Test│ Dev/AI marks as fixed
│(Good-to-Test)│
└─────┬────────┘
      │
      ▼
┌──────────────┐     ┌──────────────┐
│  Tester      │────>│  Send Back   │ (if broken)
│  Verifies    │     │ (Assigned)   │
└─────┬────────┘     └──────────────┘
      │
      ▼
┌──────────────┐
│  Resolved    │ Tester confirms fix
│  (Resolved)  │
└──────────────┘
```

---

## User Functions

### `report_bug_chrome()`
Open bug report form with auto-capture of browser state.

**Features:**
- Screenshot auto-capture
- Console logs collection
- System info detection
- Reproduction steps input

**Workflow:**
1. User calls `report_bug_chrome()`
2. Form pre-fills with screenshot and system info
3. User fills title, description, reproduction steps
4. Submits → Bug created with status "New"

---

## Manager Functions

### `manage_bug_reports(limit=50)`
Admin interface to triage bugs - assign severity/category, dismiss, or resolve.

**Features:**
- Scroll through bugs one at a time
- Set severity: Critical, High, Medium, Low
- Set category: UI, Backend, Performance, Security, etc.
- Dismiss invalid bugs
- Quick resolve for duplicates

**Workflow:**
1. Manager calls `manage_bug_reports()`
2. Reviews each bug
3. Sets severity and category
4. Status changes to "Triaged"

### `assign_bugs_interactive()`
Assign triaged bugs to developers or AI assistants.

**Features:**
- Grouped by severity (Critical → Low)
- Checkbox selection for bulk assign
- Auto-assigns to current user's username

**Workflow:**
1. Manager calls `assign_bugs_interactive()`
2. Selects bugs with checkboxes
3. Clicks "Assign Selected to Me"
4. Bugs assigned to manager's username
5. Status changes to "Assigned"

### `team_bug_dashboard()`
Overview of all bugs assigned to team members.

**Shows:**
- Developer name (username, not client_id)
- Number of bugs assigned
- Bug titles and severities
- Current status of each bug

**Use:** Track team workload and progress

---

## Developer Functions

### `my_assigned_bugs_table()`
Compact table view of your assigned bugs.

**Shows:**
- Bug ID, title, severity, status
- Truncated description (80 chars)
- Assigned date

**Use:** Quick overview of to-do list

### `my_assigned_bugs_html()`
Detailed HTML card view of your assigned bugs.

**Shows:**
- Full description (not truncated)
- Complete reproduction steps
- All progress notes with timestamps
- Color-coded severity and status badges
- Category and assignment info

**Features:**
- Scrollable cards (max 700px)
- Red theme styling
- All details visible at once

**Use:** Deep dive into bug details before fixing

### `update_my_bug_progress()`
Update status and add progress notes for your bugs.

**Features:**
- Pre-filled form with all assigned bugs
- Status dropdown: Assigned → In Progress → Good-to-Test
- Progress notes textarea
- Bulk update all bugs at once

**Workflow:**
1. Dev calls `update_my_bug_progress()`
2. Changes status (e.g., Assigned → In Progress)
3. Adds notes: "Investigating null pointer in user_service.py"
4. Clicks "Save All Updates"
5. When fixed, sets status to "Good-to-Test"

---

## Tester Functions

### `bugs_ready_for_testing()`
Testing queue showing all bugs marked as "Good-to-Test".

**Features:**
- Shows all bugs from any developer/AI
- Displays fix notes and progress history
- Two actions per bug:
  - ✅ **Resolve** - Mark as fixed and working
  - ↩️ **Send Back** - Return to dev with feedback notes

**Workflow:**

**If fix works:**
1. Tester calls `bugs_ready_for_testing()`
2. Reviews bug and fix notes
3. Tests the fix
4. Clicks "Resolve"
5. Status changes to "Resolved"

**If fix broken:**
1. Tester calls `bugs_ready_for_testing()`
2. Reviews bug and fix notes
3. Tests the fix → Still broken
4. Clicks "Send Back to Dev"
5. Enters notes: "Still crashes on login with empty username"
6. Bug returns to "Assigned" status
7. Notes appended to progress_notes with timestamp

### `audit_resolved_bugs(limit=50)`
View resolved bugs for audit trail.

**Shows:**
- Bug title, severity, category
- Who fixed it (developer/AI name)
- When reported and when resolved
- Progress notes summary

**Use:** Historical record of fixes

---

## AI Functions

See [AI_BUG_RESOLVER.md](./AI_BUG_RESOLVER.md) for complete AI workflow documentation.

### `get_bugs_for_ai(status="Assigned", severity=None, limit=10)`
Get bugs as structured JSON for AI processing.

**Returns:** Array of bugs with all details (no HTML)

**Example:**
```python
bugs = await get_bugs_for_ai(status="Assigned", severity="Critical")
```

### `get_bug_details(bug_id)`
Get full details of a specific bug.

**Returns:** Complete bug data including:
- Description and reproduction steps
- System info and log context
- Screenshot path
- All progress notes

**Example:**
```python
bug = await get_bug_details("uuid-here")
print(bug["reproduction_steps"])
```

### `ai_fix_bug(bug_id, fix_notes)`
Mark bug as fixed after AI makes code changes.

**Automatically:**
- Sets status to "Good-to-Test"
- Appends fix notes with timestamp
- Adds AI name to notes
- Makes bug appear in testing queue

**Example:**
```python
await ai_fix_bug(
    "uuid-here",
    "Fixed null pointer in user_service.py:142 by adding null check"
)
```

---

## Database Schema

### bug_reports table

| Column | Type | Description |
|--------|------|-------------|
| bug_id | TEXT | UUID primary key |
| user_id | TEXT | Reporter's user ID |
| username | TEXT | Reporter's username |
| session_id | TEXT | Session identifier |
| title | TEXT | Bug title |
| description | TEXT | Full description |
| reproduction_steps | TEXT | How to reproduce |
| severity | TEXT | Critical, High, Medium, Low |
| category | TEXT | UI, Backend, Performance, etc. |
| system_info | TEXT | OS, browser, versions |
| log_context | TEXT | Error logs and console output |
| screenshot_path | TEXT | Path to screenshot file |
| screenshot_name | TEXT | Screenshot filename |
| status | TEXT | New, Triaged, Assigned, etc. |
| assigned_to | TEXT | Developer/AI username |
| assigned_at | TIMESTAMP | When assigned |
| progress_notes | TEXT | Running log of updates |
| reported_at | TIMESTAMP | When bug was reported |
| updated_at | TIMESTAMP | Last modification time |

---

## Status Flow

### Status Values

1. **New** - Just reported, not yet reviewed
2. **Triaged** - Manager reviewed and categorized
3. **Assigned** - Assigned to developer/AI
4. **In Progress** - Developer actively working on it
5. **Good-to-Test** - Fix complete, ready for testing
6. **Resolved** - Tester verified fix works
7. **Dismissed** - Invalid/duplicate/won't fix

### Status Transitions

```
New → Triaged (via manage_bug_reports)
Triaged → Assigned (via assign_bugs_interactive)
Assigned → In Progress (via update_my_bug_progress)
In Progress → Good-to-Test (via update_my_bug_progress or ai_fix_bug)
Good-to-Test → Resolved (via bugs_ready_for_testing → Resolve)
Good-to-Test → Assigned (via bugs_ready_for_testing → Send Back)
Any → Dismissed (via manage_bug_reports)
```

---

## Complete Workflows

### Human Developer Workflow

1. Manager assigns bugs → `assign_bugs_interactive()`
2. Dev checks assigned bugs → `my_assigned_bugs_html()`
3. Dev picks a bug to work on
4. Dev updates status to "In Progress" → `update_my_bug_progress()`
5. Dev fixes the code
6. Dev adds notes and sets to "Good-to-Test" → `update_my_bug_progress()`
7. Tester verifies → `bugs_ready_for_testing()`
8. ✅ Works → Resolve OR ❌ Broken → Send Back

### AI Developer Workflow

1. Manager assigns bugs → `assign_bugs_interactive()`
2. AI gets assigned bugs → `get_bugs_for_ai(status="Assigned")`
3. AI reads bug details → `get_bug_details(bug_id)`
4. AI analyzes code, makes fixes
5. AI marks as fixed → `ai_fix_bug(bug_id, fix_notes)`
6. Tester verifies → `bugs_ready_for_testing()`
7. ✅ Works → Resolve OR ❌ Broken → Send Back with notes
8. If sent back, AI sees notes in `get_bug_details()` and tries again

---

## Function Reference

### User Functions
- `report_bug_chrome()` - Report bug with browser state capture

### Manager Functions
- `manage_bug_reports(limit=50)` - Triage bugs
- `assign_bugs_interactive()` - Assign bugs to devs/AI
- `team_bug_dashboard()` - View team workload
- `list_bug_reports(status=None, severity=None, limit=50)` - List bugs with filters
- `view_bug_report(bug_id)` - View single bug details

### Developer Functions
- `my_assigned_bugs_table()` - Compact table view
- `my_assigned_bugs_html()` - Detailed card view
- `update_my_bug_progress()` - Update status and notes

### Tester Functions
- `bugs_ready_for_testing()` - Testing queue
- `audit_resolved_bugs(limit=50)` - Resolved bugs history

### AI Functions
- `get_bugs_for_ai(status, severity, limit)` - Get bugs as JSON
- `get_bug_details(bug_id)` - Get full bug info
- `ai_fix_bug(bug_id, fix_notes)` - Mark as fixed

### Admin Functions
- `update_bug_severity(bug_id, severity)` - Change severity
- `update_bug_category(bug_id, category)` - Change category
- `update_bug_status(bug_id, status)` - Change status directly

---

## Best Practices

### For Users Reporting Bugs
- Write clear, specific titles
- Include exact reproduction steps
- Attach screenshots when possible
- Mention what you expected vs what happened

### For Managers
- Triage bugs daily to keep queue flowing
- Set severity accurately (Critical = system down, Low = minor annoyance)
- Assign based on expertise and workload
- Use categories to track bug patterns

### For Developers
- Update progress regularly so testers know status
- Be specific in notes (file names, line numbers)
- Test your fix before marking "Good-to-Test"
- If stuck, add notes explaining blocker

### For Testers
- Test against original reproduction steps
- If sending back, be specific about what's still broken
- Include new error messages or behaviors
- Verify edge cases, not just happy path

### For AI Assistants
- Read full bug details including reproduction steps
- Be extremely specific in fix_notes (files, lines, changes)
- Test fixes before marking "Good-to-Test"
- If sent back, carefully read tester feedback

---

## File Structure

```
dynamic_functions/
├── bug_report.py              # All bug tracking functions
├── README.bug_report.md       # This file
├── AI_BUG_RESOLVER.md         # AI workflow documentation
├── bug_reports.db             # SQLite database
├── json/                      # Bug report JSON exports
│   └── bug_*.json
└── screenshots/               # Bug screenshots
    └── screenshot_*.png
```

---

## Troubleshooting

### "No bugs assigned to you" but I know there are bugs
- Bugs might be assigned to your `client_id` instead of username
- Functions now check both - restart server if issue persists

### Screenshot not capturing
- Make sure you're using Chrome with MCP DevTools
- Check browser permissions for screenshots

### AI can't see bugs
- Make sure bugs are in "Assigned" status
- Check `get_bugs_for_ai()` filters match bug properties

### Tester notes not showing up
- Check `progress_notes` field in `get_bug_details()`
- Notes are appended with timestamps, scroll to bottom

---

## Support

For issues or feature requests, file a bug using `report_bug_chrome()` with category "Bug Tracker" 😉
