"""
tools/system_tools.py — Siri-like OS integration tools for Friday 2.0.
Provides active window detection, desktop notifications, and clipboard access.
"""
import sys
import subprocess
from langchain_core.tools import tool


@tool
def get_active_window() -> str:
    """Get the title and process name of the currently active (foreground) window on Windows.
    Use this to understand what app the user is currently working in."""
    try:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value

        # Get process name from window handle
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            import psutil
            proc = psutil.Process(pid.value)
            process_name = proc.name()
        except Exception:
            process_name = "unknown"

        return f"Active window: '{title}' (process: {process_name})"
    except Exception as e:
        return f"Could not get active window: {e}"


@tool
def send_desktop_notification(title: str, message: str) -> str:
    """Send a Windows desktop notification (toast notification) to the user.
    Use this to proactively alert the user about reminders, completed tasks, or important information.
    Args:
        title: The notification title (keep short, under 50 chars)
        message: The notification body text (under 200 chars)
    """
    try:
        # Try Windows 10+ toast via PowerShell (no extra packages)
        ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$toastXml = [xml] $template.GetXml()
$toastXml.GetElementsByTagName('text')[0].AppendChild($toastXml.CreateTextNode('{title.replace("'", "")}')) | Out-Null
$toastXml.GetElementsByTagName('text')[1].AppendChild($toastXml.CreateTextNode('{message.replace("'", "")}')) | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($toastXml.OuterXml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Sylphya').Show($toast)
"""
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, timeout=5
        )
        return f"Desktop notification sent: '{title}' — {message}"
    except Exception as e:
        return f"Notification failed: {e}"


@tool
def get_clipboard_text() -> str:
    """Read the current text content of the Windows clipboard.
    Use this when the user says 'what did I copy' or 'read my clipboard'."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5
        )
        text = result.stdout.strip()
        if not text:
            return "Clipboard is empty or contains non-text content."
        return f"Clipboard content: {text[:500]}"
    except Exception as e:
        return f"Could not read clipboard: {e}"


@tool
def set_clipboard_text(text: str) -> str:
    """Write text to the Windows clipboard.
    Use this when the user asks to copy something, or after generating content they want to paste.
    Args:
        text: The text to write to clipboard
    """
    try:
        ps_cmd = f"Set-Clipboard -Value '{text.replace(chr(39), '')}'"
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, timeout=5
        )
        return f"Copied to clipboard: {text[:100]}{'...' if len(text) > 100 else ''}"
    except Exception as e:
        return f"Could not set clipboard: {e}"
