import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import shutil
import json
import asyncio
import subprocess
import tempfile
import time
import datetime
import base64
import re
import io

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import edge_tts
from groq import Groq

# Native Agent Runner imports (Zero LangChain / LangGraph)
from agent_runner import SystemMessage, HumanMessage, AIMessage, ChatMessage, execute_agent_turn


load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

public_audio_dir = os.path.join(base_dir, "public", "audio")
os.makedirs(public_audio_dir, exist_ok=True)

def cleanup_all_spoken_audio():
    """Removes all spoken audio files (reply_*, etc.) from public_audio_dir."""
    count = 0
    valid_extensions = (".mp3", ".wav", ".webm", ".ogg", ".aac", ".m4a", ".tmp")
    try:
        if os.path.exists(public_audio_dir):
            for fname in os.listdir(public_audio_dir):
                if (fname.startswith("reply_") or fname.startswith("out_") or fname.startswith("in_")) and fname.endswith(valid_extensions):
                    try:
                        os.remove(os.path.join(public_audio_dir, fname))
                        count += 1
                    except Exception as ce:
                        print(f"[CLEANUP] Could not remove {fname}: {ce}")
    except Exception as e:
        print(f"[CLEANUP ERROR] Failed during spoken audio cleanup: {e}")
    if count > 0:
        print(f"[CLEANUP] Purged {count} leftover spoken audio file(s) from {public_audio_dir}")
    return count

# Run initial cleanup on startup
cleanup_all_spoken_audio()

# Mount static files
app.mount("/audio", StaticFiles(directory=public_audio_dir), name="audio")

# =========================================================
# TOOLS - Friday's comprehensive Windows control suite
# =========================================================
from tools import ALL_FRIDAY_TOOLS
from memory import (
    memory_db, remember_user_statement, search_memories_semantic,
    maybe_compress_history, log_interaction, log_feedback, feedback_stats
)

tools = ALL_FRIDAY_TOOLS

# =========================================================
# LANGGRAPH AGENT SETUP
# =========================================================

SYSTEM_PROMPT = """Sylphya: charming AI secretary. Max 3-7 words per reply (one tiny sentence, never ramble).
- Plain text only for speech (no markdown/emojis). Proactively use tools when asked.
- Emotions: neutral, happy, thinking, concerned, surprised, excited, embarrassed, curious, annoyed, playful, loving.
- Output JSON ONLY: {"text": "3-7 words reply", "emotion": "happy", "intensity": 0.8}"""

def extract_text(content) -> str:
    if isinstance(content, str): return content.strip()
    if isinstance(content, list): return "".join(p.get("text", "") if isinstance(p, dict) else str(getattr(p, "text", p)) for p in content).strip()
    return str(content).strip()

