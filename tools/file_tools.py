import os
import sys
import shutil
from langchain_core.tools import tool

# Determine base directory
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_path(path_str: str) -> str:
    """Expand user shortcuts like 'Desktop', 'Downloads', '~' into full absolute paths."""
    user_home = os.path.expanduser("~")
    lower = path_str.lower().strip()
    
    shortcuts = {
        "desktop": os.path.join(user_home, "Desktop"),
        "downloads": os.path.join(user_home, "Downloads"),
        "documents": os.path.join(user_home, "Documents"),
        "pictures": os.path.join(user_home, "Pictures"),
        "music": os.path.join(user_home, "Music"),
        "videos": os.path.join(user_home, "Videos"),
        "project": base_dir,
        "workspace": base_dir,
    }
    
    # Check exact shortcut
    if lower in shortcuts:
        return shortcuts[lower]
        
    # Check leading shortcut (e.g. "Desktop/my_folder")
    for key, folder in shortcuts.items():
        if lower.startswith(key + "/") or lower.startswith(key + "\\"):
            remainder = path_str[len(key) + 1:]
            return os.path.join(folder, remainder)
            
    # Standard resolution
    expanded = os.path.expanduser(path_str)
    if not os.path.isabs(expanded):
        return os.path.abspath(os.path.join(base_dir, expanded))
    return os.path.abspath(expanded)


@tool
def create_folder(folder_path: str) -> str:
    """Create a new folder on Windows.
    Accepts paths like 'Desktop/MyNewProject', 'Downloads/Data', or full paths."""
    try:
        target = _resolve_path(folder_path)
        os.makedirs(target, exist_ok=True)
        return f"Successfully created directory: {target}, Sir."
    except Exception as e:
        return f"Failed to create directory: {str(e)}"


@tool
def create_or_write_file(file_path: str, content: str, mode: str = "write") -> str:
    """Create or write code/text to a file on your PC.
    - file_path: Path to the file (e.g. 'Desktop/test.py', 'notes.txt', 'project/main.py').
    - content: The text or code to write into the file.
    - mode: 'write' to overwrite/create, or 'append' to add to existing file."""
    try:
        target = _resolve_path(file_path)
        parent_dir = os.path.dirname(target)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        file_mode = "a" if mode.lower() == "append" else "w"
        with open(target, file_mode, encoding="utf-8") as f:
            f.write(content)
            
        action_verb = "Appended to" if file_mode == "a" else "Created/Written"
        return f"{action_verb} file successfully at {target} ({len(content)} characters), Sir."
    except Exception as e:
        return f"Failed to write file: {str(e)}"


@tool
def open_file(file_path: str) -> str:
    """Open any file, document, or folder on your PC using its default Windows application (e.g. VS Code, Word, media player, or File Explorer)."""
    try:
        target = _resolve_path(file_path)
        if not os.path.exists(target):
            return f"File or folder not found: {target}"
            
        os.startfile(target)
        return f"Opened '{os.path.basename(target)}' in its default application, Sir."
    except Exception as e:
        return f"Failed to open file: {str(e)}"


@tool
def search_files(query: str, root_folder: str = "Desktop", max_results: int = 10) -> str:
    """Search for files matching a filename or extension across folders.
    - query: Name or extension to search for (e.g. '.py', 'report', 'resume.pdf').
    - root_folder: Starting folder (e.g. 'Desktop', 'Downloads', 'Documents', 'project')."""
    try:
        root = _resolve_path(root_folder)
        if not os.path.exists(root):
            return f"Root directory does not exist: {root}"
            
        matches = []
        q_lower = query.lower()
        
        # Traverse directory tree (cap traversal depth to prevent stalling)
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden and system folders
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ["node_modules", "$Recycle.Bin"]]
            
            for f in filenames:
                if q_lower in f.lower():
                    matches.append(os.path.join(dirpath, f))
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
                
        if not matches:
            return f"No files matching '{query}' found in {root}."
            
        result_lines = [f"Found {len(matches)} matching file(s) in {root}:"]
        for m in matches:
            size = os.path.getsize(m)
            result_lines.append(f"- {os.path.basename(m)} ({size:,} bytes) in {os.path.dirname(m)}")
        return "\n".join(result_lines)
    except Exception as e:
        return f"Search failed: {str(e)}"
