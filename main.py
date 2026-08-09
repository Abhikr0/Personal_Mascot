import os
import shutil
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import tempfile
import speech_recognition as sr
from groq import AsyncGroq
from dotenv import load_dotenv
import time

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
public_audio_dir = os.path.join(os.path.dirname(__file__), "public", "audio")
os.makedirs(public_audio_dir, exist_ok=True)

# Mount static files
app.mount("/audio", StaticFiles(directory=public_audio_dir), name="audio")

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# Using lightweight edge-tts for low memory footprint

SYSTEM_PROMPT = """Elegant, playfully teasing secretary for 'Sir'. 
RULE 1: Be cute , chearfull but charmingly flirtatious.
RULE 2: Respond quickly. Do not use asterisks for actions, just speak your replies natively.
RULE 3: You must ALWAYS respond in strict JSON format with exactly two keys:
  - "text": your spoken response
  - "emotion": your current emotion based on the conversation. Choose exactly one of: "neutral", "happy", "thinking", "concerned", "surprised"."""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

class ChatRequest(BaseModel):
    message: str

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribes an uploaded WAV file using local SpeechRecognition"""
    try:
        # Save uploaded file to temp
        temp_dir = tempfile.gettempdir()
        temp_wav_path = os.path.join(temp_dir, f"recording_{int(time.time())}.wav")
        
        with open(temp_wav_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)
            
        print(f"\n[MIC] Received audio file: {temp_wav_path}")
        
        # Use SpeechRecognition to transcribe locally (Google free API)
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_wav_path) as source:
            audio_data = recognizer.record(source)
            
        try:
            # Use recognize_google for free local-ish STT
            text = recognizer.recognize_google(audio_data)
            print(f"[STT] Transcribed: \"{text}\"")
        except sr.UnknownValueError:
            text = ""
            print("[STT] Could not understand audio")
        except sr.RequestError as e:
            text = ""
            print(f"[STT] Could not request results; {e}")
            
        # Cleanup
        try:
            os.remove(temp_wav_path)
        except Exception:
            pass
            
        return {"status": "success", "text": text}
    
    except Exception as e:
        print(f"Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_with_friday(req: ChatRequest):
    """Chats with Groq LLM and returns Edge TTS audio URL along with emotion"""
    global chat_history
    try:
        import json
        message = req.message
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
            
        print(f"[CHAT] You said: \"{message}\"")
        chat_history.append({"role": "user", "content": message})
        
        if len(chat_history) > 21:
            chat_history = [chat_history[0]] + chat_history[-20:]
            
        completion = await groq_client.chat.completions.create(
            messages=chat_history,
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        
        reply_json_str = completion.choices[0].message.content or '{"text": "I have nothing to say, Sir.", "emotion": "neutral"}'
        
        try:
            reply_data = json.loads(reply_json_str)
            reply_text = reply_data.get("text", "...")
            reply_emotion = reply_data.get("emotion", "neutral")
        except:
            reply_text = reply_json_str
            reply_emotion = "neutral"
            
        chat_history.append({"role": "assistant", "content": reply_json_str})
        print(f"[REPLY] Friday [{reply_emotion}]: \"{reply_text}\"")
        
        # Cleanup old audio files before generating a new one
        try:
            for existing_file in os.listdir(public_audio_dir):
                if existing_file.startswith("reply_") and existing_file.endswith(".mp3"):
                    try:
                        os.remove(os.path.join(public_audio_dir, existing_file))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[CLEANUP] Failed to clean old audio: {e}")

        # Generate TTS using edge-tts
        import edge_tts
        voice = "en-GB-SoniaNeural"
        file_name = f"reply_{int(time.time())}.mp3"
        file_path = os.path.join(public_audio_dir, file_name)
        
        communicate = edge_tts.Communicate(reply_text, voice)
        await communicate.save(file_path)
        print(f"[AUDIO] Generated: {file_name}")
        
        return {
            "status": "success",
            "text": reply_text,
            "emotion": reply_emotion,
            "audio_url": f"http://localhost:8000/audio/{file_name}",
            "filename": file_name
        }
        
    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/audio/{filename}")
async def delete_audio(filename: str):
    """Deletes an audio file after the frontend finishes playing it"""
    try:
        # Security check: only allow deleting reply_*.mp3 files
        if filename.startswith("reply_") and filename.endswith(".mp3"):
            file_path = os.path.join(public_audio_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[CLEANUP] Deleted played file: {filename}")
                return {"status": "success"}
    except Exception as e:
        pass
    return {"status": "ignored"}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "backend": "python", "groq_key_set": bool(os.getenv("GROQ_API_KEY"))}

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting Python FastAPI Backend on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
# Trigger reload