MISTRAL_MODELS = ["ministral-3b-latest", "open-mistral-nemo", "ministral-8b-latest", "mistral-small-latest", "codestral-latest"]
GEMINI_MODELS = ["gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

# Build candidate priority list (Mistral models first, then Gemini models, then Groq models)
CANDIDATE_MODEL_CONFIGS = []
if os.getenv("MISTRAL_API_KEY"):
    for m in MISTRAL_MODELS:
        CANDIDATE_MODEL_CONFIGS.append(("mistral", m))

if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
    for m in GEMINI_MODELS:
        CANDIDATE_MODEL_CONFIGS.append(("gemini", m))

if os.getenv("GROQ_API_KEY"):
    for m in GROQ_MODELS:
        CANDIDATE_MODEL_CONFIGS.append(("groq", m))


# Singleton Groq client for low-latency STT
_groq_client = None

def get_groq_client():
    global _groq_client
    key = os.getenv("GROQ_API_KEY")
    if key and _groq_client is None:
        try:
            _groq_client = Groq(api_key=key)
        except Exception as e:
            print(f"[STT] Groq client init error: {e}")
    return _groq_client

def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "recording.webm") -> str:
    """Basic, fast, lightweight STT (Groq Cloud if key available, else Google SpeechRecognition)"""
    if not audio_bytes or len(audio_bytes) < 300:
        return ""

    # 1. Groq Cloud Whisper (0 CPU, 0 RAM, ~0.5s sub-second cloud)
    groq_client = get_groq_client()
    if groq_client:
        try:
            t0 = time.time()
            transcription = groq_client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model="whisper-large-v3-turbo",
                temperature=0.0,
                prompt="Hey Sylphya, Friday, Sir."
            )
            text = transcription.text.strip()
            t1 = time.time()
            print(f"[STT:Groq] Transcribed in {t1 - t0:.3f}s: \"{text}\"")
            if text:
                return text
        except Exception as ge:
            print(f"[STT:Groq] Fallback ({ge})")

    # 2. Basic Fallback: Google Speech Recognition via direct REST API (zero extra packages)
    temp_dir = tempfile.gettempdir()
    temp_in = os.path.join(temp_dir, f"in_{int(time.time())}_{filename}")
    temp_wav = os.path.join(temp_dir, f"out_{int(time.time())}.wav")
    try:
        with open(temp_in, "wb") as f:
            f.write(audio_bytes)
        target_wav = temp_in if filename.lower().endswith(".wav") else temp_wav
        if target_wav != temp_in:
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_in, "-ar", "16000", "-ac", "1", temp_wav],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        if os.path.exists(target_wav):
            import httpx
            with open(target_wav, "rb") as af:
                wav_data = af.read()
            url = "https://www.google.com/speech-api/v2/recognize?client=chromium&lang=en-US&maxresults=1"
            headers = {"Content-Type": "audio/l16; rate=16000"}
            resp = httpx.post(url, content=wav_data, headers=headers, timeout=6.0)
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    if line.strip():
                        parsed = json.loads(line)
                        results = parsed.get("result", [])
                        if results and "alternative" in results[0]:
                            alt = results[0]["alternative"][0].get("transcript", "").strip()
                            if alt:
                                return alt
    except Exception as e:
        print(f"[STT:Fallback] Note: {e}. Set GROQ_API_KEY in .env for sub-second Whisper transcription.")
    finally:
        for p in [temp_in, temp_wav]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    return ""

# Chat history (LangChain message format)
chat_history: list = []

