import os
import time
import ctypes
import subprocess
import psutil
from langchain_core.tools import tool

# Windows Virtual-Key Codes for Media & Volume
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3


def _send_vk(vk_code: int):
    """Send key down and key up events for a virtual key code."""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


@tool
def control_media_volume(action: str, steps: int = 3) -> str:
    """Control Windows volume and media playback.
    Actions supported:
    - 'volume_up' or 'up': increase system volume
    - 'volume_down' or 'down': decrease system volume
    - 'mute' or 'unmute': toggle audio mute
    - 'play_pause' or 'play' or 'pause': toggle media playback
    - 'next_track' or 'next': skip to next song/video
    - 'prev_track' or 'previous': return to previous song/video
    The steps parameter indicates how many ticks to raise/lower volume (default 3)."""
    action_clean = action.lower().strip()
    
    try:
        if "up" in action_clean or "louder" in action_clean:
            for _ in range(max(1, min(steps, 15))):
                _send_vk(VK_VOLUME_UP)
                time.sleep(0.02)
            return f"Turned volume up by {steps} steps, Sir."
            
        elif "down" in action_clean or "quieter" in action_clean or "lower" in action_clean:
            for _ in range(max(1, min(steps, 15))):
                _send_vk(VK_VOLUME_DOWN)
                time.sleep(0.02)
            return f"Turned volume down by {steps} steps, Sir."
            
        elif "mute" in action_clean:
            _send_vk(VK_VOLUME_MUTE)
            return "Toggled mute status, Sir."
            
        elif "play" in action_clean or "pause" in action_clean:
            _send_vk(VK_MEDIA_PLAY_PAUSE)
            return "Toggled media playback, Sir."
            
        elif "next" in action_clean:
            _send_vk(VK_MEDIA_NEXT_TRACK)
            return "Skipped to the next track, Sir."
            
        elif "prev" in action_clean or "back" in action_clean:
            _send_vk(VK_MEDIA_PREV_TRACK)
            return "Skipped to the previous track, Sir."
            
        else:
            return f"Unknown media action '{action}'. Options: volume_up, volume_down, mute, play_pause, next_track, prev_track."
    except Exception as e:
        return f"Failed to control media: {str(e)}"


@tool
def close_application(app_name: str) -> str:
    """Close or terminate a running application by name (e.g. 'notepad', 'chrome', 'spotify', 'calc', 'code', 'discord')."""
    target = app_name.lower().strip()
    # Map common friendly names to process names
    app_map = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "CalculatorApp.exe",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "spotify": "spotify.exe",
        "discord": "discord.exe",
        "code": "code.exe",
        "vscode": "code.exe",
        "visual studio code": "code.exe",
        "edge": "msedge.exe",
        "terminal": "WindowsTerminal.exe",
        "cmd": "cmd.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "paint": "mspaint.exe",
    }
    
    proc_target = app_map.get(target, target)
    if not proc_target.endswith(".exe"):
        proc_target_alt = proc_target + ".exe"
    else:
        proc_target_alt = proc_target

    closed_count = 0
    # Search psutil processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pname = proc.name().lower()
            if pname == proc_target.lower() or pname == proc_target_alt.lower() or target in pname:
                proc.terminate()
                closed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if closed_count > 0:
        return f"Successfully closed {app_name} ({closed_count} process instances terminated), Sir."
    else:
        # Fallback to taskkill
        try:
            kill_cmd = f"taskkill /f /im {proc_target_alt}"
            res = subprocess.run(kill_cmd, shell=True, capture_output=True, text=True, timeout=5)
            if "SUCCESS" in (res.stdout or ""):
                return f"Closed {app_name} via taskkill, Sir."
        except:
            pass
        return f"No active process matching '{app_name}' was found running, Sir."


@tool
def list_running_apps() -> str:
    """List prominent user applications currently running on your Windows PC."""
    try:
        # Filter for typical desktop applications
        common_apps = {
            "chrome.exe": "Google Chrome",
            "msedge.exe": "Microsoft Edge",
            "firefox.exe": "Firefox",
            "code.exe": "Visual Studio Code",
            "notepad.exe": "Notepad",
            "spotify.exe": "Spotify",
            "discord.exe": "Discord",
            "slack.exe": "Slack",
            "teams.exe": "Microsoft Teams",
            "calc.exe": "Calculator",
            "CalculatorApp.exe": "Calculator",
            "mspaint.exe": "Paint",
            "WindowsTerminal.exe": "Windows Terminal",
            "cmd.exe": "Command Prompt",
            "powershell.exe": "PowerShell",
            "explorer.exe": "File Explorer",
            "steam.exe": "Steam",
            "obs64.exe": "OBS Studio",
            "winword.exe": "Microsoft Word",
            "excel.exe": "Microsoft Excel"
        }
        
        found = set()
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.name()
                if name in common_apps:
                    found.add(common_apps[name])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if found:
            return "Active applications:\n" + "\n".join(f"- {app}" for app in sorted(found))
        else:
            return "No prominent third-party desktop applications detected currently running, Sir."
    except Exception as e:
        return f"Failed to list running apps: {str(e)}"


@tool
def manage_window(action: str, target: str = "") -> str:
    """Manage desktop windows.
    Actions supported:
    - 'show_desktop' or 'minimize_all': toggles show desktop (Win+D)
    - 'minimize': minimizes the current active window
    - 'maximize': maximizes the current active window
    - 'restore': restores the current window size
    - 'switch': switches to the next window (Alt+Tab)"""
    action_clean = action.lower().strip()
    
    try:
        import pyautogui
        
        if "desktop" in action_clean or "minimize_all" in action_clean:
            pyautogui.hotkey('win', 'd')
            return "Toggled desktop view (Win+D), Sir."
            
        elif "minimize" in action_clean:
            pyautogui.hotkey('win', 'down')
            return "Minimized the active window, Sir."
            
        elif "maximize" in action_clean:
            pyautogui.hotkey('win', 'up')
            return "Maximized the active window, Sir."
            
        elif "restore" in action_clean:
            pyautogui.hotkey('win', 'down')
            return "Restored window position, Sir."
            
        elif "switch" in action_clean or "alt_tab" in action_clean:
            pyautogui.hotkey('alt', 'tab')
            return "Switched active window (Alt+Tab), Sir."
            
        else:
            return f"Action '{action}' not recognized. Options: show_desktop, minimize, maximize, restore, switch."
    except Exception as e:
        return f"Window management failed: {str(e)}"


@tool
def open_settings(setting_name: str = "") -> str:
    """Open Windows Settings or a specific settings panel (e.g. 'sound', 'display', 'bluetooth', 'network', 'wifi', 'apps', 'battery', 'update')."""
    try:
        settings_map = {
            "sound": "ms-settings:sound",
            "audio": "ms-settings:sound",
            "volume": "ms-settings:sound",
            "display": "ms-settings:display",
            "screen": "ms-settings:display",
            "bluetooth": "ms-settings:bluetooth",
            "network": "ms-settings:network",
            "wifi": "ms-settings:network-wifi",
            "apps": "ms-settings:appsfeatures",
            "battery": "ms-settings:batterysaver",
            "power": "ms-settings:powersleep",
            "update": "ms-settings:windowsupdate",
            "storage": "ms-settings:storagesense",
            "notifications": "ms-settings:notifications",
        }
        
        uri = settings_map.get(setting_name.lower().strip(), "ms-settings:")
        subprocess.Popen(f"start {uri}", shell=True)
        return f"Opened Windows Settings for '{setting_name or 'Main Settings'}', Sir."
    except Exception as e:
        return f"Failed to open Settings: {str(e)}"
