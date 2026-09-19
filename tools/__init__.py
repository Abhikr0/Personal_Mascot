from .base_tools import (
    get_current_time,
    get_system_status,
    web_search,
    open_website,
    open_application,
    take_screenshot,
    write_note,
    read_notes,
    read_file,
    list_files,
)

from .windows_tools import (
    control_media_volume,
    close_application,
    list_running_apps,
    manage_window,
    open_settings,
)

from .gui_tools import (
    get_mouse_position,
    mouse_move,
    mouse_click,
    keyboard_type,
    keyboard_hotkey,
    scroll_screen,
)

from .file_tools import (
    create_folder,
    create_or_write_file,
    open_file,
    search_files,
)

from .memory_tools import (
    remember_information,
    recall_memory,
    list_memories,
    forget_memory,
)

from .system_tools import (
    get_active_window,
    send_desktop_notification,
    get_clipboard_text,
    set_clipboard_text,
)

ALL_FRIDAY_TOOLS = [
    # Base & Information
    get_current_time,
    get_system_status,
    web_search,
    open_website,
    open_application,
    take_screenshot,
    write_note,
    read_notes,

    # Intelligent Memory Knowledge Base
    remember_information,
    recall_memory,
    list_memories,
    forget_memory,

    # Windows OS & Process Management
    control_media_volume,
    close_application,
    list_running_apps,
    manage_window,
    open_settings,

    # Siri-like OS Integration
    get_active_window,
    send_desktop_notification,
    get_clipboard_text,
    set_clipboard_text,

    # GUI & Peripheral Automation
    get_mouse_position,
    mouse_move,
    mouse_click,
    keyboard_type,
    keyboard_hotkey,
    scroll_screen,

    # File & Directory Control
    create_folder,
    create_or_write_file,
    read_file,
    list_files,
    open_file,
    search_files,
]
