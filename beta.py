import streamlit as st
import os
import json
import asyncio
import websockets
import base64
import wave
import tempfile

# API Configuration from Streamlit Secrets
API_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
API_KEY = st.secrets["OPENAI_API_KEY"]  # Securely retrieve API key

# Streamlit UI Setup
st.title("GPT-4o Realtime Speech-to-Text & Text-to-Speech Interaction")
status = st.empty()  # Placeholder for status updates
log_area = st.empty()  # Placeholder to show response logs

# Initialize conversation history
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

def log_and_display(message):
    """Log messages in Streamlit and the console."""
    log_area.write(message)
    print(message)

def write_audio_to_wav(audio_buffer):
    """Write the buffered audio chunks into a proper WAV file."""
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")

    # Create a new WAV file and set the proper parameters
    with wave.open(temp_audio.name, 'wb') as wf:
        wf.setnchannels(1)  # Mono audio
        wf.setsampwidth(2)  # 16-bit audio
        wf.setframerate(19000)  # Match the sample rate
        wf.writeframes(audio_buffer)  # Write the audio data

    return temp_audio.name

async def connect_to_openai(input_text=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        status.text("Connecting to OpenAI Realtime API...")
        async with websockets.connect(API_URL, extra_headers=headers) as ws:
            log_and_display("Connected to OpenAI Realtime API.")

            # Initialize the session
            session_event = {
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": "You are a helpful assistant called Aris.",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.1,
                        "prefix_padding_ms": 10,
                        "silence_duration_ms": 999,
                    },
                },
            }
            await ws.send(json.dumps(session_event))
            log_and_display("Session initialized.")

            # Populate conversation history
            for item in st.session_state.conversation_history:
                await ws.send(json.dumps(item))
                log_and_display(f"Restored conversation item: {item}")

            # Send new user input if available
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
                st.session_state.conversation_history.append(user_message)  # Save to history
                log_and_display(f"Sent text input: {input_text}")

            # Request AI response
            response_request = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                    "output_audio_format": "pcm16",
                },
            }
            await ws.send(json.dumps(response_request))
            log_and_display("Requested AI response.")

            # Buffer to accumulate audio chunks
            audio_buffer = bytearray()

            # Process responses from WebSocket
            async for response in ws:
                res = json.loads(response)
                log_and_display(f"Received response: {res}")

                # Initialize delta to avoid undefined variable errors
                delta = ""

                if res.get("type") == "response.text.delta":
                    delta = res.get("delta", "")
                    if delta:
                        st.write(delta)  # Display partial text

                        # Save assistant response to conversation history
                        assistant_message = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "text", "text": delta}],
                            },
                        }
                        st.session_state.conversation_history.append(assistant_message)

                elif res.get("type") == "response.audio.delta":
                    audio_chunk = base64.b64decode(res["delta"])
                    audio_buffer.extend(audio_chunk)  # Accumulate chunks

                elif res.get("type") in {"response.audio.done", "response.audio_transcript.done"}:
                    # Handle transcript when available
                    transcript = res.get("transcript", "")
                    if transcript:
                        st.write(transcript)

                elif res.get("type") == "response.done":
                    log_and_display("Response completed.")
                    break

                else:
                    log_and_display(f"Unexpected event: {res}")

            # Write the accumulated audio to a WAV file
            if audio_buffer:
                log_and_display("Writing audio to WAV...")
                wav_file = write_audio_to_wav(audio_buffer)

                # Play the final WAV audio in Streamlit with autoplay enabled
                with open(wav_file, "rb") as f:
                    st.audio(f.read(), format="audio/wav", autoplay=True)

    except websockets.exceptions.ConnectionClosedError as e:
        st.error(f"Connection closed unexpectedly: {e}")
        log_and_display(f"Connection closed: {e}")
    except Exception as e:
        st.error(f"An error occurred: {e}")
        log_and_display(f"An error occurred: {e}")


# Streamlit UI to Start Conversation
conversation_active = st.checkbox("Activate Conversation")

if conversation_active:
    user_text = st.text_input("Enter text input:")

    if user_text:
        asyncio.run(connect_to_openai(input_text=user_text))
