import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_ai_answer(query: str, topic: str, transcript: str) -> str:
    prompt = f"""
    You are a helpful classroom assistant.
    The current lecture topic is: {topic}
    Recent lecture transcript: {transcript}
    
    A student is confused and asks: {query}
    
    Answer in 10-15 words only. Be direct and simple.
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()


def compress_query(query: str) -> str:
    prompt = f"""
    Compress this student question into a 3-4 word tag only.
    No punctuation, no explanation, just the tag.
    
    Question: {query}
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()