from assistant.client import GroqClient
from assistant.voice import VoiceHandler
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import os

console = Console()

def main():
    try:
        client = GroqClient()
        model_info = "llama-3.1-8b-instant"
    except Exception as e:
        console.print(f"[bold red]Error initializing AI client:[/bold red] {e}")
        return

    system_prompt = "Elegant, playfully teasing secretary for 'Sir'. Use tools ONLY when truly necessary. ONE tool at a time. NO XML tags in text. Be concise but charmingly flirtatious."
    voice_handler = VoiceHandler(voice="en-GB-SoniaNeural")
    
    console.print(Panel(
        f"[bold cyan]Groq Devoted Secretary Ready[/bold cyan]\n"
        f"[italic white]Using Model: {model_info}[/italic white]\n"
        "[bold yellow]I'm listening for your command, Sir...[/bold yellow]", 
        title="Welcome", 
        expand=False
    ))

    # Initial greeting
    voice_handler.speak("Hello Sir. I am ready and waiting. How may I be of service to you today?")

    is_awake = True

    while True:
        try:
            if not is_awake:
                console.print("\n[dim white]Secretary is sleeping... (Say 'Wake up' or Clap!)[/dim white]")
            else:
                console.print("\n[bold blue]Listening...[/bold blue]")
            
            audio_path, peak, claps = voice_handler.record_audio()
            
            # Double clap detection
            if not is_awake and claps == 2:
                is_awake = True
                voice_handler.speak("I heard a double clap, Sir! I'm here. How may I help you?")
                console.print("[bold cyan]Assistant woke up from a double clap![/bold cyan]")
                continue

            if not audio_path:
                continue

            user_input = client.transcribe_audio(audio_path)
            
            # Remove temp file
            try: os.remove(audio_path)
            except: pass

            if not user_input or not str(user_input).strip():
                continue

            # Robust cleaning: remove punctuation for better matching
            import string
            clean_input = str(user_input).strip().lower().translate(str.maketrans('', '', string.punctuation)).strip()

            # Skip if input is empty after cleaning (e.g., just punctuation like ".")
            if not clean_input:
                continue

            # Debug logging during sleep
            if not is_awake:
                console.print(f"[dim yellow]Sleep-mode heard: '{clean_input}'[/dim yellow]")
                
                # Filter out hallucinations even during sleep
                hallucinations = ["thank you", "thanks for watching", "thanks", "you", "watch", "subscribe"]
                if clean_input in hallucinations:
                    continue
                    
                wake_words = ["awake", "arise", "waiki waiki", "wake up", "hi", "hello assistant", "secretary"]
                if any(wake in clean_input for wake in wake_words):
                    is_awake = True
                    voice_handler.speak("I'm here, Sir. What can I do for you?")
                    console.print("[bold cyan]Assistant is now awake![/bold cyan]")
                continue

            # Filter out common Whisper hallucinations from silence/background noise
            hallucinations = ["thank you", "thanks for watching", "thanks", "you", "watch", "subscribe"]
            if clean_input in hallucinations:
                console.print(f"[dim yellow]Filtered Whisper artifact: '{user_input}'[/dim yellow]")
                continue

            console.print(f"[bold green]You:[/bold green] {user_input}")

            # Exit trigger
            if any(quit_word in clean_input for quit_word in ["goodbye", "exit", "quit", "goodbye assistant"]):
                voice_handler.speak("Of course, Sir. I'll be here if you need me again. Have a wonderful day.")
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            # Sleep/Pause trigger
            if any(p in clean_input for p in ["sleep", "pause", "that's all for now"]):
                is_awake = False
                voice_handler.speak("I'll take a nap then, Sir. Just call me when you need me.")
                continue

            with console.status("[bold blue]Thinking...", spinner="dots"):
                token_generator = client.get_response_stream(user_input, system_prompt=system_prompt)
            
            if token_generator:
                console.print("[bold cyan]Secretary:[/bold cyan] ", end="")
                voice_handler.speak_stream(token_generator)
                print()
            else:
                console.print("[dim white](Assistant provided no response)[/dim white]")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            break

if __name__ == "__main__":
    main()
