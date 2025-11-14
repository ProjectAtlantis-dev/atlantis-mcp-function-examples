import atlantis
import sqlite3
import requests
import json
import time
import random
import os
import uuid
import base64
import asyncio
from datetime import datetime
import io

def get_python_server_dir():
    """Get the python-server directory path"""
    return os.path.dirname(os.path.dirname(__file__))

@visible
async def qwen_image_edit(edit_prompt: str = "change hair color to purple", **kwargs):
    """
    🎨 QWEN IMAGE EDIT

    Edit an existing image using Qwen's image editing capabilities.
    Upload an image and provide an edit prompt to modify it.

    Args:
        edit_prompt: Description of how to edit the image

    Example edit prompts:
    - "change hair color to purple"
    - "add a sunset background"
    - "make it cyberpunk style"
    - "add falling snow"
    - "change outfit to formal dress"
    """

    # Collect any extra positional args that were parsed separately and join them with the prompt
    extra_words = [str(v) for k, v in kwargs.items() if k not in ['edit_prompt']]
    if extra_words:
        edit_prompt = edit_prompt + " " + " ".join(extra_words)

    username = atlantis.get_caller() or "unknown_user"
    await atlantis.owner_log(f"qwen_image_edit called by {username} with edit_prompt: {edit_prompt}")

    # Generate unique upload id to avoid conflicts
    uploadId = f"qwen_edit_{str(uuid.uuid4()).replace('-', '')[:8]}"

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
        </style>
        <h3 style="color: #667eea;">🎨 Qwen Image Edit</h3>
        <p style="color: #ccc;">Upload an image to edit with AI</p>

        <div style="background: rgba(102, 126, 234, 0.2); padding: 10px; border-radius: 6px; margin: 10px 0;">
            <strong style="color: #667eea;">✏️ Edit Instruction:</strong>
            <p style="color: #fff; margin: 5px 0 0 0;">{EDIT_PROMPT}</p>
        </div>

        <label for="fileUpload_{UPLOAD_ID}" class="fancy-file-upload">
            🖼️ Choose Image to Edit
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
        ">Edit Image</button>
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
                sendButton.style.background = 'linear-gradient(145deg, #667eea 0%, #764ba2 100%)';
                sendButton.style.cursor = 'pointer';
                sendButton.innerText = "Edit Image";
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

    # Replace placeholders with actual uploadId and edit_prompt
    minipage = minipage.replace("{UPLOAD_ID}", uploadId).replace("{EDIT_PROMPT}", edit_prompt)
    miniscript = miniscript.replace("{UPLOAD_ID}", uploadId)

    # ComfyUI configuration
    server_address = "0.0.0.0:8188"  # GPU server for advanced models

    # Define callback for when file is uploaded
    async def process_uploaded_image(filename, filetype, base64Content):
        try:
            # Job tracking
            job_id = f"{username}.{uploadId}"

            # Use the edit_prompt from the function parameter (captured in closure)
            await atlantis.owner_log(f"[{job_id}] === QWEN IMAGE EDIT ===")
            await atlantis.owner_log(f"[{job_id}] Filename: {filename}")
            await atlantis.owner_log(f"[{job_id}] Filetype: {filetype}")
            await atlantis.owner_log(f"[{job_id}] Using edit prompt from function parameter: '{edit_prompt}'")

            await atlantis.client_log("📥 Processing uploaded image...")
            await atlantis.client_log(f"✏️ Edit instruction: {edit_prompt}")
            await asyncio.sleep(0)

            # =================================================================
            # STEP 2: SAVE IMAGE TO TEMP FILE
            # =================================================================
            await atlantis.client_log("🖼️ Saving uploaded image...")
            await asyncio.sleep(0)

            # Decode base64 and save image temporarily
            base64_data = base64Content
            if base64_data.startswith('data:'):
                base64_data = base64_data.split(',')[1]

            file_bytes = base64.b64decode(base64_data)

            temp_filename = f"temp_qwen_edit_{uploadId}.png"

            await atlantis.client_log("📤 Uploading image to ComfyUI server...")
            await asyncio.sleep(0)

            # Upload image to ComfyUI server using in-memory buffer
            file_buffer = io.BytesIO(file_bytes)
            file_buffer.seek(0)

            # Keep buffer alive by storing filename separately
            files = {'image': (temp_filename, file_buffer, 'image/png')}

            try:
                upload_response = requests.post(
                    f"http://{server_address}/upload/image",
                    files=files,
                    timeout=30
                )
                upload_response.raise_for_status()
            finally:
                file_buffer.close()

            # =================================================================
            # STEP 3: CREATE QWEN EDIT WORKFLOW
            # =================================================================
            await atlantis.client_log("⚙️ Building Qwen image edit workflow...")
            await asyncio.sleep(0)

            # Qwen image edit workflow - using actual working workflow
            edit_workflow = {
                "3": {
                    "inputs": {
                        "seed": random.randint(1, 2**32 - 1),
                        "steps": 20,
                        "cfg": 2.5,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "denoise": 1,
                        "model": ["75", 0],
                        "positive": ["76", 0],
                        "negative": ["77", 0],
                        "latent_image": ["88", 0]
                    },
                    "class_type": "KSampler",
                    "_meta": {"title": "KSampler"}
                },
                "8": {
                    "inputs": {
                        "samples": ["3", 0],
                        "vae": ["39", 0]
                    },
                    "class_type": "VAEDecode",
                    "_meta": {"title": "VAE Decode"}
                },
                "37": {
                    "inputs": {
                        "unet_name": "qwen_image_edit_fp8_e4m3fn.safetensors",
                        "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {"title": "Load Diffusion Model"}
                },
                "38": {
                    "inputs": {
                        "clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                        "type": "qwen_image",
                        "device": "default"
                    },
                    "class_type": "CLIPLoader",
                    "_meta": {"title": "Load CLIP"}
                },
                "39": {
                    "inputs": {
                        "vae_name": "qwen_image_vae.safetensors"
                    },
                    "class_type": "VAELoader",
                    "_meta": {"title": "Load VAE"}
                },
                "60": {
                    "inputs": {
                        "filename_prefix": "QwenEdit",
                        "images": ["8", 0]
                    },
                    "class_type": "SaveImage",
                    "_meta": {"title": "Save Image"}
                },
                "66": {
                    "inputs": {
                        "shift": 3,
                        "model": ["37", 0]
                    },
                    "class_type": "ModelSamplingAuraFlow",
                    "_meta": {"title": "ModelSamplingAuraFlow"}
                },
                "75": {
                    "inputs": {
                        "strength": 1,
                        "model": ["66", 0]
                    },
                    "class_type": "CFGNorm",
                    "_meta": {"title": "CFGNorm"}
                },
                "76": {
                    "inputs": {
                        "prompt": edit_prompt,
                        "clip": ["38", 0],
                        "vae": ["39", 0],
                        "image": ["93", 0]
                    },
                    "class_type": "TextEncodeQwenImageEdit",
                    "_meta": {"title": "TextEncodeQwenImageEdit"}
                },
                "77": {
                    "inputs": {
                        "prompt": "",
                        "clip": ["38", 0],
                        "vae": ["39", 0],
                        "image": ["93", 0]
                    },
                    "class_type": "TextEncodeQwenImageEdit",
                    "_meta": {"title": "TextEncodeQwenImageEdit"}
                },
                "78": {
                    "inputs": {
                        "image": temp_filename
                    },
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image"}
                },
                "88": {
                    "inputs": {
                        "pixels": ["93", 0],
                        "vae": ["39", 0]
                    },
                    "class_type": "VAEEncode",
                    "_meta": {"title": "VAE Encode"}
                },
                "93": {
                    "inputs": {
                        "upscale_method": "lanczos",
                        "megapixels": 1,
                        "image": ["78", 0]
                    },
                    "class_type": "ImageScaleToTotalPixels",
                    "_meta": {"title": "Scale Image to Total Pixels"}
                }
            }

            # =================================================================
            # STEP 4: SUBMIT WORKFLOW
            # =================================================================
            await atlantis.client_log("🚀 Submitting edit workflow...")
            await asyncio.sleep(0)

            payload = {"prompt": edit_workflow}
            response = requests.post(
                f"http://{server_address}/prompt",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()

            response_data = response.json()
            prompt_id = response_data.get("prompt_id")

            if not prompt_id:
                await atlantis.client_log("❌ Error: No prompt_id returned from ComfyUI server")
                return

            await atlantis.client_log(f"✅ Workflow submitted! ID: {prompt_id}")
            await asyncio.sleep(0)

            # =================================================================
            # STEP 5: POLL FOR COMPLETION
            # =================================================================
            await atlantis.client_log("⏳ Processing image edit (may take up to 10 minutes)...")
            await asyncio.sleep(0)

            max_wait_time = 3600  # 1 hour max
            start_time = time.time()
            last_update = 0

            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)

                # Progress updates every 20 seconds
                if elapsed - last_update >= 20:
                    await atlantis.client_log(f"🔄 Still editing... ({elapsed}s elapsed)")
                    last_update = elapsed

                try:
                    history_response = requests.get(f"http://{server_address}/history/{prompt_id}")

                    if history_response.status_code == 200:
                        history_data = history_response.json()
                        if prompt_id in history_data:
                            break

                except requests.RequestException as e:
                    await atlantis.client_log(f"⚠️ Request error: {str(e)}")

                await asyncio.sleep(3)

            if time.time() - start_time >= max_wait_time:
                await atlantis.client_log(f"❌ Edit timeout after {max_wait_time} seconds")
                return

            await atlantis.client_log("📥 Edit complete! Downloading result...")
            await asyncio.sleep(0)

            # =================================================================
            # STEP 6: DOWNLOAD AND DISPLAY EDITED IMAGE
            # =================================================================
            prompt_history = history_data[prompt_id]
            outputs = prompt_history.get("outputs", {})

            if not outputs:
                await atlantis.client_log("❌ No outputs found in workflow result")
                return

            saved_files = []

            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for i, image_info in enumerate(node_output["images"]):
                        filename_from_server = image_info["filename"]
                        subfolder = image_info.get("subfolder", "")
                        image_type = image_info.get("type", "output")

                        # Download parameters
                        params = {"filename": filename_from_server, "type": image_type}
                        if subfolder:
                            params["subfolder"] = subfolder

                        # Download edited image
                        img_response = requests.get(f"http://{server_address}/view", params=params)
                        img_response.raise_for_status()

                        # Encode as base64 for display
                        result_base64 = base64.b64encode(img_response.content).decode('utf-8')

                        saved_files.append({
                            "filename": filename_from_server,
                            "base64": result_base64,
                            "size": len(img_response.content)
                        })

                        await atlantis.client_log(f"📥 Downloaded: {filename_from_server}")
                        await asyncio.sleep(0)

            # =================================================================
            # STEP 7: DISPLAY RESULTS
            # =================================================================
            if saved_files:
                await atlantis.client_log("🎨 Displaying edited image...")
                await asyncio.sleep(0)

                for image_info in saved_files:
                    file_ext = os.path.splitext(image_info["filename"])[1].lower().lstrip('.') or 'png'

                    # Create display HTML
                    display_html = f"""
                    <div style="
                        max-width: 1000px;
                        margin: 20px auto;
                        padding: 25px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 15px;
                        color: white;
                        font-family: Arial, sans-serif;
                    ">
                        <h2 style="text-align: center; margin-bottom: 20px;">
                            ✏️ Image Edit Complete!
                        </h2>

                        <div style="
                            background: rgba(255,255,255,0.1);
                            padding: 15px;
                            border-radius: 10px;
                            margin-bottom: 20px;
                            text-align: center;
                        ">
                            <div style="font-size: 14px; margin-bottom: 10px;">
                                <strong>Edit Instruction:</strong> {edit_prompt}
                            </div>
                            <div style="font-size: 12px; opacity: 0.8;">
                                Edited: {image_info["filename"]}
                            </div>
                        </div>

                        <div style="text-align: center;">
                            <img src="data:image/{file_ext};base64,{image_info["base64"]}"
                                 style="
                                    max-width: 100%;
                                    height: auto;
                                    border-radius: 10px;
                                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                                 " />
                        </div>

                        <div style="
                            text-align: center;
                            margin-top: 20px;
                            padding-top: 15px;
                            border-top: 1px solid rgba(255,255,255,0.2);
                            font-size: 14px;
                        ">
                            📏 <strong>File Size:</strong> {image_info["size"]:,} bytes
                        </div>
                    </div>
                    """

                    await atlantis.client_html(display_html)
                    await asyncio.sleep(0)

                await atlantis.client_log(f"✨ Image edit complete! Generated {len(saved_files)} edited image(s).")
            else:
                await atlantis.client_log("❌ No edited images found in workflow output")

            await atlantis.owner_log(f"Image edit completed for {username}: {edit_prompt}")

        except requests.RequestException as e:
            error_msg = f"ComfyUI server error: {str(e)}"
            await atlantis.owner_log(f"Edit API error: {e}")
            await atlantis.client_log(f"❌ {error_msg}")

        except Exception as e:
            error_msg = f"Image edit error: {str(e)}"
            await atlantis.owner_log(f"Edit error: {e}")
            await atlantis.client_log(f"❌ {error_msg}")

    # Register the upload callback
    async def upload(filename, filetype, base64Content):
        await atlantis.client_log(f"🎨 Starting Qwen image edit for {username}...")
        await atlantis.client_log("Processing uploaded image for editing...")
        await process_uploaded_image(filename, filetype, base64Content)


    await atlantis.client_upload(uploadId, upload)
    await atlantis.client_html(minipage)
    await atlantis.client_script(miniscript)
