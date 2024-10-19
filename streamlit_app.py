import base64
import openai
from openai import OpenAI
import streamlit as st
import requests
import sounddevice as sd
import numpy as np
import queue

# Set your OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Initialize OpenAI client
client = OpenAI()

# Initialize a queue to store audio data
audio_queue = queue.Queue()

# Function to capture audio
def audio_callback(indata, frames, time, status):
    audio_queue.put(indata.copy())

# Fetch the audio file and convert it to a base64 encoded string
url = "https://openaiassets.blob.core.windows.net/$web/API/docs/audio/alloy.wav"
response = requests.get(url)
response.raise_for_status()
wav_data = response.content
encoded_string = base64.b64encode(wav_data).decode('utf-8')
def get_ai_response():
    # Collect audio data from the queue
    audio_data = []
    while not audio_queue.empty():
        audio_data.append(audio_queue.get())

    if audio_data:
        # Convert audio data to a format suitable for OpenAI API
        audio_data = np.concatenate(audio_data, axis=0)

        # Call OpenAI API with the audio data
        completion = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            messages=[{
                "role": "user",
                "content": [
                    { 
                        "type": "text",
                        "text": "What is in this recording?"
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": encoded_string,
                            "format": "wav"
                        }
                    }
                ]}
            ]
        )

        # Decode and save the audio response
        wav_bytes = base64.b64decode(completion.choices[0].message.audio.data)
        with open("response.wav", "wb") as f:
            f.write(wav_bytes)

        return completion.choices[0].message.content
    else:
        return "No audio data captured. Please try recording again."

# Streamlit app layout
st.title("Real-time Voice Discussion with OpenAI")

recording = st.checkbox("Start/Stop Recording")

if recording:
    # Start audio stream
    with sd.InputStream(callback=audio_callback):
        st.write("Recording...")
        sd.sleep(5000)  # Record for 5 seconds

    # Get AI response
    response_text = get_ai_response()
    st.write("AI Response:", response_text)
