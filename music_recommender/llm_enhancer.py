import json
from openai import OpenAI

# Placeholder for OPENAI_API_KEY and potentially a default model
# It's better to get these from a config file or environment variables
# from .config import OPENAI_API_KEY, OPENAI_MODEL_GPT4O # Assuming you add OPENAI_MODEL_GPT4O to config

DEFAULT_MODEL = "gpt-4o" # We'll use this for now

def augment_song_details_with_llm(song_title: str, artist_name: str, existing_details: dict, openai_client: OpenAI, model: str = DEFAULT_MODEL):
    """
    Augments song details using an LLM (e.g., GPT-4o) to find or infer additional attributes.

    Args:
        song_title: The title of the song.
        artist_name: The name of the artist.
        existing_details: A dictionary of already known details about the song.
        openai_client: An initialized OpenAI client.
        model: The OpenAI model to use (e.g., "gpt-4o").

    Returns:
        A dictionary with augmented details. Returns existing_details if LLM call fails or provides no new info.
    """
    print(f"\nAttempting to augment details for '{song_title}' by {artist_name} using {model}...")

    # Construct a detailed prompt
    prompt_parts = [
        f"You are an expert musicologist and researcher. Your task is to provide detailed and accurate information about the song '{song_title}' by '{artist_name}'.",
        "Given the following known details (if any):",
        json.dumps(existing_details, indent=2),
        "\nPlease research and provide the following additional information. If any piece of information is speculative or not commonly known, please indicate that or omit it if confidence is very low.",
        "Format your response as a JSON object with the following keys (use null or an empty list if information is not found/applicable):",
        "- 'composers': (list of strings) Names of the composer(s).",
        "- 'producers': (list of strings) Names of the producer(s).",
        "- 'lyricists': (list of strings) Names of the lyricist(s), if different from composers or performing artists.",
        "- 'recording_studios': (list of strings) Names of the recording studio(s) where the song was primarily recorded.",
        "- 'session_musicians': (list of objects, each with 'name' and 'instrument' fields) Notable session musicians or guest performers and their instruments.",
        "- 'specific_sub_genres': (list of strings) More specific sub-genre classifications beyond broad terms (e.g., 'Progressive Metal', 'Ambient Techno', 'Neo-Soul').",
        "- 'instrumentation_details': (list of strings) Key instruments or notable instrumental features (e.g., 'prominent use of saxophone solo', 'driven by a Moog synthesizer riff', 'features a string quartet').",
        "- 'mood_atmosphere_tempo': (object with 'moods': [list of strings], 'atmosphere': [list of strings], 'tempo_description': string) Describe the overall mood (e.g., 'melancholy', 'uplifting', 'aggressive'), atmosphere (e.g., 'dreamy', 'intense', 'sparse'), and tempo (e.g., 'slow-tempo ballad', 'mid-tempo groove', 'fast-paced rocker').",
        "- 'historical_context_significance': (string) Any notable historical context, cultural impact, or significance of the track (e.g., 'pioneering track in the X genre', 'a response to Y social event', 'won Z award').",
        "- 'llm_confidence_notes': (string) Any notes about the confidence of the provided information or if certain parts are speculative."
        "\nEnsure the entire output is a single valid JSON object."
    ]
    prompt = "\n".join(prompt_parts)

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert musicologist providing detailed song information in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more factual, less creative responses
            # max_tokens can be set high, but be mindful of cost and actual need
            # For GPT-4o, the max output is 4096 tokens. Let's use a generous amount.
            max_tokens=3000, 
            response_format={"type": "json_object"} # Ensure JSON output if supported by model version
        )

        llm_response_content = response.choices[0].message.content
        if llm_response_content:
            print(f"LLM ({model}) provided augmentation data for '{song_title}'.")
            augmented_data = json.loads(llm_response_content)
            
            # Merge with existing details, LLM data takes precedence for shared keys if we want that,
            # or we can selectively update.
            # For now, let's assume the LLM output is the primary source for these new fields.
            updated_details = existing_details.copy()
            updated_details.update(augmented_data) # This will add new keys and overwrite existing ones if they match
            return updated_details
        else:
            print(f"LLM ({model}) provided no content for '{song_title}'.")
            return existing_details

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response for '{song_title}': {e}")
        print(f"LLM Raw Response: {llm_response_content}")
        return existing_details
    except Exception as e:
        print(f"An error occurred during LLM call for '{song_title}': {e}")
        return existing_details

