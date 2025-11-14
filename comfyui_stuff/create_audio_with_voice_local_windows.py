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
import io

logger = logging.getLogger("mcp_client")

def update_workflow_seeds(workflow):
    """Randomize seeds in the workflow for unique generations"""
    for node_id, node_data in workflow.items():
        if "seed" in node_data.get("inputs", {}):
            node_data["inputs"]["seed"] = random.randint(1, 2**32 - 1)
    return workflow

@visible
async def create_audio_with_voice(prompt: str = "Hello! This is a test of the voice cloning system.", **kwargs):
    """
    Creates audio from an uploaded voice sample using ComfyUI workflow with real-time status updates. Maximum 30 seconds of audio.

    Args:
        prompt: Text to be spoken in the cloned voice
    """

    # Collect any extra positional args that were parsed separately and join them with the prompt
    extra_words = [str(v) for k, v in kwargs.items() if k not in ['prompt']]
    if extra_words:
        prompt = prompt + " " + " ".join(extra_words)

    username = atlantis.get_caller() or "unknown_user"

    await atlantis.owner_log(f"create_audio_with_voice called by {username} with prompt: {prompt}")

    # Generate unique upload id to avoid conflicts
    uploadId = f"audio_upload_{str(uuid.uuid4()).replace('-', '')[:8]}"

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
                min-height: 100px;
            }
            .prompt-input:focus {
                outline: none;
                border-color: #9c4bd9;
                box-shadow: 0 0 10px rgba(108, 43, 151, 0.4);
            }
        </style>
        <h3 style="color: #6c2b97;">🎵 Upload Voice to Create Audio</h3>
        <p style="color: #ccc;">Select an audio file (max 30 seconds) to clone voice</p>

        <div style="background: rgba(108, 43, 151, 0.2); padding: 10px; border-radius: 6px; margin: 10px 0;">
            <strong style="color: #6c2b97;">📝 Text to Speak:</strong>
            <p style="color: #fff; margin: 5px 0 0 0;">{PROMPT}</p>
        </div>

        <label for="fileUpload_{UPLOAD_ID}" class="fancy-file-upload">
            🎤 Choose Audio File (Max 30s)
            <input style='margin:5px' type="file" id="fileUpload_{UPLOAD_ID}" name="fileUpload_{UPLOAD_ID}" accept="audio/*" />
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
        ">Generate Audio</button>
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
                sendButton.innerText = "Generate Audio";
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
    async def process_uploaded_audio(filename, filetype, base64Content, data=None):
        try:
            # Job tracking
            job_id = f"{username}.{uploadId}"

            # Use the prompt from the function parameter (captured in closure)
            await atlantis.owner_log(f"[{job_id}] === AUDIO GENERATION ===")
            await atlantis.owner_log(f"[{job_id}] Filename: {filename}")
            await atlantis.owner_log(f"[{job_id}] Filetype: {filetype}")
            await atlantis.owner_log(f"[{job_id}] Using prompt from function parameter: '{prompt}'")

            await atlantis.client_log("📥 Processing uploaded audio...")
            await atlantis.client_log(f"🎵 Text to speak: {prompt[:100]}...")

            # Decode base64 and save audio temporarily
            base64_data = base64Content
            if base64_data.startswith('data:'):
                base64_data = base64_data.split(',')[1]

            file_bytes = base64.b64decode(base64_data)

            temp_filename = f"temp_input_{uploadId}.mp3"

            await atlantis.client_log("📋 Loading audio generation workflow...")

            # Audio workflow JSON based on audio2audio_prod_api_fix.json
            workflow_data = {
                "2": {
                    "inputs": {
                        "audio": temp_filename,
                        "audioUI": ""
                    },
                    "class_type": "LoadAudio",
                    "_meta": {"title": "LoadAudio"}
                },
                "4": {
                    "inputs": {
                        "filename_prefix": "audio/ComfyUI",
                        "audioUI": "",
                        "audio": ["6", 0]
                    },
                    "class_type": "SaveAudio",
                    "_meta": {"title": "SaveAudio"}
                },
                "5": {
                    "inputs": {
                        "text": prompt,
                        "model": "VibeVoice-Large",
                        "attention_type": "sdpa",
                        "free_memory_after_generate": True,
                        "diffusion_steps": 30,
                        "seed": random.randint(1, 2**32 - 1),
                        "cfg_scale": 1.2,
                        "use_sampling": False,
                        "temperature": 0.95,
                        "top_p": 0.95,
                        "max_words_per_chunk": 250,
                        "voice_to_clone": ["2", 0]
                    },
                    "class_type": "VibeVoiceSingleSpeakerNode",
                    "_meta": {"title": "VibeVoice Single Speaker"}
                },
                "6": {
                    "inputs": {
                        "anything": ["5", 0]
                    },
                    "class_type": "easy cleanGpuUsed",
                    "_meta": {"title": "Clean VRAM Used"}
                }
            }

            await atlantis.client_log("🎲 Randomizing seeds for unique generation...")

            # Randomize seeds for unique generation
            workflow = update_workflow_seeds(workflow_data)

            await atlantis.client_log("🚀 Submitting audio job to ComfyUI server...")

            # Upload audio to ComfyUI server using in-memory buffer
            file_buffer = io.BytesIO(file_bytes)
            file_buffer.seek(0)
            files = {'image': (temp_filename, file_buffer, 'audio/mpeg')}

            try:
                upload_response = requests.post(
                    f"http://{server_address}/upload/image",
                    files=files,
                    timeout=30
                )
                upload_response.raise_for_status()
            finally:
                file_buffer.close()

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

            await atlantis.client_log(f"✅ Audio job submitted! ID: {prompt_id}")

            # Check queue status
            try:
                queue_response = requests.get(f"http://{server_address}/queue")
                if queue_response.status_code == 200:
                    queue_data = queue_response.json()
                    pending = len(queue_data.get("queue_pending", []))
                    running = len(queue_data.get("queue_running", []))
                    await atlantis.client_log(f"📊 Queue status: {running} running, {pending} pending")
            except:
                pass

            await atlantis.client_log("⏳ Waiting for audio generation to complete...")

            # Poll for completion
            max_wait_time = 300  # 5 minutes max
            start_time = time.time()
            last_update = 0

            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)

                # Send progress update every 20 seconds
                if elapsed - last_update >= 20:
                    await atlantis.client_log(f"🔄 Still generating audio... ({elapsed}s elapsed)")
                    last_update = elapsed

                try:
                    history_response = requests.get(f"http://{server_address}/history/{prompt_id}")

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

                await asyncio.sleep(5)  # Check every 5 seconds

            if time.time() - start_time >= max_wait_time:
                await atlantis.client_log("❌ Timeout: Audio generation took too long")
                return

            await atlantis.client_log("📥 Audio generation complete! Downloading audio...")

            # Extract and save audio files
            prompt_history = history_data[prompt_id]
            outputs = prompt_history.get("outputs", {})
            saved_audios = []

            await atlantis.client_log(f"🔍 Debug: Found outputs for nodes: {list(outputs.keys())}")

            # Look for SaveAudio node (node 4 in workflow)
            for node_id, node_output in outputs.items():
                await atlantis.client_log(f"🔍 Debug: Node {node_id} output keys: {list(node_output.keys())}")

                # Check for audio output
                if "audio" in node_output:
                    await atlantis.client_log(f"🎵 Found audio in node {node_id}: {len(node_output['audio'])} items")

                    for i, audio_info in enumerate(node_output["audio"]):
                        await atlantis.client_log(f"🔍 Debug: audio item {i}: {audio_info}")

                        filename = audio_info["filename"]
                        subfolder = audio_info.get("subfolder", "")
                        media_type = audio_info.get("type", "output")

                        # Build download parameters
                        params = {"filename": filename, "type": media_type}
                        if subfolder:
                            params["subfolder"] = subfolder

                        await atlantis.client_log(f"📥 Downloading: {filename} from {subfolder}")

                        # Download audio
                        audio_response = requests.get(f"http://{server_address}/view", params=params)
                        audio_response.raise_for_status()

                        # Encode as base64 for web display
                        audio_base64 = base64.b64encode(audio_response.content).decode('utf-8')

                        saved_audios.append({
                            "original_filename": filename,
                            "size": len(audio_response.content),
                            "node_id": node_id,
                            "base64": audio_base64
                        })

            if saved_audios:
                await atlantis.client_log("🎵 Processing final audio...")

                await atlantis.client_log(f"Generated {len(saved_audios)} audio files from voice for {username}")

                # Create HTML audio player
                for i, audio in enumerate(saved_audios):
                    audio_extension = audio['original_filename'].split('.')[-1].lower()
                    mime_type = f"audio/{audio_extension if audio_extension in ['mp3', 'wav', 'ogg', 'webm'] else 'mpeg'}"

                    audio_html = f"""
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
                            <h4 style="color: #6c2b97; margin: 0 0 10px 0;">🎵 Generated Audio</h4>
                            <audio
                                controls
                                style="
                                    width: 100%;
                                    max-width: 100%;
                                    border-radius: 8px;
                                    display: block;
                                    margin: 0 auto;
                                "
                            >
                                <source src="data:{mime_type};base64,{audio['base64']}" type="{mime_type}">
                                Your browser does not support the audio tag.
                            </audio>
                            <p style="color: #ccc; margin: 10px 0 0 0; font-size: 12px;">
                                Size: {audio['size'] // 1024:.1f} KB | Right-click to save
                            </p>
                        </div>
                    </div>
                    """

                    await atlantis.client_html(audio_html)

                await atlantis.client_log(f"✨ Generated {len(saved_audios)} audio file(s) from your voice! 🎵💜")
            else:
                await atlantis.client_log("❌ No audio found in workflow output")

        except requests.RequestException as e:
            error_msg = f"ComfyUI API error: {str(e)}"
            await atlantis.owner_log(f"API error: {e}")
            await atlantis.client_log(f"❌ {error_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            await atlantis.owner_log(f"Unexpected error: {e}")
            await atlantis.client_log(f"❌ {error_msg}")

    # Register the upload callback
    async def upload(filename, filetype, base64Content, data=None):
        await atlantis.client_log(f"🎵 Starting audio generation from voice for {username} - this may take up to 2 minutes...")
        await atlantis.client_log("Processing uploaded audio for voice cloning...")

        # Validate audio duration (max 30 seconds)
        try:
            base64_data = base64Content
            if base64_data.startswith('data:'):
                base64_data = base64_data.split(',')[1]

            file_bytes = base64.b64decode(base64_data)

            # Check file size as rough estimate (assuming ~128kbps mp3)
            # 128kbps = 16KB/s, so 30s = ~480KB
            max_size = 1024 * 1024  # 1MB to be safe
            if len(file_bytes) > max_size:
                await atlantis.client_log("❌ Error: Audio file is too large. Please use audio shorter than 30 seconds.")
                return

        except Exception as e:
            logger.warning(f"Could not validate audio duration: {e}")

        await process_uploaded_audio(filename, filetype, base64Content, data)


    await atlantis.client_upload(uploadId, upload)
    await atlantis.client_html(minipage)
    await atlantis.client_script(miniscript)
