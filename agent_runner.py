import os
import re
import json
import asyncio
from typing import List, Dict, Any, Optional, Set
from dotenv import load_dotenv

load_dotenv(override=True)


# =========================================================================
# TOOL PRUNING  — Send only relevant tools instead of all 33 every turn
# =========================================================================

# Tools that are always injected regardless of message content
_ALWAYS_ON_TOOLS: Set[str] = {
    "web_search",
    "get_current_time",
    "get_weather",
    "get_system_status",
    "remember_fact",
}

# Keyword → extra tool names to inject when the keyword appears in the user message
_KEYWORD_TOOL_MAP: Dict[str, Set[str]] = {
    # File operations
    "file": {"read_file", "list_files"},
    "read":  {"read_file"},
    "write": {"create_or_write_file"},
    "folder": {"list_files", "create_folder"},
    "directory": {"list_files", "create_folder"},
    # App / window control
    "open":   {"open_app", "open_website"},
    "launch": {"open_app"},
    "close":  {"close_app"},
    "app":    {"open_app", "close_app", "list_running_apps"},
    "window": {"get_frontmost_app", "list_running_apps"},
    # Music / media
    "music": {"play_music", "control_music", "get_volume"},
    "play":  {"play_music", "open_app"},
    "pause": {"control_music"},
    "song":  {"play_music"},
    "spotify": {"play_music", "control_music"},
    # Volume
    "volume": {"set_volume", "get_volume"},
    "mute":   {"set_volume"},
    # Screenshot
    "screenshot": {"take_screenshot"},
    "screen": {"take_screenshot", "get_frontmost_app"},
    # Clipboard
    "clipboard": {"get_clipboard_text", "set_clipboard_text"},
    "copy": {"get_clipboard_text"},
    "paste": {"set_clipboard_text"},
    # Notes
    "note": {"open_notes_and_write", "read_notes"},
    "notes": {"open_notes_and_write", "read_notes"},
    "write": {"open_notes_and_write", "create_or_write_file"},
    # Shortcuts / automation
    "shortcut": {"run_shortcut"},
    "automate": {"run_shortcut"},
    # Memory
    "remember": {"remember_information", "recall_memory"},
    "forget": {"forget_memory"},
    "memory": {"recall_memory", "list_memories"},
    # Search / web
    "search": {"web_search"},
    "web": {"web_search", "open_url"},
    # System
    "lock": {"lock_screen"},
    "sleep": {"sleep_mac"},
    "battery": {"get_battery"},
    "trash": {"empty_trash"},
    "notification": {"send_notification"},
    "notify": {"send_notification"},
}


def _prune_tools(tools: List[Any], last_user_message: str = "") -> List[Any]:
    """Return a reduced tool list based on always-on tools + keyword matching."""
    if not tools:
        return tools

    tool_name_map = {t.name: t for t in tools}
    selected_names: Set[str] = set(_ALWAYS_ON_TOOLS)

    # Add keyword-matched tools
    words = set(re.findall(r"\w+", last_user_message.lower()))
    for kw, extra_tools in _KEYWORD_TOOL_MAP.items():
        if kw in words:
            selected_names.update(extra_tools)

    # Collect matching tools (preserve original order)
    pruned = [t for t in tools if t.name in selected_names]

    # Safety: if pruning leaves us with nothing useful, return full list
    if not pruned:
        return tools

    removed = len(tools) - len(pruned)
    if removed > 0:
        print(f"[TOOL-PRUNE] {len(pruned)}/{len(tools)} tools selected ({removed} pruned) for: \"{last_user_message[:60]}\"")
    return pruned


class ChatMessage:
    """Lightweight message representation replacing LangChain message classes."""
    def __init__(
        self,
        role: str,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None
    ):
        self.role = role
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.tool_call_id = tool_call_id
        self.name = name

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    def __repr__(self):
        return f"ChatMessage(role={self.role!r}, content={self.content[:40]!r}, tool_calls={len(self.tool_calls)})"


class SystemMessage(ChatMessage):
    def __init__(self, content: str):
        super().__init__(role="system", content=content)


class HumanMessage(ChatMessage):
    def __init__(self, content: str):
        super().__init__(role="user", content=content)


class AIMessage(ChatMessage):
    def __init__(self, content: str = "", tool_calls: Optional[List[Dict[str, Any]]] = None):
        super().__init__(role="assistant", content=content, tool_calls=tool_calls)


def normalize_messages(messages: List[Any]) -> List[ChatMessage]:
    normalized = []
    for m in messages:
        if isinstance(m, ChatMessage):
            normalized.append(m)
        elif isinstance(m, dict):
            normalized.append(ChatMessage(
                role=m.get("role", "user"),
                content=m.get("content", ""),
                tool_calls=m.get("tool_calls"),
                tool_call_id=m.get("tool_call_id"),
                name=m.get("name")
            ))
        elif hasattr(m, "content"):
            role = "user"
            cls_name = m.__class__.__name__.lower()
            if "system" in cls_name:
                role = "system"
            elif "ai" in cls_name or "assistant" in cls_name:
                role = "assistant"
            elif "human" in cls_name or "user" in cls_name:
                role = "user"
            normalized.append(ChatMessage(role=role, content=str(m.content)))
        else:
            normalized.append(ChatMessage(role="user", content=str(m)))
    return normalized


