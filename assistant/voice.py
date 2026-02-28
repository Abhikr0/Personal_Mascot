import os
import asyncio
import sounddevice as sd
import numpy as np
from scipy.io import wavfile
import edge_tts
import pygame
import tempfile

class VoiceHandler:
    def __init__(self, voice="en-US-GuyNeural"):
        self.voice = voice
        pygame.mixer.init()

    def record_audio(self, silence_threshold=60, silence_duration=1.5, fs=16000):
        """Records audio until silence is detected for silence_duration."""
        recording = []
        state = {'silent_chunks': 0, 'total_samples': 0, 'has_started': False, 'max_peak': 0, 'peaks': []}
        max_silent_chunks = int(silence_duration / 0.1)
        
        def callback(indata, frames, time, status):
            # Calculate RMS (Root Mean Square) for volume
            rms = np.sqrt(np.mean(indata.astype(float)**2))
            
            # Track peak amplitude for clap detection
            current_peak = np.max(np.abs(indata))
            if current_peak > state['max_peak']:
                state['max_peak'] = current_peak
            
            # Collect significant peaks for analysis
            if current_peak > 15000: # Threshold for considering it a "pulse"
                state['peaks'].append(current_peak)
            else:
                state['peaks'].append(0) # Pad with 0 to keep time alignment

            # Use a conservative threshold for starting (auto-detect speech)
            if not state['has_started']:
                if rms > silence_threshold * 1.5 or current_peak > 15000:
                    state['has_started'] = True
            
            if state['has_started']:
                if rms < silence_threshold and current_peak < 10000:
                    state['silent_chunks'] += 1
                else:
                    state['silent_chunks'] = 0
                recording.append(indata.copy())
            
            state['total_samples'] += frames

        # Increased blocksize to ensure stable RMS calculation
        with sd.InputStream(samplerate=fs, channels=1, callback=callback, dtype='int16', blocksize=int(fs * 0.1)):
            while True:
                sd.sleep(100)
                # Stop if silence threshold met AFTER speech has started
                if state['has_started'] and state['silent_chunks'] >= max_silent_chunks:
                    break
                # Fail-safe: if recording > 60s of actual speech, stop
                if state['has_started'] and len(recording) * 0.1 > 60:
                    break
        
        if not recording:
            return None, state['max_peak'], 0
            
        audio_data = np.concatenate(recording, axis=0)
        
        # Analyze peaks to count claps
        claps = 0
        in_clap = False
        # Each index in state['peaks'] is 0.1 seconds (blocksize=0.1s)
        for p in state['peaks']:
            if p > 18000: # Slightly lower than the main threshold to catch sharp pulses
                if not in_clap:
                    claps += 1
                    in_clap = True
            else:
                in_clap = False

        temp_dir = tempfile.gettempdir()
        temp_audio = os.path.join(temp_dir, "input_audio.wav")
        wavfile.write(temp_audio, fs, audio_data)
        return temp_audio, state['max_peak'], claps

    async def _generate_speech(self, text, output_file):
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_file)

    def _play_audio(self, file_path):
        """Helper to play audio file and wait until done."""
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Playback error: {e}")

    def speak(self, text):
        """Converts text to speech and plays it (blocking)."""
        if not text or not text.strip(): return
        temp_audio = os.path.join(tempfile.gettempdir(), f"voice_{os.urandom(4).hex()}.mp3")
        try:
            asyncio.run(self._generate_speech(text, temp_audio))
            self._play_audio(temp_audio)
        finally:
            if os.path.exists(temp_audio):
                try: os.remove(temp_audio)
                except: pass

    def speak_stream(self, token_generator):
        """Processes a stream of tokens, speaking sentences as they are completed."""
        import threading
        import queue
        import re

        audio_queue = queue.Queue()
        stop_event = threading.Event()

        def playback_worker():
            while not stop_event.is_set() or not audio_queue.empty():
                try:
                    audio_file = audio_queue.get(timeout=0.1)
                    self._play_audio(audio_file)
                    try: os.remove(audio_file)
                    except: pass
                    audio_queue.task_done()
                except queue.Empty:
                    continue

        playback_thread = threading.Thread(target=playback_worker, daemon=True)
        playback_thread.start()

        buffer = ""
        sentence_endings = re.compile(r'(?<=[.!?]) +')

        try:
            for token in token_generator:
                if token is None: continue
                print(token, end="", flush=True) # UI feedback
                buffer += token
                
                # Check for sentence completion
                # We split by sentence endings followed by space, or just look for punctuation
                sentences = re.split(r'(?<=[.!?])\s+', buffer)
                if len(sentences) > 1:
                    # All but the last one are complete
                    for s in sentences[:-1]:
                        s = s.strip()
                        if s:
                            temp_audio = os.path.join(tempfile.gettempdir(), f"stream_{os.urandom(4).hex()}.mp3")
                            asyncio.run(self._generate_speech(s, temp_audio))
                            audio_queue.put(temp_audio)
                    buffer = sentences[-1]
            
            # Final buffer piece
            if buffer.strip():
                temp_audio = os.path.join(tempfile.gettempdir(), f"stream_{os.urandom(4).hex()}.mp3")
                asyncio.run(self._generate_speech(buffer.strip(), temp_audio))
                audio_queue.put(temp_audio)

        finally:
            audio_queue.join()
            stop_event.set()
            playback_thread.join()

if __name__ == "__main__":
    # Test recording and speaking
    vh = VoiceHandler()
    vh.speak("Testing dynamic recording. Speak now, and I will stop when you are silent.")
    audio_path = vh.record_audio()
    print(f"Audio saved to {audio_path}")
    vh.speak("I recorded your voice. Now I will play it back for you.")
    
    # Playback test
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.mixer.music.unload()
