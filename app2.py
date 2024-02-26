from fastapi import FastAPI, File, UploadFile
from typing import Optional
import shutil
import tempfile
from main import get_transcript_from_audio  # Ensure this points to your actual function

app = FastAPI()

@app.post("/transcribe/")
async def transcribe_audio(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_file_path = temp_file.name
    transcript = get_transcript_from_audio(temp_file_path)
    return {"transcript": transcript}