# =========================================================================
# PROVIDER RUNNERS (Native SDKs, no LangChain)
# =========================================================================

def _run_mistral(
    messages: List[ChatMessage],
    model_name: str,
    tools: List[Any],
    api_key: str
) -> List[ChatMessage]:
    from mistralai.client import Mistral

    client = Mistral(api_key=api_key)
    # Prune tools based on the last user message
    last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
    effective_tools = _prune_tools(tools, last_user_msg)
    tool_map = {t.name: t for t in tools}  # keep full map for execution
    tool_schemas = [t.openai_tool for t in effective_tools] if effective_tools else None

    history = [m.to_dict() for m in messages]
    result_messages: List[ChatMessage] = []

    for _ in range(5):
        resp = client.chat.complete(
            model=model_name,
            messages=history,
            tools=tool_schemas,
            temperature=0.7,
            max_tokens=1024
        )
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            tc_data = []
            for tc in tool_calls:
                tc_data.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                })
            ai_msg = AIMessage(content=msg.content or "", tool_calls=tc_data)
            result_messages.append(ai_msg)

            # Record in history for next round
            tc_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)
                    }
                }
                for tc in tool_calls
            ]
            history.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tc_dicts
            })

            # Execute tools
            for tc in tool_calls:
                t_name = tc.function.name
                t_args_str = tc.function.arguments
                try:
                    args = json.loads(t_args_str) if isinstance(t_args_str, str) else (t_args_str or {})
                except Exception:
                    args = {}

                tool_fn = tool_map.get(t_name)
                if tool_fn:
                    try:
                        res = tool_fn.invoke(args)
                    except Exception as err:
                        res = f"Tool execution error: {err}"
                else:
                    res = f"Tool {t_name} not found"

                res_str = str(res)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": t_name,
                    "content": res_str
                })
                result_messages.append(ChatMessage(role="tool", content=res_str, tool_call_id=tc.id, name=t_name))
        else:
            final_ai = AIMessage(content=msg.content or "")
            result_messages.append(final_ai)
            break

    return result_messages


def _run_gemini(
    messages: List[ChatMessage],
    model_name: str,
    tools: List[Any],
    api_key: str
) -> List[ChatMessage]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    tool_map = {t.name: t for t in tools}  # full map for execution
    # Prune tools based on the last user message
    last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
    effective_tools = _prune_tools(tools, last_user_msg)

    # Extract system instruction
    sys_instruction = None
    contents = []
    for m in messages:
        if m.role == "system":
            sys_instruction = m.content
        elif m.role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m.content)]))
        elif m.role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=m.content)]))

    tool_callables = [t.fn for t in effective_tools] if effective_tools else None
    config = types.GenerateContentConfig(
        system_instruction=sys_instruction,
        temperature=0.7,
        max_output_tokens=400,
        tools=tool_callables
    )

    result_messages: List[ChatMessage] = []

    for _ in range(5):
        resp = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )

        # Check for function calls
        function_calls = resp.function_calls
        if function_calls:
            tc_data = []
            for fc in function_calls:
                tc_data.append({
                    "id": getattr(fc, "id", fc.name),
                    "name": fc.name,
                    "args": dict(fc.args) if hasattr(fc, "args") else {}
                })
            ai_msg = AIMessage(content=resp.text or "", tool_calls=tc_data)
            result_messages.append(ai_msg)

            # Append model turn with function calls
            if resp.candidates and resp.candidates[0].content:
                contents.append(resp.candidates[0].content)

            # Execute function calls and add function responses
            fn_response_parts = []
            for fc in function_calls:
                t_name = fc.name
                t_args = dict(fc.args) if hasattr(fc, "args") else {}
                tool_fn = tool_map.get(t_name)
                if tool_fn:
                    try:
                        res = tool_fn.invoke(t_args)
                    except Exception as err:
                        res = f"Error: {err}"
                else:
                    res = f"Tool {t_name} not found"

                res_str = str(res)
                result_messages.append(ChatMessage(role="tool", content=res_str, name=t_name))
                fn_response_parts.append(types.Part.from_function_response(
                    name=t_name,
                    response={"result": res_str}
                ))

            contents.append(types.Content(role="user", parts=fn_response_parts))
        else:
            final_ai = AIMessage(content=resp.text or "")
            result_messages.append(final_ai)
            break

    return result_messages


