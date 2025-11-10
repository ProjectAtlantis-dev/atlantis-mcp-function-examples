# Contributing to Atlantis MCP Function Examples

First off, thank you for considering contributing to Atlantis MCP Function Examples! It's people like you that make this project such a great learning resource for the community.

## 🎯 What We're Looking For

We welcome contributions of:

- **New example functions** - Show off creative use cases
- **Improved documentation** - Help others understand the code better
- **Bug fixes** - Correct issues in existing examples
- **Code improvements** - Better patterns, performance, or error handling
- **UI/UX enhancements** - More polished user interfaces

## 📋 Guidelines

### Code Quality

1. **Follow existing patterns** - Look at current examples for style and structure
2. **Use type hints** - Help AI agents and developers understand your code
3. **Write docstrings** - Explain what your function does and its parameters
4. **Handle errors gracefully** - Provide user-friendly error messages
5. **Clean up resources** - Remove temp files, close connections, etc.

### Example Structure

```python
@visible
async def your_function_name(param1: str, param2: int = 10):
    """
    Brief description of what this function does

    Args:
        param1: Description of first parameter
        param2: Description of second parameter with default value
    """
    # Get current user
    username = atlantis.get_caller() or "unknown_user"

    try:
        # Log progress
        await atlantis.client_log("Starting process...")

        # Your logic here

        await atlantis.client_log("✅ Complete!")

    except Exception as e:
        await atlantis.client_log(f"❌ Error: {str(e)}")
        await atlantis.owner_log(f"Error in your_function_name: {e}")
```

### Security

- ✅ **Never commit API keys or secrets**
- ✅ **Use environment variables** for sensitive data
- ✅ **Validate user input** to prevent injection attacks
- ✅ **Sanitize file uploads** before processing

### Documentation

- Add your example to the main README.md
- Include setup instructions if special dependencies are needed
- Provide example usage or screenshots if helpful
- Comment complex logic inline

## 🚀 How to Contribute

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/atlantis-mcp-function-examples.git
cd atlantis-mcp-function-examples
```

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use prefixes:
- `feature/` - New functionality
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code improvements

### 3. Make Your Changes

- Write clean, well-documented code
- Test thoroughly with Atlantis MCP Server
- Ensure no secrets are committed

### 4. Test

- Run your function in a real Atlantis MCP environment
- Test error cases and edge conditions
- Verify UI components render correctly
- Check that cleanup happens properly

### 5. Commit

Use clear, descriptive commit messages:

```bash
git commit -m "Add video thumbnail generator example"
git commit -m "Fix file cleanup in audio synthesis"
git commit -m "Docs: Add ComfyUI setup guide"
```

### 6. Push & Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a pull request on GitHub with:
- Clear description of what you added/changed
- Why the change is useful
- Any special setup needed
- Screenshots/videos if applicable

## 🔍 Review Process

1. Maintainers will review your PR
2. We may suggest changes or improvements
3. Once approved, your contribution will be merged
4. You'll be credited in the commit history!

## 💡 Example Categories

Consider contributing to these areas:

### Missing Examples
- Database operations (PostgreSQL, MongoDB)
- Authentication & OAuth flows
- File processing (PDFs, spreadsheets)
- Email automation
- Web scraping
- Data visualization
- Machine learning inference
- Real-time notifications
- Payment processing
- Calendar/scheduling

### Improvements Needed
- More comprehensive error handling
- Better UI/UX patterns
- Performance optimizations
- Mobile-responsive interfaces
- Accessibility improvements

## 🤝 Community

- Be respectful and constructive
- Help others learn
- Share knowledge generously
- Give credit where due
- Have fun building cool stuff!

## 📝 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## ❓ Questions?

- Open an issue for questions about contributing
- Check existing issues/PRs for similar work
- Reach out in [Discussions](https://github.com/ProjectAtlantis-dev/atlantis-mcp-function-examples/discussions)

---

Thank you for helping make Atlantis MCP Function Examples better! 🎉
