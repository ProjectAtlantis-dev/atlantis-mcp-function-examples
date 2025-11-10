# Atlantis MCP Function Examples

A collection of production-ready example functions for the [Atlantis MCP Server](https://github.com/ProjectAtlantis-dev/atlantis-mcp-server/). These examples help AI coding agents understand what's possible and demonstrate best practices for building dynamic functions in the Atlantis system.

## 📖 Overview

This repository serves as a learning resource and template library for developers building applications with Atlantis MCP. Each example is fully functional and demonstrates real-world use cases including:

- **Marketing Automation** - Social media content generation, brand management, and multi-platform posting
- **ComfyUI Integration** - Image generation, video creation, audio synthesis, and AI-powered image editing
- **Bug Report Management** - Intelligent bug tracking and automated resolution workflows

## 🚀 Installation

### Prerequisites

- [Atlantis MCP Server](https://github.com/ProjectAtlantis-dev/atlantis-mcp-server/) installed and running
- Python 3.8 or higher

### Setup

1. **Clone this repository into your Atlantis MCP Server's `dynamic_functions` directory:**

```bash
cd /path/to/atlantis-mcp-server/python-server/dynamic_functions
git clone https://github.com/ProjectAtlantis-dev/atlantis-mcp-function-examples.git
```

2. **Your directory structure should look like this:**

```
atlantis-mcp-server/
└── python-server/
    └── dynamic_functions/
        └── atlantis-mcp-function-examples/
            ├── marketing/
            ├── comfyui_stuff/
            └── bug_reports/
```

3. **Configure API keys (if using specific examples):**

```bash
# For marketing examples
export GEMINI_API_KEY="your-gemini-api-key"

# Add any other API keys needed for specific examples
```

4. **Restart your Atlantis MCP Server** to load the new functions.

## 📚 Example Categories

### 🎯 Marketing (`/marketing`)

Complete social media management suite with AI-powered content generation:

- **Multi-platform posting** (Twitter, LinkedIn, Facebook, Instagram)
- **Brand management** - Create and manage multiple brand identities
- **AI content generation** - Platform-optimized posts with Gemini AI
- **Image generation** - Create custom visuals for posts
- **Analytics** - Track engagement and performance

**Key Functions:**
- `create_brand()` - Set up new brand profiles
- `generate_social_post()` - AI-generated, platform-optimized content
- `post_to_twitter()`, `post_to_linkedin()`, `post_to_facebook()` - Publish content
- `save_linkedin_token()`, `save_facebook_token()` - OAuth integration

### 🎨 ComfyUI Integration (`/comfyui_stuff`)

Advanced AI media generation using ComfyUI workflows:

- **Video Generation** - Animate images with text prompts
- **Audio Synthesis** - Voice cloning from audio samples
- **Image Upscaling** - AI-powered 2x upscaling with SeedVR2
- **Image Editing** - Qwen-based intelligent image modifications

**Key Functions:**
- `create_video_with_image()` - Text-to-animation from images
- `create_audio_with_voice()` - Clone voices and generate speech
- `upscale_image_default()` - High-quality image upscaling
- `qwen_image_edit()` - AI-powered image editing

**Requirements:** ComfyUI server running on `0.0.0.0:8188` with required models installed

### 🐛 Bug Reports (`/bug_reports`)

Intelligent bug tracking system with AI-assisted resolution:

- **Smart bug categorization** - Auto-classify severity and priority
- **File tracking** - Associate code files with bug reports
- **AI resolution suggestions** - Get automated fix recommendations
- **Status workflow** - Track bugs from report to resolution

**Key Functions:**
- `create_bug_report()` - Submit new bugs with auto-classification
- `list_bugs()` - View and filter bug database
- `update_bug_status()` - Manage bug lifecycle
- `get_bug_details()` - Deep dive into specific issues

## 🔧 How to Use These Examples

### 1. **As Learning Resources**

Study the code to understand:
- How to structure Atlantis functions with `@visible` decorator
- Async/await patterns for UI interactions
- File upload handling with base64 encoding
- HTML/CSS/JavaScript injection for custom UIs
- Database integration patterns
- External API integration (ComfyUI, social media APIs)

### 2. **As Templates**

Copy and modify examples for your own use cases:
```python
@visible
async def your_custom_function(param1: str, param2: int = 10):
    """
    Your function description here

    Args:
        param1: Description
        param2: Description with default
    """
    username = atlantis.get_caller() or "unknown_user"
    await atlantis.client_log(f"Starting process for {username}...")

    # Your logic here

    await atlantis.client_log("✅ Complete!")
```

### 3. **As Building Blocks**

Mix and match components:
- Reuse UI components (file uploaders, progress indicators)
- Adapt database patterns for your data
- Leverage API integration patterns
- Build upon existing workflows

## 🎓 Key Concepts Demonstrated

### Atlantis Client APIs

```python
# Logging to user's interface
await atlantis.client_log("Message to user")
await atlantis.owner_log("Server-side logging")

# Rendering HTML/CSS in user's interface
await atlantis.client_html("<div>Custom UI</div>")
await atlantis.client_script("// JavaScript code")

# File uploads
await atlantis.client_upload(upload_id, callback_function)

# Get current user
username = atlantis.get_caller()
```

### File Upload Pattern

```python
uploadId = f"upload_{str(uuid.uuid4()).replace('-', '')[:8]}"

async def process_file(filename, filetype, base64Content):
    # Decode and process file
    base64_data = base64Content.split(',')[1] if base64Content.startswith('data:') else base64Content
    file_bytes = base64.b64decode(base64_data)
    # ... process file

await atlantis.client_upload(uploadId, process_file)
```

### UI Injection Pattern

```python
# HTML with placeholders
html_template = '''
<div id="my_component_{UPLOAD_ID}">
    <!-- Your HTML -->
</div>
'''

# JavaScript with event handlers
js_template = '''
document.getElementById('button_{UPLOAD_ID}').addEventListener('click', async function() {
    await studioClient.sendRequest("engage", {
        accessToken: "{UPLOAD_ID}",
        mode: "action",
        data: { /* your data */ }
    });
});
'''

# Replace placeholders and inject
await atlantis.client_html(html_template.replace("{UPLOAD_ID}", uploadId))
await atlantis.client_script(js_template.replace("{UPLOAD_ID}", uploadId))
```

## 🤖 Working with AI Coding Agents

These examples are specifically designed to help AI coding agents (like Claude, GPT-4, etc.) understand:

1. **Function Structure** - Proper async patterns and decorators
2. **Error Handling** - Robust try/catch with user-friendly messages
3. **UI/UX Patterns** - Progress indicators, file uploads, confirmations
4. **API Integration** - External services, polling, webhooks
5. **Data Persistence** - SQLite patterns, JSON configs

When working with an AI agent, you can reference these examples:
> "Create a function similar to `create_audio_with_voice()` but for text-to-speech instead of voice cloning"

> "Use the file upload pattern from `qwen_image_edit()` but modify it to accept PDF files"

## 🛠️ Development

### Creating Your Own Functions

1. Create a new directory in `dynamic_functions/`
2. Add your Python files with `@visible` decorated functions
3. Follow the patterns demonstrated in these examples
4. Test thoroughly with the Atlantis MCP Server
5. Submit a PR if you'd like to contribute back!

### Best Practices

- ✅ Always use async/await for I/O operations
- ✅ Provide clear, descriptive docstrings
- ✅ Include type hints for parameters
- ✅ Log progress for long-running operations
- ✅ Handle errors gracefully with user-friendly messages
- ✅ Use environment variables for sensitive data
- ✅ Clean up temporary files

## 🤝 Contributing

We welcome contributions! To add your own examples:

1. Fork this repository
2. Create a new directory for your example category
3. Add well-documented, working code
4. Update this README with your example
5. Submit a pull request

## 📄 License

[Add your license here]

## 🔗 Related Projects

- [Atlantis MCP Server](https://github.com/ProjectAtlantis-dev/atlantis-mcp-server/) - The main server application
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Required for media generation examples

## 💬 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/ProjectAtlantis-dev/atlantis-mcp-function-examples/issues)
- **Discussions**: Join the conversation in [Discussions](https://github.com/ProjectAtlantis-dev/atlantis-mcp-function-examples/discussions)
- **Main Project**: Visit [Atlantis MCP Server](https://github.com/ProjectAtlantis-dev/atlantis-mcp-server/) for core documentation

---

**Made with ❤️ for the Atlantis MCP community**