def _run_groq(
    messages: List[ChatMessage],
    model_name: str,
    tools: List[Any],
    api_key: str
) -> List[ChatMessage]:
    from groq import Groq

    client = Groq(api_key=api_key)
    tool_map = {t.name: t for t in tools}  # full map for execution
    # Prune tools based on the last user message
    last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
    effective_tools = _prune_tools(tools, last_user_msg)
    tool_schemas = [t.openai_tool for t in effective_tools] if effective_tools else None

    history = [m.to_dict() for m in messages]
    result_messages: List[ChatMessage] = []

    for _ in range(5):
        resp = client.chat.completions.create(
            model=model_name or "qwen/qwen3.8-27b",
            messages=history,
            tools=tool_schemas,
            temperature=0.7,
            max_tokens=1024
        )
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            tc_data = []
            for tc in tool_calls:
                tc_data.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                })
            ai_msg = AIMessage(content=msg.content or "", tool_calls=tc_data)
            result_messages.append(ai_msg)

            history.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)
                        }
                    }
                    for tc in tool_calls
                ]
            })

            for tc in tool_calls:
                t_name = tc.function.name
                t_args_str = tc.function.arguments
                try:
                    args = json.loads(t_args_str) if isinstance(t_args_str, str) else (t_args_str or {})
                except Exception:
                    args = {}

                tool_fn = tool_map.get(t_name)
                if tool_fn:
                    try:
                        res = tool_fn.invoke(args)
                    except Exception as err:
                        res = f"Tool execution error: {err}"
                else:
                    res = f"Tool {t_name} not found"

                res_str = str(res)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": t_name,
                    "content": res_str
                })
                result_messages.append(ChatMessage(role="tool", content=res_str, tool_call_id=tc.id, name=t_name))
        else:
            final_ai = AIMessage(content=msg.content or "")
            result_messages.append(final_ai)
            break

    return result_messages


def _run_hermes(
    messages: List[ChatMessage],
    model_name: str,
    tools: List[Any],
    api_key: str,
    api_base: Optional[str] = None
) -> List[ChatMessage]:
    """Runs a turn against Hermes local OpenAI-compatible API server (default http://127.0.0.1:8642)."""
    try:
        import httpx
        has_httpx = True
    except ImportError:
        has_httpx = False
        import requests

    base_url = (api_base or os.getenv("HERMES_API_BASE", "http://127.0.0.1:8642/v1")).rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    history = [m.to_dict() for m in messages]

    # Prune tools based on the last user message
    last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
    effective_tools = _prune_tools(tools, last_user_msg) if tools else []
    tool_map = {t.name: t for t in tools} if tools else {}
    tool_schemas = [t.openai_tool for t in effective_tools] if effective_tools else None

    result_messages: List[ChatMessage] = []

    resolved_model = model_name or os.getenv("HERMES_MODEL", "hermes-agent")
    payload: Dict[str, Any] = {
        "model": resolved_model,
        "messages": history,
        "temperature": 0.7,
        "stream": False
    }

    # If calling a model other than hermes-agent, provide client-side tool schemas
    if tool_schemas and resolved_model != "hermes-agent":
        payload["tools"] = tool_schemas

    if has_httpx:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    else:
        resp = requests.post(url, headers=headers, json=payload, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls")

    if tool_calls:
        tc_data = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            tc_data.append({
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "args": args
            })
        ai_msg = AIMessage(content=content, tool_calls=tc_data)
        result_messages.append(ai_msg)

        history.append({
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc.get("id"),
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name"),
                        "arguments": tc.get("function", {}).get("arguments") if isinstance(tc.get("function", {}).get("arguments"), str) else json.dumps(tc.get("function", {}).get("arguments", {}))
                    }
                }
                for tc in tool_calls
            ]
        })

        for tc in tool_calls:
            fn = tc.get("function", {})
            t_name = fn.get("name", "")
            args_str = fn.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
            except Exception:
                args = {}

            tool_fn = tool_map.get(t_name)
            if tool_fn:
                try:
                    res = tool_fn.invoke(args)
                except Exception as err:
                    res = f"Tool execution error: {err}"
            else:
                res = f"Tool {t_name} not found"

            res_str = str(res)
            history.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": t_name,
                "content": res_str
            })
            result_messages.append(ChatMessage(role="tool", content=res_str, tool_call_id=tc.get("id"), name=t_name))
    else:
        final_ai = AIMessage(content=content)
        result_messages.append(final_ai)

    return result_messages


def execute_agent_turn(
    messages: List[Any],
    provider: str,
    model_name: str,
    tools: List[Any]
) -> Dict[str, Any]:
    """
    Executes a single conversational agent turn with tools.
    Returns: {"messages": [ChatMessage, ...]}
    """
    norm_messages = normalize_messages(messages)

    if provider == "hermes":
        api_key = os.getenv("HERMES_API_KEY", "")
        api_base = os.getenv("HERMES_API_BASE", "http://127.0.0.1:8642/v1")
        out_messages = _run_hermes(norm_messages, model_name, tools, api_key, api_base)

    elif provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is not configured in environment.")
        out_messages = _run_mistral(norm_messages, model_name, tools, api_key)

    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured in environment.")
        out_messages = _run_gemini(norm_messages, model_name, tools, api_key)

    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured in environment.")
        out_messages = _run_groq(norm_messages, model_name, tools, api_key)

    else:
        raise ValueError(f"Unsupported model provider: {provider}")

    return {"messages": out_messages}

