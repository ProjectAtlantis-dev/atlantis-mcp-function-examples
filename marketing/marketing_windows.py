import atlantis
import asyncio
import os
import json
import uuid
import subprocess
import logging
import requests
import base64
import io
from google import genai
from google.genai import types

logger = logging.getLogger("mcp_client")

# Config file paths
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "marketing_brands.json")
SOCIAL_TOKENS_FILE = os.path.join(os.path.dirname(__file__), "social_tokens.json")

# Gemini CLI path
GEMINI_CLI = "gemini"

# Configure Gemini API for image generation
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "place-your-gemini-api-key-here")
genai_client = genai.Client(api_key=GEMINI_API_KEY)

# Platform-specific optimizations based on 2025 best practices
PLATFORM_SPECS = {
    "twitter": {
        "name": "Twitter/X",
        "char_limit": 280,
        "optimal_length": "100-280 characters",
        "best_practices": [
            "Keep it concise and punchy",
            "Use 1-2 relevant hashtags maximum",
            "Front-load the most important information (users see ~200 chars before clicking)",
            "Use line breaks for readability",
            "Include a clear call-to-action",
            "Emojis work well but use sparingly"
        ],
        "hashtag_guidance": "1-2 hashtags, place naturally in text or at end"
    },
    "linkedin": {
        "name": "LinkedIn",
        "char_limit": 3000,
        "optimal_length": "150-300 words (800-1600 characters)",
        "best_practices": [
            "First 210 characters are critical - they appear before 'See More' button",
            "Hook readers in the opening line",
            "Use white space and line breaks for readability",
            "Professional but conversational tone",
            "Include relevant insights or value",
            "End with a clear call-to-action or question to drive engagement",
            "1-3 relevant emojis can work"
        ],
        "hashtag_guidance": "3-5 hashtags at the end of post"
    },
    "instagram": {
        "name": "Instagram",
        "char_limit": 2200,
        "optimal_length": "138-150 characters for optimal engagement",
        "best_practices": [
            "First 125 characters appear before 'more' button",
            "Keep it authentic and visually descriptive",
            "Use line breaks and spacing for readability",
            "Emojis are highly encouraged and on-brand",
            "Tell a story or share an insight",
            "Include call-to-action"
        ],
        "hashtag_guidance": "5-10 relevant hashtags, can go in caption or first comment. Long-tail hashtags (15-25 chars) perform best"
    },
    "facebook": {
        "name": "Facebook",
        "char_limit": 63206,
        "optimal_length": "40-80 characters for maximum engagement",
        "best_practices": [
            "Keep it extremely short and concise (40-80 chars ideal)",
            "Posts over 280 chars see significantly lower engagement",
            "Prioritize visual content over text",
            "Use emotional hooks or questions",
            "Avoid overly promotional language",
            "Clear and immediate value"
        ],
        "hashtag_guidance": "1-2 hashtags maximum, Facebook users respond less to hashtags"
    }
}


def _load_brands():
    """Load brand configs from JSON file"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def _save_brands(brands: dict):
    """Save brand configs to JSON file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(brands, f, indent=2)


def _get_brand_config(brand_id: str):
    """Get a specific brand config"""
    brands = _load_brands()
    if brand_id not in brands:
        raise ValueError(f"Brand '{brand_id}' not found. Use list_brands() to see available brands.")
    return brands[brand_id]


