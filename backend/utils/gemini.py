def get_ai_answer(query: str, topic: str, transcript: str) -> str:
    return f"This relates to {topic}, focus on the core definition."

def compress_query(query: str) -> str:
    words = query.strip().split()
    return " ".join(words[:4])