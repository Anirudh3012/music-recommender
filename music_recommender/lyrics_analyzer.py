import json
from .api_clients import get_openai_client

def get_lyrical_insights(lyrics_text, model="gpt-3.5-turbo"):
    """
    Analyzes lyrics using the OpenAI API to extract themes, sentiments, and keywords.

    Args:
        lyrics_text (str): The lyrics of the song.
        model (str): The OpenAI model to use (e.g., "gpt-3.5-turbo", "gpt-4").

    Returns:
        dict: A dictionary containing 'themes', 'sentiments', and 'keywords'.
              Returns None if an error occurs or insights cannot be generated.
    """
    openai_client = get_openai_client()
    if not openai_client:
        print("OpenAI client not available for lyrics analysis.")
        return None

    if not lyrics_text or not lyrics_text.strip():
        print("Lyrics text is empty, skipping analysis.")
        return {"themes": [], "sentiments": [], "keywords": [], "summary": "Lyrics were empty."}

    system_prompt = """You are an expert music analyst. Analyze the provided song lyrics.

Identify the main themes, distinct sentiments expressed (and if possible, link them to themes or parts of the song), and a list of 5-7 significant keywords or concepts.

Provide your output STRICTLY in the following JSON format, with no other text before or after the JSON block:

{
  "themes": ["theme1", "theme2", ...],
  "sentiments": [
    {"sentiment_type": "e.g., joyful", "description": "Expressed in the chorus regarding theme X"},
    {"sentiment_type": "e.g., melancholic", "description": "Throughout the verses reflecting on theme Y"}
  ],
  "keywords": ["keyword1", "keyword2", ...],
  "overall_summary": "A brief one or two sentence summary of the song's lyrical content."
}

Ensure all string values within the JSON are properly escaped."""

    user_prompt = f"Here are the lyrics:\n\n{lyrics_text}"

    try:
        print(f"Analyzing lyrics with OpenAI model: {model}...")
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,  # Adjust for creativity vs. factuality
            max_tokens=500, # Adjust based on expected output length
            response_format={"type": "json_object"} # For newer models that support JSON mode
        )
        
        insights_json_str = response.choices[0].message.content
        
        # print(f"DEBUG: OpenAI Raw Response:\n{insights_json_str}") # For debugging

        insights = json.loads(insights_json_str)
        return insights

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from OpenAI response: {e}")
        print(f"Raw response was: {insights_json_str}")
        return None
    except Exception as e:
        print(f"An error occurred while communicating with OpenAI or processing lyrics: {e}")
        # You might want to log the full traceback here for debugging
        # import traceback
        # print(traceback.format_exc())
        return None

DEFAULT_GPT4O_MODEL = "gpt-4o"

