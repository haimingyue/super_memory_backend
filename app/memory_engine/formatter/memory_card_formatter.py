def format_memory_card(question: str, keywords: list[str], imagery: list[str], recap: str) -> dict:
    back = (
        "关键词：\n"
        + " → ".join(keywords)
        + "\n\n想象画面：\n"
        + "\n".join([f"{i + 1}. {line}" for i, line in enumerate(imagery)])
        + "\n\n快速复述：\n"
        + recap
    )
    return {
        "front": question,
        "back": back,
    }
