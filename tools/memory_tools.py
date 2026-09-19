from typing import Optional
from langchain_core.tools import tool
from memory import memory_db, remember_user_statement


@tool
def remember_information(statement: str) -> str:
    """Intelligently analyze and save durable personal facts, names, dates, times, schedules, preferences, or project notes into Sylphya's memory knowledge base.
    Use this whenever Sir says 'Remember that...', shares his name, mentions an appointment or meeting, or reveals a preference."""
    try:
        saved = remember_user_statement(statement)
        if not saved:
            return "Understood Sir, though there were no durable long-term facts or dates that required permanent saving in that statement."
        
        details = []
        for item in saved:
            dt_str = f" (Date/Time: {item['date_time']})" if item.get("date_time") else ""
            details.append(f"- [{item['category'].title()}] {item['key'].replace('_', ' ').title()}: {item['value']}{dt_str}")
        
        return f"Saved {len(saved)} memory item(s) to knowledge base, Sir:\n" + "\n".join(details)
    except Exception as e:
        return f"Failed to save memory: {str(e)}"


@tool
def recall_memory(query: str, category: Optional[str] = "") -> str:
    """Search Sylphya's intelligent memory knowledge base for past information, schedules, dates, names, preferences, or notes.
    Use this whenever Sir asks questions like 'When is my meeting?', 'What is my name?', 'Who is X?', 'What do I like?', or 'What did I tell you about Y?'."""
    try:
        cat_filter = category.strip().lower() if category and category.strip() else None
        results = memory_db.search_memories(query=query, category=cat_filter, limit=5)
        
        if not results:
            return f"No memories found matching '{query}', Sir."
            
        items = []
        for r in results:
            dt_info = f" | Date/Time: {r['date_time']}" if r.get("date_time") else ""
            items.append(f"- [{r['category'].title()}] {r['key'].replace('_', ' ').title()}: {r['value']}{dt_info}")
            
        return f"Found {len(results)} relevant memory record(s):\n" + "\n".join(items)
    except Exception as e:
        return f"Failed to recall memory: {str(e)}"


@tool
def list_memories(category: Optional[str] = "") -> str:
    """List stored memories from Sylphya's knowledge base.
    Optional category parameter can be: 'identity', 'schedule', 'preference', 'contact', or 'fact'. Leave blank for all."""
    try:
        cat_filter = category.strip().lower() if category and category.strip() else None
        all_mems = memory_db.list_all_memories(category=cat_filter)
        
        if not all_mems:
            category_desc = f" in category '{category}'" if category else ""
            return f"No memories currently stored{category_desc}, Sir."
            
        # Group by category
        grouped = {}
        for r in all_mems:
            c = r["category"].title()
            if c not in grouped:
                grouped[c] = []
            dt_str = f" ({r['date_time']})" if r.get("date_time") else ""
            grouped[c].append(f"  • {r['key'].replace('_', ' ').title()}: {r['value']}{dt_str}")
            
        lines = [f"Total stored memories: {len(all_mems)}"]
        for cat, entries in grouped.items():
            lines.append(f"📂 {cat}:")
            lines.extend(entries[:10])
            
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list memories: {str(e)}"


@tool
def forget_memory(target: str) -> str:
    """Delete a memory from Sylphya's knowledge base by its key, topic, or ID (e.g. 'project_demo', 'dentist_appointment', or 'old meeting')."""
    try:
        success = memory_db.delete_memory(target)
        if success:
            return f"Successfully removed '{target}' from memory, Sir."
        else:
            return f"No memory record matching '{target}' was found to delete, Sir."
    except Exception as e:
        return f"Failed to delete memory: {str(e)}"
