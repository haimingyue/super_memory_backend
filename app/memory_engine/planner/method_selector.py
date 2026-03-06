def select_memory_method(content_type: str) -> str:
    mapping = {
        "sequence_list": "link_method",
        "numbered_list": "peg_method",
        "alphabet_list": "peg_method",
        "timeline": "timeline_method",
        "large_list": "link_method",
        "concept": "substitute_method",
    }
    return mapping.get(content_type, "link_method")
