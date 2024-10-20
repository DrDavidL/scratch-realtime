import streamlit as st
import os
import json
import asyncio
import websockets
import base64
import wave
import tempfile
from streamlit_mic_recorder import mic_recorder, speech_to_text

# API Configuration
API_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
API_KEY = st.secrets["OPENAI_API_KEY"]

# UI Setup
st.title("GPT-4o Interaction Modes")

# Conversation History Initialization
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

def log_and_display(message):
    log_area.write(message)
    print(message)

def write_audio_to_wav(audio_buffer):
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    with wave.open(temp_audio.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio_buffer)
    return temp_audio.name

async def connect_to_openai(input_text=None, audio_bytes=None, output_format="text"):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(API_URL, extra_headers=headers) as ws:
            session_event = {
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": "You are a helpful assistant called Aris.",
                    "voice": "alloy" if output_format == "audio" else None,
                    "output_audio_format": "pcm16" if output_format == "audio" else None,
                },
            }
            await ws.send(json.dumps(session_event))

            for item in st.session_state.conversation_history:
                await ws.send(json.dumps(item))

            if input_text:
                user_message = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": input_text}],
                    },
                }
                await ws.send(json.dumps(user_message))
                st.session_state.conversation_history.append(user_message)

            elif audio_bytes:
                audio_base64 = base64.b64encode(audio_bytes).decode()
                audio_message = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_audio", "audio": audio_base64}],
                    },
                }
                await ws.send(json.dumps(audio_message))
                st.session_state.conversation_history.append(audio_message)

            response_request = {"type": "response.create"}
            await ws.send(json.dumps(response_request))

            audio_buffer = bytearray()
            async for response in ws:
                res = json.loads(response)
                delta = res.get("delta", "")
                if delta:
                    st.write(delta)

                if res.get("type") == "response.audio.delta":
                    audio_chunk = base64.b64decode(res["delta"])
                    audio_buffer.extend(audio_chunk)

                elif res.get("type") == "response.done":
                    break

            if audio_buffer:
                wav_file = write_audio_to_wav(audio_buffer)
                with open(wav_file, "rb") as f:
                    st.audio(f.read(), format="audio/wav", autoplay=True)

    except Exception as e:
        st.error(f"Error: {e}")

# Select Interaction Mode
st.write("Choose your interaction mode:")
interaction_mode = st.selectbox(
    "Select Mode",
    (
        "Voice Input Streaming → Voice Output Streaming",
        "Voice Input (Recorded) → Voice Output Streaming",
        "Text Input → Voice Output Streaming",
        "Text Input → Text Output"
    ),
)

log_area = st.empty()

# Handle Interaction Based on Mode
if interaction_mode == "Voice Input Streaming → Voice Output Streaming":
    audio = mic_recorder(start_prompt="Start Streaming", stop_prompt="Stop Streaming", key="streaming")
    if audio and st.button("Send Streaming Audio"):
        asyncio.run(connect_to_openai(audio_bytes=audio["bytes"], output_format="audio"))

elif interaction_mode == "Voice Input (Recorded) → Voice Output Streaming":
    st.write("Record your voice:")
    audio = mic_recorder(start_prompt="Start Recording", stop_prompt="Stop Recording", key="recorded")
    if audio and st.button("Send Recorded Audio"):
        st.audio(audio["bytes"])
        asyncio.run(connect_to_openai(audio_bytes=audio["bytes"], output_format="audio"))

elif interaction_mode == "Text Input → Voice Output Streaming":
    text_input = st.text_input("Enter text:")
    if text_input and st.button("Send Text for Voice Output"):
        asyncio.run(connect_to_openai(input_text=text_input, output_format="audio"))

elif interaction_mode == "Text Input → Text Output":
    text_input = st.text_input("Enter text:")
    if text_input and st.button("Send Text for Text Output"):
        asyncio.run(connect_to_openai(input_text=text_input, output_format="text"))