def get_rich_lyrical_insights(lyrics_text: str, song_title: str, artist_name: str, openai_client, model: str = DEFAULT_GPT4O_MODEL):
    """
    Performs a deep and rich analysis of song lyrics using a powerful LLM (e.g., GPT-4o).

    Args:
        lyrics_text (str): The lyrics of the song.
        song_title (str): The title of the song (for context).
        artist_name (str): The name of the artist (for context).
        openai_client: An initialized OpenAI client.
        model (str): The OpenAI model to use.

    Returns:
        dict: A dictionary containing detailed lyrical insights based on the new comprehensive structure.
              Returns None if an error occurs or insights cannot be generated.
    """
    if not openai_client:
        print("OpenAI client not available for rich lyrics analysis.")
        return None

    if not lyrics_text or not lyrics_text.strip():
        print(f"Lyrics for '{song_title}' are empty, skipping rich analysis.")
        return {
            "song_title": song_title,
            "artist_name": artist_name,
            "analysis_model": model,
            "overall_interpretation": "Lyrics were empty.",
            "concise_summary": "Lyrics were empty.",
            "detailed_breakdown": {},
            "llm_confidence_notes": "Analysis skipped due to empty lyrics."
        }

    system_prompt = f"""
You are a highly sophisticated musicologist and literary analyst. Your task is to perform an in-depth analysis of the provided song lyrics for '{song_title}' by '{artist_name}'.

Provide your output STRICTLY in the following JSON format. Ensure all string values are properly escaped. Do not include any text before or after the JSON block itself.

JSON Structure:
{{
  "song_title": "{song_title} (echoed)",
  "artist_name": "{artist_name} (echoed)",
  "analysis_model": "{model}",
  "overall_interpretation": "(string) A paragraph summarizing the main message or interpretation of the song. Consider the deeper meanings and potential ambiguities.",
  "concise_summary": "(string) A very brief 1-2 sentence factual summary of the lyrical content.",
  "detailed_breakdown": {{
    "themes_and_concepts": [
      {{
        "theme": "(string) e.g., Love and Loss, Social Injustice, Self-Discovery",
        "description": "(string) Detailed explanation of how this theme is presented, supported by lyrical examples or inferences.",
        "related_keywords": ["(list of strings) Keywords directly related to this theme found in or inferred from lyrics"]
      }}
      // ... (include 2-4 major themes)
    ],
    "narrative_structure": {{
      "type": "(string) e.g., Linear Story, Cyclical, Abstract/Fragmented, Character Monologue, Observational",
      "description": "(string) Explanation of the lyrical progression, point of view, and structural elements."
    }},
    "emotions_and_sentiments": [
      {{
        "emotion": "(string) e.g., Deep Sorrow, Fleeting Joy, Righteous Anger, Ambivalence, Nostalgia",
        "intensity": "(string) e.g., Subtle, Overt, Building, Fading",
        "lyrical_evidence": "(string) Specific quote(s) or reference to lyrics supporting this emotion.",
        "progression_note": "(string, optional) How this emotion evolves or is contrasted within the song."
      }}
      // ... (include 2-5 distinct emotions/sentiments)
    ],
    "imagery_and_symbols": [
      {{
        "image_or_symbol": "(string) e.g., 'Setting Sun', 'Empty Road', 'Broken Mirror'",
        "description": "(string) What it might represent, its sensory details, and its role in the lyrics.",
        "type": "(string) e.g., Concrete Visual, Abstract Concept, Metaphorical Symbol, Recurring Motif"
      }}
      // ... (include 3-5 significant images/symbols)
    ],
    "literary_devices": [
      {{
        "device": "(string) e.g., Metaphor, Simile, Alliteration, Irony, Personification, Paradox, Allusion",
        "example_lyrics": "(string) Quote from lyrics demonstrating the device.",
        "explanation": "(string) How it's used and its effect on meaning or tone."
      }}
      // ... (include 2-4 notable literary devices)
    ],
    "lyrical_style_and_tone": {{
      "style_descriptors": ["(list of strings) e.g., Poetic, Conversational, Abstract, Direct, Storytelling, Cryptic"],
      "tone_descriptors": ["(list of strings) e.g., Reflective, Sarcastic, Hopeful, Resigned, Urgent, Detached"],
      "overall_description": "(string) Brief summary of the overall lyrical style and dominant tone."
    }},
    "cultural_social_historical_references": [
      {{
        "reference_type": "(string) e.g., Historical Event, Cultural Movement, Literary Allusion, Social Commentary, Biblical Reference",
        "details": "(string) Description of the reference and its perceived relevance or impact within the lyrics."
      }}
      // ... (include if any are clearly identifiable or strongly implied)
    ],
    "key_phrases_or_lines": [
      {{
        "phrase": "(string) A particularly impactful, memorable, or thematically central line or phrase.",
        "significance": "(string) Why this phrase/line is considered key to understanding the song."
      }}
      // ... (include 2-3 key phrases/lines)
    ]
  }},
  "llm_confidence_notes": "(string, optional) Any notes from you (the LLM) about the analysis, such as ambiguities in lyrics, multiple possible interpretations, or confidence levels for certain inferences."
}}
"""

    user_prompt = f"Please analyze the following lyrics for the song '{song_title}' by '{artist_name}':\n\n{lyrics_text}"

    try:
        print(f"Performing rich lyrical analysis for '{song_title}' with OpenAI model: {model}...")
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,  # Slightly higher for more nuanced interpretation but still grounded
            max_tokens=3500, # Generous token limit for detailed JSON
            response_format={"type": "json_object"}
        )
        
        insights_json_str = response.choices[0].message.content
        insights = json.loads(insights_json_str)
        print(f"Rich lyrical analysis successful for '{song_title}'.")
        return insights

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from rich lyrical analysis for '{song_title}': {e}")
        print(f"Raw response was: {insights_json_str}")
        return None
    except Exception as e:
        print(f"An error occurred during rich lyrical analysis for '{song_title}': {e}")
        return None

