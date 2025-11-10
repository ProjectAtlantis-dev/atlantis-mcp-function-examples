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
async def frames_to_video(prompt: str = "smooth transition between frames"):
    """
    Creates a video from two images (first and last frame) using ComfyUI workflow

    Args:
        prompt: Animation prompt describing the motion between the frames
    """

    username = atlantis.get_caller() or "unknown_user"

    await atlantis.owner_log(f"frames_to_video called by {username} with prompt: {prompt}")

    # Generate unique upload id to avoid conflicts
    uploadId = f"frames2vid_{str(uuid.uuid4()).replace('-', '')[:8]}"

    # Create dual file upload interface with previews
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
                justify-content: space-around;
                gap: 20px;
                margin: 20px 0;
                flex-wrap: wrap;
            }
            .preview-box {
                flex: 1;
                min-width: 200px;
                max-width: 300px;
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
        <h3 style="color: #6c2b97;">🎬 Create Video from First & Last Frame</h3>
        <p style="color: #ccc;">Upload two images - I'll generate a smooth video transition between them</p>

        <div style="background: rgba(108, 43, 151, 0.2); padding: 10px; border-radius: 6px; margin: 10px 0;">
            <strong style="color: #6c2b97;">📝 Motion Prompt:</strong>
            <p style="color: #fff; margin: 5px 0 0 0;">{PROMPT}</p>
        </div>

        <div style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
            <label for="fileUpload1_{UPLOAD_ID}" class="fancy-file-upload">
                🖼️ Choose First Frame
                <input style='margin:5px' type="file" id="fileUpload1_{UPLOAD_ID}" name="fileUpload1_{UPLOAD_ID}" accept="image/*" />
            </label>
            <label for="fileUpload2_{UPLOAD_ID}" class="fancy-file-upload">
                🖼️ Choose Last Frame
                <input style='margin:5px' type="file" id="fileUpload2_{UPLOAD_ID}" name="fileUpload2_{UPLOAD_ID}" accept="image/*" />
            </label>
        </div>

        <div class="preview-container">
            <div class="preview-box">
                <h4 style="color: #6c2b97; margin: 0;">First Frame</h4>
                <p id="filename1_{UPLOAD_ID}" style="color: #aaa; font-size: 12px; margin: 5px 0;">No file selected</p>
                <img id="preview1_{UPLOAD_ID}" alt="First frame preview" />
            </div>
            <div class="preview-box">
                <h4 style="color: #6c2b97; margin: 0;">Last Frame</h4>
                <p id="filename2_{UPLOAD_ID}" style="color: #aaa; font-size: 12px; margin: 5px 0;">No file selected</p>
                <img id="preview2_{UPLOAD_ID}" alt="Last frame preview" />
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
            ">Generate Video</button>
        </div>
    </div>
    '''

    miniscript = '''
    //js
    let foo = function() {
        const fileUpload1 = document.getElementById('fileUpload1_{UPLOAD_ID}');
        const fileUpload2 = document.getElementById('fileUpload2_{UPLOAD_ID}');
        const sendButton = document.getElementById('sendButton_{UPLOAD_ID}');
        const preview1 = document.getElementById('preview1_{UPLOAD_ID}');
        const preview2 = document.getElementById('preview2_{UPLOAD_ID}');
        const filename1 = document.getElementById('filename1_{UPLOAD_ID}');
        const filename2 = document.getElementById('filename2_{UPLOAD_ID}');

        if (!fileUpload1 || !fileUpload2 || !sendButton) {
            return;
        }

        let file1 = null;
        let file2 = null;

        function checkBothFiles() {
            if (file1 && file2) {
                sendButton.disabled = false;
                sendButton.style.opacity = '1';
                sendButton.style.background = 'linear-gradient(145deg, #6c2b97 0%, #4a1a6b 100%)';
                sendButton.style.cursor = 'pointer';
                sendButton.style.color = 'white';
            } else {
                sendButton.disabled = true;
                sendButton.style.opacity = '0.5';
                sendButton.style.background = '#cccccc';
                sendButton.style.cursor = 'not-allowed';
                sendButton.style.color = '#666';
            }
        }

        // First frame upload
        fileUpload1.addEventListener('change', function(event) {
            const input = event.target;
            if (input.files && input.files[0]) {
                file1 = input.files[0];
                filename1.textContent = file1.name;

                // Show preview
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview1.src = e.target.result;
                    preview1.classList.add('visible');
                };
                reader.readAsDataURL(file1);

                checkBothFiles();
            }
        });

        // Last frame upload
        fileUpload2.addEventListener('change', function(event) {
            const input = event.target;
            if (input.files && input.files[0]) {
                file2 = input.files[0];
                filename2.textContent = file2.name;

                // Show preview
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview2.src = e.target.result;
                    preview2.classList.add('visible');
                };
                reader.readAsDataURL(file2);

                checkBothFiles();
            }
        });

        // Send button - upload both files separately
        sendButton.addEventListener('click', async function() {
            if (file1 && file2) {
                sendButton.disabled = true;
                sendButton.innerText = 'Processing...';

                try {
                    // Read first file
                    const base64_1 = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = (e) => resolve(e.target.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(file1);
                    });

                    // Send first frame
                    await studioClient.sendRequest("engage", {
                        accessToken: "{UPLOAD_ID}_frame1",
                        mode: "upload",
                        content: "not used",
                        data: {
                            base64Content: base64_1,
                            filename: file1.name,
                            filetype: file1.type
                        }
                    });

                    // Read second file
                    const base64_2 = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = (e) => resolve(e.target.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(file2);
                    });

                    // Send second frame
                    await studioClient.sendRequest("engage", {
                        accessToken: "{UPLOAD_ID}_frame2",
                        mode: "upload",
                        content: "not used",
                        data: {
                            base64Content: base64_2,
                            filename: file2.name,
                            filetype: file2.type
                        }
                    });

                } catch (error) {
                    console.error('Error reading files:', error);
                    sendButton.disabled = false;
                    sendButton.innerText = 'Generate Video';
                }
            }
        });
    }
    foo()
    '''

    # Replace placeholders
    minipage = minipage.replace("{UPLOAD_ID}", uploadId).replace("{PROMPT}", prompt)
    miniscript = miniscript.replace("{UPLOAD_ID}", uploadId)

    # ComfyUI configuration
    server_address = "0.0.0.0:8188"

    # Storage for the two frames
    frame_storage = {}

    # Define callback for when files are uploaded
    async def process_uploaded_frames():
        try:
            # Wait for both frames to arrive
            if 'frame1' not in frame_storage or 'frame2' not in frame_storage:
                await atlantis.owner_log(f"Waiting for both frames... Currently have: {list(frame_storage.keys())}")
                return

            job_id = f"{username}.{uploadId}"

            # Get both frames from storage
            frame1_data = frame_storage['frame1']
            frame2_data = frame_storage['frame2']

            filename = frame1_data['filename']
            filetype = frame1_data['filetype']
            base64Content = frame1_data['base64Content']

            filename2 = frame2_data['filename']
            filetype2 = frame2_data['filetype']
            base64Content2 = frame2_data['base64Content']

            await atlantis.owner_log(f"[{job_id}] === FRAMES TO VIDEO ===")
            await atlantis.owner_log(f"[{job_id}] First frame: {filename}")
            await atlantis.owner_log(f"[{job_id}] Last frame: {filename2}")
            await atlantis.owner_log(f"[{job_id}] Motion prompt: '{prompt}'")

            await atlantis.client_log("📥 Processing uploaded frames...")
            await atlantis.client_log(f"🎬 Motion prompt: {prompt[:100]}...")
            await asyncio.sleep(0)

            # Decode and save first frame
            base64_data1 = base64Content
            if base64_data1 and base64_data1.startswith('data:'):
                base64_data1 = base64_data1.split(',')[1]
            file_bytes1 = base64.b64decode(base64_data1)

            temp_filename1 = f"temp_frame1_{uploadId}.png"
            temp_path1 = os.path.join("/tmp", temp_filename1)
            with open(temp_path1, 'wb') as f:
                f.write(file_bytes1)

            # Decode and save last frame
            base64_data2 = base64Content2
            if base64_data2 and base64_data2.startswith('data:'):
                base64_data2 = base64_data2.split(',')[1]
            file_bytes2 = base64.b64decode(base64_data2)

            temp_filename2 = f"temp_frame2_{uploadId}.png"
            temp_path2 = os.path.join("/tmp", temp_filename2)
            with open(temp_path2, 'wb') as f:
                f.write(file_bytes2)

            await atlantis.client_log("📋 Loading frames-to-video workflow...")
            await asyncio.sleep(0)

            # First and last frame to video workflow
            workflow_data = {
                "6": {
                    "inputs": {
                        "text": prompt or "smooth transition between frames",
                        "clip": ["38", 0]
                    },
                    "class_type": "CLIPTextEncode",
                    "_meta": {"title": "CLIP Text Encode (Positive Prompt)"}
                },
                "7": {
                    "inputs": {
                        "text": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走",
                        "clip": ["38", 0]
                    },
                    "class_type": "CLIPTextEncode",
                    "_meta": {"title": "CLIP Text Encode (Negative Prompt)"}
                },
                "8": {
                    "inputs": {
                        "samples": ["58", 0],
                        "vae": ["39", 0]
                    },
                    "class_type": "VAEDecode",
                    "_meta": {"title": "VAE Decode"}
                },
                "37": {
                    "inputs": {
                        "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                        "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {"title": "Load Diffusion Model"}
                },
                "38": {
                    "inputs": {
                        "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                        "type": "wan",
                        "device": "default"
                    },
                    "class_type": "CLIPLoader",
                    "_meta": {"title": "Load CLIP"}
                },
                "39": {
                    "inputs": {
                        "vae_name": "wan_2.1_vae.safetensors"
                    },
                    "class_type": "VAELoader",
                    "_meta": {"title": "Load VAE"}
                },
                "54": {
                    "inputs": {
                        "shift": 5,
                        "model": ["91", 0]
                    },
                    "class_type": "ModelSamplingSD3",
                    "_meta": {"title": "ModelSamplingSD3"}
                },
                "55": {
                    "inputs": {
                        "shift": 5,
                        "model": ["92", 0]
                    },
                    "class_type": "ModelSamplingSD3",
                    "_meta": {"title": "ModelSamplingSD3"}
                },
                "56": {
                    "inputs": {
                        "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                        "weight_dtype": "default"
                    },
                    "class_type": "UNETLoader",
                    "_meta": {"title": "Load Diffusion Model"}
                },
                "57": {
                    "inputs": {
                        "add_noise": "enable",
                        "noise_seed": 0,
                        "steps": 4,
                        "cfg": 1,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "start_at_step": 0,
                        "end_at_step": 2,
                        "return_with_leftover_noise": "enable",
                        "model": ["54", 0],
                        "positive": ["67", 0],
                        "negative": ["67", 1],
                        "latent_image": ["67", 2]
                    },
                    "class_type": "KSamplerAdvanced",
                    "_meta": {"title": "KSampler (Advanced)"}
                },
                "58": {
                    "inputs": {
                        "add_noise": "disable",
                        "noise_seed": 0,
                        "steps": 4,
                        "cfg": 1,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "start_at_step": 2,
                        "end_at_step": 10000,
                        "return_with_leftover_noise": "disable",
                        "model": ["55", 0],
                        "positive": ["67", 0],
                        "negative": ["67", 1],
                        "latent_image": ["57", 0]
                    },
                    "class_type": "KSamplerAdvanced",
                    "_meta": {"title": "KSampler (Advanced)"}
                },
                "60": {
                    "inputs": {
                        "fps": 16,
                        "images": ["8", 0]
                    },
                    "class_type": "CreateVideo",
                    "_meta": {"title": "Create Video"}
                },
                "61": {
                    "inputs": {
                        "filename_prefix": "video/frames2vid_",
                        "format": "auto",
                        "codec": "auto",
                        "video": ["60", 0]
                    },
                    "class_type": "SaveVideo",
                    "_meta": {"title": "Save Video"}
                },
                "62": {
                    "inputs": {
                        "image": temp_filename2  # Last frame
                    },
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image"}
                },
                "67": {
                    "inputs": {
                        "width": 640,
                        "height": 768,
                        "length": 81,
                        "batch_size": 1,
                        "positive": ["6", 0],
                        "negative": ["7", 0],
                        "vae": ["39", 0],
                        "start_image": ["68", 0],
                        "end_image": ["62", 0]
                    },
                    "class_type": "WanFirstLastFrameToVideo",
                    "_meta": {"title": "WanFirstLastFrameToVideo"}
                },
                "68": {
                    "inputs": {
                        "image": temp_filename1  # First frame
                    },
                    "class_type": "LoadImage",
                    "_meta": {"title": "Load Image"}
                },
                "91": {
                    "inputs": {
                        "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                        "strength_model": 1,
                        "model": ["37", 0]
                    },
                    "class_type": "LoraLoaderModelOnly",
                    "_meta": {"title": "LoraLoaderModelOnly"}
                },
                "92": {
                    "inputs": {
                        "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                        "strength_model": 1,
                        "model": ["56", 0]
                    },
                    "class_type": "LoraLoaderModelOnly",
                    "_meta": {"title": "LoraLoaderModelOnly"}
                }
            }

            await atlantis.client_log("🎲 Randomizing seeds for unique generation...")
            await asyncio.sleep(0)

            # Randomize seeds
            workflow = update_workflow_seeds(workflow_data)

            await atlantis.client_log("🚀 Uploading frames and submitting video job to ComfyUI...")
            await asyncio.sleep(0)

            # Upload both images to ComfyUI server
            with open(temp_path1, 'rb') as f:
                files = {'image': (temp_filename1, f, 'image/png')}
                upload_response = requests.post(
                    f"http://{server_address}/upload/image",
                    files=files
                )
                upload_response.raise_for_status()

            with open(temp_path2, 'rb') as f:
                files = {'image': (temp_filename2, f, 'image/png')}
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

            # Poll for completion
            max_wait_time = 3600
            start_time = time.time()
            last_update = 0

            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)

                if elapsed - last_update >= 20:
                    await atlantis.client_log(f"🔄 Still generating video... ({elapsed}s elapsed)")
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
                await atlantis.client_log("❌ Timeout: Video generation took too long")
                return

            await atlantis.client_log("📥 Video generation complete! Downloading video...")
            await asyncio.sleep(0)

            # Extract and save videos
            prompt_history = history_data[prompt_id]
            outputs = prompt_history.get("outputs", {})
            saved_videos = []

            for node_id, node_output in outputs.items():
                video_keys = ["videos", "gifs", "images"]

                for key in video_keys:
                    if key in node_output:
                        for i, media_info in enumerate(node_output[key]):
                            filename_out = media_info["filename"]
                            subfolder = media_info.get("subfolder", "")
                            media_type = media_info.get("type", "output")

                            params = {"filename": filename_out, "type": media_type}
                            if subfolder:
                                params["subfolder"] = subfolder

                            await atlantis.client_log(f"📥 Downloading: {filename_out}")

                            # Download video
                            video_response = requests.get(f"http://{server_address}/view", params=params)
                            video_response.raise_for_status()

                            # Encode as base64
                            video_base64 = base64.b64encode(video_response.content).decode('utf-8')

                            saved_videos.append({
                                "original_filename": filename_out,
                                "size": len(video_response.content),
                                "node_id": node_id,
                                "base64": video_base64,
                                "media_type": key
                            })

            if saved_videos:
                await atlantis.client_log("🎬 Processing final video...")
                await asyncio.sleep(0)

                # Create HTML video player
                for video in saved_videos:
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
                            <h4 style="color: #6c2b97; margin: 0 0 10px 0;">🎬 Generated Video from Frames</h4>
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

                await atlantis.client_log(f"✨ Generated video from your frames! 🎬💜")
            else:
                await atlantis.client_log("❌ No videos found in workflow output")

            # Clean up temp files
            try:
                os.remove(temp_path1)
                os.remove(temp_path2)
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

    # Register separate callbacks for each frame
    async def upload_frame1(filename, filetype, base64Content):
        await atlantis.client_log(f"📥 Received first frame: {filename}")
        frame_storage['frame1'] = {
            'filename': filename,
            'filetype': filetype,
            'base64Content': base64Content
        }
        # Check if we have both frames now
        if 'frame2' in frame_storage:
            await atlantis.client_log(f"🎬 Starting frames-to-video generation for {username} - this may take 4-10 minutes...")
            await process_uploaded_frames()

    async def upload_frame2(filename, filetype, base64Content):
        await atlantis.client_log(f"📥 Received second frame: {filename}")
        frame_storage['frame2'] = {
            'filename': filename,
            'filetype': filetype,
            'base64Content': base64Content
        }
        # Check if we have both frames now
        if 'frame1' in frame_storage:
            await atlantis.client_log(f"🎬 Starting frames-to-video generation for {username} - this may take 4-10 minutes...")
            await process_uploaded_frames()

    await atlantis.client_upload(f"{uploadId}_frame1", upload_frame1)
    await atlantis.client_upload(f"{uploadId}_frame2", upload_frame2)
    await atlantis.client_html(minipage)
    await atlantis.client_script(miniscript)
