import atlantis
import sqlite3
import uuid
import json
import os
import base64
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("mcp_client")

async def _init_bug_db():
    """Initialize bug reports database and return a persistent connection."""
    existing_db = atlantis.shared.get("bug_db")
    if existing_db:
        logger.info(f"Reusing existing bug_db connection: {existing_db}")
        return existing_db

    db_path = os.path.join(os.path.dirname(__file__), "bug_reports.db")
    logger.info(f"Creating NEW bug_db connection at: {db_path}")
    db = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = DELETE")

    # Bug reports table
    db.execute('''
        CREATE TABLE IF NOT EXISTS bug_reports (
            bug_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            session_id TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            reproduction_steps TEXT,
            severity TEXT,
            category TEXT,
            system_info TEXT,
            log_context TEXT,
            screenshot_path TEXT,
            screenshot_name TEXT,
            status TEXT DEFAULT 'New',
            assigned_to TEXT,
            assigned_at TIMESTAMP,
            progress_notes TEXT,
            reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add new columns if they don't exist (for existing databases)
    try:
        db.execute("ALTER TABLE bug_reports ADD COLUMN assigned_at TIMESTAMP")
        logger.info("Added assigned_at column")
    except sqlite3.OperationalError as e:
        logger.info(f"assigned_at column already exists or error: {e}")

    try:
        db.execute("ALTER TABLE bug_reports ADD COLUMN progress_notes TEXT")
        logger.info("Added progress_notes column")
    except sqlite3.OperationalError as e:
        logger.info(f"progress_notes column already exists or error: {e}")

    db.commit()
    logger.info("Bug reports database initialized")

    atlantis.shared.set("bug_db", db)
    return db

@visible
async def report_bug():
    """Report a bug with detailed information including screenshots. Opens a form to collect bug details."""
    caller = atlantis.get_caller() or "unknown"

    FORM_ID = f"bug_{str(uuid.uuid4()).replace('-', '')[:8]}"

    htmlStr = f'''
    <div style="white-space:normal;padding: 20px;
                background: linear-gradient(135deg, #1a0a0a 0%, #2d1b1b 100%);
                border: 2px solid #8b0000;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(139,0,0,0.5);
                box-sizing: border-box;">
        <h2 style="margin-top: 0; color: #ff4444; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">🐛 Bug Report</h2>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Title *</label>
            <input type="text" id="title_{FORM_ID}" placeholder="Brief description of the bug..."
                   style="width: 700px; padding: 10px; background: #2a1a1a; border: 1px solid #8b0000;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Description *</label>
            <textarea id="description_{FORM_ID}" placeholder="What happened? What did you expect to happen?"
                      rows="4"
                      style="width: 100%; padding: 10px; background: #2a1a1a; border: 1px solid #8b0000;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">How to Reproduce (optional)</label>
            <textarea id="reproduction_steps_{FORM_ID}" placeholder="Step 1: ...\nStep 2: ...\nStep 3: ..."
                      rows="4"
                      style="width: 100%; padding: 10px; background: #2a1a1a; border: 1px solid #8b0000;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Relevant Logs / Error Messages (optional)</label>
            <textarea id="log_context_{FORM_ID}" placeholder="Paste any error messages or relevant log entries (include timestamps if available)..."
                      rows="4"
                      style="width: 100%; padding: 10px; background: #2a1a1a; border: 1px solid #8b0000;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical; font-family: monospace; font-size: 12px;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Screenshot (optional)</label>
            <div style="position: relative;">
                <label for="screenshot_{FORM_ID}" style="
                    display: inline-block;
                    padding: 10px 20px;
                    background: linear-gradient(145deg, #5a2a2a 0%, #3a1a1a 100%);
                    color: #ffaaaa;
                    border: 1px solid #8b0000;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">
                    📷 Choose Screenshot
                </label>
                <input type="file" id="screenshot_{FORM_ID}" accept="image/*"
                       style="position: absolute; opacity: 0; pointer-events: none;">
                <span id="screenshot_name_{FORM_ID}" style="color: #aaa; margin-left: 10px; font-size: 12px;">No file selected</span>
            </div>
            <div id="screenshot_preview_{FORM_ID}" style="margin-top: 10px;"></div>
        </div>

        <button id="submit_{FORM_ID}"
                style="padding: 12px 30px;
                       background: linear-gradient(145deg, #8b0000 0%, #5a0000 100%);
                       color: #fff;
                       border: 1px solid #ff0000;
                       border-radius: 6px;
                       cursor: pointer;
                       font-weight: bold;
                       font-size: 16px;
                       box-shadow: 0 4px 8px rgba(139,0,0,0.4);
                       width: 100%;">
            🐛 Submit Bug Report
        </button>
    </div>
    '''

    await atlantis.client_html(htmlStr)

    miniscript = '''
    //js
    let foo = function() {
        thread.console.bold('Bug report form script executing');

        const titleField = document.getElementById('title_{FORM_ID}');
        const descField = document.getElementById('description_{FORM_ID}');
        const reproField = document.getElementById('reproduction_steps_{FORM_ID}');
        const logsField = document.getElementById('log_context_{FORM_ID}');
        const screenshotInput = document.getElementById('screenshot_{FORM_ID}');
        const screenshotName = document.getElementById('screenshot_name_{FORM_ID}');
        const screenshotPreview = document.getElementById('screenshot_preview_{FORM_ID}');
        const submitBtn = document.getElementById('submit_{FORM_ID}');

        let screenshotData = null;
        let screenshotFilename = null;

        // Handle screenshot selection
        screenshotInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                screenshotFilename = file.name;
                screenshotName.textContent = file.name;
                screenshotName.style.color = '#4CAF50';

                // Show preview
                const reader = new FileReader();
                reader.onload = function(event) {
                    screenshotData = event.target.result;
                    screenshotPreview.innerHTML = '<img src="' + event.target.result + '" style="max-width: 100%; border-radius: 6px; border: 1px solid #8b0000; margin-top: 5px;">';
                };
                reader.readAsDataURL(file);
            }
        });

        // Submit button
        submitBtn.addEventListener('click', async function() {
            // Validation
            if (!titleField.value.trim()) {
                alert('Please enter a bug title');
                return;
            }
            if (!descField.value.trim()) {
                alert('Please enter a bug description');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Submitting...';

            let data = {
                title: titleField.value.trim(),
                description: descField.value.trim(),
                reproduction_steps: reproField.value.trim() || null,
                log_context: logsField.value.trim() || null,
                screenshot_data: screenshotData,
                screenshot_name: screenshotFilename
            };

            thread.console.info('Submitting bug report');

            try {
                let content = '@*submit_bug_report';
                await sendChatter(eventData.connAccessToken, content, data);
                submitBtn.textContent = '✓ Submitted!';
                submitBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            } catch (error) {
                thread.console.error('Error submitting bug report:', error);
                submitBtn.textContent = 'Error - Try Again';
                submitBtn.disabled = false;
                submitBtn.style.background = 'linear-gradient(145deg, #8b0000 0%, #5a0000 100%)';
            }
        });
    }
    foo()
    '''

    miniscript = miniscript.replace("{FORM_ID}", FORM_ID)
    await atlantis.client_script(miniscript)
@visible
async def submit_bug_report(
    title: str,
    description: str,
    reproduction_steps: Optional[str] = None,
    log_context: Optional[str] = None,
    screenshot_data: Optional[str] = None,
    screenshot_name: Optional[str] = None
):
    """Internal handler for bug report submission. Called automatically when user submits the form."""
    username = atlantis.get_caller() or "unknown"
    user_id = atlantis.get_client_id() or str(uuid.uuid4())
    session_id = atlantis.get_session_id() or "unknown"

    # Get system info automatically from the MCP environment
    import platform
    system_info = f"{platform.system()} {platform.release()} - Python {platform.python_version()}"

    db = await _init_bug_db()
    bug_id = str(uuid.uuid4())

    # Handle screenshot if provided
    screenshot_path = None
    if screenshot_data and screenshot_name:
        try:
            # Decode base64 screenshot
            if screenshot_data.startswith('data:'):
                screenshot_data = screenshot_data.split(',')[1]

            screenshot_bytes = base64.b64decode(screenshot_data)

            # Create screenshots directory
            screenshots_dir = os.path.join(os.path.dirname(__file__), "bug_screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            # Save screenshot
            safe_filename = f"{bug_id}_{screenshot_name}"
            screenshot_path = os.path.join(screenshots_dir, safe_filename)

            with open(screenshot_path, 'wb') as f:
                f.write(screenshot_bytes)

            logger.info(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.error(f"Error saving screenshot: {e}")
            screenshot_path = None

    # Insert bug report
    db.execute('''
        INSERT INTO bug_reports (
            bug_id, user_id, username, session_id, title, description, reproduction_steps,
            system_info, log_context, screenshot_path, screenshot_name, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New')
    ''', (
        bug_id, user_id, username, session_id, title, description, reproduction_steps,
        system_info, log_context, screenshot_path, screenshot_name
    ))

    db.commit()

    result = [{
        "Field": "Bug ID",
        "Value": bug_id
    }, {
        "Field": "Title",
        "Value": title
    }, {
        "Field": "Session",
        "Value": session_id
    }, {
        "Field": "System",
        "Value": system_info
    }]

    if screenshot_path:
        result.append({"Field": "Screenshot", "Value": screenshot_name})

    await atlantis.client_data("✅ Bug Report Submitted", result)
    logger.info(f"Bug {bug_id} reported by {username}: {title}")

@visible
async def list_bug_reports(status: Optional[str] = None, severity: Optional[str] = None, limit: int = 20):
    """List bug reports with optional filtering by status or severity. Shows most recent bugs first. Excludes Dismissed and Resolved by default."""
    db = await _init_bug_db()

    # Convert string "none" to None
    if status and status.lower() == "none":
        status = None
    if severity and severity.lower() == "none":
        severity = None

    logger.info(f"list_bug_reports called with status={status}, severity={severity}, limit={limit}")
    logger.info(f"Database object: {db}")

    query = "SELECT bug_id, title, severity, category, status, username, reported_at, screenshot_name FROM bug_reports WHERE status NOT IN ('Dismissed', 'Resolved')"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if severity:
        query += " AND severity = ?"
        params.append(severity)

    query += " ORDER BY reported_at DESC LIMIT ?"
    params.append(limit)

    logger.info(f"Executing query: {query}")
    logger.info(f"Query params: {params}")
    cursor = db.execute(query, params)

    rows = cursor.fetchall()
    logger.info(f"Query returned {len(rows)} rows")

    bugs = []
    for row in rows:
        bug_id, title, sev, cat, stat, user, reported, screenshot = row
        bugs.append({
            "bug_id": bug_id,
            "title": title,
            "severity": sev or "Unassigned",
            "category": cat or "Uncategorized",
            "status": stat,
            "reported_by": user,
            "reported_at": reported,
            "has_screenshot": "📸" if screenshot else ""
        })

    await atlantis.client_data(f"Bug Reports ({len(bugs)})", bugs)

@visible
async def view_bug_report(bug_id: str):
    """View full details of a specific bug report including screenshot."""
    db = await _init_bug_db()

    cursor = db.execute('''
        SELECT bug_id, username, title, description, reproduction_steps, severity,
               category, user_context, system_info, error_timestamp, log_context,
               screenshot_path, screenshot_name, status, assigned_to, reported_at
        FROM bug_reports WHERE bug_id = ?
    ''', (bug_id,))

    row = cursor.fetchone()
    if not row:
        await atlantis.client_log(f"❌ Bug report {bug_id} not found")
        return {"error": "Bug not found"}

    (bug_id, username, title, desc, repro, sev, cat, context, system,
     timestamp, logs, screenshot_path, screenshot_name, status, assigned, reported) = row

    # Display bug details
    await atlantis.client_log(f"🐛 Bug Report: {bug_id}")
    await atlantis.client_log(f"📋 Title: {title}")
    await atlantis.client_log(f"👤 Reported by: {username} at {reported}")
    await atlantis.client_log(f"🔴 Severity: {sev} | Category: {cat} | Status: {status}")
    if assigned:
        await atlantis.client_log(f"👨‍💻 Assigned to: {assigned}")
    await atlantis.client_log(f"\n📝 Description:\n{desc}")
    if repro:
        await atlantis.client_log(f"\n🔄 Reproduction Steps:\n{repro}")
    if context:
        await atlantis.client_log(f"\n💭 User Context: {context}")
    if system:
        await atlantis.client_log(f"\n💻 System: {system}")
    if timestamp:
        await atlantis.client_log(f"\n⏰ Error Time: {timestamp}")
    if logs:
        await atlantis.client_log(f"\n📋 Logs:\n{logs}")

    # Show screenshot if exists
    if screenshot_path and os.path.exists(screenshot_path):
        try:
            with open(screenshot_path, 'rb') as f:
                screenshot_bytes = f.read()
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            html = f'''
            <div style="margin: 15px 0; padding: 15px; background: #1a0a0a; border: 2px solid #8b0000; border-radius: 8px;">
                <h4 style="color: #ff4444; margin-top: 0;">📸 Screenshot: {screenshot_name}</h4>
                <img src="data:image/png;base64,{screenshot_base64}" style="max-width: 100%; border-radius: 6px; border: 1px solid #8b0000;">
            </div>
            '''
            await atlantis.client_html(html)
        except Exception as e:
            logger.error(f"Error loading screenshot: {e}")

    logger.info(f"report_bug completed successfully for bug_id={bug_id}, title={title}")

@visible
async def manage_bug_reports(limit: int = 20):
    """Opens an admin interface to manage bug reports - assign severity/category, dismiss, or resolve bugs. Shows one bug form at a time that you can scroll through."""
    logger.info(f"manage_bug_reports called with limit={limit}")

    db = await _init_bug_db()

    sql = '''
        SELECT bug_id, title, description, reproduction_steps, severity, category, status,
               username, reported_at, session_id, system_info, log_context, screenshot_path, screenshot_name
        FROM bug_reports
        WHERE status NOT IN ('Dismissed', 'Resolved')
        ORDER BY reported_at DESC
        LIMIT ?
    '''
    logger.info(f"Executing SQL: {sql}")
    logger.info(f"With limit: {limit}")

    cursor = db.execute(sql, (limit,))
    bugs = cursor.fetchall()

    logger.info(f"Found {len(bugs)} pending bug reports")

    if not bugs:
        logger.info("No pending bugs, returning early")
        await atlantis.client_log("✅ No pending bug reports to manage!")
        return

    FORM_ID = f"mgmt_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Build bug report cards
    cards_html = ""
    for idx, bug in enumerate(bugs):
        (bug_id, title, description, reproduction_steps, severity, category, status,
         username, reported_at, session_id, system_info, log_context, screenshot_path, screenshot_name) = bug

        severity = severity or ""
        category = category or ""

        # Load screenshot if exists
        screenshot_html = ""
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                with open(screenshot_path, 'rb') as f:
                    screenshot_bytes = f.read()
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                screenshot_html = f'''
                <div style="margin-top: 15px;">
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">📸 Screenshot: {screenshot_name}</label>
                    <img src="data:image/png;base64,{screenshot_base64}" style="max-width: 100%; border-radius: 6px; border: 1px solid #8b0000;">
                </div>
                '''
            except Exception as e:
                logger.error(f"Error loading screenshot: {e}")

        # Show first card by default, hide others
        display = "" if idx == 0 else "display: none;"

        cards_html += f'''
        <div class="bug-card-{FORM_ID}" id="card_{bug_id}" data-index="{idx}" style="{display} padding: 20px; background: #1a1a2a; border: 2px solid #5a5a8b; border-radius: 10px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="color: #ff6666; margin: 0;">Bug #{idx + 1} of {len(bugs)}</h3>
                <span style="color: #aaa; font-size: 12px;">ID: {bug_id[:13]}...</span>
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Title</label>
                <div style="padding: 10px; background: #0a0a1a; border: 1px solid #3a3a5a; border-radius: 4px; color: #fff;">
                    {title}
                </div>
            </div>

            <div style="margin-bottom: 15px;">
                <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Description</label>
                <div style="padding: 10px; background: #0a0a1a; border: 1px solid #3a3a5a; border-radius: 4px; color: #fff; white-space: pre-wrap;">
                    {description}
                </div>
            </div>

            {f'''
            <div style="margin-bottom: 15px;">
                <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Reproduction Steps</label>
                <div style="padding: 10px; background: #0a0a1a; border: 1px solid #3a3a5a; border-radius: 4px; color: #fff; white-space: pre-wrap;">
                    {reproduction_steps}
                </div>
            </div>
            ''' if reproduction_steps else ""}

            {f'''
            <div style="margin-bottom: 15px;">
                <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Logs / Error Messages</label>
                <div style="padding: 10px; background: #0a0a1a; border: 1px solid #3a3a5a; border-radius: 4px; color: #fff; white-space: pre-wrap; font-family: monospace; font-size: 11px;">
                    {log_context}
                </div>
            </div>
            ''' if log_context else ""}

            {screenshot_html}

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; padding: 15px; background: #0a0a1a; border-radius: 6px;">
                <div>
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-size: 12px;">Reported By</label>
                    <div style="color: #aaa;">{username}</div>
                </div>
                <div>
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-size: 12px;">Reported At</label>
                    <div style="color: #aaa;">{reported_at}</div>
                </div>
                <div>
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-size: 12px;">Session ID</label>
                    <div style="color: #aaa; font-family: monospace; font-size: 11px;">{session_id}</div>
                </div>
                <div>
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-size: 12px;">System</label>
                    <div style="color: #aaa; font-size: 11px;">{system_info or "N/A"}</div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                <div>
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Severity</label>
                    <select id="severity_{bug_id}" data-bugid="{bug_id}"
                            style="width: 100%; padding: 10px; background: #2a1a1a; border: 1px solid #8b0000;
                                   border-radius: 4px; color: #fff;">
                        <option value="" {"selected" if not severity else ""}>Unassigned</option>
                        <option value="Low" {"selected" if severity == "Low" else ""}>Low</option>
                        <option value="Medium" {"selected" if severity == "Medium" else ""}>Medium</option>
                        <option value="High" {"selected" if severity == "High" else ""}>High</option>
                        <option value="Critical" {"selected" if severity == "Critical" else ""}>Critical</option>
                    </select>
                </div>

                <div>
                    <label style="display: block; color: #ffaaaa; margin-bottom: 5px; font-weight: bold;">Category</label>
                    <select id="category_{bug_id}" data-bugid="{bug_id}"
                            style="width: 100%; padding: 10px; background: #2a1a1a; border: 1px solid #8b0000;
                                   border-radius: 4px; color: #fff;">
                        <option value="" {"selected" if not category else ""}>Uncategorized</option>
                        <option value="UI" {"selected" if category == "UI" else ""}>UI</option>
                        <option value="Performance" {"selected" if category == "Performance" else ""}>Performance</option>
                        <option value="Crash" {"selected" if category == "Crash" else ""}>Crash</option>
                        <option value="Data" {"selected" if category == "Data" else ""}>Data</option>
                        <option value="Network" {"selected" if category == "Network" else ""}>Network</option>
                        <option value="Other" {"selected" if category == "Other" else ""}>Other</option>
                    </select>
                </div>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 20px;">
                <button id="save_{bug_id}" data-bugid="{bug_id}" class="save-btn"
                        style="flex: 1; padding: 12px; background: linear-gradient(145deg, #2a5a7a 0%, #1a3a5a 100%);
                               color: #fff; border: 1px solid #3a7a9a; border-radius: 6px; cursor: pointer; font-weight: bold;">
                    💾 Save Changes
                </button>
                <button id="resolve_{bug_id}" data-bugid="{bug_id}" class="resolve-btn"
                        style="flex: 1; padding: 12px; background: linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%);
                               color: #fff; border: 1px solid #3a7a3a; border-radius: 6px; cursor: pointer; font-weight: bold;">
                    ✓ Mark Resolved
                </button>
                <button id="dismiss_{bug_id}" data-bugid="{bug_id}" class="dismiss-btn"
                        style="flex: 1; padding: 12px; background: linear-gradient(145deg, #5a2a2a 0%, #3a1a1a 100%);
                               color: #fff; border: 1px solid #7a3a3a; border-radius: 6px; cursor: pointer; font-weight: bold;">
                    ✕ Dismiss
                </button>
            </div>
        </div>
        '''

    html = f'''
    <div id="bug_mgmt_overlay_{FORM_ID}" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 9999; display: flex; align-items: center; justify-content: center;">
        <div id="bug_mgmt_container_{FORM_ID}" style="white-space:normal; padding: 20px; background: linear-gradient(135deg, #0a0a1a 0%, #1b1b2d 100%); border: 2px solid #5a5a8b; border-radius: 10px; box-shadow: 0 10px 30px rgba(90,90,139,0.5); box-sizing: border-box; max-width: 900px; max-height: 90vh; overflow-y: auto; position: relative;">
            <button id="close_btn_{FORM_ID}" style="position: absolute; top: 15px; right: 15px; background: #8b0000; color: #fff; border: 1px solid #ff0000; border-radius: 50%; width: 30px; height: 30px; cursor: pointer; font-size: 18px; font-weight: bold; line-height: 1;">✕</button>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-right: 40px;">
                <h2 style="margin: 0; color: #8a8aff; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">🛠️ Bug Report Management</h2>
                <div style="display: flex; gap: 10px;">
                    <button id="prev_btn_{FORM_ID}" style="padding: 8px 16px; background: #3a3a5a; color: #fff; border: 1px solid #5a5a7a; border-radius: 6px; cursor: pointer; font-weight: bold;">← Previous</button>
                    <button id="next_btn_{FORM_ID}" style="padding: 8px 16px; background: #3a3a5a; color: #fff; border: 1px solid #5a5a7a; border-radius: 6px; cursor: pointer; font-weight: bold;">Next →</button>
                </div>
            </div>
            <div id="cards_container_{FORM_ID}">
{cards_html}
            </div>
        </div>
    </div>
    '''

    await atlantis.client_html(html)

    script = f'''
    //js
    (function() {{
        thread.console.log('Bug management script loading...');

        const overlay = document.getElementById('bug_mgmt_overlay_{FORM_ID}');

        // Check if this form was already closed - don't reopen on refresh
        const wasClosedKey = 'bug_mgmt_closed_{FORM_ID}';
        if (sessionStorage.getItem(wasClosedKey) === 'true') {{
            thread.console.log('Form was already closed, removing on reload');
            if (overlay && overlay.parentNode) {{
                overlay.remove();
            }}
            return; // Exit script
        }}

        // Show the overlay since it's a fresh open
        if (overlay) {{
            overlay.style.display = 'flex';
        }}

        let currentIndex = 0;
        const totalBugs = {len(bugs)};
        const cards = document.querySelectorAll('.bug-card-{FORM_ID}');
        const prevBtn = document.getElementById('prev_btn_{FORM_ID}');
        const nextBtn = document.getElementById('next_btn_{FORM_ID}');
        const closeBtn = document.getElementById('close_btn_{FORM_ID}');

        // Track pending changes to apply on close
        const pendingChanges = [];

        thread.console.log('Found', cards.length, 'bug cards for form {FORM_ID}');

        // Force close function
        window.closeBugMgmt_{FORM_ID} = function() {{
            thread.console.log('Closing bug management, pending changes:', pendingChanges.length);

            // Mark as closed in sessionStorage so it doesn't reopen on refresh
            sessionStorage.setItem('bug_mgmt_closed_{FORM_ID}', 'true');

            // Cleanup event listeners BEFORE removing overlay
            if (closeBtn) {{
                closeBtn.replaceWith(closeBtn.cloneNode(true));
            }}
            document.removeEventListener('keydown', escHandler);

            // Apply changes BEFORE closing (synchronously)
            if (pendingChanges.length > 0) {{
                thread.console.log('Applying changes before close...');

                (async function() {{
                    for (const change of pendingChanges) {{
                        try {{
                            if (change.type === 'severity') {{
                                await sendChatter(eventData.connAccessToken, '@*update_bug_severity', {{
                                    bug_id: change.bug_id,
                                    severity: change.severity
                                }});
                            }} else if (change.type === 'category') {{
                                await sendChatter(eventData.connAccessToken, '@*update_bug_category', {{
                                    bug_id: change.bug_id,
                                    category: change.category
                                }});
                            }} else if (change.type === 'status') {{
                                await sendChatter(eventData.connAccessToken, '@*update_bug_status', {{
                                    bug_id: change.bug_id,
                                    status: change.status
                                }});
                            }}
                        }} catch (e) {{
                            thread.console.error('Error applying change:', e);
                        }}
                    }}
                    thread.console.log('Updates complete, removing overlay');

                    // Close AFTER changes are applied
                    if (overlay && overlay.parentNode) {{
                        overlay.remove();
                    }}

                    // Clean up global function reference
                    delete window.closeBugMgmt_{FORM_ID};
                }})();
            }} else {{
                // No pending changes, close immediately
                if (overlay && overlay.parentNode) {{
                    overlay.remove();
                }}

                // Clean up global function reference
                delete window.closeBugMgmt_{FORM_ID};
            }}
        }};

        // Close button handler
        closeBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            thread.console.log('Close button clicked');
            window.closeBugMgmt_{FORM_ID}();
        }});


        // Close on ESC key
        const escHandler = (e) => {{
            if (e.key === 'Escape') {{
                thread.console.log('ESC pressed, closing');
                window.closeBugMgmt_{FORM_ID}();
                document.removeEventListener('keydown', escHandler);
            }}
        }};
        document.addEventListener('keydown', escHandler);

        if (cards.length === 0) {{
            thread.console.error('No bug cards found!');
            return;
        }}

        function showCard(index) {{
            thread.console.log('Showing card', index);
            cards.forEach((card, i) => {{
                card.style.display = i === index ? 'block' : 'none';
            }});
            currentIndex = index;

            // Re-enable buttons after showing card
            prevBtn.disabled = false;
            nextBtn.disabled = false;
            prevBtn.style.opacity = '1';
            nextBtn.style.opacity = '1';
            prevBtn.style.cursor = 'pointer';
            nextBtn.style.cursor = 'pointer';

            // Disable if at boundaries
            if (index === 0) {{
                prevBtn.disabled = true;
                prevBtn.style.opacity = '0.5';
                prevBtn.style.cursor = 'not-allowed';
            }}
            if (index === totalBugs - 1) {{
                nextBtn.disabled = true;
                nextBtn.style.opacity = '0.5';
                nextBtn.style.cursor = 'not-allowed';
            }}
        }}

        prevBtn.addEventListener('click', (e) => {{
            e.preventDefault();
            e.stopPropagation();
            thread.console.log('Prev clicked');
            if (currentIndex > 0 && !prevBtn.disabled) {{
                showCard(currentIndex - 1);
            }}
        }});

        nextBtn.addEventListener('click', (e) => {{
            e.preventDefault();
            e.stopPropagation();
            thread.console.log('Next clicked');
            if (currentIndex < totalBugs - 1 && !nextBtn.disabled) {{
                showCard(currentIndex + 1);
            }}
        }});

        // Use event delegation on the OVERLAY (never changes)
        overlay.addEventListener('click', async function(e) {{
            const target = e.target;

            // Close on background click
            if (target === overlay) {{
                thread.console.log('Overlay background clicked, closing');
                window.closeBugMgmt_{FORM_ID}();
                return;
            }}

            // Save button handler
            if (target.classList.contains('save-btn')) {{
                e.stopPropagation();
                const bugId = target.dataset.bugid;
                const severity = document.getElementById('severity_' + bugId).value;
                const category = document.getElementById('category_' + bugId).value;

                thread.console.log('Queuing changes for bug', bugId);

                // Store changes locally (don't call server yet)
                pendingChanges.push({{
                    type: 'severity',
                    bug_id: bugId,
                    severity: severity
                }});
                pendingChanges.push({{
                    type: 'category',
                    bug_id: bugId,
                    category: category
                }});

                target.disabled = true;
                target.textContent = '✓ Saved!';
                target.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
                setTimeout(() => {{
                    target.disabled = false;
                    target.textContent = '💾 Save Changes';
                    target.style.background = 'linear-gradient(145deg, #2a5a7a 0%, #1a3a5a 100%)';
                }}, 2000);
            }}

            // Resolve button handler
            if (target.classList.contains('resolve-btn')) {{
                e.stopPropagation();
                const bugId = target.dataset.bugid;
                thread.console.log('Queuing resolve for bug', bugId);

                // Store change locally
                pendingChanges.push({{
                    type: 'status',
                    bug_id: bugId,
                    status: 'Resolved'
                }});

                target.disabled = true;
                target.textContent = '✓ Resolved!';
                setTimeout(() => {{
                    if (currentIndex < totalBugs - 1) {{
                        showCard(currentIndex + 1);
                    }} else if (currentIndex > 0) {{
                        showCard(currentIndex - 1);
                    }}
                }}, 1000);
            }}

            // Dismiss button handler
            if (target.classList.contains('dismiss-btn')) {{
                e.stopPropagation();
                const bugId = target.dataset.bugid;
                thread.console.log('Queuing dismiss for bug', bugId);

                // Store change locally
                pendingChanges.push({{
                    type: 'status',
                    bug_id: bugId,
                    status: 'Dismissed'
                }});

                target.disabled = true;
                target.textContent = '✕ Dismissed!';
                setTimeout(() => {{
                    if (currentIndex < totalBugs - 1) {{
                        showCard(currentIndex + 1);
                    }} else if (currentIndex > 0) {{
                        showCard(currentIndex - 1);
                    }}
                }}, 1000);
            }}
        }});

        // Don't call showCard(0) on load - first card is already visible in HTML
        thread.console.log('Bug management script loaded');
    }})();
    '''

    await atlantis.client_script(script)

@visible
async def update_bug_severity(bug_id: str, severity: str):
    """Update the severity of a bug report."""
    logger.info(f"update_bug_severity called with bug_id={bug_id}, severity={severity}")

    db = await _init_bug_db()

    if not severity:
        severity = None

    sql = "UPDATE bug_reports SET severity = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?"
    params = (severity, bug_id)

    logger.info(f"Executing SQL: {sql}")
    logger.info(f"With params: {params}")

    db.execute(sql, params)
    db.commit()

    await atlantis.client_log(f"✅ Bug {bug_id} severity updated to {severity}")
    logger.info(f"Bug {bug_id} severity updated to {severity}")
    logger.info(f"update_bug_severity completed successfully")

@visible
async def update_bug_category(bug_id: str, category: str):
    """Update the category of a bug report."""
    logger.info(f"update_bug_category called with bug_id={bug_id}, category={category}")

    db = await _init_bug_db()

    if not category:
        category = None

    sql = "UPDATE bug_reports SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?"
    params = (category, bug_id)

    logger.info(f"Executing SQL: {sql}")
    logger.info(f"With params: {params}")

    db.execute(sql, params)
    db.commit()

    await atlantis.client_log(f"✅ Bug {bug_id} category updated to {category}")
    logger.info(f"Bug {bug_id} category updated to {category}")
    logger.info(f"update_bug_category completed successfully")

@visible
async def update_bug_status(bug_id: str, status: str):
    """Update the status of a bug report (e.g., Resolved, Dismissed)."""
    logger.info(f"update_bug_status called with bug_id={bug_id}, status={status}")

    db = await _init_bug_db()

    sql = "UPDATE bug_reports SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?"
    params = (status, bug_id)

    logger.info(f"Executing SQL: {sql}")
    logger.info(f"With params: {params}")

    db.execute(sql, params)
    db.commit()

    await atlantis.client_log(f"✅ Bug {bug_id} status updated to {status}")
    logger.info(f"Bug {bug_id} status updated to {status}")
    logger.info(f"update_bug_status completed successfully")

# ============================================================
# Bug Assignment & To-Do List Functions
# ============================================================

@visible
async def assign_bugs_interactive():
    """
    Shows triaged bugs grouped by severity with checkboxes.
    Select bugs and click 'Assign to Me & Build To-Do List' to assign them to yourself.
    """
    logger.info("assign_bugs_interactive called")

    db = await _init_bug_db()

    # Get all triaged bugs (has severity/category, not yet assigned)
    sql = '''
        SELECT bug_id, title, severity, category, description, reported_at
        FROM bug_reports
        WHERE status IN ('New', 'Triaged')
        AND (assigned_to IS NULL OR assigned_to = '')
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END,
            reported_at DESC
    '''

    cursor = db.execute(sql)
    bugs = cursor.fetchall()

    if not bugs:
        await atlantis.client_log("✅ No unassigned bugs available!")
        return

    FORM_ID = f"assign_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Build bug cards with checkboxes
    bug_cards = ""
    for bug_id, title, severity, category, description, reported_at in bugs:
        sev_color = {
            'Critical': '#ff0000',
            'High': '#ff6600',
            'Medium': '#ffaa00',
            'Low': '#00aa00'
        }.get(severity, '#666')

        bug_cards += f'''
        <div style="margin: 10px 0; padding: 15px; background: rgba(26, 10, 10, 0.5);
                    border-left: 4px solid {sev_color}; border-radius: 6px;">
            <div style="display: flex; align-items: start; gap: 10px;">
                <input type="checkbox" id="bug_{bug_id}_{FORM_ID}" value="{bug_id}"
                       style="margin-top: 4px; width: 18px; height: 18px; cursor: pointer;">
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                        <h4 style="margin: 0; color: #ff4444; font-size: 16px;">{title}</h4>
                        <div style="display: flex; gap: 8px; flex-shrink: 0;">
                            <span style="padding: 4px 10px; background: {sev_color}; color: white;
                                        border-radius: 4px; font-size: 12px; font-weight: bold;">
                                {severity or 'Unset'}
                            </span>
                            {f'<span style="padding: 4px 10px; background: #444; color: #aaa; border-radius: 4px; font-size: 12px;">{category}</span>' if category else ''}
                        </div>
                    </div>
                    <p style="margin: 5px 0; color: #ccc; font-size: 13px;">{description[:150]}{'...' if len(description) > 150 else ''}</p>
                    <div style="font-size: 11px; color: #888;">
                        Bug ID: {bug_id} | Reported: {reported_at}
                    </div>
                </div>
            </div>
        </div>
        '''

    html = f'''
    <div style="white-space: normal; padding: 20px; background: linear-gradient(135deg, #1a0a0a 0%, #2d1b1b 100%);
                border: 2px solid #8b0000; border-radius: 10px; box-shadow: 0 10px 30px rgba(139,0,0,0.5);">
        <h2 style="margin-top: 0; color: #ff4444;">📋 Assign Bugs to My To-Do List</h2>
        <p style="color: #aaa; margin-bottom: 20px;">Select bugs to assign to yourself. They will appear in your to-do list.</p>

        <div id="bugList_{FORM_ID}" style="max-height: 600px; overflow-y: auto;">
            {bug_cards}
        </div>

        <div style="margin-top: 20px; padding: 15px; background: rgba(100, 0, 0, 0.2); border: 1px solid #aa0000; border-radius: 6px;">
            <button id="assignBtn_{FORM_ID}"
                    style="width: 100%; padding: 15px; background: linear-gradient(145deg, #8b0000 0%, #5a0000 100%);
                           color: white; border: 1px solid #ff0000; border-radius: 6px; cursor: pointer;
                           font-weight: bold; font-size: 16px;">
                ✅ Assign to Me & Build To-Do List
            </button>
        </div>
    </div>
    '''

    await atlantis.client_html(html)

    script = '''
    //js
    let foo = function() {
        const assignBtn = document.getElementById('assignBtn_{FORM_ID}');

        assignBtn.addEventListener('click', async function() {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]:checked');
            const bugIds = Array.from(checkboxes).map(cb => cb.value);

            if (bugIds.length === 0) {
                alert('Please select at least one bug!');
                return;
            }

            assignBtn.disabled = true;
            assignBtn.textContent = 'Assigning...';

            try {
                await sendChatter(eventData.connAccessToken, '@*_assign_bugs_to_me', { bug_ids: bugIds.join(',') });
                assignBtn.textContent = '✓ Assigned!';
                assignBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            } catch (error) {
                thread.console.error('Error assigning bugs:', error);
                assignBtn.textContent = 'Error - Try Again';
                assignBtn.disabled = false;
            }
        });
    }
    foo()
    '''

    script = script.replace("{FORM_ID}", FORM_ID)
    await atlantis.client_script(script)

    logger.info(f"assign_bugs_interactive completed, showed {len(bugs)} bugs")


@visible
async def _assign_bugs_to_me(bug_ids: str):
    """Internal handler called from assign_bugs_interactive form."""
    logger.info(f"_assign_bugs_to_me called with bug_ids={bug_ids}")

    client_id = atlantis.get_client_id()
    username = atlantis.get_caller() or client_id or "unknown"
    bug_id_list = [b.strip() for b in bug_ids.split(',') if b.strip()]

    db = await _init_bug_db()

    assigned_count = 0
    for bug_id in bug_id_list:
        db.execute('''
            UPDATE bug_reports
            SET assigned_to = ?, assigned_at = CURRENT_TIMESTAMP,
                status = 'Assigned', updated_at = CURRENT_TIMESTAMP
            WHERE bug_id = ?
        ''', (username, bug_id))
        assigned_count += 1

    db.commit()

    result = [{
        "Field": "Assigned To",
        "Value": username
    }, {
        "Field": "Bugs Assigned",
        "Value": str(assigned_count)
    }]

    await atlantis.client_data("✅ To-Do List Created", result)
    await atlantis.client_log(f"Use my_assigned_bugs() to view your to-do list!")

    logger.info(f"Assigned {assigned_count} bugs to {username}")


@visible
async def my_assigned_bugs_table():
    """View your assigned bugs as a table (compact view)."""
    logger.info("my_assigned_bugs_table called")

    client_id = atlantis.get_client_id()
    username = atlantis.get_caller() or client_id or "unknown"
    db = await _init_bug_db()

    sql = '''
        SELECT bug_id, title, severity, category, status, description,
               reproduction_steps, assigned_at, progress_notes
        FROM bug_reports
        WHERE (assigned_to = ? OR assigned_to = ?)
        AND status NOT IN ('Resolved', 'Dismissed')
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END,
            assigned_at DESC
    '''

    cursor = db.execute(sql, (username, client_id))
    rows = cursor.fetchall()

    if not rows:
        await atlantis.client_log(f"📭 No bugs currently assigned to you!")
        return

    bugs = []
    for bug_id, title, severity, category, status, description, repro_steps, assigned_at, progress_notes in rows:
        bugs.append({
            "bug_id": bug_id,
            "title": title,
            "severity": severity or "Unset",
            "category": category or "Uncategorized",
            "status": status,
            "description": description[:80] + "..." if len(description) > 80 else description,
            "assigned_at": assigned_at
        })

    await atlantis.client_data(f"🔧 My To-Do List ({len(bugs)} bugs)", bugs)
    logger.info(f"my_assigned_bugs_table returned {len(bugs)} bugs for {username}")


@visible
async def my_assigned_bugs_html():
    """View your assigned bugs with full details in HTML card format."""
    logger.info("my_assigned_bugs_html called")

    client_id = atlantis.get_client_id()
    username = atlantis.get_caller() or client_id or "unknown"
    db = await _init_bug_db()

    sql = '''
        SELECT bug_id, title, severity, category, status, description,
               reproduction_steps, assigned_at, progress_notes
        FROM bug_reports
        WHERE (assigned_to = ? OR assigned_to = ?)
        AND status NOT IN ('Resolved', 'Dismissed')
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END,
            assigned_at DESC
    '''

    cursor = db.execute(sql, (username, client_id))
    rows = cursor.fetchall()

    if not rows:
        await atlantis.client_log(f"📭 No bugs currently assigned to you!")
        return

    # Build HTML cards for each bug
    bug_cards = ""
    for bug_id, title, severity, category, status, description, repro_steps, assigned_at, progress_notes in rows:
        # Severity color
        sev_color = {
            'Critical': '#ff0000',
            'High': '#ff6600',
            'Medium': '#ffaa00',
            'Low': '#00aa00'
        }.get(severity, '#666')

        # Status color
        status_color = {
            'Assigned': '#666',
            'In Progress': '#0066ff',
            'Good-to-Test': '#00aa00'
        }.get(status, '#666')

        # Format repro steps
        repro_html = ""
        if repro_steps and repro_steps.strip():
            repro_html = f'''
            <div style="margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 4px;">
                <strong style="color: #ff8888;">Steps to Reproduce:</strong>
                <pre style="margin: 5px 0 0 0; white-space: pre-wrap; font-family: monospace; color: #ccc;">{repro_steps}</pre>
            </div>
            '''

        # Format progress notes
        notes_html = ""
        if progress_notes and progress_notes.strip():
            notes_html = f'''
            <div style="margin-top: 10px; padding: 10px; background: rgba(0,100,0,0.1); border-left: 3px solid #00aa00; border-radius: 4px;">
                <strong style="color: #88ff88;">Progress Notes:</strong>
                <pre style="margin: 5px 0 0 0; white-space: pre-wrap; font-family: monospace; color: #aaffaa;">{progress_notes}</pre>
            </div>
            '''

        bug_cards += f'''
        <div style="margin: 15px 0; padding: 20px; background: rgba(26, 10, 10, 0.7);
                    border-left: 5px solid {sev_color}; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.4);">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                <div style="flex: 1;">
                    <h3 style="margin: 0 0 5px 0; color: #ff4444;">{title}</h3>
                    <p style="margin: 0; color: #999; font-size: 13px;">Bug ID: <code style="background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 3px;">{bug_id}</code></p>
                </div>
                <div style="display: flex; gap: 8px; margin-left: 15px;">
                    <span style="padding: 6px 12px; background: {sev_color}; color: white;
                                border-radius: 4px; font-size: 12px; font-weight: bold; white-space: nowrap;">
                        {severity or 'Unset'}
                    </span>
                    <span style="padding: 6px 12px; background: {status_color}; color: white;
                                border-radius: 4px; font-size: 12px; font-weight: bold; white-space: nowrap;">
                        {status}
                    </span>
                </div>
            </div>

            <div style="margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 4px;">
                <strong style="color: #ff8888;">Description:</strong>
                <p style="margin: 5px 0 0 0; color: #ddd; line-height: 1.5;">{description}</p>
            </div>

            {repro_html}
            {notes_html}

            <div style="margin-top: 10px; padding: 8px; background: rgba(100,100,100,0.1); border-radius: 4px; font-size: 12px; color: #888;">
                <strong>Category:</strong> {category or 'Uncategorized'} | <strong>Assigned:</strong> {assigned_at or 'Unknown'}
            </div>
        </div>
        '''

    html = f'''
    <div style="white-space: normal; padding: 20px; background: linear-gradient(135deg, #1a0a0a 0%, #2d1b1b 100%);
                border: 2px solid #8b0000; border-radius: 10px; box-shadow: 0 10px 30px rgba(139,0,0,0.5); max-width: 1200px;">
        <h2 style="margin-top: 0; color: #ff4444;">🔧 My To-Do List</h2>
        <p style="color: #aaa; margin-bottom: 20px;">You have <strong style="color: #ff4444;">{len(rows)}</strong> bug(s) assigned to you.</p>

        <div style="max-height: 700px; overflow-y: auto; padding-right: 10px;">
            {bug_cards}
        </div>
    </div>
    '''

    await atlantis.client_html(html)
    logger.info(f"my_assigned_bugs_html returned {len(rows)} bugs for {username}")


@visible
async def update_my_bug_progress():
    """
    Prefilled form showing all YOUR assigned bugs with dropdowns to update status.
    Status options: Assigned → In Progress → Good-to-Test
    """
    logger.info("update_my_bug_progress called")

    client_id = atlantis.get_client_id()
    username = atlantis.get_caller() or client_id or "unknown"
    db = await _init_bug_db()

    sql = '''
        SELECT bug_id, title, severity, status, description
        FROM bug_reports
        WHERE (assigned_to = ? OR assigned_to = ?)
        AND status NOT IN ('Resolved', 'Dismissed')
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END
    '''

    cursor = db.execute(sql, (username, client_id))
    bugs = cursor.fetchall()

    if not bugs:
        await atlantis.client_log("📭 No bugs currently assigned to you!")
        return

    FORM_ID = f"progress_{str(uuid.uuid4()).replace('-', '')[:8]}"

    bug_rows = ""
    for bug_id, title, severity, status, description in bugs:
        sev_color = {
            'Critical': '#ff0000',
            'High': '#ff6600',
            'Medium': '#ffaa00',
            'Low': '#00aa00'
        }.get(severity, '#666')

        bug_rows += f'''
        <div style="margin: 15px 0; padding: 15px; background: rgba(26, 10, 10, 0.5);
                    border-left: 4px solid {sev_color}; border-radius: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 5px 0; color: #ff4444;">{title}</h4>
                    <p style="margin: 0; color: #999; font-size: 12px;">Bug ID: {bug_id}</p>
                    <p style="margin: 5px 0 0 0; color: #ccc; font-size: 13px;">{description[:100]}{'...' if len(description) > 100 else ''}</p>
                </div>
                <span style="padding: 4px 10px; background: {sev_color}; color: white;
                            border-radius: 4px; font-size: 12px; font-weight: bold; margin-left: 10px;">
                    {severity or 'Unset'}
                </span>
            </div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <label style="color: #aaa; font-size: 13px;">Status:</label>
                <select id="status_{bug_id}_{FORM_ID}" data-bug-id="{bug_id}"
                        style="padding: 8px; background: #1a2a2a; border: 1px solid #8b0000;
                               border-radius: 4px; color: #fff; flex: 1;">
                    <option value="Assigned" {'selected' if status == 'Assigned' else ''}>Assigned</option>
                    <option value="In Progress" {'selected' if status == 'In Progress' else ''}>In Progress</option>
                    <option value="Good-to-Test" {'selected' if status == 'Good-to-Test' else ''}>Good-to-Test</option>
                </select>
            </div>
            <div style="margin-top: 10px;">
                <label style="color: #aaa; font-size: 13px; display: block; margin-bottom: 5px;">Progress Notes:</label>
                <textarea id="notes_{bug_id}_{FORM_ID}" data-bug-id="{bug_id}"
                          placeholder="Add notes about your progress..."
                          style="width: 100%; padding: 8px; background: #1a2a2a; border: 1px solid #555;
                                 border-radius: 4px; color: #fff; min-height: 60px; resize: vertical; box-sizing: border-box;"></textarea>
            </div>
        </div>
        '''

    html = f'''
    <div style="white-space: normal; padding: 20px; background: linear-gradient(135deg, #1a0a0a 0%, #2d1b1b 100%);
                border: 2px solid #8b0000; border-radius: 10px; box-shadow: 0 10px 30px rgba(139,0,0,0.5);">
        <h2 style="margin-top: 0; color: #ff4444;">🔧 Update My Bug Progress</h2>
        <p style="color: #aaa; margin-bottom: 20px;">Update the status and add notes for your assigned bugs.</p>

        <div style="max-height: 600px; overflow-y: auto;">
            {bug_rows}
        </div>

        <button id="updateBtn_{FORM_ID}"
                style="width: 100%; padding: 15px; margin-top: 20px;
                       background: linear-gradient(145deg, #8b0000 0%, #5a0000 100%);
                       color: white; border: 1px solid #ff0000; border-radius: 6px; cursor: pointer;
                       font-weight: bold; font-size: 16px;">
            💾 Save All Updates
        </button>
    </div>
    '''

    await atlantis.client_html(html)

    script = '''
    //js
    let foo = function() {
        const updateBtn = document.getElementById('updateBtn_{FORM_ID}');

        updateBtn.addEventListener('click', async function() {
            const statusSelects = document.querySelectorAll('[id^="status_"][id$="_{FORM_ID}"]');
            const updates = [];

            statusSelects.forEach(select => {
                const bugId = select.dataset.bugId;
                const status = select.value;
                const notesField = document.getElementById('notes_' + bugId + '_{FORM_ID}');
                const notes = notesField ? notesField.value : '';

                updates.push({ bug_id: bugId, status: status, notes: notes });
            });

            updateBtn.disabled = true;
            updateBtn.textContent = 'Saving...';

            try {
                await sendChatter(eventData.connAccessToken, '@*_save_bug_progress', {
                    updates: JSON.stringify(updates)
                });
                updateBtn.textContent = '✓ Saved!';
                updateBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            } catch (error) {
                thread.console.error('Error updating bugs:', error);
                updateBtn.textContent = 'Error - Try Again';
                updateBtn.disabled = false;
            }
        });
    }
    foo()
    '''

    script = script.replace("{FORM_ID}", FORM_ID)
    await atlantis.client_script(script)

    logger.info(f"update_my_bug_progress completed for {username}, showed {len(bugs)} bugs")


@visible
async def _save_bug_progress(updates: str):
    """Internal handler for saving bug progress updates."""
    logger.info(f"_save_bug_progress called with updates={updates}")

    update_list = json.loads(updates)

    db = await _init_bug_db()

    for update in update_list:
        bug_id = update['bug_id']
        status = update['status']
        notes = update.get('notes', '')

        db.execute('''
            UPDATE bug_reports
            SET status = ?, progress_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bug_id = ?
        ''', (status, notes, bug_id))

    db.commit()

    await atlantis.client_log(f"✅ Updated {len(update_list)} bug(s) successfully!")
    logger.info(f"Updated {len(update_list)} bugs")


@visible
async def bugs_ready_for_testing():
    """
    Shows all bugs with status 'Good-to-Test'.
    Options: Mark as Resolved, or Send back to dev with notes.
    """
    logger.info("bugs_ready_for_testing called")

    db = await _init_bug_db()

    sql = '''
        SELECT bug_id, title, severity, category, assigned_to, description, progress_notes
        FROM bug_reports
        WHERE status = 'Good-to-Test'
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END
    '''

    cursor = db.execute(sql)
    bugs = cursor.fetchall()

    if not bugs:
        await atlantis.client_log("✅ No bugs waiting for testing!")
        return

    FORM_ID = f"testing_{str(uuid.uuid4()).replace('-', '')[:8]}"

    bug_cards = ""
    for bug_id, title, severity, category, assigned_to, description, progress_notes in bugs:
        sev_color = {
            'Critical': '#ff0000',
            'High': '#ff6600',
            'Medium': '#ffaa00',
            'Low': '#00aa00'
        }.get(severity, '#666')

        bug_cards += f'''
        <div style="margin: 15px 0; padding: 15px; background: rgba(26, 10, 10, 0.5);
                    border-left: 4px solid {sev_color}; border-radius: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 5px 0; color: #ff4444;">{title}</h4>
                    <p style="margin: 0; color: #999; font-size: 12px;">
                        Bug ID: {bug_id} | Dev: {assigned_to or 'Unassigned'}
                    </p>
                    <p style="margin: 5px 0 0 0; color: #ccc; font-size: 13px;">{description[:150]}{'...' if len(description) > 150 else ''}</p>
                    {f'<p style="margin: 8px 0 0 0; padding: 8px; background: rgba(0, 100, 100, 0.2); border-left: 2px solid #00aaaa; color: #aaffff; font-size: 12px;"><strong>Dev Notes:</strong> {progress_notes}</p>' if progress_notes else ''}
                </div>
                <div style="display: flex; gap: 8px; flex-shrink: 0; margin-left: 10px;">
                    <span style="padding: 4px 10px; background: {sev_color}; color: white;
                                border-radius: 4px; font-size: 12px; font-weight: bold;">
                        {severity or 'Unset'}
                    </span>
                    {f'<span style="padding: 4px 10px; background: #444; color: #aaa; border-radius: 4px; font-size: 12px;">{category}</span>' if category else ''}
                </div>
            </div>

            <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button class="resolveBtn" data-bug-id="{bug_id}"
                        style="flex: 1; min-width: 150px; padding: 10px; background: linear-gradient(145deg, #8b0000 0%, #5a0000 100%);
                               color: white; border: 1px solid #ff0000; border-radius: 4px; cursor: pointer; font-weight: bold;">
                    ✅ Mark Resolved
                </button>
                <button class="sendBackBtn" data-bug-id="{bug_id}" data-assigned-to="{assigned_to or ''}"
                        style="flex: 1; min-width: 150px; padding: 10px; background: linear-gradient(145deg, #aa6600 0%, #663300 100%);
                               color: white; border: 1px solid #ff9900; border-radius: 4px; cursor: pointer; font-weight: bold;">
                    ↩️ Send Back to Dev
                </button>
            </div>

            <div id="sendBackForm_{bug_id}_{FORM_ID}" style="display: none; margin-top: 10px;">
                <label style="color: #aaa; font-size: 13px; display: block; margin-bottom: 5px;">Reason to send back:</label>
                <textarea id="sendBackNotes_{bug_id}_{FORM_ID}"
                          placeholder="Explain what needs to be fixed..."
                          style="width: 100%; padding: 8px; background: #1a2a2a; border: 1px solid #555;
                                 border-radius: 4px; color: #fff; min-height: 80px; resize: vertical; box-sizing: border-box;"></textarea>
                <button class="confirmSendBack" data-bug-id="{bug_id}" data-assigned-to="{assigned_to or ''}"
                        style="margin-top: 10px; padding: 10px 20px; background: linear-gradient(145deg, #aa0000 0%, #660000 100%);
                               color: white; border: 1px solid #ff0000; border-radius: 4px; cursor: pointer; font-weight: bold;">
                    Confirm Send Back
                </button>
            </div>
        </div>
        '''

    html = f'''
    <div style="white-space: normal; padding: 20px; background: linear-gradient(135deg, #1a0a0a 0%, #2d1b1b 100%);
                border: 2px solid #8b0000; border-radius: 10px; box-shadow: 0 10px 30px rgba(139,0,0,0.5);">
        <h2 style="margin-top: 0; color: #ff4444;">🧪 Testing Queue</h2>
        <p style="color: #aaa; margin-bottom: 20px;">Review bugs ready for testing. Mark as resolved or send back to developer.</p>

        <div style="max-height: 700px; overflow-y: auto;">
            {bug_cards}
        </div>
    </div>
    '''

    await atlantis.client_html(html)

    script = '''
    //js
    let foo = function() {
        // Resolve buttons
        document.querySelectorAll('.resolveBtn').forEach(btn => {
            btn.addEventListener('click', async function() {
                const bugId = this.dataset.bugId;

                if (!confirm('Mark this bug as Resolved?')) return;

                this.disabled = true;
                this.textContent = 'Resolving...';

                try {
                    await sendChatter(eventData.connAccessToken, '@*_resolve_bug', { bug_id: bugId });
                    this.textContent = '✓ Resolved!';
                    this.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
                } catch (error) {
                    thread.console.error('Error resolving bug:', error);
                    this.textContent = 'Error';
                    this.disabled = false;
                }
            });
        });

        // Send back buttons
        document.querySelectorAll('.sendBackBtn').forEach(btn => {
            btn.addEventListener('click', function() {
                const bugId = this.dataset.bugId;
                const form = document.getElementById('sendBackForm_' + bugId + '_{FORM_ID}');
                form.style.display = form.style.display === 'none' ? 'block' : 'none';
            });
        });

        // Confirm send back buttons
        document.querySelectorAll('.confirmSendBack').forEach(btn => {
            btn.addEventListener('click', async function() {
                const bugId = this.dataset.bugId;
                const assignedTo = this.dataset.assignedTo;
                const notesField = document.getElementById('sendBackNotes_' + bugId + '_{FORM_ID}');
                const notes = notesField.value;

                if (!notes.trim()) {
                    alert('Please provide a reason for sending back!');
                    return;
                }

                this.disabled = true;
                this.textContent = 'Sending...';

                try {
                    await sendChatter(eventData.connAccessToken, '@*_send_bug_back_to_dev', {
                        bug_id: bugId,
                        assigned_to: assignedTo,
                        notes: notes
                    });
                    this.textContent = '✓ Sent Back!';
                    this.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
                } catch (error) {
                    thread.console.error('Error sending back bug:', error);
                    this.textContent = 'Error';
                    this.disabled = false;
                }
            });
        });
    }
    foo()
    '''

    script = script.replace("{FORM_ID}", FORM_ID)
    await atlantis.client_script(script)

    logger.info(f"bugs_ready_for_testing completed, showed {len(bugs)} bugs")


@visible
async def _resolve_bug(bug_id: str):
    """Internal handler to mark bug as resolved."""
    logger.info(f"_resolve_bug called for bug_id={bug_id}")

    db = await _init_bug_db()

    db.execute('''
        UPDATE bug_reports
        SET status = 'Resolved', updated_at = CURRENT_TIMESTAMP
        WHERE bug_id = ?
    ''', (bug_id,))

    db.commit()

    await atlantis.client_log(f"✅ Bug {bug_id} marked as Resolved!")
    logger.info(f"Bug {bug_id} resolved")


@visible
async def _send_bug_back_to_dev(bug_id: str, assigned_to: str, notes: str):
    """Internal handler to send bug back to developer."""
    logger.info(f"_send_bug_back_to_dev called for bug_id={bug_id}, assigned_to={assigned_to}")

    db = await _init_bug_db()

    # Append tester notes to progress_notes
    current_notes_sql = "SELECT progress_notes FROM bug_reports WHERE bug_id = ?"
    cursor = db.execute(current_notes_sql, (bug_id,))
    row = cursor.fetchone()
    current_notes = row[0] if row and row[0] else ""

    client_id = atlantis.get_client_id()
    tester = atlantis.get_caller() or client_id or "unknown"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_note = f"\n\n[{timestamp}] Sent back by {tester}:\n{notes}"
    updated_notes = current_notes + new_note

    db.execute('''
        UPDATE bug_reports
        SET status = 'Assigned', progress_notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE bug_id = ?
    ''', (updated_notes, bug_id))

    db.commit()

    await atlantis.client_log(f"↩️ Bug {bug_id} sent back to {assigned_to}")
    logger.info(f"Bug {bug_id} sent back to {assigned_to}")


@visible
async def team_bug_dashboard():
    """Manager view showing who is working on what bugs."""
    logger.info("team_bug_dashboard called")

    db = await _init_bug_db()

    sql = '''
        SELECT assigned_to, bug_id, title, severity, status, assigned_at
        FROM bug_reports
        WHERE assigned_to IS NOT NULL
        AND assigned_to != ''
        AND status NOT IN ('Resolved', 'Dismissed')
        ORDER BY assigned_to,
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END
    '''

    cursor = db.execute(sql)
    rows = cursor.fetchall()

    if not rows:
        await atlantis.client_log("📭 No bugs currently assigned to anyone!")
        return

    # Group by developer
    dev_bugs = {}
    for assigned_to, bug_id, title, severity, status, assigned_at in rows:
        if assigned_to not in dev_bugs:
            dev_bugs[assigned_to] = []
        dev_bugs[assigned_to].append({
            "bug_id": bug_id,
            "title": title,
            "severity": severity or "Unset",
            "status": status,
            "assigned_at": assigned_at
        })

    # Create summary data
    summary = []
    for dev, bugs in dev_bugs.items():
        summary.append({
            "developer": dev,
            "total_bugs": len(bugs),
            "assigned": len([b for b in bugs if b['status'] == 'Assigned']),
            "in_progress": len([b for b in bugs if b['status'] == 'In Progress']),
            "good_to_test": len([b for b in bugs if b['status'] == 'Good-to-Test']),
            "critical": len([b for b in bugs if b['severity'] == 'Critical']),
            "high": len([b for b in bugs if b['severity'] == 'High'])
        })

    await atlantis.client_data("👥 Team Bug Dashboard", summary)

    # Show detailed breakdown
    for dev, bugs in dev_bugs.items():
        await atlantis.client_data(f"🔧 {dev}'s Bugs ({len(bugs)})", bugs)

    logger.info(f"team_bug_dashboard completed, {len(dev_bugs)} developers with bugs")


@visible
async def audit_resolved_bugs(limit: int = 50):
    """View resolved bugs for audit trail. Shows who fixed, when, and resolution notes."""
    logger.info(f"audit_resolved_bugs called with limit={limit}")

    db = await _init_bug_db()

    sql = '''
        SELECT bug_id, title, severity, category, assigned_to, reported_at, updated_at, progress_notes
        FROM bug_reports
        WHERE status = 'Resolved'
        ORDER BY updated_at DESC
        LIMIT ?
    '''

    cursor = db.execute(sql, (limit,))
    rows = cursor.fetchall()

    if not rows:
        await atlantis.client_log("📭 No resolved bugs found!")
        return

    bugs = []
    for bug_id, title, severity, category, assigned_to, reported_at, updated_at, progress_notes in rows:
        bugs.append({
            "bug_id": bug_id,
            "title": title,
            "severity": severity or "Unset",
            "category": category or "Uncategorized",
            "fixed_by": assigned_to or "Unknown",
            "reported": reported_at,
            "resolved": updated_at,
            "notes": progress_notes[:100] + "..." if progress_notes and len(progress_notes) > 100 else progress_notes or ""
        })

    await atlantis.client_data(f"✅ Resolved Bugs Audit ({len(bugs)})", bugs)
    logger.info(f"audit_resolved_bugs returned {len(bugs)} resolved bugs")


# ============================================================================
# AI WORKFLOW FUNCTIONS - Streamlined for AI bug fixing
# ============================================================================

@visible
async def get_bugs_for_ai(status: str = "Assigned", severity: str = None, limit: int = 10):
    """
    Get bugs as structured JSON for AI to process. Returns array of bugs with all details.
    Status options: New, Triaged, Assigned, In Progress, Good-to-Test, Resolved, Dismissed
    Severity options: Critical, High, Medium, Low
    """
    logger.info(f"get_bugs_for_ai called with status={status}, severity={severity}, limit={limit}")

    db = await _init_bug_db()

    # Build SQL with optional filters
    sql = '''
        SELECT bug_id, title, description, reproduction_steps, severity, category,
               status, assigned_to, assigned_at, progress_notes, reported_at
        FROM bug_reports
        WHERE 1=1
    '''
    params = []

    if status:
        sql += " AND status = ?"
        params.append(status)

    if severity:
        sql += " AND severity = ?"
        params.append(severity)

    sql += '''
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END,
            reported_at DESC
        LIMIT ?
    '''
    params.append(limit)

    cursor = db.execute(sql, params)
    rows = cursor.fetchall()

    bugs = []
    for bug_id, title, description, repro_steps, severity, category, status, assigned_to, assigned_at, progress_notes, reported_at in rows:
        bugs.append({
            "bug_id": bug_id,
            "title": title,
            "description": description,
            "reproduction_steps": repro_steps,
            "severity": severity,
            "category": category,
            "status": status,
            "assigned_to": assigned_to,
            "assigned_at": assigned_at,
            "progress_notes": progress_notes,
            "reported_at": reported_at
        })

    logger.info(f"get_bugs_for_ai returned {len(bugs)} bugs")
    return bugs


@visible
async def get_bug_details(bug_id: str):
    """
    Get full details of a specific bug as JSON. Use this to read all bug information before fixing.
    Returns complete bug data including description, reproduction steps, notes, etc.
    """
    logger.info(f"get_bug_details called for bug_id={bug_id}")

    db = await _init_bug_db()

    cursor = db.execute('''
        SELECT bug_id, title, description, reproduction_steps, severity, category,
               status, assigned_to, assigned_at, progress_notes, system_info,
               log_context, screenshot_path, reported_at, updated_at
        FROM bug_reports
        WHERE bug_id = ?
    ''', (bug_id,))

    row = cursor.fetchone()

    if not row:
        await atlantis.client_log(f"❌ Bug {bug_id} not found")
        return None

    bug_id, title, description, repro_steps, severity, category, status, assigned_to, assigned_at, progress_notes, system_info, log_context, screenshot_path, reported_at, updated_at = row

    bug_data = {
        "bug_id": bug_id,
        "title": title,
        "description": description,
        "reproduction_steps": repro_steps,
        "severity": severity,
        "category": category,
        "status": status,
        "assigned_to": assigned_to,
        "assigned_at": assigned_at,
        "progress_notes": progress_notes,
        "system_info": system_info,
        "log_context": log_context,
        "screenshot_path": screenshot_path,
        "reported_at": reported_at,
        "updated_at": updated_at
    }

    logger.info(f"get_bug_details returned bug: {title}")
    return bug_data


@visible
async def ai_fix_bug(bug_id: str, fix_notes: str):
    """
    Mark bug as fixed and ready for testing. AI should call this AFTER making code changes.

    Args:
        bug_id: The bug ID to mark as fixed
        fix_notes: Description of what was changed/fixed (be specific about files/lines changed)

    This automatically:
    - Updates status to 'Good-to-Test'
    - Appends fix notes with timestamp
    - Makes bug appear in human testing queue (bugs_ready_for_testing)
    """
    logger.info(f"ai_fix_bug called for bug_id={bug_id}")

    db = await _init_bug_db()

    # Get current progress notes
    cursor = db.execute("SELECT progress_notes, title FROM bug_reports WHERE bug_id = ?", (bug_id,))
    row = cursor.fetchone()

    if not row:
        await atlantis.client_log(f"❌ Bug {bug_id} not found")
        return {"status": "error", "message": "Bug not found"}

    current_notes, title = row
    current_notes = current_notes or ""

    # Get AI identity
    client_id = atlantis.get_client_id()
    ai_name = atlantis.get_caller() or client_id or "AI"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append fix notes
    new_note = f"\n\n[{timestamp}] Fixed by {ai_name}:\n{fix_notes}"
    updated_notes = current_notes + new_note

    # Update bug to Good-to-Test
    db.execute('''
        UPDATE bug_reports
        SET status = 'Good-to-Test',
            progress_notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE bug_id = ?
    ''', (updated_notes, bug_id))

    db.commit()

    result = [{
        "Field": "Bug ID",
        "Value": bug_id
    }, {
        "Field": "Title",
        "Value": title
    }, {
        "Field": "Status",
        "Value": "Good-to-Test ✅"
    }, {
        "Field": "Fixed By",
        "Value": ai_name
    }, {
        "Field": "Fix Notes",
        "Value": fix_notes
    }]

    await atlantis.client_data(f"✅ Bug Fixed and Ready for Testing", result)
    logger.info(f"ai_fix_bug: Bug {bug_id} marked as Good-to-Test by {ai_name}")

    return {"status": "success", "bug_id": bug_id, "new_status": "Good-to-Test"}


@visible
async def get_bugs_for_ai(status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """
    Get bugs as structured JSON for AI to process. Returns array of bugs with all details.
    Status options: New, Triaged, Assigned, In Progress, Good-to-Test, Resolved, Dismissed
    Leave status empty to get New and Triaged bugs (default). Use comma-separated for multiple: "New,Triaged"
    """
    logger.info(f"get_bugs_for_ai called with status={status}, limit={limit}")

    db = await _init_bug_db()

    # Default to New and Triaged if no status specified
    if not status:
        status_list = ['New', 'Triaged']
    else:
        status_list = [s.strip() for s in status.split(',')]

    placeholders = ','.join(['?' for _ in status_list])
    sql = f'''
        SELECT bug_id, title, description, reproduction_steps, severity, category, status,
               username, reported_at, system_info, log_context, assigned_to, notes
        FROM bug_reports
        WHERE status IN ({placeholders})
        ORDER BY reported_at DESC
        LIMIT ?
    '''

    cursor = db.execute(sql, (*status_list, limit))
    bugs = cursor.fetchall()

    result = []
    for bug in bugs:
        (bug_id, title, description, reproduction_steps, severity, category, status,
         username, reported_at, system_info, log_context, assigned_to, notes) = bug

        result.append({
            "bug_id": bug_id,
            "title": title,
            "description": description,
            "reproduction_steps": reproduction_steps,
            "severity": severity,
            "category": category,
            "status": status,
            "username": username,
            "reported_at": reported_at,
            "system_info": system_info,
            "log_context": log_context,
            "assigned_to": assigned_to,
            "notes": notes
        })

    logger.info(f"Returning {len(result)} bugs for AI processing")
    return {"bugs": result, "count": len(result)}

@visible
async def ai_manage_bugs(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process multiple bug updates at once for AI automation.

    Updates: Array of bug update objects
    Example:
    [
        {
            "bug_id": "abc123",
            "severity": "High",
            "category": "Crash",
            "notes": "AI Analysis: Critical crash in login flow"
        },
        {
            "bug_id": "def456",
            "severity": "Low",
            "category": "UI",
            "status": "Dismissed",
            "notes": "AI Analysis: Duplicate of existing report"
        }
    ]

    Fields you can update per bug:
    - bug_id: REQUIRED - the bug to update
    - severity: Critical, High, Medium, Low (optional)
    - category: UI, Performance, Crash, Data, Network, Other (optional)
    - status: Triaged, Dismissed, etc (optional)
    - notes: AI analysis/reasoning (optional, will be appended)

    Returns: Summary of applied updates
    """
    try:
        if updates is None:
            return {"error": "Updates parameter is required"}

        if not isinstance(updates, list):
            return {"error": "Updates must be an array"}

        logger.info(f"ai_manage_bugs called with {len(updates)} updates")

        updates_list = updates

        db = await _init_bug_db()
        applied = []
        errors = []

        for update in updates_list:
            bug_id = update.get('bug_id')
            if not bug_id:
                errors.append({"error": "Missing bug_id", "update": update})
                continue

            try:
                # Update severity if provided
                if 'severity' in update and update['severity']:
                    db.execute(
                        "UPDATE bug_reports SET severity = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?",
                        (update['severity'], bug_id)
                    )
                    applied.append(f"Bug {bug_id[:8]} severity → {update['severity']}")

                # Update category if provided
                if 'category' in update and update['category']:
                    db.execute(
                        "UPDATE bug_reports SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?",
                        (update['category'], bug_id)
                    )
                    applied.append(f"Bug {bug_id[:8]} category → {update['category']}")

                # Update status if provided
                if 'status' in update and update['status']:
                    db.execute(
                        "UPDATE bug_reports SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?",
                        (update['status'], bug_id)
                    )
                    applied.append(f"Bug {bug_id[:8]} status → {update['status']}")

                # Append notes if provided
                if 'notes' in update and update['notes']:
                    # Get existing notes
                    cursor = db.execute("SELECT notes FROM bug_reports WHERE bug_id = ?", (bug_id,))
                    row = cursor.fetchone()
                    existing_notes = row[0] if row and row[0] else ""

                    # Append new notes with timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_notes = f"{existing_notes}\n\n[AI - {timestamp}]\n{update['notes']}" if existing_notes else f"[AI - {timestamp}]\n{update['notes']}"

                    db.execute(
                        "UPDATE bug_reports SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE bug_id = ?",
                        (new_notes, bug_id)
                    )
                    applied.append(f"Bug {bug_id[:8]} notes appended")

                db.commit()

            except Exception as e:
                logger.error(f"Error updating bug {bug_id}: {e}")
                errors.append({"bug_id": bug_id, "error": str(e)})

        result = {
            "success": True,
            "applied_count": len(applied),
            "applied": applied,
            "error_count": len(errors),
            "errors": errors
        }

        await atlantis.client_log(f"✅ AI processed {len(applied)} bug updates ({len(errors)} errors)")
        logger.info(f"ai_manage_bugs completed: {result}")

        return result

    except Exception as e:
        logger.error(f"ai_manage_bugs error: {e}")
        return {"error": str(e)}

@visible
async def read_ai_bug_resolver_docs():
    """
    Read the AI Bug Resolver documentation. Returns complete guide for AI assistants on how to automatically fix bugs.
    Use this to understand the AI bug-fixing workflow.
    """
    logger.info("read_ai_bug_resolver_docs called")

    docs_path = os.path.join(os.path.dirname(__file__), "AI_BUG_RESOLVER.md")

    try:
        with open(docs_path, 'r') as f:
            content = f.read()

        logger.info(f"Returning AI_BUG_RESOLVER.md ({len(content)} chars)")
        return content
    except FileNotFoundError:
        logger.error("AI_BUG_RESOLVER.md not found")
        return "Error: Documentation file not found"


@visible
async def read_bug_report_docs():
    """
    Read the complete Bug Report System documentation. Returns full guide covering all workflows for users, managers, developers, testers, and AI.
    Use this to understand the entire bug tracking system.
    """
    logger.info("read_bug_report_docs called")

    docs_path = os.path.join(os.path.dirname(__file__), "README.bug_report.md")

    try:
        with open(docs_path, 'r') as f:
            content = f.read()

        logger.info(f"Returning README.bug_report.md ({len(content)} chars)")
        return content
    except FileNotFoundError:
        logger.error("README.bug_report.md not found")
        return "Error: Documentation file not found"
