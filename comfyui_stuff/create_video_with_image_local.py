import atlantis
import json
import uuid
import requests
import time
import os
import random
import base64
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger("mcp_client")

def update_workflow_seeds(workflow):
    """Randomize seeds in the workflow for unique generations"""
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
            if "seed" in node_data.get("inputs", {}):
                node_data["inputs"]["seed"] = random.randint(1, 2**32 - 1)
            if "noise_seed" in node_data.get("inputs", {}):
                node_data["inputs"]["noise_seed"] = random.randint(1, 2**32 - 1)
    return workflow

@visible
async def create_video_with_image(prompt: str = "she sways her hips from side-to-side as if dancing to unheard music and winks as the camera zooms in for a close-up of her face"):
    """
    Creates a video from an uploaded image using ComfyUI workflow with real-time status updates

    Args:
        prompt: Animation prompt describing the desired video motion
    """

    username = atlantis.get_caller() or "unknown_user"

    await atlantis.owner_log(f"create_video_with_image called by {username} with prompt: {prompt}")

    # Generate unique upload id to avoid conflicts
    uploadId = f"video_upload_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Create file upload interface
    minipage = '''
    <div style="white-space:normal;display:flex;flex-direction:column">
        <style>
            .fancy-file-upload {
                display: inline-block;
                padding: 5px;
                background: linear-gradient(145deg, #c0c0c0 0%, #8a8a8a 50%, #565656 100%);
                color: #2c2c2c;
                border: 1px solid #999;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.3), 0 2px 4px rgba(0,0,0,0.3);
                transition: all 0.2s ease;
                position: relative;
                overflow: hidden;
                text-shadow: 0 1px 0 rgba(255,255,255,0.5);
                white-space: nowrap;
            }
            .fancy-file-upload:hover {
                background: linear-gradient(145deg, #d0d0d0 0%, #9a9a9a 50%, #666 100%);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.4), 0 3px 6px rgba(0,0,0,0.4);
            }
            .fancy-file-upload input[type=file] {
                position: absolute;
                left: 0;
                top: 0;
                opacity: 0;
                cursor: pointer;
                width: 100%;
                height: 100%;
            }
            .prompt-input {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #6c2b97;
                border-radius: 6px;
                background: #1a0833;
                color: #fff;
                font-size: 14px;
                resize: vertical;
                min-height: 60px;
            }
            .prompt-input:focus {
                outline: none;
                border-color: #9c4bd9;
                box-shadow: 0 0 10px rgba(108, 43, 151, 0.4);
            }
        </style>
        <h3 style="color: #6c2b97;">🎬 Upload Image to Create Video</h3>
        <p style="color: #ccc;">Select an image file to generate video</p>

        <div style="background: rgba(108, 43, 151, 0.2); padding: 10px; border-radius: 6px; margin: 10px 0;">
            <strong style="color: #6c2b97;">📝 Animation Prompt:</strong>
            <p style="color: #fff; margin: 5px 0 0 0;">{PROMPT}</p>
        </div>

        <label for="fileUpload_{UPLOAD_ID}" class="fancy-file-upload">
            🖼️ Choose Image File
            <input style='margin:5px' type="file" id="fileUpload_{UPLOAD_ID}" name="fileUpload_{UPLOAD_ID}" accept="image/*" />
        </label>
        <button id="sendButton_{UPLOAD_ID}" disabled style="
            padding: 8px 20px;
            background: #cccccc;
            color: #666;
            border: none;
            border-radius: 6px;
            cursor: not-allowed;
            font-size: 14px;
            font-weight: bold;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
            opacity: 0.5;
        ">Generate Video</button>
    </div>
    '''

    miniscript = '''
    //js
    let foo = function() {
        const fileUpload = document.getElementById('fileUpload_{UPLOAD_ID}');
        const sendButton = document.getElementById('sendButton_{UPLOAD_ID}');

        if (!fileUpload || !sendButton) {
            return;
        }

        // File input event listener
        fileUpload.addEventListener('change', function(event) {
            const input = event.target;
            if (input.files && input.files[0]) {
                const file = input.files[0];

                // Store file for sending
                window.atlantis_file_selected_{UPLOAD_ID} = {
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    file: file
                };

                // Enable the Send button
                sendButton.disabled = false;
                sendButton.style.opacity = '1';
                sendButton.style.background = 'linear-gradient(145deg, #6c2b97 0%, #4a1a6b 100%)';
                sendButton.style.cursor = 'pointer';
                sendButton.innerText = "Generate Video";
                sendButton.style.color = 'white';
            }
        });

        // Send button event listener
        sendButton.addEventListener('click', async function() {
            if (window.atlantis_file_selected_{UPLOAD_ID} && window.atlantis_file_selected_{UPLOAD_ID}.file) {
                const file = window.atlantis_file_selected_{UPLOAD_ID}.file;

                // Convert file to base64
                const reader = new FileReader();
                reader.onload = async function(e) {
                    const base64Content = e.target.result;

                    // Send file as base64 via studioClient to server
                    let reqParams = {
                        accessToken: "{UPLOAD_ID}",
                        mode: "upload",
                        content: "not used",
                        data: {
                            base64Content,
                            filename: file.name,
                            filetype: file.type
                        }
                    };

                    await studioClient.sendRequest("engage", reqParams);

                    // Disable button after sending
                    sendButton.disabled = true;
                    sendButton.innerText = 'Processing...';
                };
                reader.readAsDataURL(file);
            }
        });
    }
    foo()
    '''

    # Replace placeholders with actual uploadId and prompt
    minipage = minipage.replace("{UPLOAD_ID}", uploadId).replace("{PROMPT}", prompt)
    miniscript = miniscript.replace("{UPLOAD_ID}", uploadId)

    # ComfyUI configuration
    server_address = "0.0.0.0:8188"

    # Define callback for when file is uploaded
    async def process_uploaded_image(filename, filetype, base64Content):
        try:
            # Job tracking
            job_id = f"{username}.{uploadId}"

            # Use the prompt from the function parameter (captured in closure)
            await atlantis.owner_log(f"[{job_id}] === VIDEO GENERATION ===")
            await atlantis.owner_log(f"[{job_id}] Filename: {filename}")
            await atlantis.owner_log(f"[{job_id}] Filetype: {filetype}")
            await atlantis.owner_log(f"[{job_id}] Using prompt from function parameter: '{prompt}'")

            await atlantis.client_log("📥 Processing uploaded image...")
            await atlantis.client_log(f"🎬 Animation prompt: {prompt[:100]}...")
            await asyncio.sleep(0)

            # Decode base64 and save image temporarily
            base64_data = base64Content
            if base64_data.startswith('data:'):
                base64_data = base64_data.split(',')[1]

            file_bytes = base64.b64decode(base64_data)

            # Save to temp location for ComfyUI
            temp_filename = f"temp_input_{uploadId}.png"
            temp_path = os.path.join("/tmp", temp_filename)

            with open(temp_path, 'wb') as f:
                f.write(file_bytes)

            await atlantis.client_log("📋 Loading video generation workflow...")
            await asyncio.sleep(0)

            # Your video workflow JSON
            workflow_data = {
                "84": {
                    "inputs": {
                        "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                        "type": "wan",
                        "device": "default"
                    },
                    "class_type": "CLIPLoader",
                    "_meta": {"title": "Load CLIP"}
                },
                "85": {
                    "inputs": {
                        "add_noise": "disable",
                        "noise_seed": 0,
                        "steps": 4,
                        "cfg": 1,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "start_at_step": 2,
                        "end_at_step": 4,
                        "return_with_leftover_noise": "disable",
                        "model": ["103", 0],
                        "positive": ["98", 0],
                        "negative": ["98", 1],
                        "latent_image": ["86", 0]
                    },
                    "class_type": "KSamplerAdvanced",
                    "_meta": {"title": "KSampler (Advanced)"}
                },
                "86": {
                    "inputs": {
                        "add_noise": "enable",
                        "noise_seed": 84011927580470,
                        "steps": 4,
                        "cfg": 1,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "start_at_step": 0,
                        "end_at_step": 2,
                        "return_with_leftover_noise": "enable",
                        "model": ["104", 0],
                        "positive": ["98", 0],
                        "negative": ["98", 1],
                        "latent_image": ["98", 2]
                    },
                    "class_type": "KSamplerAdvanced",
                    "_meta": {"title": "KSampler (Advanced)"}
                },
                "87": {
                    "inputs": {
                        "samples": ["85", 0],
                        "vae": ["90", 0]
                    },
                    "class_type": "VAEDecode",
                    "_meta": {"title": "VAE Decode"}
                },
                "89": {
                    "inputs": {
                        "text": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走, third actor",
                        "clip": ["84", 0]
                    },
                    "class_type": "CLIPTextEncode",
                    "_meta": {"title": "CLIP Text Encode (Negative Prompt)"}
                },
                "90": {
                    "inputs": {
                        "vae_name": "wan_2.1_vae.safetensors"
                    },
                    "class_type": "VAELoader",
                    "_meta": {"title": "Load VAE"}
                },
                "93": {
                    "inputs": {
                        "text": prompt or "she sways her hips from side-to-side as if dancing to unheard music and winks as the camera zooms in for a close-up of her face",
                        "clip": ["84", 0]
                    },
                    "class_type": "CLIPTextEncode",
                    "_meta": {"title": "CLIP Text Encode (Positive Prompt)"}
                },
                "94": {
                    "inputs": {
                        "fps": 16,
                        "images": ["87", 0]
                    },
                    "class_type": "CreateVideo",
                    "_meta": {"title": "Create Video"}
                },
                "95": {
                    "inputs": {
                        "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                        "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {"title": "Load Diffusion Model"}
                },
                "96": {
                    "inputs": {
                        "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                        "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {"title": "Load Diffusion Model"}
                },
                "97": {
                    "inputs": {
                        "image": temp_filename  # Use our uploaded image
                    },
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image"}
                },
                "98": {
                    "inputs": {
                        "width": 640,
                        "height": 768,
                        "length": 81,
                        "batch_size": 1,
                        "positive": ["93", 0],
                        "negative": ["89", 0],
                        "vae": ["90", 0],
                        "start_image": ["97", 0]
                    },
                    "class_type": "WanImageToVideo",
                    "_meta": {"title": "WanImageToVideo"}
                },
                "101": {
                    "inputs": {
                        "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                        "strength_model": 1.0000000000000002,
                        "model": ["95", 0]
                    },
                    "class_type": "LoraLoaderModelOnly",
                    "_meta": {"title": "LoraLoaderModelOnly"}
                },
                "102": {
                    "inputs": {
                        "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                        "strength_model": 1.0000000000000002,
                        "model": ["96", 0]
                    },
                    "class_type": "LoraLoaderModelOnly",
                    "_meta": {"title": "LoraLoaderModelOnly"}
                },
                "103": {
                    "inputs": {
                        "shift": 5.000000000000001,
                        "model": ["102", 0]
                    },
                    "class_type": "ModelSamplingSD3",
                    "_meta": {"title": "ModelSamplingSD3"}
                },
                "104": {
                    "inputs": {
                        "shift": 5.000000000000001,
                        "model": ["101", 0]
                    },
                    "class_type": "ModelSamplingSD3",
                    "_meta": {"title": "ModelSamplingSD3"}
                },
                "108": {
                    "inputs": {
                        "filename_prefix": "video/ComfyUI",
                        "format": "auto",
                        "codec": "auto",
                        "video": ["94", 0]
                    },
                    "class_type": "SaveVideo",
                    "_meta": {"title": "Save Video"}
                }
            }

            await atlantis.client_log("🎲 Randomizing seeds for unique generation...")
            await asyncio.sleep(0)

            # Randomize seeds for unique generation
            workflow = update_workflow_seeds(workflow_data)

            await atlantis.client_log("🚀 Submitting video job to ComfyUI server...")
            await asyncio.sleep(0)

            # Upload image to ComfyUI server first
            with open(temp_path, 'rb') as f:
                files = {'image': (temp_filename, f, 'image/png')}
                upload_response = requests.post(
                    f"http://{server_address}/upload/image",
                    files=files
                )
                upload_response.raise_for_status()

            # Queue the workflow
            payload = {"prompt": workflow}
            response = requests.post(
                f"http://{server_address}/prompt",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            response_data = response.json()
            prompt_id = response_data.get("prompt_id")
            if not prompt_id:
                await atlantis.client_log("❌ Error: No prompt_id returned from ComfyUI")
                return

            await atlantis.client_log(f"✅ Video job submitted! ID: {prompt_id}")
            await asyncio.sleep(0)

            # Check queue status
            try:
                queue_response = requests.get(f"http://{server_address}/queue")
                if queue_response.status_code == 200:
                    queue_data = queue_response.json()
                    pending = len(queue_data.get("queue_pending", []))
                    running = len(queue_data.get("queue_running", []))
                    await atlantis.client_log(f"📊 Queue status: {running} running, {pending} pending")
                    await asyncio.sleep(0)
            except:
                pass

            await atlantis.client_log("⏳ Waiting for video generation to complete...")
            await asyncio.sleep(0)

            # Poll for completion - videos take longer
            max_wait_time = 3600  # takes a while so one hour max
            start_time = time.time()
            last_update = 0

            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)

                # Send progress update every 20 seconds
                if elapsed - last_update >= 20:
                    await atlantis.client_log(f"🔄 Still generating video... ({elapsed}s elapsed)")
                    last_update = elapsed

                try:
                    history_response = requests.get(f"http://{server_address}/history/{prompt_id}", timeout=30)

                    if history_response.status_code == 200:
                        history_data = history_response.json()

                        if prompt_id in history_data:
                            break

                    elif history_response.status_code == 404:
                        pass
                    else:
                        logger.warning(f"Unexpected response code: {history_response.status_code}")

                except requests.RequestException as e:
                    logger.warning(f"Request error: {e}")

                await asyncio.sleep(5)  # Check every 5 seconds for videos

            if time.time() - start_time >= max_wait_time:
                await atlantis.client_log("❌ Timeout: Video generation took too long")
                return

            await atlantis.client_log("📥 Video generation complete! Downloading video...")
            await asyncio.sleep(0)

            # Extract and save videos - debug the outputs first
            prompt_history = history_data[prompt_id]
            outputs = prompt_history.get("outputs", {})
            saved_videos = []

            await atlantis.client_log(f"🔍 Debug: Found outputs for nodes: {list(outputs.keys())}")

            # Look for SaveVideo node (node 108 in your workflow)
            for node_id, node_output in outputs.items():
                await atlantis.client_log(f"🔍 Debug: Node {node_id} output keys: {list(node_output.keys())}")

                # Check for different possible keys - ComfyUI might use different formats
                video_keys = ["videos", "gifs", "images"]  # SaveVideo might save as different types

                for key in video_keys:
                    if key in node_output:
                        await atlantis.client_log(f"🎬 Found {key} in node {node_id}: {len(node_output[key])} items")

                        for i, media_info in enumerate(node_output[key]):
                            await atlantis.client_log(f"🔍 Debug: {key} item {i}: {media_info}")

                            filename = media_info["filename"]
                            subfolder = media_info.get("subfolder", "")
                            media_type = media_info.get("type", "output")

                            # Build download parameters
                            params = {"filename": filename, "type": media_type}
                            if subfolder:
                                params["subfolder"] = subfolder

                            await atlantis.client_log(f"📥 Downloading: {filename} from {subfolder}")

                            # Download video/media
                            video_response = requests.get(f"http://{server_address}/view", params=params)
                            video_response.raise_for_status()

                            # Encode as base64 for web display
                            video_base64 = base64.b64encode(video_response.content).decode('utf-8')

                            saved_videos.append({
                                "original_filename": filename,
                                "size": len(video_response.content),
                                "node_id": node_id,
                                "base64": video_base64,
                                "media_type": key
                            })

            if saved_videos:
                await atlantis.client_log("🎬 Processing final video...")
                await asyncio.sleep(0)

                await atlantis.client_log(f"Generated {len(saved_videos)} videos from image for {username}")

                # Create HTML video player
                for i, video in enumerate(saved_videos):
                    video_extension = video['original_filename'].split('.')[-1].lower()
                    mime_type = f"video/{video_extension if video_extension in ['mp4', 'webm', 'ogg'] else 'mp4'}"

                    video_html = f"""
                    <div style="
                        border: 2px solid #6c2b97;
                        border-radius: 10px;
                        margin: 15px 0;
                        background: linear-gradient(135deg, #0c0c1e 0%, #1a0833 100%);
                        box-shadow: 0 0 15px rgba(108, 43, 151, 0.6);
                        overflow: hidden;
                        width: 100%;
                        max-width: 100%;
                    ">
                        <div style="padding: 15px; text-align: center; width: 100%;">
                            <h4 style="color: #6c2b97; margin: 0 0 10px 0;">🎬 Generated Video</h4>
                            <video
                                controls
                                autoplay
                                loop
                                muted
                                style="
                                    width: 100%;
                                    max-width: 100%;
                                    height: auto;
                                    border-radius: 8px;
                                    box-shadow: 0 0 15px rgba(255, 0, 255, 0.4);
                                    display: block;
                                    margin: 0 auto;
                                "
                            >
                                <source src="data:{mime_type};base64,{video['base64']}" type="{mime_type}">
                                Your browser does not support the video tag.
                            </video>
                            <p style="color: #ccc; margin: 10px 0 0 0; font-size: 12px;">
                                Size: {video['size'] // 1024:.1f} KB | Right-click to save
                            </p>
                        </div>
                    </div>
                    """

                    await atlantis.client_html(video_html)
                    await asyncio.sleep(0)

                await atlantis.client_log(f"✨ Generated {len(saved_videos)} video(s) from your image! 🎬💜")
            else:
                await atlantis.client_log("❌ No videos found in workflow output")

            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass

        except requests.RequestException as e:
            error_msg = f"ComfyUI API error: {str(e)}"
            await atlantis.owner_log(f"API error: {e}")
            await atlantis.client_log(f"❌ {error_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            await atlantis.owner_log(f"Unexpected error: {e}")
            await atlantis.client_log(f"❌ {error_msg}")

    # Register the upload callback
    async def upload(filename, filetype, base64Content):
        await atlantis.client_log(f"🎬 Starting video generation from image for {username} - this may take from 4 to 10 minutes depending on server load...")
        await atlantis.client_log("Processing uploaded image for video generation...")
        await process_uploaded_image(filename, filetype, base64Content)


    await atlantis.client_upload(uploadId, upload)
    await atlantis.client_html(minipage)
    await atlantis.client_script(miniscript)
