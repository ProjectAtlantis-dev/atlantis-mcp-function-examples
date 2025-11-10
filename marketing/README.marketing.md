# Marketing Content Generator

Automated social media content generation using Gemini AI with brand-aware context.

## Quick Start

### 1. Create a Brand Profile

Call `create_brand_config()` - it will show a form with these fields:

**Required Fields:**
- **brand_id**: Short identifier (e.g., "atlantis", "acme") - use this to reference the brand later
- **brand_name**: Full brand name (e.g., "Project Atlantis")
- **description**: What does your business do? (e.g., "Futuristic robot research playground in Greenland")
- **target_audience**: Who are you talking to? (e.g., "Tech enthusiasts, robotics researchers, engineers")
- **brand_voice**: How do you sound? (e.g., "technical", "friendly", "professional", "playful", "authoritative")

**Optional Fields:**
- **key_messages**: Core value props, USPs, mission statement
- **product_services**: What you sell/offer
- **competitors**: Who you compete with
- **hashtags**: Brand hashtags you commonly use
- **website**: Your website URL

**Example:**
```
brand_id: atlantis
brand_name: Project Atlantis
description: Futuristic robot research playground on the southwest coast of Greenland. Building the future of robotics and AI.
target_audience: Tech enthusiasts, robotics researchers, AI developers, innovation leaders
brand_voice: innovative, technical yet approachable, visionary
key_messages: Pushing boundaries of robotics. Open research environment. Building tomorrow's technology today.
product_services: Robot research facilities, AI testing grounds, collaborative workspaces
hashtags: #ProjectAtlantis #RoboticsResearch #AIInnovation
```

### 2. List Your Brands

Call `list_brands()` to see all configured brands.

### 3. Generate Social Media Posts

Call `generate_social_post()` with:
- **brand_id**: Which brand (e.g., "atlantis")
- **topic**: What to post about (e.g., "New robot arm prototype completed")
- **platform**: twitter, linkedin, instagram, or facebook
- **tone**: (optional) Override brand voice with specific tone

**Example:**
```
brand_id: atlantis
topic: We just completed testing our new adaptive robot arm that can handle delicate objects
platform: twitter
tone: excited
```

**Output:** Ready-to-post content optimized for the platform with hashtags!

### 4. Repurpose Long Content

Call `repurpose_content()` to turn blog posts/articles into multiple social posts:
- **brand_id**: Which brand
- **content**: Your long-form content (paste article text)
- **num_posts**: How many posts to generate (default: 5)
- **platforms**: Comma-separated list (e.g., "twitter,linkedin,instagram")

**Example:**
```
brand_id: atlantis
content: [paste your blog post or article]
num_posts: 5
platforms: twitter,linkedin
```

**Output:** Multiple platform-optimized posts extracted from your content!

## Available Functions

### Brand Management
- `create_brand_config()` - Create/update brand profile (shows form)
- `list_brands()` - View all brands
- `view_brand_config(brand_id)` - View brand details
- `delete_brand_config(brand_id)` - Delete a brand

### Content Generation
- `generate_social_post(brand_id, topic, platform, tone)` - Generate single post
- `repurpose_content(brand_id, content, num_posts, platforms)` - Generate multiple posts from content

## Platform Best Practices (2025)

Built-in optimization for:

**Twitter/X:**
- 280 char limit
- Optimal: 100-280 chars
- 1-2 hashtags max
- Front-load key info

**LinkedIn:**
- 3000 char limit
- Optimal: 800-1600 chars
- First 210 chars critical (appears before "See More")
- 3-5 hashtags at end

**Instagram:**
- 2200 char limit
- Optimal: 138-150 chars
- First 125 chars shown
- 5-10 hashtags (long-tail work best)

**Facebook:**
- 63,206 char limit
- Optimal: 40-80 chars (!!)
- Keep it VERY short
- 1-2 hashtags max

## Technical Details

- Uses Gemini CLI (`/opt/homebrew/bin/gemini`)
- Free daily quota
- Configs stored in `marketing_brands.json`
- Brand context injected into all prompts
- Platform-specific formatting and best practices

## Troubleshooting

**"Brand not found"**: Run `list_brands()` to see available brands, or create one with `create_brand_config()`

**"Gemini CLI failed"**: Check that `gemini` CLI is installed and authenticated

**No output/errors**: Check the logs in `dynamic_functions/*.log` files