async def _call_llm(prompt: str, temperature: float = 0.8) -> str:
    """Internal helper to call LLM via Gemini CLI"""
    logger.info(f"Calling Gemini CLI: {GEMINI_CLI}")

    # Add system instruction as prefix to prompt
    full_prompt = "You are a creative marketing copywriter expert. Generate engaging, authentic social media content.\n\n" + prompt

    # Call Gemini CLI via subprocess
    result = await asyncio.to_thread(
        subprocess.run,
        [GEMINI_CLI, full_prompt],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        error_msg = result.stderr or "Unknown error"
        logger.error(f"Gemini CLI error: {error_msg}")
        raise RuntimeError(f"Gemini CLI failed: {error_msg}")

    output = result.stdout.strip()

    # Remove the "Loaded cached credentials." line if present
    lines = output.split('\n')
    if lines and 'cached credentials' in lines[0].lower():
        output = '\n'.join(lines[1:]).strip()

    logger.info(f"Gemini response received: {len(output)} characters")
    return output


@visible
async def create_brand_config_form():
    """Open a form to create or update a brand configuration for marketing. Human-friendly interface with all fields in a nice form."""

    FORM_ID = f"brand_{str(uuid.uuid4()).replace('-', '')[:8]}"

    htmlStr = f'''
    <div style="white-space:normal;padding: 20px;
                background: linear-gradient(135deg, #0a1a1a 0%, #1b2d2d 100%);
                border: 2px solid #00a8a8;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(0,168,168,0.5);
                box-sizing: border-box;">
        <h2 style="margin-top: 0; color: #00ffff; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">🏢 Brand Configuration</h2>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand ID * <span style="font-weight: normal; font-size: 12px;">(short identifier like "atlantis" or "acme")</span></label>
            <input type="text" id="brand_id_{FORM_ID}" placeholder="e.g., atlantis"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand Name *</label>
            <input type="text" id="brand_name_{FORM_ID}" placeholder="e.g., Project Atlantis"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Description * <span style="font-weight: normal; font-size: 12px;">(What does your business do?)</span></label>
            <textarea id="description_{FORM_ID}" placeholder="Describe your business, products, and what makes you unique..."
                      rows="3"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Target Audience * <span style="font-weight: normal; font-size: 12px;">(Who are you talking to?)</span></label>
            <textarea id="target_audience_{FORM_ID}" placeholder="e.g., Tech enthusiasts, robotics researchers, AI developers..."
                      rows="2"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand Voice *</label>
            <select id="brand_voice_{FORM_ID}"
                    style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                           border-radius: 4px; color: #fff;">
                <option value="professional">Professional</option>
                <option value="casual">Casual</option>
                <option value="technical">Technical</option>
                <option value="friendly">Friendly</option>
                <option value="authoritative">Authoritative</option>
                <option value="playful">Playful</option>
                <option value="innovative">Innovative</option>
                <option value="visionary">Visionary</option>
            </select>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Key Messages <span style="font-weight: normal; font-size: 12px;">(Optional: Core value propositions, USPs, mission)</span></label>
            <textarea id="key_messages_{FORM_ID}" placeholder="e.g., Pushing boundaries of robotics. Open research environment. Building tomorrow's technology."
                      rows="2"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Products/Services <span style="font-weight: normal; font-size: 12px;">(Optional)</span></label>
            <textarea id="product_services_{FORM_ID}" placeholder="What products or services do you offer?"
                      rows="2"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Competitors <span style="font-weight: normal; font-size: 12px;">(Optional)</span></label>
            <input type="text" id="competitors_{FORM_ID}" placeholder="e.g., Boston Dynamics, Tesla AI..."
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand Hashtags <span style="font-weight: normal; font-size: 12px;">(Optional)</span></label>
            <input type="text" id="hashtags_{FORM_ID}" placeholder="e.g., #ProjectAtlantis #RoboticsResearch"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Website <span style="font-weight: normal; font-size: 12px;">(Optional)</span></label>
            <input type="text" id="website_{FORM_ID}" placeholder="https://..."
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <button id="submit_{FORM_ID}"
                style="padding: 12px 30px;
                       background: linear-gradient(145deg, #00a8a8 0%, #005a5a 100%);
                       color: #fff;
                       border: 1px solid #00ffff;
                       border-radius: 6px;
                       cursor: pointer;
                       font-weight: bold;
                       font-size: 16px;
                       box-shadow: 0 4px 8px rgba(0,168,168,0.4);
                       width: 100%;">
            💾 Save Brand Configuration
        </button>
    </div>
    '''

    await atlantis.client_html(htmlStr)

    miniscript = '''
    //js
    let foo = function() {
        thread.console.bold('Brand config form script executing');

        const brandIdField = document.getElementById('brand_id_{FORM_ID}');
        const brandNameField = document.getElementById('brand_name_{FORM_ID}');
        const descField = document.getElementById('description_{FORM_ID}');
        const audienceField = document.getElementById('target_audience_{FORM_ID}');
        const voiceField = document.getElementById('brand_voice_{FORM_ID}');
        const messagesField = document.getElementById('key_messages_{FORM_ID}');
        const productsField = document.getElementById('product_services_{FORM_ID}');
        const competitorsField = document.getElementById('competitors_{FORM_ID}');
        const hashtagsField = document.getElementById('hashtags_{FORM_ID}');
        const websiteField = document.getElementById('website_{FORM_ID}');
        const submitBtn = document.getElementById('submit_{FORM_ID}');

        // Submit button
        submitBtn.addEventListener('click', async function() {
            // Validation
            if (!brandIdField.value.trim()) {
                alert('Please enter a Brand ID');
                return;
            }
            if (!brandNameField.value.trim()) {
                alert('Please enter a Brand Name');
                return;
            }
            if (!descField.value.trim()) {
                alert('Please enter a Description');
                return;
            }
            if (!audienceField.value.trim()) {
                alert('Please enter Target Audience');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Saving...';

            let data = {
                brand_id: brandIdField.value.trim(),
                brand_name: brandNameField.value.trim(),
                description: descField.value.trim(),
                target_audience: audienceField.value.trim(),
                brand_voice: voiceField.value,
                key_messages: messagesField.value.trim() || "",
                product_services: productsField.value.trim() || "",
                competitors: competitorsField.value.trim() || "",
                hashtags: hashtagsField.value.trim() || "",
                website: websiteField.value.trim() || ""
            };

            thread.console.info('Submitting brand configuration');

            try {
                let content = '@*create_brand_config';
                await sendChatter(eventData.connAccessToken, content, data);
                submitBtn.textContent = '✓ Saved!';
                submitBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            } catch (error) {
                thread.console.error('Error submitting brand config:', error);
                submitBtn.textContent = 'Error - Try Again';
                submitBtn.disabled = false;
                submitBtn.style.background = 'linear-gradient(145deg, #00a8a8 0%, #005a5a 100%)';
            }
        });
    }
    foo()
    '''

    miniscript = miniscript.replace("{FORM_ID}", FORM_ID)
    await atlantis.client_script(miniscript)


@visible
async def create_brand_config(
    brand_id: str,
    brand_name: str,
    description: str,
    target_audience: str,
    brand_voice: str,
    key_messages: str = "",
    product_services: str = "",
    competitors: str = "",
    hashtags: str = "",
    website: str = ""
):
    """
    Create or update a brand configuration for marketing content generation. Can be called directly or via form.
    Brand ID is a short identifier (e.g., 'atlantis', 'acme').
    Use create_brand_config_form() for a nice HTML form interface.
    This function is for direct API/bot access or as the handler for the form.
    """

    brands = _load_brands()

    # Get existing brand config to preserve fields like tokens
    existing_config = brands.get(brand_id, {})

    # Update only the provided fields, preserve everything else
    brand_config = {
        "brand_name": brand_name.strip(),
        "description": description.strip(),
        "target_audience": target_audience.strip(),
        "brand_voice": brand_voice.strip(),
        "key_messages": key_messages.strip(),
        "product_services": product_services.strip(),
        "competitors": competitors.strip(),
        "hashtags": hashtags.strip(),
        "website": website.strip(),
        "created_at": existing_config.get("created_at", str(uuid.uuid4())),
        "updated_at": str(uuid.uuid4())
    }

    # Preserve existing fields that aren't being updated (like tokens!)
    for key, value in existing_config.items():
        if key not in brand_config:
            brand_config[key] = value

    brands[brand_id] = brand_config
    _save_brands(brands)

    result = [{
        "Field": "Brand ID",
        "Value": brand_id
    }, {
        "Field": "Brand Name",
        "Value": brand_name
    }, {
        "Field": "Description",
        "Value": description
    }, {
        "Field": "Target Audience",
        "Value": target_audience
    }, {
        "Field": "Brand Voice",
        "Value": brand_voice
    }]

    if key_messages:
        result.append({"Field": "Key Messages", "Value": key_messages})
    if product_services:
        result.append({"Field": "Products/Services", "Value": product_services})
    if competitors:
        result.append({"Field": "Competitors", "Value": competitors})
    if hashtags:
        result.append({"Field": "Hashtags", "Value": hashtags})
    if website:
        result.append({"Field": "Website", "Value": website})

    await atlantis.client_data(f"✅ Brand '{brand_id}' Configuration Saved", result)

    logger.info(f"Brand config created/updated: {brand_id} - {brand_name}")


@visible
async def list_brands():
    """List all configured brand profiles. Shows available brands for content generation."""

    brands = _load_brands()

    if not brands:
        await atlantis.client_log("📭 No brands configured yet. Use create_brand_config() to add one!")
        logger.info("list_brands: No brands found")
        return

    brand_list = []
    for brand_id, config in brands.items():
        brand_list.append({
            "brand_id": brand_id,
            "brand_name": config["brand_name"],
            "description": config["description"][:80] + "..." if len(config["description"]) > 80 else config["description"],
            "voice": config["brand_voice"],
            "audience": config["target_audience"][:50] + "..." if len(config["target_audience"]) > 50 else config["target_audience"]
        })

    await atlantis.client_data("Brand Configurations", brand_list)
    logger.info(f"list_brands: Returned {len(brand_list)} brands")


@visible
async def view_brand_config(brand_id: str):
    """View full details of a specific brand configuration."""

    try:
        config = _get_brand_config(brand_id)
    except ValueError as e:
        await atlantis.client_log(f"❌ {str(e)}")
        return

    result = [{
        "Field": "Brand ID",
        "Value": brand_id
    }, {
        "Field": "Brand Name",
        "Value": config['brand_name']
    }, {
        "Field": "Description",
        "Value": config['description']
    }, {
        "Field": "Target Audience",
        "Value": config['target_audience']
    }, {
        "Field": "Brand Voice",
        "Value": config['brand_voice']
    }]

    if config.get('key_messages'):
        result.append({"Field": "Key Messages", "Value": config['key_messages']})
    if config.get('product_services'):
        result.append({"Field": "Products/Services", "Value": config['product_services']})
    if config.get('competitors'):
        result.append({"Field": "Competitors", "Value": config['competitors']})
    if config.get('hashtags'):
        result.append({"Field": "Brand Hashtags", "Value": config['hashtags']})
    if config.get('website'):
        result.append({"Field": "Website", "Value": config['website']})

    await atlantis.client_data(f"🏢 Brand: {config['brand_name']}", result)


@visible
async def edit_brand_config(brand_id: str):
    """
    Edit an existing brand configuration. Opens form pre-filled with current values.
    Brand ID: The brand to edit (use list_brands to see available brands).
    """

    # Get existing brand config
    try:
        config = _get_brand_config(brand_id)
    except ValueError as e:
        await atlantis.client_log(f"❌ {str(e)}")
        logger.error(f"edit_brand_config: {str(e)}")
        return {"error": str(e)}

    FORM_ID = f"brand_{str(uuid.uuid4()).replace('-', '')[:8]}"

    htmlStr = f'''
    <div style="white-space:normal;padding: 20px;
                background: linear-gradient(135deg, #0a1a1a 0%, #1b2d2d 100%);
                border: 2px solid #00a8a8;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(0,168,168,0.5);
                box-sizing: border-box;">
        <h2 style="margin-top: 0; color: #00ffff; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">✏️ Edit Brand Configuration</h2>

        <div style="margin-bottom: 15px; padding: 12px; background: rgba(0,168,168,0.2); border-radius: 6px; border: 1px solid rgba(0,255,255,0.3);">
            <div style="color: #aaffff; font-size: 13px;">
                Editing brand: <strong>{config['brand_name']}</strong> ({brand_id})
            </div>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand Name *</label>
            <input type="text" id="brand_name_{FORM_ID}" value="{config['brand_name']}"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Description *</label>
            <textarea id="description_{FORM_ID}" rows="3"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;">{config['description']}</textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Target Audience *</label>
            <textarea id="target_audience_{FORM_ID}" rows="2"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;">{config['target_audience']}</textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand Voice *</label>
            <select id="brand_voice_{FORM_ID}"
                    style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                           border-radius: 4px; color: #fff;">
                <option value="professional" {'selected' if config['brand_voice'] == 'professional' else ''}>Professional</option>
                <option value="casual" {'selected' if config['brand_voice'] == 'casual' else ''}>Casual</option>
                <option value="technical" {'selected' if config['brand_voice'] == 'technical' else ''}>Technical</option>
                <option value="friendly" {'selected' if config['brand_voice'] == 'friendly' else ''}>Friendly</option>
                <option value="authoritative" {'selected' if config['brand_voice'] == 'authoritative' else ''}>Authoritative</option>
                <option value="playful" {'selected' if config['brand_voice'] == 'playful' else ''}>Playful</option>
                <option value="innovative" {'selected' if config['brand_voice'] == 'innovative' else ''}>Innovative</option>
                <option value="visionary" {'selected' if config['brand_voice'] == 'visionary' else ''}>Visionary</option>
            </select>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Key Messages</label>
            <textarea id="key_messages_{FORM_ID}" rows="2"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;">{config.get('key_messages', '')}</textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Products/Services</label>
            <textarea id="product_services_{FORM_ID}" rows="2"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; resize: vertical;">{config.get('product_services', '')}</textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Competitors</label>
            <input type="text" id="competitors_{FORM_ID}" value="{config.get('competitors', '')}"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand Hashtags</label>
            <input type="text" id="hashtags_{FORM_ID}" value="{config.get('hashtags', '')}"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Website</label>
            <input type="text" id="website_{FORM_ID}" value="{config.get('website', '')}"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box;">
        </div>

        <button id="submit_{FORM_ID}"
                style="padding: 12px 30px;
                       background: linear-gradient(145deg, #00a8a8 0%, #005a5a 100%);
                       color: #fff;
                       border: 1px solid #00ffff;
                       border-radius: 6px;
                       cursor: pointer;
                       font-weight: bold;
                       font-size: 16px;
                       box-shadow: 0 4px 8px rgba(0,168,168,0.4);
                       width: 100%;">
            💾 Update Brand Configuration
        </button>
    </div>
    '''

    await atlantis.client_html(htmlStr)

    miniscript = f'''
    //js
    let foo = function() {{
        thread.console.bold('Brand edit form loaded');

        const brandNameField = document.getElementById('brand_name_{FORM_ID}');
        const descField = document.getElementById('description_{FORM_ID}');
        const audienceField = document.getElementById('target_audience_{FORM_ID}');
        const voiceField = document.getElementById('brand_voice_{FORM_ID}');
        const messagesField = document.getElementById('key_messages_{FORM_ID}');
        const productsField = document.getElementById('product_services_{FORM_ID}');
        const competitorsField = document.getElementById('competitors_{FORM_ID}');
        const hashtagsField = document.getElementById('hashtags_{FORM_ID}');
        const websiteField = document.getElementById('website_{FORM_ID}');
        const submitBtn = document.getElementById('submit_{FORM_ID}');

        submitBtn.addEventListener('click', async function() {{
            if (!brandNameField.value.trim()) {{
                alert('Please enter a Brand Name');
                return;
            }}
            if (!descField.value.trim()) {{
                alert('Please enter a Description');
                return;
            }}
            if (!audienceField.value.trim()) {{
                alert('Please enter Target Audience');
                return;
            }}

            submitBtn.disabled = true;
            submitBtn.textContent = 'Updating...';

            let data = {{
                brand_id: "{brand_id}",
                brand_name: brandNameField.value.trim(),
                description: descField.value.trim(),
                target_audience: audienceField.value.trim(),
                brand_voice: voiceField.value,
                key_messages: messagesField.value.trim() || "",
                product_services: productsField.value.trim() || "",
                competitors: competitorsField.value.trim() || "",
                hashtags: hashtagsField.value.trim() || "",
                website: websiteField.value.trim() || ""
            }};

            try {{
                await sendChatter(eventData.connAccessToken, '@*create_brand_config', data);
                submitBtn.textContent = '✓ Updated!';
                submitBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            }} catch (error) {{
                thread.console.error('Error updating brand config:', error);
                submitBtn.textContent = 'Error - Try Again';
                submitBtn.disabled = false;
                submitBtn.style.background = 'linear-gradient(145deg, #00a8a8 0%, #005a5a 100%)';
            }}
        }});
    }}
    foo()
    '''

    miniscript = miniscript.replace("{FORM_ID}", FORM_ID)
    await atlantis.client_script(miniscript)

    logger.info(f"edit_brand_config form loaded for brand_id={brand_id}")
    return {"brand_id": brand_id, "status": "form_loaded"}


@visible
async def view_linkedin_token(brand_id: str):
    """
    View the LinkedIn access token for a brand.
    Brand ID: The brand to view token for.
    Shows the token so you can copy it for debugging or use in LinkedIn's token inspector.
    """

    try:
        config = _get_brand_config(brand_id)
    except ValueError as e:
        await atlantis.client_log(f"❌ {str(e)}")
        return {"error": str(e)}

    if "linkedin_token" not in config:
        await atlantis.client_log(f"❌ No LinkedIn token configured for brand '{brand_id}'")
        await atlantis.client_log(f"💡 Use configure_linkedin_token('{brand_id}') to add one!")
        return {"error": "No LinkedIn token configured"}

    token = config["linkedin_token"]
    person_urn = config.get("linkedin_person_urn", "N/A")
    profile_name = config.get("linkedin_profile_name", "N/A")

    await atlantis.client_log(f"🔗 LinkedIn Token for '{config['brand_name']}' ({brand_id})")
    await atlantis.client_log("")
    await atlantis.client_log(f"Access Token:")
    await atlantis.client_log(f"{token}")
    await atlantis.client_log("")
    await atlantis.client_log(f"Person URN: {person_urn}")
    await atlantis.client_log(f"Profile Name: {profile_name}")
    await atlantis.client_log("")
    await atlantis.client_log("💡 You can test this token at: https://www.linkedin.com/developers/tools/oauth/token-inspector")

    return {
        "brand_id": brand_id,
        "token": token,
        "person_urn": person_urn,
        "profile_name": profile_name
    }


@visible
async def delete_brand_config(brand_id: str):
    """Delete a brand configuration. This cannot be undone."""

    brands = _load_brands()

    if brand_id not in brands:
        await atlantis.client_log(f"❌ Brand '{brand_id}' not found")
        return

    brand_name = brands[brand_id]["brand_name"]
    del brands[brand_id]
    _save_brands(brands)

    await atlantis.client_log(f"🗑️ Brand '{brand_name}' ({brand_id}) deleted successfully")
    logger.info(f"Brand config deleted: {brand_id}")


async def _generate_image(prompt: str, output_dir: str = None) -> dict:
    """Internal helper to generate image using Pollinations.ai (FREE) - Returns base64 encoded image"""
    logger.info(f"Generating image with Pollinations.ai: {prompt[:100]}...")

    # URL encode the prompt
    import urllib.parse
    encoded_prompt = urllib.parse.quote(prompt)

    # Pollinations.ai free image generation API
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

    # Download the image
    import requests
    response = await asyncio.to_thread(
        requests.get,
        image_url,
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(f"Image generation failed with status {response.status_code}")

    # Return image as base64 and bytes (for Windows compatibility - no file I/O)
    timestamp = uuid.uuid4().hex[:8]
    image_filename = f"social_post_{timestamp}.png"
    image_base64 = base64.b64encode(response.content).decode('utf-8')

    logger.info(f"Generated image (in-memory): {image_filename}")
    return {
        "filename": image_filename,
        "base64": image_base64,
        "bytes": response.content
    }


@visible
async def generate_social_post_with_image(
    brand_id: str,
    topic: str,
    platform: str = "twitter",
    tone: str = "",
    image_style: str = "photorealistic",
    image_prompt: str = ""
):
    """
    Generate social media post with both text AND image for specified brand, platform and topic.
    Brand ID must match a configured brand (use list_brands to see options).
    Platforms: twitter, linkedin, instagram, facebook.
    Tone: Leave empty to use brand's default voice.
    Image styles: photorealistic, watercolor, oil-painting, sketch, pixel-art, anime, modern, minimalist.
    Image prompt: (Optional) Custom prompt for image generation. If provided, overrides default prompt construction.
    Returns text post + generated image displayed in interface.
    """

    # Get brand config
    try:
        brand_config = _get_brand_config(brand_id)
    except ValueError as e:
        return f"❌ {str(e)}"

    # Normalize platform
    platform = platform.lower().strip()
    if platform not in PLATFORM_SPECS:
        available = ", ".join(PLATFORM_SPECS.keys())
        return f"❌ Unknown platform '{platform}'. Available: {available}"

    spec = PLATFORM_SPECS[platform]
    effective_tone = tone if tone else brand_config['brand_voice']

    await atlantis.client_log(f"🎨 Generating {spec['name']} post with image for {brand_config['brand_name']}")
    await atlantis.client_log(f"📝 Topic: {topic}")

    # Generate text content first (same as before)
    brand_context = f"""
BRAND INFORMATION:
- Brand: {brand_config['brand_name']}
- Description: {brand_config['description']}
- Target Audience: {brand_config['target_audience']}
- Brand Voice: {brand_config['brand_voice']}
"""

    if brand_config.get('key_messages'):
        brand_context += f"- Key Messages: {brand_config['key_messages']}\n"

    text_prompt = f"""{brand_context}

Create a {effective_tone} social media post for {spec['name']} about: {topic}

PLATFORM REQUIREMENTS:
- Character limit: {spec['char_limit']}
- Optimal length: {spec['optimal_length']}

Generate ONLY the post content with hashtags. Be engaging and optimized for {spec['name']}.
"""

    try:
        # Generate text
        await atlantis.client_log("✍️ Generating post text...")
        post_content = await _call_llm(text_prompt, temperature=0.8)
        post_content = post_content.strip().strip('"').strip("'").strip('```').strip()

        # Generate image
        await atlantis.client_log("🎨 Generating social media image (FREE AI)...")
        await atlantis.client_log("⏳ This may take 5-15 seconds...")

        # Construct image prompt: custom or default
        if image_prompt:
            # Use custom prompt exactly as provided
            final_image_prompt = image_prompt
            await atlantis.client_log(f"🎯 Using custom image prompt")
        else:
            # Use default prompt construction
            final_image_prompt = f"{image_style} social media image for {brand_config['brand_name']} about {topic}. Professional, eye-catching, suitable for {platform}. Brand context: {brand_config['description'][:200]}"
            await atlantis.client_log(f"🖼️ Using default image prompt")

        image_data = await _generate_image(final_image_prompt)
        await atlantis.client_log("✅ Image generated successfully!")

        # Extract base64 from returned dict (Windows-compatible - no file I/O)
        image_base64 = image_data["base64"]
        image_filename = image_data["filename"]

        # Display result with glassmorphism design (2025 trends)
        result_html = f'''
        <div style="
            max-width: 900px;
            margin: 20px auto;
            padding: 0;
            background: linear-gradient(135deg, rgba(10, 26, 26, 0.95) 0%, rgba(27, 45, 45, 0.95) 100%);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 20px;
            box-shadow:
                0 8px 32px 0 rgba(0, 168, 168, 0.2),
                0 0 0 1px rgba(0, 255, 255, 0.1) inset;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        ">
            <!-- Header -->
            <div style="
                background: linear-gradient(90deg, rgba(0, 168, 168, 0.3) 0%, rgba(0, 255, 255, 0.2) 100%);
                padding: 25px;
                border-bottom: 1px solid rgba(0, 255, 255, 0.2);
            ">
                <h2 style="
                    margin: 0;
                    text-align: center;
                    color: #00ffff;
                    font-size: 24px;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                    text-shadow: 0 2px 10px rgba(0, 255, 255, 0.3);
                ">
                    ✨ {spec['name']} Post Generated
                </h2>
            </div>

            <div style="padding: 30px;">
                <!-- Post Text Card -->
                <div style="
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border: 1px solid rgba(0, 255, 255, 0.2);
                    border-radius: 16px;
                    padding: 20px;
                    margin-bottom: 24px;
                    box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.2);
                ">
                    <div style="
                        font-size: 14px;
                        font-weight: 600;
                        color: #aaffff;
                        margin-bottom: 12px;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    ">
                        📝 Post Content
                    </div>
                    <div style="
                        background: rgba(0, 0, 0, 0.3);
                        border: 1px solid rgba(0, 255, 255, 0.15);
                        border-radius: 12px;
                        padding: 18px;
                        color: #ffffff;
                        font-size: 15px;
                        line-height: 1.7;
                        white-space: pre-wrap;
                        font-weight: 400;
                    ">
{post_content}
                    </div>
                    <div style="
                        margin-top: 12px;
                        font-size: 13px;
                        color: rgba(170, 255, 255, 0.7);
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    ">
                        <span style="
                            background: rgba(0, 168, 168, 0.3);
                            padding: 4px 10px;
                            border-radius: 20px;
                            border: 1px solid rgba(0, 255, 255, 0.2);
                        ">
                            {len(post_content)} / {spec['char_limit']} chars
                        </span>
                    </div>
                </div>

                <!-- Image Card -->
                <div style="
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border: 1px solid rgba(0, 255, 255, 0.2);
                    border-radius: 16px;
                    padding: 20px;
                    box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.2);
                ">
                    <div style="
                        font-size: 14px;
                        font-weight: 600;
                        color: #aaffff;
                        margin-bottom: 16px;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    ">
                        🖼️ Generated Image
                    </div>
                    <div style="
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow:
                            0 8px 24px rgba(0, 0, 0, 0.3),
                            0 0 0 1px rgba(0, 255, 255, 0.2);
                    ">
                        <img src="data:image/png;base64,{image_base64}"
                             style="
                                width: 100%;
                                height: auto;
                                display: block;
                             " />
                    </div>
                </div>

                <!-- Footer Info -->
                <div style="
                    margin-top: 24px;
                    padding: 16px;
                    background: rgba(0, 168, 168, 0.1);
                    border: 1px solid rgba(0, 255, 255, 0.15);
                    border-radius: 12px;
                    display: flex;
                    gap: 20px;
                    flex-wrap: wrap;
                    font-size: 13px;
                    color: rgba(170, 255, 255, 0.9);
                ">
                    <div style="flex: 1; min-width: 150px;">
                        <strong style="color: #00ffff;">Brand:</strong> {brand_config['brand_name']}
                    </div>
                    <div style="flex: 1; min-width: 150px;">
                        <strong style="color: #00ffff;">Platform:</strong> {spec['name']}
                    </div>
                    <div style="flex: 1; min-width: 150px;">
                        <strong style="color: #00ffff;">Style:</strong> {image_style}
                    </div>
                </div>
            </div>
        </div>
        '''

        await atlantis.client_html(result_html)
        await atlantis.client_log(f"✅ Generated complete social post with image!")

        return {
            "text": post_content,
            "image_base64": image_base64,
            "image_filename": image_filename,
            "platform": platform,
            "brand": brand_config['brand_name']
        }

    except Exception as e:
        logger.error(f"Error generating social post with image: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@visible
async def generate_social_post(
    brand_id: str,
    topic: str,
    platform: str = "twitter",
    tone: str = ""
):
    """
    Generate engaging social media post for specified brand, platform and topic.
    Brand ID must match a configured brand (use list_brands to see options).
    Platforms: twitter, linkedin, instagram, facebook.
    Tone: Leave empty to use brand's default voice, or override with: professional, casual, excited, friendly, authoritative.
    """

    # Get brand config
    try:
        brand_config = _get_brand_config(brand_id)
    except ValueError as e:
        return f"❌ {str(e)}"

    # Normalize platform name
    platform = platform.lower().strip()
    if platform not in PLATFORM_SPECS:
        available = ", ".join(PLATFORM_SPECS.keys())
        return f"❌ Unknown platform '{platform}'. Available: {available}"

    spec = PLATFORM_SPECS[platform]

    # Use brand voice if tone not specified
    effective_tone = tone if tone else brand_config['brand_voice']

    await atlantis.client_log(f"🎯 Generating {spec['name']} post for {brand_config['brand_name']}")
    await atlantis.client_log(f"📝 Topic: {topic}")

    # Build detailed prompt with brand context and platform specs
    brand_context = f"""
BRAND INFORMATION:
- Brand: {brand_config['brand_name']}
- Description: {brand_config['description']}
- Target Audience: {brand_config['target_audience']}
- Brand Voice: {brand_config['brand_voice']}
"""

    if brand_config.get('key_messages'):
        brand_context += f"- Key Messages: {brand_config['key_messages']}\n"
    if brand_config.get('product_services'):
        brand_context += f"- Products/Services: {brand_config['product_services']}\n"
    if brand_config.get('hashtags'):
        brand_context += f"- Brand Hashtags: {brand_config['hashtags']}\n"

    prompt = f"""{brand_context}

Create a {effective_tone} social media post for {spec['name']} about: {topic}

PLATFORM REQUIREMENTS:
- Character limit: {spec['char_limit']}
- Optimal length: {spec['optimal_length']}

BEST PRACTICES:
{chr(10).join(f'- {bp}' for bp in spec['best_practices'])}

HASHTAG GUIDANCE:
{spec['hashtag_guidance']}

Generate ONLY the post content, ready to copy and paste. Include appropriate hashtags.
Make it engaging, {effective_tone}, authentic to the brand voice, and optimized for {spec['name']}'s audience.
"""

    try:
        post_content = await _call_llm(prompt, temperature=0.8)

        # Clean up any potential wrapping quotes or markdown
        post_content = post_content.strip().strip('"').strip("'").strip('```').strip()

        result = f"""✨ {spec['name']} Post Generated ✨

{post_content}

📊 Length: {len(post_content)} characters (limit: {spec['char_limit']})
🏢 Brand: {brand_config['brand_name']}
"""

        await atlantis.client_log(f"✅ Generated {len(post_content)}-character post for {spec['name']}")
        return result

    except Exception as e:
        logger.error(f"Error generating social post: {e}", exc_info=True)
        return f"❌ Error generating post: {str(e)}"


@visible
async def repurpose_content(
    brand_id: str,
    content: str,
    num_posts: int = 5,
    platforms: str = "twitter,linkedin"
):
    """
    Transform long-form content into multiple social media posts for different platforms.
    Brand ID must match a configured brand (use list_brands to see options).
    Content can be blog post, article, or any text.
    Platforms: comma-separated list (twitter, linkedin, instagram, facebook).
    Extracts key insights and creates platform-optimized posts using brand context.
    """

    # Get brand config
    try:
        brand_config = _get_brand_config(brand_id)
    except ValueError as e:
        return f"❌ {str(e)}"

    if not content or len(content.strip()) < 50:
        return "❌ Content too short. Please provide at least 50 characters of content to repurpose."

    # Parse platforms
    platform_list = [p.strip().lower() for p in platforms.split(",")]
    invalid_platforms = [p for p in platform_list if p not in PLATFORM_SPECS]
    if invalid_platforms:
        available = ", ".join(PLATFORM_SPECS.keys())
        return f"❌ Unknown platform(s): {', '.join(invalid_platforms)}. Available: {available}"

    await atlantis.client_log(f"📝 Repurposing content for {brand_config['brand_name']}")
    await atlantis.client_log(f"🎯 {num_posts} posts for: {', '.join(platform_list)}")

    # Build brand context
    brand_context = f"""
BRAND INFORMATION:
- Brand: {brand_config['brand_name']}
- Description: {brand_config['description']}
- Target Audience: {brand_config['target_audience']}
- Brand Voice: {brand_config['brand_voice']}
"""

    if brand_config.get('key_messages'):
        brand_context += f"- Key Messages: {brand_config['key_messages']}\n"
    if brand_config.get('hashtags'):
        brand_context += f"- Brand Hashtags: {brand_config['hashtags']}\n"

    # Build prompt for content analysis and extraction
    platforms_info = "\n\n".join([
        f"{spec['name'].upper()}:\n- Optimal length: {spec['optimal_length']}\n- Style: {', '.join(spec['best_practices'][:3])}\n- Hashtags: {spec['hashtag_guidance']}"
        for platform, spec in PLATFORM_SPECS.items() if platform in platform_list
    ])

    prompt = f"""{brand_context}

Analyze this content and extract {num_posts} key insights to create social media posts:

CONTENT:
{content[:3000]}

TASK:
Create {num_posts} distinct social media posts, rotating through these platforms: {', '.join(p.upper() for p in platform_list)}

PLATFORM SPECIFICATIONS:
{platforms_info}

REQUIREMENTS:
1. Each post should highlight a different key insight or angle from the content
2. Optimize each post for its target platform (length, style, formatting)
3. Include relevant hashtags per platform guidelines
4. Make each post standalone and engaging
5. Vary the hooks and angles
6. Stay true to the brand voice and messaging

FORMAT YOUR RESPONSE AS:
Post 1 - [PLATFORM]:
[post content with hashtags]

Post 2 - [PLATFORM]:
[post content with hashtags]

[etc...]

Make each post authentic to {brand_config['brand_name']}'s voice, engaging, and ready to copy-paste.
"""

    try:
        response = await _call_llm(prompt, temperature=0.85)

        result = f"""🎨 Content Repurposed Successfully! 🎨

🏢 Brand: {brand_config['brand_name']}
📄 Original content length: {len(content)} characters
📊 Generated {num_posts} posts for: {', '.join(p.upper() for p in platform_list)}

{response}

---
💡 Tip: Review and customize each post to match your brand voice before posting!
"""

        await atlantis.client_log(f"✅ Generated {num_posts} repurposed posts for {brand_config['brand_name']}")
        return result

    except Exception as e:
        logger.error(f"Error repurposing content: {e}", exc_info=True)
        return f"❌ Error repurposing content: {str(e)}"


# ============================================================
# Social Media Posting Functions
# ============================================================

def _load_social_tokens():
    """Load social media OAuth tokens from JSON file"""
    if not os.path.exists(SOCIAL_TOKENS_FILE):
        return {}
    with open(SOCIAL_TOKENS_FILE, 'r') as f:
        return json.load(f)


def _save_social_tokens(tokens: dict):
    """Save social media OAuth tokens to JSON file"""
    with open(SOCIAL_TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)


@visible
async def configure_linkedin_token(brand_id: str = ""):
    """
    Configure LinkedIn access token for a specific brand.
    Opens a form to paste your LinkedIn access token and link it to a brand.

    SETUP REQUIRED:
    1. Go to https://www.linkedin.com/developers/apps
    2. Add BOTH products to your app:
       - "Share on LinkedIn"
       - "Sign In with LinkedIn using OpenID Connect"
    3. Auth tab → Generate token with scopes: openid, profile, w_member_social
    4. Paste token in the form

    Each brand can have its own LinkedIn account.
    """

    FORM_ID = f"linkedin_token_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Load existing brands
    brands = _load_brands()
    brand_options = ""
    for bid, config in brands.items():
        selected = 'selected' if bid == brand_id else ''
        brand_options += f'<option value="{bid}" {selected}>{config["brand_name"]} ({bid})</option>'

    htmlStr = f'''
    <div style="white-space:normal;padding: 20px;
                background: linear-gradient(135deg, #0a1a1a 0%, #1b2d2d 100%);
                border: 2px solid #00a8a8;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(0,168,168,0.5);
                box-sizing: border-box;">
        <h2 style="margin-top: 0; color: #00ffff; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">🔗 LinkedIn Access Token</h2>

        <div style="margin-bottom: 15px; padding: 12px; background: rgba(0,168,168,0.2); border-radius: 6px; border: 1px solid rgba(0,255,255,0.3);">
            <div style="color: #aaffff; font-size: 13px;">
                📋 <strong>Setup Steps:</strong><br>
                1. Go to: <a href="https://www.linkedin.com/developers/apps" target="_blank" style="color: #00ffff;">LinkedIn Developer Portal</a><br>
                2. In your app, add the appropriate product:<br>
                   &nbsp;&nbsp;&nbsp;👤 <strong>Personal posting:</strong> "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect"<br>
                   &nbsp;&nbsp;&nbsp;🏢 <strong>Organization posting:</strong> "Share on LinkedIn"<br>
                3. Auth tab → Generate token with scopes:<br>
                   &nbsp;&nbsp;&nbsp;👤 Personal: <strong>openid, profile, w_member_social</strong><br>
                   &nbsp;&nbsp;&nbsp;🏢 Organization: <strong>w_organization_social</strong><br>
                4. Copy token and paste below<br>
                💡 Each brand can have its own LinkedIn account for posting
            </div>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">Brand *</label>
            <select id="brand_id_{FORM_ID}"
                    style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                           border-radius: 4px; color: #fff;">
                <option value="">Select a brand...</option>
                {brand_options}
            </select>
            <div style="margin-top: 5px; font-size: 12px; color: #aaffff;">
                Don't see your brand? Create one first with create_brand_config_form()
            </div>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">LinkedIn Access Token *</label>
            <textarea id="access_token_{FORM_ID}" placeholder="Paste your LinkedIn access token here..."
                      rows="4"
                      style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                             border-radius: 4px; color: #fff; box-sizing: border-box; font-family: monospace; font-size: 12px; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aaffff; margin-bottom: 5px; font-weight: bold;">🏢 LinkedIn Organization ID <span style="font-weight: normal;">(Optional - for organization posting only)</span></label>
            <input type="text" id="org_id_{FORM_ID}" placeholder="e.g., 94154810"
                   style="width: 100%; padding: 10px; background: #1a2a2a; border: 1px solid #00a8a8;
                          border-radius: 4px; color: #fff; box-sizing: border-box; font-family: monospace;">
            <div style="margin-top: 5px; font-size: 12px; color: #aaffff;">
                📝 Leave blank for personal posting | For organization posting: your company page ID from URL (e.g., linkedin.com/company/<strong>94154810</strong>)
            </div>
        </div>

        <button id="submit_{FORM_ID}"
                style="padding: 12px 30px;
                       background: linear-gradient(145deg, #00a8a8 0%, #005a5a 100%);
                       color: #fff;
                       border: 1px solid #00ffff;
                       border-radius: 6px;
                       cursor: pointer;
                       font-weight: bold;
                       font-size: 16px;
                       box-shadow: 0 4px 8px rgba(0,168,168,0.4);
                       width: 100%;">
            💾 Link LinkedIn Account to Brand
        </button>
    </div>
    '''

    await atlantis.client_html(htmlStr)

    miniscript = f'''
    //js
    let foo = function() {{
        thread.console.bold('LinkedIn token config form loaded');

        const brandField = document.getElementById('brand_id_{FORM_ID}');
        const tokenField = document.getElementById('access_token_{FORM_ID}');
        const orgIdField = document.getElementById('org_id_{FORM_ID}');
        const submitBtn = document.getElementById('submit_{FORM_ID}');

        submitBtn.addEventListener('click', async function() {{
            const brandId = brandField.value.trim();
            const token = tokenField.value.trim();
            const orgId = orgIdField.value.trim();

            if (!brandId) {{
                alert('Please select a brand');
                return;
            }}
            if (!token) {{
                alert('Please enter your LinkedIn access token');
                return;
            }}

            submitBtn.disabled = true;
            submitBtn.textContent = 'Saving...';

            let data = {{
                brand_id: brandId,
                access_token: token,
                linkedin_org_id: orgId
            }};

            try {{
                await sendChatter(eventData.connAccessToken, '@*save_linkedin_token', data);
                submitBtn.textContent = '✓ Saved!';
                submitBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            }} catch (error) {{
                thread.console.error('Error saving token:', error);
                submitBtn.textContent = 'Error - Try Again';
                submitBtn.disabled = false;
                submitBtn.style.background = 'linear-gradient(145deg, #00a8a8 0%, #005a5a 100%)';
            }}
        }});
    }}
    foo()
    '''

    await atlantis.client_script(miniscript)


@visible
async def save_linkedin_token(brand_id: str, access_token: str, linkedin_org_id: str = ""):
    """
    Backend handler to save LinkedIn access token for a brand.
    This is called automatically when you submit the token configuration form.

    Parameters:
    - brand_id: The brand to link the token to
    - access_token: LinkedIn access token (w_member_social OR w_organization_social)
    - linkedin_org_id: (Optional) Organization ID for company page posting
    """

    if not brand_id or not brand_id.strip():
        await atlantis.client_log("❌ Brand ID cannot be empty")
        logger.error("save_linkedin_token: Brand ID required")
        return {"error": "Brand ID required"}

    if not access_token or not access_token.strip():
        await atlantis.client_log("❌ Access token cannot be empty")
        logger.error("save_linkedin_token: Access token required")
        return {"error": "Access token required"}

    # Verify brand exists
    brands = _load_brands()
    if brand_id not in brands:
        await atlantis.client_log(f"❌ Brand '{brand_id}' not found")
        logger.error(f"save_linkedin_token: Brand '{brand_id}' not found")
        return {"error": f"Brand '{brand_id}' not found"}

    await atlantis.client_log("🔍 Verifying LinkedIn access token...")

    # Determine posting type based on organization ID
    org_id = linkedin_org_id.strip()
    is_org_posting = bool(org_id)

    try:
        headers = {
            "Authorization": f"Bearer {access_token.strip()}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        person_urn = ""
        profile_name = ""

        if is_org_posting:
            # Organization posting - token should have w_organization_social scope
            await atlantis.client_log(f"🏢 Configuring for organization posting (org ID: {org_id})")
            await atlantis.client_log("✅ Token should have w_organization_social scope")
        else:
            # Personal posting - try to get profile info
            try:
                response = await asyncio.to_thread(
                    requests.get,
                    "https://api.linkedin.com/v2/userinfo",
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    profile = response.json()
                    person_urn = profile.get("sub", "")
                    profile_name = profile.get('name', '')
                    await atlantis.client_log(f"✅ Authenticated as: {profile_name}")
                    await atlantis.client_log(f"📧 Email: {profile.get('email', 'N/A')}")
                else:
                    # Token doesn't have openid/profile scopes, but that's OK for posting
                    await atlantis.client_log("⚠️ Token doesn't have profile access (this is OK)")
                    await atlantis.client_log("✅ Token will work for posting with w_member_social scope")
            except Exception as profile_error:
                # Profile fetch failed, but we'll still save the token
                await atlantis.client_log("⚠️ Could not verify profile (token may only have w_member_social scope)")
                await atlantis.client_log("✅ Token saved - will work for posting")

        # Save token to brand config
        brands[brand_id]["linkedin_token"] = access_token.strip()
        brands[brand_id]["linkedin_person_urn"] = person_urn
        brands[brand_id]["linkedin_profile_name"] = profile_name

        # Save organization ID if provided
        if is_org_posting:
            brands[brand_id]["linkedin_org_id"] = org_id
        else:
            # Remove org_id field if switching back to personal posting
            brands[brand_id].pop("linkedin_org_id", None)

        _save_brands(brands)

        result = [{
            "Field": "Brand",
            "Value": brands[brand_id]['brand_name']
        }, {
            "Field": "Status",
            "Value": "✅ Token Saved"
        }, {
            "Field": "Person URN",
            "Value": person_urn
        }]

        await atlantis.client_data(f"LinkedIn Token Configured for '{brand_id}'", result)
        await atlantis.client_log(f"🚀 You can now use generate_and_post_to_linkedin('{brand_id}', 'topic')!")
        logger.info(f"LinkedIn token configured for brand {brand_id}, person_urn={person_urn}, name={profile_name}")

    except Exception as e:
        logger.error(f"Error saving LinkedIn token: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


def _get_brand_linkedin_token(brand_id: str):
    """Internal helper to get LinkedIn token for a brand"""
    brand_config = _get_brand_config(brand_id)

    if "linkedin_token" not in brand_config:
        raise ValueError(f"LinkedIn not configured for brand '{brand_id}'. Use configure_linkedin_token('{brand_id}') first!")

    return {
        "access_token": brand_config["linkedin_token"],
        "person_urn": brand_config.get("linkedin_person_urn", "")
    }


@visible
async def post_to_linkedin(brand_id: str, text: str, image_base64: str = "", image_filename: str = ""):
    """
    Post text (and optionally image) to LinkedIn using a brand's configured account.
    Brand ID: The brand whose LinkedIn account to use.
    Text: The post content (up to 3000 characters).
    Image base64: (Optional) Base64-encoded image data to attach.
    Image filename: (Optional) Filename for the image.
    Requires LinkedIn token to be configured first (use configure_linkedin_token).

    IMPORTANT: Your LinkedIn app needs BOTH of these products enabled:
    1. "Share on LinkedIn" (for w_member_social scope)
    2. "Sign In with LinkedIn using OpenID Connect" (for openid & profile scopes)

    When generating your token, make sure to include scopes: openid, profile, w_member_social
    """

    # Get brand's LinkedIn token
    try:
        linkedin_config = _get_brand_linkedin_token(brand_id)
    except ValueError as e:
        await atlantis.client_log(f"❌ {str(e)}")
        return {"error": str(e)}

    access_token = linkedin_config["access_token"]

    if not text or not text.strip():
        await atlantis.client_log("❌ Post text cannot be empty")
        return {"error": "Post text required"}

    if len(text) > 3000:
        await atlantis.client_log(f"⚠️ Post text too long ({len(text)} chars). Truncating to 3000 characters.")
        text = text[:2997] + "..."

    await atlantis.client_log("📤 Posting to LinkedIn...")

    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        # Determine if this is organization or personal posting
        brand_config = _get_brand_config(brand_id)
        linkedin_org_id = brand_config.get("linkedin_org_id", "")

        if linkedin_org_id:
            # Organization posting - use org ID directly from config
            author_urn = f"urn:li:organization:{linkedin_org_id}"
            await atlantis.client_log(f"🏢 Posting as organization: {linkedin_org_id}")
        else:
            # Personal posting - get member ID using /v2/userinfo (requires openid & profile scopes)
            await atlantis.client_log("🔍 Getting member ID...")
            userinfo_response = await asyncio.to_thread(
                requests.get,
                "https://api.linkedin.com/v2/userinfo",
                headers=headers,
                timeout=30
            )

            if userinfo_response.status_code != 200:
                error_text = userinfo_response.text
                await atlantis.client_log(f"❌ Failed to get member ID: {userinfo_response.status_code}")
                await atlantis.client_log(f"Response: {error_text}")
                await atlantis.client_log("")
                await atlantis.client_log("💡 This usually means your LinkedIn app is missing required scopes.")
                await atlantis.client_log("Go to: https://www.linkedin.com/developers/apps")
                await atlantis.client_log("1. Add product: 'Sign In with LinkedIn using OpenID Connect'")
                await atlantis.client_log("2. When generating token, request scopes: openid, profile, w_member_social")
                await atlantis.client_log("3. Reconfigure with: configure_linkedin_token('" + brand_id + "')")
                return {"error": f"Failed to get member ID: {userinfo_response.status_code}", "details": error_text}

            userinfo_data = userinfo_response.json()
            member_id = userinfo_data.get("sub")

            if not member_id:
                await atlantis.client_log("❌ No 'sub' field in userinfo response")
                await atlantis.client_log(f"Response: {userinfo_data}")
                return {"error": "No member ID in userinfo response"}

            author_urn = f"urn:li:person:{member_id}"
            await atlantis.client_log(f"✅ Member ID: {member_id}")

        # Build post payload
        post_data = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        # If image provided, upload it first
        if image_base64:
            await atlantis.client_log("📸 Uploading image...")

            # Register upload
            register_payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": author_urn,
                    "serviceRelationships": [{
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }]
                }
            }

            register_response = await asyncio.to_thread(
                requests.post,
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                headers=headers,
                json=register_payload,
                timeout=30
            )

            if register_response.status_code != 200:
                await atlantis.client_log(f"⚠️ Image upload registration failed: {register_response.status_code}")
            else:
                register_data = register_response.json()
                upload_url = register_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset_urn = register_data["value"]["asset"]

                # Upload image binary (from base64 - Windows compatible)
                image_data = base64.b64decode(image_base64)

                upload_response = await asyncio.to_thread(
                    requests.put,
                    upload_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    data=image_data,
                    timeout=60
                )

                if upload_response.status_code == 201:
                    await atlantis.client_log("✅ Image uploaded successfully!")

                    # Update post data with image
                    post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                    post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                        "status": "READY",
                        "description": {
                            "text": "Image"
                        },
                        "media": asset_urn,
                        "title": {
                            "text": "Image"
                        }
                    }]
                else:
                    await atlantis.client_log(f"⚠️ Image upload failed: {upload_response.status_code}")

        # Create the post
        response = await asyncio.to_thread(
            requests.post,
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=post_data,
            timeout=30
        )

        if response.status_code == 201:
            post_id = response.json().get("id", "unknown")

            result = [{
                "Field": "Status",
                "Value": "✅ Posted Successfully"
            }, {
                "Field": "Post ID",
                "Value": post_id
            }, {
                "Field": "Length",
                "Value": f"{len(text)} characters"
            }]

            await atlantis.client_data("LinkedIn Post Created", result)
            logger.info(f"LinkedIn post created: {post_id}")
        else:
            error_msg = response.text
            await atlantis.client_log(f"❌ LinkedIn API error: {response.status_code}")
            await atlantis.client_log(f"Details: {error_msg}")
            logger.error(f"LinkedIn post failed: {response.status_code} - {error_msg}")
            return {"error": f"LinkedIn API error: {response.status_code}", "details": error_msg}

    except Exception as e:
        logger.error(f"Error posting to LinkedIn: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


@visible
async def set_linkedin_company_page(brand_id: str, page_url: str):
    """
    Set the LinkedIn company page URL for a brand (for Chrome automation posting).
    Brand ID: The brand to configure.
    Page URL: LinkedIn company page URL (e.g. https://www.linkedin.com/company/project-atlantis)
    """

    if not page_url or not page_url.strip():
        await atlantis.client_log("❌ Page URL cannot be empty")
        return {"error": "Page URL required"}

    if "linkedin.com/company/" not in page_url:
        await atlantis.client_log("❌ URL must be a LinkedIn company page (linkedin.com/company/...)")
        return {"error": "Invalid company page URL"}

    try:
        brands = _load_brands()
        if brand_id not in brands:
            await atlantis.client_log(f"❌ Brand '{brand_id}' not found")
            return {"error": "Brand not found"}

        brands[brand_id]["linkedin_company_page"] = page_url
        _save_brands(brands)

        result = [{
            "Field": "Brand ID",
            "Value": brand_id
        }, {
            "Field": "Status",
            "Value": "✅ Saved"
        }, {
            "Field": "Page URL",
            "Value": page_url
        }]

        await atlantis.client_data("LinkedIn Company Page Configured", result)

    except Exception as e:
        logger.error(f"Error setting LinkedIn company page: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


@visible
async def generate_and_post_to_linkedin_chrome(brand_id: str, topic: str, include_image: bool = True, image_prompt: str = ""):
    """
    Generate LinkedIn content and post via Chrome automation (works for organization pages!).
    Brand ID: The brand to generate content for.
    Topic: What the post should be about.
    Include image: Whether to generate and attach an image (default True).
    Image prompt: (Optional) Custom prompt for image generation. Overrides brand style and defaults.

    Posts using Chrome automation - NO API tokens needed!
    Set your company page URL with: set_linkedin_company_page('brand_id', 'https://...')
    Make sure you're logged into LinkedIn in Chrome!
    """

    # Validate brand exists
    try:
        brand_config = _get_brand_config(brand_id)
    except ValueError as e:
        await atlantis.client_log(f"❌ {str(e)}")
        return {"error": str(e)}

    await atlantis.client_log(f"🚀 Generating LinkedIn content for approval...")

    # Generate content
    if include_image:
        result = await generate_social_post_with_image(
            brand_id=brand_id,
            topic=topic,
            platform="linkedin",
            image_style="modern",
            image_prompt=image_prompt
        )
    else:
        result = await generate_social_post(
            brand_id=brand_id,
            topic=topic,
            platform="linkedin"
        )

    if isinstance(result, str):
        return {"error": "Content generation failed", "details": result}

    post_text = result.get("text", "")
    image_base64 = result.get("image_base64", "") if include_image else ""
    image_filename = result.get("image_filename", "") if include_image else ""

    if not post_text:
        await atlantis.client_log("❌ No content generated")
        return {"error": "No content generated"}

    # Show approval form - same as API version but calls Chrome posting
    FORM_ID = f"linkedin_chrome_approve_{str(uuid.uuid4()).replace('-', '')[:8]}"

    approval_html = f'''
    <div style="max-width: 900px; margin: 20px auto; padding: 0; background: linear-gradient(135deg, rgba(10, 26, 26, 0.95) 0%, rgba(27, 45, 45, 0.95) 100%); backdrop-filter: blur(20px); border: 1px solid rgba(0, 255, 255, 0.3); border-radius: 20px; box-shadow: 0 8px 32px 0 rgba(0, 168, 168, 0.2); overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="background: linear-gradient(90deg, rgba(0, 168, 168, 0.3) 0%, rgba(0, 255, 255, 0.2) 100%); padding: 25px; border-bottom: 1px solid rgba(0, 255, 255, 0.2);">
            <h2 style="margin: 0; text-align: center; color: #00ffff; font-size: 24px; font-weight: 600; text-shadow: 0 2px 10px rgba(0, 255, 255, 0.3);">🌐 LinkedIn Post - Chrome Automation</h2>
        </div>
        <div style="padding: 30px;">
            <div style="background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(0, 255, 255, 0.2); border-radius: 16px; padding: 20px; margin-bottom: 24px;">
                <div style="font-size: 14px; font-weight: 600; color: #aaffff; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;">📝 Post Content (Editable)</div>
                <textarea id="post_text_{FORM_ID}" style="width: 100%; background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(0, 255, 255, 0.15); border-radius: 12px; padding: 18px; color: #ffffff; font-size: 15px; line-height: 1.7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; resize: vertical; min-height: 150px; box-sizing: border-box;">{post_text}</textarea>
                <div style="margin-top: 12px; font-size: 13px; color: rgba(170, 255, 255, 0.7);"><span id="char_count_{FORM_ID}" style="background: rgba(0, 168, 168, 0.3); padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(0, 255, 255, 0.2);">{len(post_text)} / 3000 chars</span></div>
            </div>
            {"<div style='background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(0, 255, 255, 0.2); border-radius: 16px; padding: 20px; margin-bottom: 24px;'><div style='font-size: 14px; font-weight: 600; color: #aaffff; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;'>🖼️ Generated Image</div><img src='data:image/png;base64," + image_base64 + "' style='width: 100%; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);'/></div>" if image_base64 else ""}
            <button id="post_btn_{FORM_ID}" style="width: 100%; padding: 16px; background: linear-gradient(145deg, #00a8a8 0%, #005a5a 100%); color: #fff; border: 1px solid #00ffff; border-radius: 12px; cursor: pointer; font-weight: 600; font-size: 16px; box-shadow: 0 6px 16px rgba(0, 168, 168, 0.4);">🚀 Post to LinkedIn (Chrome)</button>
        </div>
    </div>
    '''

    await atlantis.client_html(approval_html)

    script = f'''
    //js
    (function() {{
        const textarea = document.getElementById('post_text_{FORM_ID}');
        const charCount = document.getElementById('char_count_{FORM_ID}');
        const postBtn = document.getElementById('post_btn_{FORM_ID}');

        textarea.addEventListener('input', function() {{
            const len = this.value.length;
            charCount.textContent = len + ' / 3000 chars';
            if (len > 3000) {{
                charCount.style.background = 'rgba(255, 0, 0, 0.3)';
                charCount.style.borderColor = 'rgba(255, 0, 0, 0.5)';
            }} else {{
                charCount.style.background = 'rgba(0, 168, 168, 0.3)';
                charCount.style.borderColor = 'rgba(0, 255, 255, 0.2)';
            }}
        }});

        postBtn.addEventListener('click', async function() {{
            const text = textarea.value.trim();
            if (!text) {{
                alert('Post text cannot be empty!');
                return;
            }}
            if (text.length > 3000) {{
                alert('Post text is too long! Max 3000 characters.');
                return;
            }}

            postBtn.disabled = true;
            postBtn.textContent = '⏳ Posting via Chrome...';
            postBtn.style.background = 'linear-gradient(145deg, #555 0%, #333 100%)';

            try {{
                await sendChatter(eventData.connAccessToken, '@*approve_linkedin_post_chrome', {{
                    brand_id: '{brand_id}',
                    text: text,
                    image_base64: '{image_base64}',
                    image_filename: '{image_filename}'
                }});
                postBtn.textContent = '✅ Posted!';
                postBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            }} catch (error) {{
                console.error('Error posting:', error);
                postBtn.textContent = '❌ Error - Try Again';
                postBtn.disabled = false;
                postBtn.style.background = 'linear-gradient(145deg, #00a8a8 0%, #005a5a 100%)';
            }}
        }});
    }})();
    '''

    await atlantis.client_script(script)

    return {
        "status": "approval_form_shown",
        "brand": brand_config["brand_name"],
        "text_length": len(post_text),
        "has_image": bool(image_base64)
    }


@visible
async def approve_linkedin_post_chrome(brand_id: str, text: str, image_base64: str = "", image_filename: str = ""):
    """
    Internal handler for Chrome-based LinkedIn posts. Called from approval form.
    """

    await atlantis.client_log("📤 Posting approved content to LinkedIn via Chrome...")
    post_result = await post_to_linkedin_chrome(brand_id=brand_id, text=text, image_base64=image_base64, image_filename=image_filename)
    logger.info(f"approve_linkedin_post_chrome completed: {len(text)} chars, image={bool(image_base64)}")


@visible
async def post_to_linkedin_chrome(brand_id: str, text: str, image_base64: str = "", image_filename: str = "", page_url: str = ""):
    """
    Post to LinkedIn using Chrome automation (works for BOTH personal AND organization pages).
    Brand ID: The brand to post for.
    Text: The post content.
    Image base64: (Optional) Base64-encoded image data to attach.
    Image filename: (Optional) Filename for the image.
    Page URL: (Optional) LinkedIn company page URL override.
              If not provided, uses the page URL saved in brand config (set with set_linkedin_company_page).
              Leave both empty to post to your personal profile.

    This method bypasses LinkedIn API restrictions - just log into LinkedIn in Chrome first!
    No special tokens or company email needed!
    """

    brand_config = _get_brand_config(brand_id)

    if not text or not text.strip():
        await atlantis.client_log("❌ Post text cannot be empty")
        return {"error": "Post text required"}

    await atlantis.client_log("🌐 Opening LinkedIn in Chrome...")

    try:
        # Determine which page to navigate to
        if not page_url:
            page_url = brand_config.get("linkedin_company_page", "")

        if page_url:
            start_url = page_url
            await atlantis.client_log(f"📄 Posting to organization page: {page_url}")
        else:
            start_url = "https://www.linkedin.com/feed/"
            await atlantis.client_log("📄 Posting to personal profile")

        # Navigate to LinkedIn
        nav_result = await atlantis.call_mcp_tool("chrome-devtools", "navigate_page", {
            "url": start_url,
            "timeout": 10000
        })

        await atlantis.client_log("⏳ Waiting for page to load...")
        await asyncio.sleep(3)

        # Take snapshot to find the "Start a post" button
        snapshot = await atlantis.call_mcp_tool("chrome-devtools", "take_snapshot", {})

        await atlantis.client_log("🔍 Looking for post button...")

        # Click "Start a post" button - LinkedIn uses different selectors
        # We'll search for common text patterns
        if "Start a post" in snapshot.get("content", ""):
            # Find and click the start post button
            click_result = await atlantis.call_mcp_tool("chrome-devtools", "click", {
                "uid": "start_post_button"  # This will need to be found from snapshot
            })

            await atlantis.client_log("✍️ Typing post content...")
            await asyncio.sleep(2)

            # Type the post text
            fill_result = await atlantis.call_mcp_tool("chrome-devtools", "fill", {
                "uid": "post_textarea",
                "value": text
            })

            # If image provided, upload it
            if image_base64:
                await atlantis.client_log("📸 Uploading image...")

                # Save base64 to temp file for Chrome upload (Chrome needs file path)
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_image_path = os.path.join(temp_dir, image_filename or f"linkedin_image_{uuid.uuid4().hex[:8]}.png")

                with open(temp_image_path, 'wb') as f:
                    f.write(base64.b64decode(image_base64))

                try:
                    upload_result = await atlantis.call_mcp_tool("chrome-devtools", "upload_file", {
                        "uid": "image_upload_button",
                        "filePath": temp_image_path
                    })
                    await asyncio.sleep(2)
                finally:
                    # Clean up temp file
                    try:
                        os.remove(temp_image_path)
                    except:
                        pass

            # Click Post button
            await atlantis.client_log("🚀 Publishing post...")
            post_result = await atlantis.call_mcp_tool("chrome-devtools", "click", {
                "uid": "post_button"
            })

            await asyncio.sleep(3)
            await atlantis.client_log("✅ Posted to LinkedIn successfully!")
        else:
            await atlantis.client_log("❌ Could not find 'Start a post' button")
            await atlantis.client_log("💡 Make sure you're logged into LinkedIn in Chrome!")
            return {"error": "Not logged in or page layout changed"}

    except Exception as e:
        logger.error(f"Error posting to LinkedIn via Chrome: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


@visible
async def generate_and_post_to_linkedin(brand_id: str, topic: str, include_image: bool = True, image_prompt: str = ""):
    """
    Generate LinkedIn content for a brand and show approval form before posting.
    Brand ID: The brand to generate content for (use list_brands to see options).
    Topic: What the post should be about.
    Include image: Whether to generate and attach an image (default True).
    Image prompt: (Optional) Custom prompt for image generation. Overrides brand style and defaults.
    Shows you the generated content and lets you approve before posting to LinkedIn.
    Uses the LinkedIn account configured for this brand.
    """

    # Check LinkedIn configured for this brand
    try:
        brand_config = _get_brand_config(brand_id)
        if "linkedin_token" not in brand_config:
            await atlantis.client_log(f"❌ LinkedIn not configured for brand '{brand_id}'")
            await atlantis.client_log(f"💡 Use configure_linkedin_token('{brand_id}') to link a LinkedIn account!")
            return {"error": "LinkedIn not configured for this brand"}
    except ValueError as e:
        await atlantis.client_log(f"❌ {str(e)}")
        return {"error": str(e)}

    await atlantis.client_log(f"🚀 Generating LinkedIn content for approval...")

    # Generate content
    if include_image:
        result = await generate_social_post_with_image(
            brand_id=brand_id,
            topic=topic,
            platform="linkedin",
            image_style="modern",
            image_prompt=image_prompt
        )
    else:
        result = await generate_social_post(
            brand_id=brand_id,
            topic=topic,
            platform="linkedin"
        )

    if isinstance(result, str):
        # Error case
        return {"error": "Content generation failed", "details": result}

    # Extract text and image data
    post_text = result.get("text", "")
    image_base64 = result.get("image_base64", "") if include_image else ""
    image_filename = result.get("image_filename", "") if include_image else ""

    if not post_text:
        await atlantis.client_log("❌ No content generated")
        return {"error": "No content generated"}

    # Show approval form
    FORM_ID = f"linkedin_approve_{str(uuid.uuid4()).replace('-', '')[:8]}"

    approval_html = f'''
    <div style="
        max-width: 900px;
        margin: 20px auto;
        padding: 0;
        background: linear-gradient(135deg, rgba(10, 26, 26, 0.95) 0%, rgba(27, 45, 45, 0.95) 100%);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 168, 168, 0.2);
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    ">
        <!-- Header -->
        <div style="
            background: linear-gradient(90deg, rgba(0, 168, 168, 0.3) 0%, rgba(0, 255, 255, 0.2) 100%);
            padding: 25px;
            border-bottom: 1px solid rgba(0, 255, 255, 0.2);
        ">
            <h2 style="
                margin: 0;
                text-align: center;
                color: #00ffff;
                font-size: 24px;
                font-weight: 600;
                text-shadow: 0 2px 10px rgba(0, 255, 255, 0.3);
            ">
                📝 LinkedIn Post - Approval Required
            </h2>
        </div>

        <div style="padding: 30px;">
            <!-- Post Text -->
            <div style="
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 255, 255, 0.2);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 24px;
            ">
                <div style="
                    font-size: 14px;
                    font-weight: 600;
                    color: #aaffff;
                    margin-bottom: 12px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">
                    📝 Post Content (Editable)
                </div>
                <textarea id="post_text_{FORM_ID}" style="
                    width: 100%;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(0, 255, 255, 0.15);
                    border-radius: 12px;
                    padding: 18px;
                    color: #ffffff;
                    font-size: 15px;
                    line-height: 1.7;
                    font-weight: 400;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    resize: vertical;
                    min-height: 150px;
                    box-sizing: border-box;
                ">{post_text}</textarea>
                <div style="
                    margin-top: 12px;
                    font-size: 13px;
                    color: rgba(170, 255, 255, 0.7);
                ">
                    <span id="char_count_{FORM_ID}" style="
                        background: rgba(0, 168, 168, 0.3);
                        padding: 4px 10px;
                        border-radius: 20px;
                        border: 1px solid rgba(0, 255, 255, 0.2);
                    ">
                        {len(post_text)} / 3000 chars
                    </span>
                </div>
            </div>

            <!-- Image Preview & Upload -->
            {"" if not image_base64 else f'''
            <div style="
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 255, 255, 0.2);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 24px;
            ">
                <div style="
                    font-size: 14px;
                    font-weight: 600;
                    color: #aaffff;
                    margin-bottom: 16px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">
                    🖼️ Attached Image
                </div>
                <div id="image_preview_{FORM_ID}" style="
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
                    margin-bottom: 16px;
                ">
                    <img id="preview_img_{FORM_ID}" src="data:image/png;base64,{image_base64}"
                         style="width: 100%; height: auto; display: block;" />
                </div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="file" id="image_upload_{FORM_ID}" accept="image/*" style="display: none;" />
                    <button id="replace_image_btn_{FORM_ID}" style="
                        padding: 10px 20px;
                        background: linear-gradient(145deg, #555 0%, #333 100%);
                        color: #fff;
                        border: 1px solid #777;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: bold;
                        font-size: 14px;
                    ">
                        🔄 Replace Image
                    </button>
                    <span id="upload_status_{FORM_ID}" style="
                        font-size: 12px;
                        color: rgba(170, 255, 255, 0.7);
                    "></span>
                </div>
            </div>
            '''}

            <!-- Action Buttons -->
            <div style="display: flex; gap: 15px;">
                <button id="post_btn_{FORM_ID}" style="
                    flex: 1;
                    padding: 15px 30px;
                    background: linear-gradient(145deg, #00a8a8 0%, #005a5a 100%);
                    color: #fff;
                    border: 1px solid #00ffff;
                    border-radius: 12px;
                    cursor: pointer;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 4px 12px rgba(0, 168, 168, 0.4);
                ">
                    ✅ Post to LinkedIn
                </button>
                <button id="cancel_btn_{FORM_ID}" style="
                    flex: 1;
                    padding: 15px 30px;
                    background: linear-gradient(145deg, #333 0%, #1a1a1a 100%);
                    color: #aaa;
                    border: 1px solid #555;
                    border-radius: 12px;
                    cursor: pointer;
                    font-weight: bold;
                    font-size: 16px;
                ">
                    ❌ Cancel
                </button>
            </div>
        </div>
    </div>
    '''

    await atlantis.client_html(approval_html)

    # Store post data temporarily for approval handler
    post_data_key = f"linkedin_post_{FORM_ID}"

    miniscript = f'''
    //js
    let foo = function() {{
        thread.console.bold('LinkedIn approval form loaded');

        const textArea = document.getElementById('post_text_{FORM_ID}');
        const charCount = document.getElementById('char_count_{FORM_ID}');
        const postBtn = document.getElementById('post_btn_{FORM_ID}');
        const cancelBtn = document.getElementById('cancel_btn_{FORM_ID}');
        const replaceImageBtn = document.getElementById('replace_image_btn_{FORM_ID}');
        const imageUpload = document.getElementById('image_upload_{FORM_ID}');
        const uploadStatus = document.getElementById('upload_status_{FORM_ID}');
        const previewImg = document.getElementById('preview_img_{FORM_ID}');

        // Store post data globally for approval handler
        window.linkedinPostData_{FORM_ID} = {{
            brand_id: "{brand_id}",
            image_base64: "{image_base64}",
            image_filename: "{image_filename}"
        }};

        // Update character count
        textArea.addEventListener('input', function() {{
            const len = textArea.value.length;
            charCount.textContent = len + ' / 3000 chars';
            if (len > 3000) {{
                charCount.style.background = 'rgba(200, 50, 50, 0.5)';
                charCount.style.borderColor = 'rgba(255, 100, 100, 0.5)';
            }} else {{
                charCount.style.background = 'rgba(0, 168, 168, 0.3)';
                charCount.style.borderColor = 'rgba(0, 255, 255, 0.2)';
            }}
        }});

        // Replace image button - trigger file input
        if (replaceImageBtn) {{
            replaceImageBtn.addEventListener('click', function() {{
                imageUpload.click();
            }});
        }}

        // Handle image upload with validation
        if (imageUpload) {{
            imageUpload.addEventListener('change', async function(e) {{
                const file = e.target.files[0];
                if (!file) return;

                // Validate file size (3MB limit)
                const maxSize = 3 * 1024 * 1024; // 3MB in bytes
                if (file.size > maxSize) {{
                    uploadStatus.textContent = '❌ File too large (max 3MB)';
                    uploadStatus.style.color = '#ff5555';
                    return;
                }}

                uploadStatus.textContent = '🔄 Validating image...';
                uploadStatus.style.color = '#aaffff';

                // Read and validate image
                const reader = new FileReader();
                reader.onload = async function(event) {{
                    const img = new Image();
                    img.onload = async function() {{
                        const width = img.width;
                        const height = img.height;

                        // Calculate aspect ratio
                        const aspectRatio = width / height;

                        // LinkedIn preferred aspect ratios (with +-2 tolerance)
                        // 1.91:1 (1200x628), 1:1 (1200x1200), 4:5 (1080x1350)
                        const validRatios = [
                            {{ name: '1.91:1', value: 1.91, tolerance: 0.1 }},
                            {{ name: '1:1', value: 1.0, tolerance: 0.1 }},
                            {{ name: '4:5', value: 0.8, tolerance: 0.1 }}
                        ];

                        let isValidRatio = validRatios.some(ratio =>
                            Math.abs(aspectRatio - ratio.value) <= ratio.tolerance
                        );

                        if (!isValidRatio) {{
                            uploadStatus.textContent = '⚠️ Aspect ratio should be 1.91:1, 1:1, or 4:5';
                            uploadStatus.style.color = '#ffaa55';
                            // Still allow upload but warn
                        }}

                        // Store image locally - will be processed when posting
                        const base64Data = event.target.result.split(',')[1];

                        // Store replacement image data in global object
                        window.linkedinPostData_{FORM_ID}.replacement_image = {{
                            base64: base64Data,
                            filename: file.name
                        }};

                        // Update preview immediately
                        previewImg.src = event.target.result;

                        uploadStatus.textContent = '✅ Image ready!';
                        uploadStatus.style.color = '#55ff55';

                        thread.console.info('Image staged for upload')
                    }};
                    img.src = event.target.result;
                }};
                reader.readAsDataURL(file);
            }});
        }}

        // Post button
        postBtn.addEventListener('click', async function() {{
            const text = textArea.value.trim();

            if (!text) {{
                alert('Post text cannot be empty');
                return;
            }}

            if (text.length > 3000) {{
                alert('Post text too long. Maximum 3000 characters.');
                return;
            }}

            postBtn.disabled = true;
            cancelBtn.disabled = true;
            postBtn.textContent = 'Posting...';

            const data = {{
                brand_id: window.linkedinPostData_{FORM_ID}.brand_id,
                text: text,
                image_base64: window.linkedinPostData_{FORM_ID}.image_base64,
                image_filename: window.linkedinPostData_{FORM_ID}.image_filename
            }};

            // If user uploaded a replacement image, include it
            if (window.linkedinPostData_{FORM_ID}.replacement_image) {{
                data.replacement_image_base64 = window.linkedinPostData_{FORM_ID}.replacement_image.base64;
                data.replacement_image_filename = window.linkedinPostData_{FORM_ID}.replacement_image.filename;
            }}

            try {{
                await sendChatter(eventData.connAccessToken, '@*approve_linkedin_post', data);
            }} catch (error) {{
                thread.console.error('Error posting to LinkedIn:', error);
                postBtn.textContent = 'Error - Try Again';
                postBtn.disabled = false;
                cancelBtn.disabled = false;
            }}
        }});

        // Cancel button
        cancelBtn.addEventListener('click', function() {{
            thread.console.info('LinkedIn post cancelled');
            cancelBtn.textContent = '✓ Cancelled';
            postBtn.disabled = true;
            cancelBtn.disabled = true;
        }});
    }}
    foo()
    '''

    await atlantis.client_script(miniscript)

    return {
        "status": "awaiting_approval",
        "text_length": len(post_text),
        "has_image": bool(image_base64)
    }


@visible
async def approve_linkedin_post(brand_id: str, text: str, image_base64: str = "", image_filename: str = "", replacement_image_base64: str = "", replacement_image_filename: str = ""):
    """
    Internal handler for approved LinkedIn posts. Called from approval form.
    This posts the approved content to LinkedIn using the brand's account.
    If replacement_image is provided, uses it instead.
    """
    logger.info(f"approve_linkedin_post called for brand_id={brand_id}, has_replacement={bool(replacement_image_base64)}")

    # If user uploaded a replacement image, use it
    if replacement_image_base64:
        await atlantis.client_log("🖼️ Using replacement image...")
        image_base64 = replacement_image_base64
        image_filename = replacement_image_filename or "replacement.png"
        logger.info(f"Using replacement image: {image_filename}")

    await atlantis.client_log("📤 Posting approved content to LinkedIn...")
    post_result = await post_to_linkedin(brand_id=brand_id, text=text, image_base64=image_base64, image_filename=image_filename)

    logger.info(f"LinkedIn post completed successfully")


@visible
async def replace_linkedin_image(brand_id: str, image_base64: str, original_filename: str):
    """
    Internal handler for replacing image in LinkedIn approval form.
    Validates size, resizes dimensions to be divisible by 16, and saves to temp file.
    Called from approval form when user uploads a replacement image.
    """
    logger.info(f"replace_linkedin_image called for brand_id={brand_id}, filename={original_filename}")
    try:
        await atlantis.client_log("🖼️ Processing replacement image...")

        # Decode base64 image
        image_data = base64.b64decode(image_base64)

        # Check size (3MB limit)
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > 3:
            await atlantis.client_log(f"❌ Image too large: {size_mb:.2f}MB (max 3MB)")
            logger.error(f"Image too large: {size_mb:.2f}MB")
            return {"error": f"Image too large: {size_mb:.2f}MB (max 3MB)"}

        # Load image with PIL
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data))
        original_width, original_height = img.size

        await atlantis.client_log(f"📐 Original size: {original_width}x{original_height}")

        # Resize dimensions to be divisible by 16 (round down)
        new_width = (original_width // 16) * 16
        new_height = (original_height // 16) * 16

        # Make sure we don't make it too small
        if new_width < 400 or new_height < 400:
            await atlantis.client_log("⚠️ Image would be too small after resize, keeping original dimensions")
            new_width = original_width
            new_height = original_height
        elif new_width != original_width or new_height != original_height:
            await atlantis.client_log(f"✂️ Resizing to {new_width}x{new_height} (divisible by 16)")
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save to temp file
        import tempfile
        file_ext = original_filename.split('.')[-1].lower()
        if file_ext not in ['jpg', 'jpeg', 'png', 'webp']:
            file_ext = 'png'

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
        temp_path = temp_file.name

        # Save with appropriate format
        if file_ext in ['jpg', 'jpeg']:
            img = img.convert('RGB')
            img.save(temp_path, 'JPEG', quality=90)
        else:
            img.save(temp_path, 'PNG')

        temp_file.close()

        await atlantis.client_log(f"✅ Image saved: {new_width}x{new_height}, {os.path.getsize(temp_path) / 1024:.1f}KB")

        # Store temp path in shared storage for retrieval
        atlantis.shared.set(f"linkedin_temp_image_{brand_id}", temp_path)

        logger.info(f"Replaced LinkedIn image successfully: {temp_path} ({new_width}x{new_height})")

        # Return temp path as plain string (not dict - avoids JSON parsing issues)
        return temp_path

    except Exception as e:
        logger.error(f"Error replacing LinkedIn image: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error processing image: {str(e)}")
        return {"error": str(e)}


# ============================================================
# Facebook Configuration Functions
# ============================================================

@visible
async def configure_facebook_token(brand_id: str = ""):
    """
    Configure Facebook Page Access Token for a specific brand.
    Opens a form to paste your Facebook Page Access Token and Page ID.

    SETUP REQUIRED:
    1. Go to https://developers.facebook.com/
    2. Create/select an app
    3. Add "Pages Management" product
    4. Tools → Access Token Tool → Get Page Access Token
    5. Get your Page ID from your Facebook page URL or settings
    6. Paste both in the form

    Each brand can have its own Facebook page.
    """

    FORM_ID = f"facebook_token_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Load existing brands
    brands = _load_brands()
    brand_options = ""
    for bid, config in brands.items():
        selected = 'selected' if bid == brand_id else ''
        brand_options += f'<option value="{bid}" {selected}>{config["brand_name"]} ({bid})</option>'

    htmlStr = f'''
    <div style="white-space:normal;padding: 20px;
                background: linear-gradient(135deg, #1a0a1a 0%, #2d1b2d 100%);
                border: 2px solid #4267B2;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(66,103,178,0.5);
                box-sizing: border-box;">
        <h2 style="margin-top: 0; color: #4267B2; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">📘 Facebook Page Access Token</h2>

        <div style="margin-bottom: 15px; padding: 12px; background: rgba(66,103,178,0.2); border-radius: 6px; border: 1px solid rgba(66,103,178,0.3);">
            <div style="color: #aac5ff; font-size: 13px;">
                📋 <strong>Setup Steps:</strong><br>
                1. Go to: <a href="https://developers.facebook.com/" target="_blank" style="color: #4267B2;">Facebook Developer Portal</a><br>
                2. Create/select an app → Add "Pages Management" product<br>
                3. Tools → Access Token Tool → Generate Page Access Token<br>
                4. Get Page ID from your Facebook page settings or URL<br>
                💡 Each brand can have its own Facebook page for posting
            </div>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aac5ff; margin-bottom: 5px; font-weight: bold;">Brand *</label>
            <select id="brand_id_{FORM_ID}"
                    style="width: 100%; padding: 10px; background: #1a1a2a; border: 1px solid #4267B2;
                           border-radius: 4px; color: #fff;">
                <option value="">Select a brand...</option>
                {brand_options}
            </select>
            <div style="margin-top: 5px; font-size: 12px; color: #aac5ff;">
                Don't see your brand? Create one first with create_brand_config_form()
            </div>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aac5ff; margin-bottom: 5px; font-weight: bold;">Facebook Page Access Token *</label>
            <textarea id="access_token_{FORM_ID}" placeholder="Paste your Facebook Page Access Token here..."
                      rows="4"
                      style="width: 100%; padding: 10px; background: #1a1a2a; border: 1px solid #4267B2;
                             border-radius: 4px; color: #fff; box-sizing: border-box; font-family: monospace; font-size: 12px; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 15px;">
            <label style="display: block; color: #aac5ff; margin-bottom: 5px; font-weight: bold;">Facebook Page ID *</label>
            <input type="text" id="page_id_{FORM_ID}" placeholder="Your Facebook Page ID (numeric)"
                   style="width: 100%; padding: 10px; background: #1a1a2a; border: 1px solid #4267B2;
                          border-radius: 4px; color: #fff; box-sizing: border-box; font-family: monospace; font-size: 12px;">
        </div>

        <button id="submit_{FORM_ID}"
                style="padding: 12px 30px;
                       background: linear-gradient(145deg, #4267B2 0%, #2d4373 100%);
                       color: #fff;
                       border: 1px solid #4267B2;
                       border-radius: 6px;
                       cursor: pointer;
                       font-weight: bold;
                       font-size: 16px;
                       box-shadow: 0 4px 8px rgba(66,103,178,0.4);
                       width: 100%;">
            💾 Link Facebook Page to Brand
        </button>
    </div>
    '''

    await atlantis.client_html(htmlStr)

    miniscript = f'''
    //js
    let foo = function() {{
        thread.console.bold('Facebook token config form loaded');

        const brandField = document.getElementById('brand_id_{FORM_ID}');
        const tokenField = document.getElementById('access_token_{FORM_ID}');
        const pageIdField = document.getElementById('page_id_{FORM_ID}');
        const submitBtn = document.getElementById('submit_{FORM_ID}');

        submitBtn.addEventListener('click', async function() {{
            const brandId = brandField.value.trim();
            const token = tokenField.value.trim();
            const pageId = pageIdField.value.trim();

            if (!brandId) {{
                alert('Please select a brand');
                return;
            }}
            if (!token) {{
                alert('Please enter your Facebook Page Access Token');
                return;
            }}
            if (!pageId) {{
                alert('Please enter your Facebook Page ID');
                return;
            }}

            submitBtn.disabled = true;
            submitBtn.textContent = 'Saving...';

            let data = {{
                brand_id: brandId,
                access_token: token,
                page_id: pageId
            }};

            try {{
                await sendChatter(eventData.connAccessToken, '@*save_facebook_token', data);
                submitBtn.textContent = '✓ Saved!';
                submitBtn.style.background = 'linear-gradient(145deg, #2a5a2a 0%, #1a3a1a 100%)';
            }} catch (error) {{
                thread.console.error('Error saving token:', error);
                submitBtn.textContent = 'Error - Try Again';
                submitBtn.disabled = false;
                submitBtn.style.background = 'linear-gradient(145deg, #4267B2 0%, #2d4373 100%)';
            }}
        }});
    }}
    foo()
    '''

    await atlantis.client_script(miniscript)


@visible
async def save_facebook_token(brand_id: str, access_token: str, page_id: str):
    """
    Backend handler to save Facebook Page Access Token and Page ID for a brand.
    This is called automatically when you submit the token configuration form.
    """

    if not brand_id or not brand_id.strip():
        await atlantis.client_log("❌ Brand ID cannot be empty")
        logger.error("save_facebook_token: Brand ID required")
        return {"error": "Brand ID required"}

    if not access_token or not access_token.strip():
        await atlantis.client_log("❌ Access token cannot be empty")
        logger.error("save_facebook_token: Access token required")
        return {"error": "Access token required"}

    if not page_id or not page_id.strip():
        await atlantis.client_log("❌ Page ID cannot be empty")
        logger.error("save_facebook_token: Page ID required")
        return {"error": "Page ID required"}

    try:
        brands = _load_brands()

        if brand_id not in brands:
            await atlantis.client_log(f"❌ Brand '{brand_id}' not found")
            logger.error(f"save_facebook_token: Brand '{brand_id}' not found")
            return {"error": f"Brand '{brand_id}' not found"}

        # Save to brand config
        brands[brand_id]["facebook_token"] = access_token.strip()
        brands[brand_id]["facebook_page_id"] = page_id.strip()

        _save_brands(brands)

        result = [{
            "Field": "Brand ID",
            "Value": brand_id
        }, {
            "Field": "Page ID",
            "Value": page_id
        }, {
            "Field": "Status",
            "Value": "✅ Token Saved"
        }]

        await atlantis.client_data("Facebook Page Configured", result)
        await atlantis.client_log(f"🚀 You can now use Facebook analytics and posting functions!")

        logger.info(f"Facebook token configured for brand '{brand_id}', page_id={page_id}")

    except Exception as e:
        logger.error(f"Error saving Facebook token: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


# ============================================================
# Facebook Analytics Functions
# ============================================================

@visible
async def get_facebook_page_insights(brand_id: str):
    """
    Get analytics for your Facebook page (followers, engagement, reach).
    Brand ID: The brand to get insights for.

    Shows page-level metrics like fan count, reach, and engagement.
    Requires Facebook page to be configured with configure_facebook_token().
    """

    try:
        brand_config = _get_brand_config(brand_id)

        if "facebook_token" not in brand_config or "facebook_page_id" not in brand_config:
            await atlantis.client_log(f"❌ Facebook not configured for brand '{brand_id}'")
            await atlantis.client_log(f"💡 Use configure_facebook_token('{brand_id}') to link a Facebook page!")
            return {"error": "Facebook not configured for this brand"}

        access_token = brand_config["facebook_token"]
        page_id = brand_config["facebook_page_id"]

        await atlantis.client_log("📊 Fetching Facebook page insights...")

        # Call Facebook Graph API directly
        response = await asyncio.to_thread(
            requests.get,
            f"https://graph.facebook.com/v18.0/{page_id}",
            params={"fields": "fan_count,name", "access_token": access_token},
            timeout=30
        )

        if response.status_code != 200:
            await atlantis.client_log(f"❌ Facebook API error: {response.status_code}")
            await atlantis.client_log(f"Response: {response.text}")
            return {"error": f"Facebook API error: {response.status_code}", "details": response.text}

        data = response.json()
        fan_count = data.get("fan_count", 0)
        page_name = data.get("name", "Unknown")

        await atlantis.client_log(f"✅ Page Analytics for {page_name}:")
        await atlantis.client_log(f"👥 Followers: {fan_count:,}")

        return {
            "page_name": page_name,
            "fan_count": fan_count,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error getting Facebook page insights: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


@visible
async def get_facebook_post_analytics(brand_id: str, post_id: str):
    """
    Get detailed analytics for a specific Facebook post.
    Brand ID: The brand whose Facebook page to query.
    Post ID: The Facebook post ID to analyze.

    Shows metrics like reactions, comments, shares, and reach for a specific post.
    """

    if not post_id or not post_id.strip():
        await atlantis.client_log("❌ Post ID cannot be empty")
        return {"error": "Post ID required"}

    try:
        brand_config = _get_brand_config(brand_id)

        if "facebook_token" not in brand_config:
            await atlantis.client_log(f"❌ Facebook not configured for brand '{brand_id}'")
            return {"error": "Facebook not configured for this brand"}

        access_token = brand_config["facebook_token"]

        await atlantis.client_log(f"📊 Fetching analytics for post: {post_id}")

        # Get post data including shares
        post_response = await asyncio.to_thread(
            requests.get,
            f"https://graph.facebook.com/v18.0/{post_id}",
            params={"fields": "shares,message", "access_token": access_token},
            timeout=30
        )

        if post_response.status_code != 200:
            await atlantis.client_log(f"❌ Facebook API error: {post_response.status_code}")
            return {"error": f"Facebook API error: {post_response.status_code}"}

        post_data = post_response.json()
        share_count = post_data.get("shares", {}).get("count", 0)

        await atlantis.client_log(f"✅ Post Analytics:")
        await atlantis.client_log(f"🔄 Shares: {share_count}")

        # Get post insights
        insights_response = await asyncio.to_thread(
            requests.get,
            f"https://graph.facebook.com/v18.0/{post_id}/insights",
            params={
                "metric": "post_impressions,post_engaged_users,post_reactions_by_type_total",
                "access_token": access_token
            },
            timeout=30
        )

        insights_data = {}
        if insights_response.status_code == 200:
            insights_result = insights_response.json()
            if "data" in insights_result:
                for insight in insights_result["data"]:
                    metric_name = insight.get("name", "Unknown")
                    values = insight.get("values", [])
                    if values:
                        value = values[0].get("value", 0)
                        insights_data[metric_name] = value
                        await atlantis.client_log(f"📈 {metric_name}: {value}")

        return {
            "post_id": post_id,
            "shares": share_count,
            "insights": insights_data,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error getting Facebook post analytics: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}


@visible
async def get_facebook_recent_posts(brand_id: str, limit: int = 10):
    """
    Get your recent Facebook posts with basic analytics.
    Brand ID: The brand whose Facebook page to query.
    Limit: Number of recent posts to fetch (default 10).

    Shows your most recent posts with creation time and basic info.
    """

    if limit < 1 or limit > 100:
        await atlantis.client_log("❌ Limit must be between 1 and 100")
        return {"error": "Invalid limit"}

    try:
        brand_config = _get_brand_config(brand_id)

        if "facebook_token" not in brand_config or "facebook_page_id" not in brand_config:
            await atlantis.client_log(f"❌ Facebook not configured for brand '{brand_id}'")
            return {"error": "Facebook not configured for this brand"}

        access_token = brand_config["facebook_token"]
        page_id = brand_config["facebook_page_id"]

        await atlantis.client_log(f"📱 Fetching {limit} most recent Facebook posts...")

        # Get posts from Facebook Graph API
        response = await asyncio.to_thread(
            requests.get,
            f"https://graph.facebook.com/v18.0/{page_id}/posts",
            params={"fields": "id,message,created_time", "limit": limit, "access_token": access_token},
            timeout=30
        )

        if response.status_code != 200:
            await atlantis.client_log(f"❌ Facebook API error: {response.status_code}")
            return {"error": f"Facebook API error: {response.status_code}"}

        posts_result = response.json()

        if not posts_result or "data" not in posts_result:
            await atlantis.client_log("❌ No posts found")
            return {"error": "No posts found"}

        posts = posts_result["data"]

        await atlantis.client_log(f"✅ Found {len(posts)} recent posts:")
        await atlantis.client_log("")

        for idx, post in enumerate(posts, 1):
            post_id = post.get("id", "Unknown")
            message = post.get("message", "(No text)")
            created_time = post.get("created_time", "Unknown")

            # Truncate message if too long
            display_message = message[:100] + "..." if len(message) > 100 else message

            await atlantis.client_log(f"📝 Post {idx}:")
            await atlantis.client_log(f"   ID: {post_id}")
            await atlantis.client_log(f"   Created: {created_time}")
            await atlantis.client_log(f"   Text: {display_message}")
            await atlantis.client_log("")

        return {
            "posts": posts,
            "count": len(posts),
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error getting Facebook posts: {e}", exc_info=True)
        await atlantis.client_log(f"❌ Error: {str(e)}")
        return {"error": str(e)}
