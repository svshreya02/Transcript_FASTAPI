import subprocess
import streamlink
import streamlit as st
import tempfile
import base64
import os
from dotenv import load_dotenv
import assemblyai as aai
from PIL import Image
from io import BytesIO  
from openai import OpenAI

load_dotenv()
OpenAI.api_key = os.getenv("OPENAI_API_KEY")
if not OpenAI.api_key:     
    raise ValueError("The OpenAI API key must be set in the OPENAI_API_KEY environment variable.")
client = OpenAI()

aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

# Function to execute FFmpeg command and capture output
def execute_ffmpeg_command(command):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print("FFmpeg command executed successfully.")
            return result.stdout, result.stderr
        else:
            print("Error executing FFmpeg command:")
            return None, result.stderr
    except Exception as e:
        print("An error occurred during FFmpeg execution:")
        return None, str(e)

# Function to get transcript from AssemblyAI using audio content
def get_transcript_from_audio(audio_file_path):
    try:
        # Initialize AssemblyAI client
        transcriber = aai.Transcriber()

        # Submit audio file for transcription
        transcript = transcriber.transcribe(audio_file_path)

        # Get the transcript text
        transcript_text = transcript.text
        return transcript_text
    except Exception as e:
        print(f"Error submitting transcription job: {e}")
        return None

# Function to generate description for video frames
def generate_description(base64_frames):
    try:
        prompt_messages = [
            {
                "role": "user",
                "content": [
                    "1. Generate a description for this sequence of video frames in about 90 words. 2.Return the following: i. List of objects in the video ii. Any restrictive content or sensitive content and if so which frame.",
                    *map(lambda x: {"image": x, "resize": 428}, base64_frames),
                ],
            },
        ]
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=prompt_messages,
            max_tokens=3000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in generate_description: {e}")
        return None

def generate_overall_description(transcript, video_description):
    try:
        prompt_messages = [
            {"role": "user", "content": transcript + "\n\n" + video_description},
            {"role": "assistant", "content": "Generate an oin detail description combining the transcript and video description."}
        ]
        response = client.chat.completions.create(
            model="gpt-4",
            messages=prompt_messages,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in generate_overall_description: {e}")
        return None


# Streamlit UI
st.title("Insightly Video")
stream_url = st.text_input("Enter the live stream URL (YouTube, Twitch, etc.):")

# Slider to select the number of seconds for extraction
seconds = st.slider("Select the number of seconds for extraction:", min_value=1, max_value=60, value=10)

# Check if URL is provided
if stream_url:
    # Fetch the best quality stream URL
    streams = streamlink.streams(stream_url)
    if "best" in streams:
        stream_url = streams["best"].url

        # Execute FFmpeg command and capture the output
        ffmpeg_command = [
            'ffmpeg',
            '-i', stream_url,           # Input stream URL
            '-t', str(seconds),         # Duration to process the input (selected seconds)
            '-vf', 'fps=1',             # Extract one frame per second
            '-f', 'image2pipe',         # Output format as image2pipe
            '-c:v', 'mjpeg',            # Codec for output video
            '-an',                      # No audio
            '-'
        ]
        ffmpeg_output, _ = execute_ffmpeg_command(ffmpeg_command)

        if ffmpeg_output:
            st.write("Frames Extracted:")

            # Display frames in a grid format
            cols_per_row = 3
            frame_bytes_list = ffmpeg_output.split(b'\xff\xd8')[1:]  # Skip the initial empty frame
            n_frames = len(frame_bytes_list)
            base64_frames = []
            for idx in range(0, n_frames, cols_per_row):
                cols = st.columns(cols_per_row)
                for col_index in range(cols_per_row):
                    frame_idx = idx + col_index
                    if frame_idx < n_frames:
                        with cols[col_index]:
                            # Decode base64 and display the frame
                            frame_bytes = b'\xff\xd8' + frame_bytes_list[frame_idx]
                            frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')
                            base64_frames.append(frame_base64)
                            st.image(Image.open(BytesIO(frame_bytes)), caption=f'Frame {frame_idx + 1}', use_column_width=True)

 
        # Extract audio
        audio_command = [
            'ffmpeg',
            '-i', stream_url,           # Input stream URL
            '-vn',                      # Ignore the video for the audio output
            '-acodec', 'libmp3lame',    # Set the audio codec to MP3
            '-t', str(seconds),         # Duration for the audio extraction (selected seconds)
            '-f', 'mp3',                # Output format as MP3
            '-'
        ]
        audio_output, _ = execute_ffmpeg_command(audio_command)

        if audio_output:
            st.write("Extracted Audio:")
            audio_tempfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            audio_tempfile.write(audio_output)
            audio_tempfile.close()

            st.audio(audio_output, format='audio/mpeg', start_time=0)

            # Get the transcript from AssemblyAI
            transcript = get_transcript_from_audio(audio_tempfile.name)
            if transcript:
                st.markdown("**Transcript:**")
                st.write(transcript)
            else:
                st.write("Failed to retrieve transcript.")

            # Get consolidated description for all frames
            if ffmpeg_output:
                description = generate_description(base64_frames)
                if description:
                    st.markdown("**Frame Description:**")
                    st.write(description)
                else:
                    st.write("Failed to generate description.")

                # Generate overall description using transcript and video description
                overall_description = generate_overall_description(transcript, description)
                if overall_description:
                    st.markdown("**Consolidated Description:**")
                    st.write(overall_description)
                else:
                    st.write("Failed to generate overall description.")

    else:
        st.write("No suitable streams found.")

