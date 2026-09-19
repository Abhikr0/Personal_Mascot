import time
import pyautogui
from langchain_core.tools import tool

# Set PyAutoGUI failsafe and pause
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


@tool
def get_mouse_position() -> str:
    """Get the current mouse cursor (x, y) coordinates and total screen resolution."""
    try:
        x, y = pyautogui.position()
        w, h = pyautogui.size()
        return f"Mouse is at ({x}, {y}) on a {w}x{h} display."
    except Exception as e:
        return f"Could not get mouse position: {str(e)}"


@tool
def mouse_move(x: int, y: int, duration: float = 0.3) -> str:
    """Move the mouse cursor smoothly to specific (x, y) screen coordinates."""
    try:
        w, h = pyautogui.size()
        target_x = max(0, min(x, w - 1))
        target_y = max(0, min(y, h - 1))
        pyautogui.moveTo(target_x, target_y, duration=max(0.1, duration))
        return f"Moved mouse to ({target_x}, {target_y}), Sir."
    except Exception as e:
        return f"Failed to move mouse: {str(e)}"


@tool
def mouse_click(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
    """Click the mouse button.
    - x, y: optional screen coordinates. If not specified, clicks at current cursor position.
    - button: 'left', 'right', or 'middle'.
    - clicks: 1 for single click, 2 for double click."""
    try:
        btn = button.lower().strip()
        if btn not in ["left", "right", "middle"]:
            btn = "left"
            
        if x is not None and y is not None:
            w, h = pyautogui.size()
            target_x = max(0, min(x, w - 1))
            target_y = max(0, min(y, h - 1))
            pyautogui.click(x=target_x, y=target_y, clicks=clicks, button=btn)
            return f"Clicked {btn} button {clicks} time(s) at ({target_x}, {target_y}), Sir."
        else:
            pyautogui.click(clicks=clicks, button=btn)
            curr_x, curr_y = pyautogui.position()
            return f"Clicked {btn} button {clicks} time(s) at current cursor position ({curr_x}, {curr_y}), Sir."
    except Exception as e:
        return f"Failed to click mouse: {str(e)}"


@tool
def keyboard_type(text: str, press_enter: bool = False) -> str:
    """Type a string of text using the keyboard into whatever window/field is currently focused.
    Set press_enter to True if you want to hit Enter immediately after typing."""
    try:
        pyautogui.write(text, interval=0.015)
        if press_enter:
            time.sleep(0.05)
            pyautogui.press("enter")
        return f"Typed: \"{text[:60]}{'...' if len(text) > 60 else ''}\" {'[+ Enter]' if press_enter else ''}, Sir."
    except Exception as e:
        return f"Failed to type text: {str(e)}"


@tool
def keyboard_hotkey(keys: str) -> str:
    """Press a keyboard shortcut or individual key.
    Examples of keys:
    - 'ctrl,c' (copy)
    - 'ctrl,v' (paste)
    - 'ctrl,z' (undo)
    - 'ctrl,a' (select all)
    - 'alt,f4' (close active window)
    - 'win,d' (show desktop)
    - 'enter' (press Enter)
    - 'escape' (press Esc)
    - 'backspace' (press Backspace)
    - 'tab' (press Tab)"""
    try:
        key_list = [k.strip().lower() for k in keys.split(",") if k.strip()]
        if not key_list:
            return "No valid keys provided to press."
            
        if len(key_list) == 1:
            pyautogui.press(key_list[0])
            return f"Pressed key '{key_list[0]}', Sir."
        else:
            pyautogui.hotkey(*key_list)
            return f"Pressed shortcut '{' + '.join(key_list)}', Sir."
    except Exception as e:
        return f"Failed to send shortcut '{keys}': {str(e)}"


@tool
def scroll_screen(amount: int = -300) -> str:
    """Scroll the page or active window.
    Use negative values to scroll down (e.g. -300) and positive values to scroll up (e.g. 300)."""
    try:
        pyautogui.scroll(amount)
        direction = "down" if amount < 0 else "up"
        return f"Scrolled {direction} by {abs(amount)} units, Sir."
    except Exception as e:
        return f"Failed to scroll: {str(e)}"
