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
        if "seed" in node_data.get("inputs", {}):
            node_data["inputs"]["seed"] = random.randint(1, 2**32 - 1)
        if "noise_seed" in node_data.get("inputs", {}):
            node_data["inputs"]["noise_seed"] = random.randint(1, 2**32 - 1)
    return workflow

@visible
async def upscale_image_default():
    """
    Upscales an image using SeedVR2 Video Upscaler with default settings (2x, no noise)
    """

    username = atlantis.get_caller() or "unknown_user"
    uploadId = f"upscale_def_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Create file upload interface with preview
    minipage = '''
    <div style="white-space:normal;display:flex;flex-direction:column">
        <style>
            .fancy-file-upload {
                display: inline-block;
                padding: 8px 16px;
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
                margin: 10px;
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
            .preview-container {
                display: flex;
                justify-content: center;
                margin: 20px 0;
            }
            .preview-box {
                min-width: 300px;
                max-width: 500px;
                border: 2px dashed #6c2b97;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                background: rgba(26, 8, 51, 0.5);
            }
            .preview-box img {
                max-width: 100%;
                height: auto;
                border-radius: 6px;
                margin-top: 10px;
                display: none;
                box-shadow: 0 0 10px rgba(108, 43, 151, 0.5);
            }
            .preview-box img.visible {
                display: block;
            }
        </style>
        <h3 style="color: #6c2b97;">🚀 Quick Upscale (Default Settings)</h3>
        <p style="color: #ccc;">Upload an image to upscale it 2x with default settings</p>

        <div style="display: flex; justify-content: center;">
            <label for="fileUpload_{UPLOAD_ID}" class="fancy-file-upload">
                🖼️ Choose Image to Upscale
                <input style='margin:5px' type="file" id="fileUpload_{UPLOAD_ID}" name="fileUpload_{UPLOAD_ID}" accept="image/*" />
            </label>
        </div>

        <div class="preview-container">
            <div class="preview-box">
                <h4 style="color: #6c2b97; margin: 0;">Image Preview</h4>
                <p id="filename_{UPLOAD_ID}" style="color: #aaa; font-size: 12px; margin: 5px 0;">No file selected</p>
                <img id="preview_{UPLOAD_ID}" alt="Image preview" />
            </div>
        </div>

        <div style="text-align: center; margin-top: 20px;">
            <button id="sendButton_{UPLOAD_ID}" disabled style="
                padding: 12px 30px;
                background: #cccccc;
                color: #666;
                border: none;
                border-radius: 6px;
                cursor: not-allowed;
                font-size: 16px;
                font-weight: bold;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: all 0.2s ease;
                opacity: 0.5;
            ">Upscale Image</button>
        </div>
    </div>
    '''

    miniscript = '''
    //js
    let foo = function() {
        const fileUpload = document.getElementById('fileUpload_{UPLOAD_ID}');
        const sendButton = document.getElementById('sendButton_{UPLOAD_ID}');
        const preview = document.getElementById('preview_{UPLOAD_ID}');
        const filename = document.getElementById('filename_{UPLOAD_ID}');

        if (!fileUpload || !sendButton) {
            return;
        }

        let selectedFile = null;

        fileUpload.addEventListener('change', function(event) {
            const input = event.target;
            if (input.files && input.files[0]) {
                selectedFile = input.files[0];
                filename.textContent = selectedFile.name;

                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.classList.add('visible');
                };
                reader.readAsDataURL(selectedFile);

                sendButton.disabled = false;
                sendButton.style.opacity = '1';
                sendButton.style.background = 'linear-gradient(145deg, #6c2b97 0%, #4a1a6b 100%)';
                sendButton.style.cursor = 'pointer';
                sendButton.style.color = 'white';
            }
        });

        sendButton.addEventListener('click', async function() {
            if (selectedFile) {
                sendButton.disabled = true;
                sendButton.innerText = 'Processing...';

                try {
                    const base64Data = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = (e) => resolve(e.target.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(selectedFile);
                    });

                    await studioClient.sendRequest("engage", {
                        accessToken: "{UPLOAD_ID}",
                        mode: "upload",
                        content: "not used",
                        data: {
                            base64Content: base64Data,
                            filename: selectedFile.name,
                            filetype: selectedFile.type
                        }
                    });

                } catch (error) {
                    console.error('Error reading file:', error);
                    sendButton.disabled = false;
                    sendButton.innerText = 'Upscale Image';
                }
            }
        });
    }
    foo()
    '''

    minipage = minipage.replace("{UPLOAD_ID}", uploadId)
    miniscript = miniscript.replace("{UPLOAD_ID}", uploadId)

    server_address = "0.0.0.0:8188"

    async def process_uploaded_image(filename, filetype, base64Content):
        try:
            job_id = f"{username}.{uploadId}"

            await atlantis.owner_log(f"[{job_id}] === IMAGE UPSCALE DEFAULT ===")
            await atlantis.owner_log(f"[{job_id}] Image: {filename}")

            await atlantis.client_log("📥 Processing uploaded image...")
            await asyncio.sleep(0)

            base64_data = base64Content
            if base64_data and base64_data.startswith('data:'):
                base64_data = base64_data.split(',')[1]
            file_bytes = base64.b64decode(base64_data)

            temp_filename = f"temp_upscale_def_{uploadId}.png"
            temp_path = os.path.join("/tmp", temp_filename)
            with open(temp_path, 'wb') as f:
                f.write(file_bytes)

            await atlantis.client_log("📋 Loading default upscale workflow...")
            await asyncio.sleep(0)

            # Embedded workflow with PurgeVRAM and SaveImage
            workflow_data = {
                "12": {
                    "inputs": {
                        "model": "seedvr2_ema_7b-Q4_K_M.gguf",
                        "seed": random.randint(1, 2**32 - 1),
                        "new_resolution": ["53", 0],
                        "batch_size": 1,
                        "color_correction": "none",
                        "input_noise_scale": 0,
                        "latent_noise_scale": 0.03,
                        "images": ["49", 0],
                        "block_swap_config": ["15", 0],
                        "extra_args": ["22", 0]
                    },
                    "class_type": "SeedVR2",
                    "_meta": {"title": "SeedVR2 Video Upscaler"}
                },
                "15": {
                    "inputs": {
                        "blocks_to_swap": 36,
                        "offload_io_components": True
                    },
                    "class_type": "SeedVR2BlockSwap",
                    "_meta": {"title": "SeedVR2 BlockSwap Config"}
                },
                "22": {
                    "inputs": {
                        "tiled_vae": True,
                        "vae_tile_size": 1024,
                        "vae_tile_overlap": 128,
                        "preserve_vram": True,
                        "cache_model": True,
                        "enable_debug": False,
                        "device": "cuda:0"
                    },
                    "class_type": "SeedVR2ExtraArgs",
                    "_meta": {"title": "SeedVR2 Extra Args"}
                },
                "47": {
                    "inputs": {
                        "purge_cache": True,
                        "purge_models": True,
                        "anything": ["12", 0]
                    },
                    "class_type": "PurgeVRAM_UTK",
                    "_meta": {"title": "Purge VRAM (UTK)"}
                },
                "48": {
                    "inputs": {
                        "filename_prefix": "upscaled/upscale_default_",
                        "images": ["47", 0]
                    },
                    "class_type": "SaveImage",
                    "_meta": {"title": "Save Image"}
                },
                "49": {
                    "inputs": {
                        "image": temp_filename
                    },
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image"}
                },
                "50": {
                    "inputs": {
                        "side": "Shortest",
                        "image": ["49", 0]
                    },
                    "class_type": "easy imageSizeBySide",
                    "_meta": {"title": "ImageSize (Side)"}
                },
                "51": {
                    "inputs": {
                        "multiply_by": 2,
                        "add_by": 0,
                        "numberA": ["50", 0]
                    },
                    "class_type": "MultiplicationNode",
                    "_meta": {"title": "Math Operation ♾️Mixlab"}
                },
                "52": {
                    "inputs": {
                        "value1": ["51", 1],
                        "value2": "3072"
                    },
                    "class_type": "Basic data handling: MathMin",
                    "_meta": {"title": "min"}
                },
                "53": {
                    "inputs": {
                        "input": ["52", 0]
                    },
                    "class_type": "Basic data handling: CastToInt",
                    "_meta": {"title": "to INT"}
                }
            }

            await atlantis.client_log("🎲 Randomizing seeds...")
            await asyncio.sleep(0)

            workflow = update_workflow_seeds(workflow_data)

            await atlantis.client_log("🚀 Uploading and submitting job to ComfyUI...")
            await asyncio.sleep(0)

            # Upload image
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
                await atlantis.client_log("❌ Error: No prompt_id returned")
                return

            await atlantis.client_log(f"✅ Job submitted! ID: {prompt_id}")
            await asyncio.sleep(0)

            await atlantis.client_log("⏳ Waiting for completion...")
            await asyncio.sleep(0)

            # Poll for completion
            max_wait_time = 1800
            start_time = time.time()
            last_update = 0

            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)

                if elapsed - last_update >= 20:
                    await atlantis.client_log(f"🔄 Still processing... ({elapsed}s elapsed)")
                    last_update = elapsed

                try:
                    history_response = requests.get(f"http://{server_address}/history/{prompt_id}", timeout=30)

                    if history_response.status_code == 200:
                        history_data = history_response.json()

                        if prompt_id in history_data:
                            break

                except requests.RequestException as e:
                    logger.warning(f"Request error: {e}")

                await asyncio.sleep(5)

            if time.time() - start_time >= max_wait_time:
                await atlantis.client_log("❌ Timeout: Processing took too long")
                return

            await atlantis.client_log("📥 Complete! Downloading images...")
            await asyncio.sleep(0)

            # Extract and save images
            prompt_history = history_data[prompt_id]
            outputs = prompt_history.get("outputs", {})
            saved_images = []

            # Only get images from node 48 to avoid duplicates
            for node_id, node_output in outputs.items():
                if node_id == "48" and "images" in node_output:
                    for i, image_info in enumerate(node_output["images"]):
                        filename_out = image_info["filename"]
                        subfolder = image_info.get("subfolder", "")
                        image_type = image_info.get("type", "output")

                        params = {"filename": filename_out, "type": image_type}
                        if subfolder:
                            params["subfolder"] = subfolder

                        await atlantis.client_log(f"📥 Downloading: {filename_out}")

                        image_response = requests.get(f"http://{server_address}/view", params=params)
                        image_response.raise_for_status()

                        image_base64 = base64.b64encode(image_response.content).decode('utf-8')

                        saved_images.append({
                            "original_filename": filename_out,
                            "size": len(image_response.content),
                            "node_id": node_id,
                            "base64": image_base64
                        })

            if saved_images:
                await atlantis.client_log("🎨 Processing upscaled images...")
                await asyncio.sleep(0)

                for img in saved_images:
                    image_html = f"""
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
                            <h4 style="color: #6c2b97; margin: 0 0 10px 0;">🚀 Upscaled Image</h4>
                            <img
                                src="data:image/png;base64,{img['base64']}"
                                style="
                                    width: 100%;
                                    max-width: 100%;
                                    height: auto;
                                    border-radius: 8px;
                                    box-shadow: 0 0 15px rgba(255, 0, 255, 0.4);
                                    display: block;
                                    margin: 0 auto;
                                "
                            />
                            <p style="color: #ccc; margin: 10px 0 0 0; font-size: 12px;">
                                Size: {img['size'] // 1024:.1f} KB | Right-click to save
                            </p>
                        </div>
                    </div>
                    """

                    await atlantis.client_html(image_html)
                    await asyncio.sleep(0)

                await atlantis.client_log(f"✨ Image upscaled successfully! 🚀💜")
            else:
                await atlantis.client_log("❌ No images found in workflow output")

            # Clean up
            try:
                os.remove(temp_path)
            except:
                pass

        except requests.RequestException as e:
            await atlantis.owner_log(f"API error: {e}")
            await atlantis.client_log(f"❌ ComfyUI API error: {str(e)}")

        except Exception as e:
            await atlantis.owner_log(f"Unexpected error: {e}")
            await atlantis.client_log(f"❌ Unexpected error: {str(e)}")

    await atlantis.client_upload(uploadId, process_uploaded_image)
    await atlantis.client_html(minipage)
    await atlantis.client_script(miniscript)