if __name__ == '__main__':
    # Example Usage (requires OPENAI_API_KEY to be set in config.py or environment)
    print("--- Testing Lyrics Analyzer --- ")
    example_lyrics = """
    Hello, darkness, my old friend
    I've come to talk with you again
    Because a vision softly creeping
    Left its seeds while I was sleeping
    And the vision that was planted in my brain
    Still remains
    Within the sound of silence

    In restless dreams I walked alone
    Narrow streets of cobblestone
    'Neath the halo of a street lamp
    I turned my collar to the cold and damp
    When my eyes were stabbed by the flash of a neon light
    That split the night
    And touched the sound of silence
    """
    
        # Test basic insights (old function)
    print("\n--- Testing Basic Lyrics Analyzer (Old Function) ---")
    basic_insights = get_lyrical_insights(example_lyrics) # Assumes get_openai_client() is still used internally by it
    if basic_insights:
        print("\n--- Basic Lyrical Insights --- ")
        print(f"Themes: {', '.join(basic_insights.get('themes', ['N/A']))}")
        print("Sentiments:")
        for sent in basic_insights.get('sentiments', []):
            print(f"  - {sent.get('sentiment_type', 'N/A')}: {sent.get('description', 'N/A')}")
        print(f"Keywords: {', '.join(basic_insights.get('keywords', ['N/A']))}")
        print(f"Summary: {basic_insights.get('overall_summary', 'N/A')}")
    else:
        print("Could not retrieve basic lyrical insights.")

    print("\n\n--- Testing Rich Lyrics Analyzer (New Function) ---")
    # For testing the new function, we need an OpenAI client instance.
    # In a real app, this client would be initialized in main.py and passed around.
    # For this standalone test, we'll try to get one or use a mock if needed.
    try:
        openai_client_for_test = get_openai_client()
    except Exception as e:
        print(f"Could not get OpenAI client for testing rich analyzer: {e}")
        openai_client_for_test = None

    if openai_client_for_test:
        rich_insights = get_rich_lyrical_insights(
            lyrics_text=example_lyrics, 
            song_title="The Sound of Silence", 
            artist_name="Simon & Garfunkel", 
            openai_client=openai_client_for_test
        )
        if rich_insights:
            print("\n--- Rich Lyrical Insights (New Function) --- ")
            # Print a summary or a few key fields from the rich_insights structure
            print(f"Song: {rich_insights.get('song_title')} by {rich_insights.get('artist_name')}")
            print(f"Model Used: {rich_insights.get('analysis_model')}")
            print(f"Overall Interpretation: {rich_insights.get('overall_interpretation', 'N/A')}")
            if rich_insights.get('detailed_breakdown'):
                themes = rich_insights['detailed_breakdown'].get('themes_and_concepts', [])
                if themes:
                    print("Main Theme Example:")
                    print(f"  Theme: {themes[0].get('theme')}")
                    print(f"  Description: {themes[0].get('description')}")
            # print(json.dumps(rich_insights, indent=2)) # Uncomment for full JSON output
        else:
            print("Could not retrieve rich lyrical insights.")
    else:
        print("Skipping rich lyrical insights test as OpenAI client could not be initialized.")

    # Old test call - comment out or remove if get_lyrical_insights is deprecated
    # insights = get_lyrical_insights(example_lyrics)
    if insights:
        print("\n--- Lyrical Insights --- ")
        print(f"Themes: {', '.join(insights.get('themes', ['N/A']))}")
        print("Sentiments:")
        for sent in insights.get('sentiments', []):
            print(f"  - {sent.get('sentiment_type', 'N/A')}: {sent.get('description', 'N/A')}")
        print(f"Keywords: {', '.join(insights.get('keywords', ['N/A']))}")
        print(f"Summary: {insights.get('overall_summary', 'N/A')}")
    else:
        print("Could not retrieve lyrical insights.")