class ChatRequest(BaseModel):
    message: str

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Ultra-low latency STT with Indian & British accent handling (Groq Whisper large-v3-turbo primary + Local Whisper fallback)"""
    try:
        audio_bytes = await audio.read()
        filename = audio.filename or "recording.webm"
        print(f"\n[MIC] Received audio: {filename} ({len(audio_bytes)} bytes)")
        
        text = await asyncio.to_thread(transcribe_audio_bytes, audio_bytes, filename)
        return {"status": "success", "text": text}
    except Exception as e:
        print(f"Transcription Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_with_friday(req: ChatRequest):
    """Chats with LangGraph agent and returns Edge TTS audio URL along with emotion"""
    global chat_history
    try:
        message = req.message
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
            
        print(f"[CHAT] You said: \"{message}\"")
        
        # Asynchronously extract and persist durable memory entities in the background without adding latency
        asyncio.create_task(asyncio.to_thread(remember_user_statement, message))
        
        # Fast path for simple greetings (hi, hello, hey, etc.)
        clean_msg = re.sub(r'[^\w\s]', '', message.strip().lower())
        greeting_words = ["hi", "hello", "hey", "hi sylphya", "hello sylphya", "hey sylphya", "hi friday", "hello friday", "hey friday", "hi there", "hello there", "hey there"]
        
        if clean_msg in greeting_words:
            reply_text = "Hello!"
            reply_emotion = "happy"
            reply_intensity = 0.9
            final_messages = []
            print(f"[FAST-PATH] Immediate greeting response for \"{message}\": \"{reply_text}\"")
        else:
            # Build messages for the agent with injected user profile memory
            profile_context = memory_db.get_user_profile()
            sys_prompt = SYSTEM_PROMPT
            if profile_context:
                sys_prompt += f"\n\nCURRENT USER PROFILE & KNOWN FACTS ABOUT SIR:\n{profile_context}"
                
            agent_messages = [SystemMessage(content=sys_prompt)]
            
            # Compress old conversation history to keep context tight (every 20 turns)
            chat_history[:] = maybe_compress_history(chat_history, turn_threshold=20, keep_recent=6)
            agent_messages.extend(chat_history)
            agent_messages.append(HumanMessage(content=message))
            
            # Run the native ReAct agent with multi-model fallback (Mistral -> Gemini -> Groq)
            result = None
            last_agent_error = None

            if not CANDIDATE_MODEL_CONFIGS:
                reply_text = "Please set MISTRAL_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY in .env."
                reply_emotion = "concerned"
                result = {"messages": [AIMessage(content=json.dumps({"text": reply_text, "emotion": reply_emotion, "intensity": 0.8}))]}
            else:
                for provider, candidate_model in CANDIDATE_MODEL_CONFIGS:
                    try:
                        print(f"[AGENT] Running with {provider} model: {candidate_model}...")
                        result = await asyncio.to_thread(
                            execute_agent_turn,
                            agent_messages,
                            provider,
                            candidate_model,
                            tools
                        )
                        print(f"[AGENT] Successfully completed with {provider}:{candidate_model}")
                        break
                    except Exception as model_err:
                        err_text = str(model_err)
                        last_agent_error = model_err
                        print(f"[AGENT FALLBACK] {provider}:{candidate_model} error: {err_text[:140]}")
                        continue

            if result is None:
                if last_agent_error:
                    raise last_agent_error
                else:
                    raise RuntimeError("All AI models failed to respond.")
            
            # Extract the final AI response
            final_messages = result.get("messages", [])
            
            # Find the last AI message (the final response)
            reply_text = "I have nothing to say, Sir."
            reply_emotion = "neutral"
            
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    raw_content = extract_text(msg.content)
                    print(f"[AGENT] Raw response: {raw_content}")
                    try:
                        clean = re.sub(r'```(?:json)?|```', '', raw_content)
                        s, e = clean.find('{'), clean.rfind('}')
                        data = json.loads(clean[s:e+1]) if (s != -1 and e > s) else {}
                        reply_text = data.get("text", raw_content).strip()
                        reply_emotion = data.get("emotion", "happy")
                        reply_intensity = float(data.get("intensity", 0.85))
                    except Exception:
                        reply_text, reply_emotion, reply_intensity = raw_content, "happy", 0.85
                    break
        
        reply_intensity = locals().get('reply_intensity', 0.85)
        chat_history.append(HumanMessage(content=message))
        chat_history.append(AIMessage(content=json.dumps({"text": reply_text, "emotion": reply_emotion, "intensity": reply_intensity})))
        print(f"[REPLY] Sylphya [{reply_emotion} @ {reply_intensity:.2f}]: \"{reply_text}\"")
        
        tool_records = []
        for i, msg in enumerate(final_messages):
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name, tool_args, tool_id = tc.get('name', 'unknown'), tc.get('args', {}), tc.get('id')
                    tool_result = next((str(m.content)[:300] for m in final_messages[i+1:] if getattr(m, 'tool_call_id', None) == tool_id), "")
                    tool_records.append({"name": tool_name, "args": tool_args, "result": tool_result})
                    print(f"[TOOL EXECUTED] {tool_name}({tool_args}) -> {tool_result[:80]}")
        
        # Fast In-Memory Edge-TTS
        file_name = f"reply_{int(time.time())}.mp3"
        file_path = os.path.join(public_audio_dir, file_name)
        clean_tts_text = re.sub(r'[*_#`~]', '', reply_text)
        t0 = time.time()
        communicate = edge_tts.Communicate(clean_tts_text, "en-GB-SoniaNeural", rate="+25%")
        audio_chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.extend(chunk["data"])
        t_tts = time.time() - t0
        print(f"[AUDIO:Edge-TTS] Streamed {file_name} in {t_tts:.3f}s")
        audio_b64 = base64.b64encode(audio_chunks).decode("utf-8")
        asyncio.create_task(asyncio.to_thread(lambda: open(file_path, "wb").write(audio_chunks)))
        t_total = t_tts
        
        # Log interaction for ML self-improvement
        asyncio.create_task(asyncio.to_thread(
            log_interaction,
            message, reply_text, reply_emotion, reply_intensity,
            tool_records, t_total * 1000,
            f"{primary_provider}:{primary_model}"
        ))
        
        return {
            "status": "success",
            "text": reply_text,
            "emotion": reply_emotion,
            "intensity": reply_intensity,
            "audio_url": f"http://localhost:8000/audio/{file_name}",
            "audio_base64": audio_b64,
            "filename": file_name,
            "tool_calls": tool_records
        }
        
    except Exception as e:
        print(f"Chat Error: {e}")
        import traceback
        traceback.print_exc()

        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            reply_text = "Sir, my cloud quota is temporarily cooling down. Please give me about thirty seconds and try again."
        elif "503" in err_msg or "UNAVAILABLE" in err_msg:
            reply_text = "Sir, Google's AI servers are momentarily under heavy load. Please try again in a few moments."
        else:
            reply_text = "I ran into a momentary processing hiccup, Sir. Please try your request once more."

        reply_emotion = "concerned"

        audio_b64 = None
        try:
            voice = "en-GB-SoniaNeural"
            communicate = edge_tts.Communicate(reply_text, voice, rate="+15%")
            audio_bytes = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as tts_err:
            print(f"[FALLBACK TTS ERROR] {tts_err}")

        return {
            "status": "partial_error",
            "text": reply_text,
            "emotion": reply_emotion,
            "audio_base64": audio_b64,
            "tool_calls": []
        }

class DirectToolRequest(BaseModel):
    tool_name: str
    args: dict = {}

@app.get("/api/tools")
def get_tools_list():
    """List all agent tools available to Friday"""
    return {
        "status": "success",
        "count": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description
            }
            for t in tools
        ]
    }


# =========================================================
# FEEDBACK ENDPOINT — ML Self-Improvement Loop
# =========================================================

class FeedbackRequest(BaseModel):
    text: str
    positive: bool

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Record thumbs-up/down feedback for the most recent matching reply."""
    asyncio.create_task(asyncio.to_thread(log_feedback, req.text, req.positive))
    return {"status": "success", "positive": req.positive}

