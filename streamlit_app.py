import streamlit as st
import openai
import sounddevice as sd
import numpy as np
import queue

# Set your OpenAI API key
openai.api_key = 'your-api-key-here'

# Initialize a queue to store audio data
audio_queue = queue.Queue()

# Function to capture audio
def audio_callback(indata, frames, time, status):
    audio_queue.put(indata.copy())

# Function to process audio and get AI response
def get_ai_response():
    # Collect audio data from the queue
    audio_data = []
    while not audio_queue.empty():
        audio_data.append(audio_queue.get())

    # Convert audio data to a format suitable for OpenAI API
    audio_data = np.concatenate(audio_data, axis=0)

    # Call OpenAI API with the audio data
    response = openai.Audio.create(
        model="whisper-1",
        audio=audio_data,
        response_format="text"
    )

    return response['text']

# Streamlit app layout
st.title("Real-time Voice Discussion with OpenAI")

if st.button("Start Recording"):
    # Start audio stream
    with sd.InputStream(callback=audio_callback):
        st.write("Recording...")

    # Get AI response
    response_text = get_ai_response()
    st.write("AI Response:", response_text)