if __name__ == '__main__':
    # This is a basic example of how to use the function.
    # You'll need to set up your OpenAI API key and client.
    # from config import OPENAI_API_KEY # You would need to manage your API key securely
    
    # Mock OpenAI client and key for local testing
    # In a real scenario, initialize this properly with your API key
    class MockOpenAIClient:
        class Chat:
            class Completions:
                def create(self, model, messages, temperature, max_tokens, response_format):
                    print("\n--- MOCK LLM Call ---")
                    print(f"Model: {model}")
                    print(f"Temperature: {temperature}")
                    print(f"Max Tokens: {max_tokens}")
                    print(f"Response Format: {response_format}")
                    # print("Messages:")
                    # for msg in messages:
                    #     print(f"  Role: {msg['role']}")
                    #     print(f"  Content: {msg['content'][:300]}...") # Print start of content
                    
                    # Simulate a plausible JSON response structure
                    mock_response_data = {
                        "composers": ["John Lennon", "Paul McCartney"],
                        "producers": ["George Martin"],
                        "lyricists": ["John Lennon", "Paul McCartney"],
                        "recording_studios": ["Abbey Road Studios"],
                        "session_musicians": [
                            {"name": "Billy Preston", "instrument": "Keyboards"}
                        ],
                        "specific_sub_genres": ["Psychedelic Rock", "Art Pop"],
                        "instrumentation_details": ["Features a Mellotron intro", "Backwards guitar solos", "Orchestral overdubs"],
                        "mood_atmosphere_tempo": {
                            "moods": ["nostalgic", "reflective"],
                            "atmosphere": ["dreamy", "layered"],
                            "tempo_description": "Mid-tempo with variations"
                        },
                        "historical_context_significance": "Considered a landmark in psychedelic music and studio innovation.",
                        "llm_confidence_notes": "Information is generally well-documented for this iconic song."
                    }
                    mock_json_response = json.dumps(mock_response_data)
                    
                    class MockMessage:
                        def __init__(self, content):
                            self.content = content
                    class MockChoice:
                        def __init__(self, content):
                            self.message = MockMessage(content)
                    class MockCompletion:
                        def __init__(self, content):
                            self.choices = [MockChoice(content)]
                    return MockCompletion(mock_json_response)

    mock_client = MockOpenAIClient()
    
    sample_song_title = "Strawberry Fields Forever"
    sample_artist_name = "The Beatles"
    sample_existing_details = {
        "spotify_genres": ["Rock", "Pop"],
        "year": 1967
    }

    augmented_details = augment_song_details_with_llm(
        sample_song_title,
        sample_artist_name,
        sample_existing_details,
        mock_client # Pass the mock client
    )

    print("\n--- Augmented Song Details ---")
    print(json.dumps(augmented_details, indent=2))

    # Example with a less known song (mock will still return same data for simplicity)
    sample_song_title_2 = "Echoes of the Past"
    sample_artist_name_2 = "The Obscure Band"
    sample_existing_details_2 = {
        "spotify_genres": ["Indie Rock"],
        "year": 2022
    }
    augmented_details_2 = augment_song_details_with_llm(
        sample_song_title_2,
        sample_artist_name_2,
        sample_existing_details_2,
        mock_client
    )
    print("\n--- Augmented Song Details (Obscure Song) ---")
    print(json.dumps(augmented_details_2, indent=2))