@app.get("/api/feedback/stats")
def get_feedback_stats():
    """Return interaction log statistics for ML monitoring."""
    return {"status": "success", **feedback_stats()}


# =========================================================
# WEBSOCKET STREAMING VOICE — Real-Time STT + TTS
# =========================================================

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    Full-duplex streaming voice pipeline:
    - Client sends PCM audio chunks as binary frames
    - Server runs streaming Whisper transcription
    - On silence detection (client sends JSON {'action': 'stop'}), runs agent
    - Server streams TTS audio chunks back as binary frames
    - Server sends JSON frames for transcript and emotion metadata
    """
    await websocket.accept()
    print("[WS] Voice WebSocket connected")
    audio_buffer = bytearray()
    try:
        while True:
            message = await websocket.receive()
            
            if "bytes" in message:
                # Binary: PCM audio chunk from microphone
                audio_buffer.extend(message["bytes"])
                
            elif "text" in message:
                data = json.loads(message["text"])
                action = data.get("action", "")
                
                if action == "transcribe":
                    # Client finished recording, transcribe buffered audio
                    if len(audio_buffer) > 300:
                        try:
                            text = await asyncio.to_thread(transcribe_audio_bytes, bytes(audio_buffer), "recording.webm")
                            audio_buffer.clear()
                            await websocket.send_json({"type": "transcript", "text": text})
                            print(f"[WS-STT] Transcribed: '{text}'")
                        except Exception as stt_err:
                            print(f"[WS-STT] Error: {stt_err}")
                            await websocket.send_json({"type": "error", "message": str(stt_err)})
                            audio_buffer.clear()
                    else:
                        audio_buffer.clear()
                        await websocket.send_json({"type": "transcript", "text": ""})
                
                elif action == "chat":
                    # Client sends text to process through agent + stream TTS back
                    user_text = data.get("text", "").strip()
                    if not user_text:
                        continue
                    
                    asyncio.create_task(asyncio.to_thread(remember_user_statement, user_text))
                    
                    # Quick emotion: set thinking while processing
                    await websocket.send_json({"type": "emotion", "emotion": "thinking", "intensity": 0.8})
                    
                    # Run agent
                    try:
                        profile_context = memory_db.get_user_profile()
                        sys_prompt = SYSTEM_PROMPT
                        if profile_context:
                            sys_prompt += f"\n\nUSER PROFILE:\n{profile_context}"
                        
                        agent_messages = [SystemMessage(content=sys_prompt)] + chat_history[-10:] + [HumanMessage(content=user_text)]
                        
                        result = None
                        if not CANDIDATE_MODEL_CONFIGS:
                            reply_text = "Please set MISTRAL_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY in .env."
                            reply_emotion = "concerned"
                            result = {"messages": [AIMessage(content=json.dumps({"text": reply_text, "emotion": reply_emotion}))]}
                        else:
                            for provider, candidate_model in CANDIDATE_MODEL_CONFIGS:
                                try:
                                    result = await asyncio.to_thread(
                                        execute_agent_turn,
                                        agent_messages,
                                        provider,
                                        candidate_model,
                                        tools
                                    )
                                    break
                                except Exception:
                                    continue
                        
                        reply_text = "I'm having a moment, Sir."
                        reply_emotion = "concerned"
                        reply_intensity = 0.7
                        
                        if result:
                            final_messages = result.get("messages", [])
                            for msg in reversed(final_messages):
                                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                                    raw = extract_text(msg.content)
                                    try:
                                        s = raw.find('{')
                                        e = raw.rfind('}')
                                        if s != -1 and e != -1:
                                            d = json.loads(raw[s:e+1])
                                            reply_text = d.get("text", raw)
                                            reply_emotion = d.get("emotion", "happy")
                                            reply_intensity = float(d.get("intensity", 0.85))
                                    except Exception:
                                        reply_text = raw
                                        reply_emotion = "happy"
                                        reply_intensity = 0.85
                                    break
                        
                        chat_history.append(HumanMessage(content=user_text))
                        chat_history.append(AIMessage(content=json.dumps({"text": reply_text, "emotion": reply_emotion})))
                        
                        # Send emotion + transcript before audio
                        await websocket.send_json({
                            "type": "reply_meta",
                            "text": reply_text,
                            "emotion": reply_emotion,
                            "intensity": reply_intensity,
                        })
                        
                        # Stream TTS audio chunks to frontend
                        voice = "en-GB-SoniaNeural"
                        clean_tts = reply_text.replace("*", "").replace("_", "").replace("#", "").replace("`", "")
                        communicate = edge_tts.Communicate(clean_tts, voice, rate="+15%")
                        chunk_count = 0
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                await websocket.send_bytes(chunk["data"])
                                chunk_count += 1
                        
                        # Signal end of audio stream
                        await websocket.send_json({"type": "audio_end"})
                        print(f"[WS-TTS] Streamed {chunk_count} audio chunks for '{reply_text[:50]}'")
                        
                    except Exception as agent_err:
                        print(f"[WS] Agent error: {agent_err}")
                        await websocket.send_json({"type": "error", "message": str(agent_err)})
                
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
                    
    except WebSocketDisconnect:
        print("[WS] Voice WebSocket disconnected")
    except Exception as e:
        print(f"[WS] Unexpected error: {e}")

@app.post("/api/tools/execute")
async def execute_tool_endpoint(req: DirectToolRequest):
    """Directly test or execute any tool by name"""
    tool_map = {t.name: t for t in tools}
    if req.tool_name not in tool_map:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{req.tool_name}' not found. Available: {list(tool_map.keys())}"
        )
    try:
        t = tool_map[req.tool_name]
        res = await asyncio.to_thread(t.invoke, req.args)
        return {
            "status": "success",
            "tool": req.tool_name,
            "args": req.args,
            "result": str(res)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/audio/{filename}")
async def delete_audio(filename: str):
    """Deletes an audio file after the frontend finishes playing it or when interrupted"""
    try:
        safe_name = os.path.basename(filename)
        valid_extensions = (".mp3", ".wav", ".webm", ".ogg", ".aac", ".m4a", ".tmp")
        if (safe_name.startswith("reply_") or safe_name.startswith("out_") or safe_name.startswith("in_")) and safe_name.endswith(valid_extensions):
            file_path = os.path.join(public_audio_dir, safe_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[CLEANUP] Deleted spoken audio file: {safe_name}")
                return {"status": "success", "file": safe_name}
            return {"status": "already_deleted", "file": safe_name}
    except Exception as e:
        print(f"[CLEANUP ERROR] Failed to delete audio {filename}: {e}")
        return {"status": "error", "message": str(e)}
    return {"status": "ignored"}

@app.post("/api/audio/cleanup")
@app.delete("/api/audio")
def cleanup_spoken_audio_endpoint():
    """Endpoint to clean up all spoken audio files."""
    deleted_count = cleanup_all_spoken_audio()
    return {"status": "success", "deleted_files_count": deleted_count}

@app.get("/api/health")
def health_check():
    from memory.fast_extractor import is_available as fast_ext_ok
    return {
        "status": "ok",
        "backend": "python",
        "orchestration": "native-react",
        "primary_llm": "mistral" if os.getenv("MISTRAL_API_KEY") else "gemini",
        "stt_engine": "groq_whisper_large_v3_turbo" if os.getenv("GROQ_API_KEY") else "local_faster_whisper",
        "tts_engine": "edge_tts_streaming",
        "ws_voice": "ws://localhost:8000/ws/voice",
        "semantic_memory": False,
        "fast_extractor": fast_ext_ok(),
        "mistral_key_set": bool(os.getenv("MISTRAL_API_KEY")),
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "groq_key_set": bool(os.getenv("GROQ_API_KEY")),
        "tools": [t.name for t in tools],
        "memories_count": len(memory_db.list_all_memories()),
        "feedback_stats": feedback_stats(),
    }

# =========================================================
# MEMORY KNOWLEDGE BASE ENDPOINTS
# =========================================================

class MemorySearchRequest(BaseModel):
    query: str
    category: str = ""

@app.get("/api/memory")
def get_all_memories(category: str = ""):
    """Retrieve all stored memories, optionally filtered by category"""
    cat_filter = category.strip().lower() if category else None
    return {
        "status": "success",
        "count": len(memory_db.list_all_memories(cat_filter)),
        "memories": memory_db.list_all_memories(cat_filter)
    }

@app.post("/api/memory/search")
def search_memories_endpoint(req: MemorySearchRequest):
    """Search knowledge base using hybrid semantic + FTS5 with keyword fallback"""
    cat_filter = req.category.strip().lower() if req.category else None
    results = search_memories_semantic(req.query, category=cat_filter, limit=5)
    return {
        "status": "success",
        "query": req.query,
        "count": len(results),
        "results": results
    }

@app.delete("/api/memory/{target}")
def delete_memory_endpoint(target: str):
    """Delete a memory record by ID or key"""
    deleted = memory_db.delete_memory(target)
    return {
        "status": "success" if deleted else "not_found",
        "deleted": deleted,
        "target": target
    }

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting Sylphya LangGraph Backend on http://localhost:8000")
    print(f"🔧 Tools loaded: {[t.name for t in tools]}")
    reload_mode = "--reload" in sys.argv or os.environ.get("FRIDAY_RELOAD", "").lower() in ("true", "1")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload_mode)
