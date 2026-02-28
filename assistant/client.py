import os
import re
import json
import inspect
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class GroqClient:
    def __init__(self, model="llama-3.1-8b-instant"):
        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = model

    def clean_response(self, text):
        """Removes hallucinated tool tags like <function=...> from the text."""
        if text is None:
            return ""
        
        patterns = [
            r"<function.*?>.*?(</function>)?",
            r"<tool.*?>.*?(</tool>)?",
            r"<call.*?>.*?(</call>)?",
            r"<.*?tool.*?>",
            r"<.*?function.*?>",
            r"\[function=.*?\]",
            r"\[tool=.*?\]"
        ]
        cleaned_text = str(text)
        for pattern in patterns:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        cleaned_text = re.sub(r"function=\w+\{.*?\}", "", cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        return cleaned_text.strip()

    def handle_local_trigger(self, prompt):
        p = prompt.lower().strip()
        from assistant.tools import open_youtube, web_search, ui_interact
        if "youtube" in p:
            q = p.replace("search youtube for", "").replace("open youtube", "").replace("search for", "").replace("on youtube", "").strip()
            open_youtube(q if q else ""); return f"Opening YouTube. Don't get distracted, Sir."
        if p.startswith("search for ") or p.startswith("google "):
            q = p.replace("search for ", "").replace("google ", "").strip()
            web_search(q); return f"Finding {q}. You're lost without me, Boss."
        if "minimize" in p and "all" in p:
            ui_interact("click", x=0, y=1080); return "Minimizing everything. Just us now, Sir."
        return None

    def get_response(self, prompt, system_prompt=None, tools=None):
        trig = self.handle_local_trigger(prompt)
        if trig: return trig

        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            from assistant.tools import TOOL_DEFINITIONS, AVAILABLE_TOOLS
            comp = self.client.chat.completions.create(
                model=self.model, messages=messages, 
                tools=TOOL_DEFINITIONS if tools is None else tools, tool_choice="auto"
            )
            msg = comp.choices[0].message
            tool_calls, content = msg.tool_calls, msg.content

            if tool_calls:
                messages.append(msg)
                for tc in tool_calls:
                    func = AVAILABLE_TOOLS.get(tc.function.name)
                    if func:
                        try:
                            args = json.loads(tc.function.arguments)
                            sig = inspect.signature(func)
                            res = func(**{k: v for k, v in args.items() if k in sig.parameters})
                        except Exception as e: res = f"Error: {e}"
                        messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": str(res)})
                
                if any(tc.function.name in ["open_youtube", "web_search", "ui_interact"] for tc in tool_calls):
                    return "Task completed, Sir."

                second = self.client.chat.completions.create(model=self.model, messages=messages)
                return self.clean_response(second.choices[0].message.content)

            return self.clean_response(content)
        except Exception as e: return f"Error: {str(e)}"

    def get_response_stream(self, prompt, system_prompt=None):
        """Streams the response from Groq for faster perceived speed."""
        trig = self.handle_local_trigger(prompt)
        if trig:
            yield trig
            return

        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # We skip tool use for streaming to keep it simple and ultra-fast for conversations
            # If the user wants tools, they usually don't mind a small delay for the tool to run.
            # However, for 'voice faster', we prioritize direct conversational speed.
            comp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            
            for chunk in comp:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error: {str(e)}"

    def transcribe_audio(self, audio_file_path):
        """Transcribes audio using Groq Whisper API."""
        try:
            with open(audio_file_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(os.path.basename(audio_file_path), file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="text",
                    language="en"
                )
            return transcription
        except Exception as e:
            return f"Transcription Error: {str(e)}"
