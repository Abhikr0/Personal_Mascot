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

# macOS-native automation tools
from .macos_tools import (
    open_app,
    close_app,
    list_running_apps as mac_list_running_apps,
    get_frontmost_app,
    play_music,
    control_music,
    open_notes_and_write,
    send_notification as mac_send_notification,
    run_shortcut,
    set_volume,
    get_volume,
    open_url as mac_open_url,
    lock_screen,
    sleep_mac,
    empty_trash,
    get_battery,
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
    read_file,
    list_files,
    open_file,
    search_files,

    # Intelligent Memory Knowledge Base
    remember_information,
    recall_memory,
    list_memories,
    forget_memory,

    # macOS OS & Process Management
    open_app,
    close_app,
    get_frontmost_app,
    mac_list_running_apps,
    play_music,
    control_music,
    open_notes_and_write,
    run_shortcut,
    set_volume,
    get_volume,
    lock_screen,
    sleep_mac,
    empty_trash,
    get_battery,
    mac_open_url,
    mac_send_notification,

    # Windows OS & Process Management
    control_media_volume,
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
]
