def select_hook_system(content_type: str) -> str:
    mapping = {
        "sequence_list": "none_hooks",
        "numbered_list": "number_hooks",
        "alphabet_list": "alphabet_hooks",
        "timeline": "date_hooks",
        "large_list": "space_hooks",
        "concept": "none_hooks",
    }
    return mapping.get(content_type, "none_hooks")
