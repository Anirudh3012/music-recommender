import pylast
import re
from .api_clients import get_lastfm_network, get_openai_client # Assuming get_openai_client is available
import json # Added for LLM interaction
from openai import OpenAI # Added for LLM interaction

def _clean_track_title(title):
    """
    Cleans a track title by removing common suffixes and extra information.
    e.g., '(Remastered 2011)', '(Live)', '- Radio Edit', etc.
    """
    cleaned_title = title
    # Remove content in parentheses (like 'Remastered...', 'Live at...', etc.)
    cleaned_title = re.sub(r'\s*\(.*?\)\s*', '', cleaned_title)
    # Remove content in square brackets
    cleaned_title = re.sub(r'\s*\[.*?\]\s*', '', cleaned_title)
    
    # Remove common suffixes like '- Remastered YYYY', '- Radio Edit', '- Album Version'
    # Order matters here: longer, more specific patterns first
    suffixes_to_remove = [
        r'-\s*Remastered\s*\d{4}',
        r'-\s*Remastered',
        r'-\s*Radio\s*Edit',
        r'-\s*Album\s*Version',
        r'-\s*Single\s*Version',
        r'-\s*Live\s*Version',
        r'-\s*Live\s+At\s+.*',
        r'-\s*Live',
        r'-\s*Acoustic\s*Version',
        r'-\s*Acoustic',
        r'-\s*Explicit\s*Version',
        r'-\s*Explicit'
    ]
    for suffix_pattern in suffixes_to_remove:
        cleaned_title = re.sub(r'\s*' + suffix_pattern + r'\s*$', '', cleaned_title, flags=re.IGNORECASE)
    
    cleaned_title = cleaned_title.strip(' -')
    return cleaned_title.strip()


def _calculate_jaccard_similarity(set1, set2):
    """Calculates the Jaccard similarity between two sets."""
    if not isinstance(set1, set) or not isinstance(set2, set):
        # Convert lists/tuples to sets if they aren't already
        set1 = set(set1)
        set2 = set(set2)
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    if union == 0:
        return 0.0  # Avoid division by zero if both sets are empty
    return intersection / union

def calculate_song_content_similarity(song_a_details, song_b_details, weights=None):
    """
    Calculates a content-based similarity score between two songs.

    Args:
        song_a_details (dict): Dictionary of attributes for song A.
        song_b_details (dict): Dictionary of attributes for song B.
        weights (dict, optional): Weights for combining individual similarity scores.
                                  Defaults to {'genre': 0.3, 'theme': 0.4, 'keyword': 0.3}.

    Returns:
        float: A similarity score between 0 and 1.
    """
    if weights is None:
        weights = {'genre': 0.3, 'theme': 0.4, 'keyword': 0.3}

    # Ensure lyrical_insights exist and have the required keys
    song_a_insights = song_a_details.get('lyrical_insights', {})
    song_b_insights = song_b_details.get('lyrical_insights', {})

    # Genre Similarity
    genres_a = set(song_a_details.get('artist_genres', []))
    genres_b = set(song_b_details.get('artist_genres', []))
    genre_similarity = _calculate_jaccard_similarity(genres_a, genres_b)

    # Theme Similarity
    themes_a = set(song_a_insights.get('themes', []))
    themes_b = set(song_b_insights.get('themes', []))
    theme_similarity = _calculate_jaccard_similarity(themes_a, themes_b)

    # Keyword Similarity
    keywords_a = set(song_a_insights.get('keywords', []))
    keywords_b = set(song_b_insights.get('keywords', []))
    keyword_similarity = _calculate_jaccard_similarity(keywords_a, keywords_b)

    # Weighted overall score
    total_similarity = (
        genre_similarity * weights.get('genre', 0.3) +
        theme_similarity * weights.get('theme', 0.4) +
        keyword_similarity * weights.get('keyword', 0.3)
    )
    
    # Normalize by the sum of weights actually used (in case some keys are missing in weights dict)
    # For this default implementation, sum of weights is 1.0
    # If weights could vary, normalization would be more critical.
    # current_weight_sum = weights.get('genre', 0.3) + weights.get('theme', 0.4) + weights.get('keyword', 0.3)
    # if current_weight_sum == 0: return 0.0
    # total_similarity = total_similarity / current_weight_sum 
    # This normalization is implicitly handled if weights sum to 1.

    return total_similarity


def get_lastfm_recommendations_for_track(track_name, artist_name, limit=10):
    """
    Fetches recommendations for a given track using Last.fm's similar tracks feature.

    Args:
        track_name (str): The name of the track.
        artist_name (str): The name of the artist.
        limit (int): The maximum number of recommendations to return.

    Returns:
        list: A list of dictionaries, where each dictionary contains 'name' and 'artist'
              for a recommended track. Returns an empty list if an error occurs or
              no recommendations are found.
    """
    network = get_lastfm_network()
    if not network:
        print("Last.fm network client not available for recommendations.")
        return []

    recommendations = []
    try:
        print(f"Last.fm: Getting similar tracks for '{track_name}' by '{artist_name}'...")
        track = network.get_track(artist_name, track_name)
        if not track:
            print(f"Last.fm: Track '{track_name}' by '{artist_name}' not found.")
            return []
            
        # get_similar() returns a list of pylast.Track objects
        # The first item in the list is often the track itself with a match score of 1.0, so we might skip it.
        similar_tracks_pylast = track.get_similar(limit=limit + 1) # Fetch one extra in case the first is the same track

        if not similar_tracks_pylast:
            print(f"Last.fm: No similar tracks found for original title '{track_name}' by '{artist_name}'.")
            cleaned_title = _clean_track_title(track_name)
            
            if cleaned_title and cleaned_title.lower() != track_name.lower():
                print(f"Last.fm: Retrying with cleaned title '{cleaned_title}' by '{artist_name}'...")
                try:
                    cleaned_track_obj = network.get_track(artist_name, cleaned_title)
                    if cleaned_track_obj:
                        similar_tracks_pylast = cleaned_track_obj.get_similar(limit=limit + 1)
                        if similar_tracks_pylast:
                             print(f"Last.fm: Found similar tracks using cleaned title '{cleaned_title}'.")
                except pylast.WSError as e_clean:
                    print(f"Last.fm: Cleaned title '{cleaned_title}' by '{artist_name}' not found or no similar tracks (API Error: {e_clean.details}).")
                except Exception as e_clean_general:
                    print(f"Unexpected error occurred with cleaned title '{cleaned_title}': {e_clean_general}")
            
            if not similar_tracks_pylast:
                 print(f"Last.fm: Ultimately, no similar tracks found for '{track_name}' (or its cleaned version) by '{artist_name}'.")
                 return []

        for item in similar_tracks_pylast:
            if len(recommendations) >= limit:
                break
            
            # item is a pylast.PlayedTrack or pylast.Track object
            # We need to access its 'track' attribute which is a pylast.Track, then its 'artist' and 'title'
            if isinstance(item, pylast.PlayedTrack) or isinstance(item, pylast.Track) or hasattr(item, 'item'):
                # The actual track object might be nested under 'item' for get_similar results
                actual_track = item.item if hasattr(item, 'item') else item
                
                # Check if the similar track is not the same as the input track (case-insensitive)
                if actual_track.artist.get_name().lower() == artist_name.lower() and \
                   actual_track.title.lower() == track_name.lower():
                    continue # Skip if it's the same track

                recommendations.append({
                    "name": actual_track.title,
                    "artist": actual_track.artist.get_name()
                })
            else:
                print(f"Last.fm: Unexpected item type in similar tracks: {type(item)}")

        if recommendations:
            print(f"Last.fm: Found {len(recommendations)} similar tracks.")
        else:
            print(f"Last.fm: No distinct similar tracks found after filtering for '{track_name}'.")
            
    except pylast.WSError as e:
        print(f"Last.fm API error for '{track_name}' by '{artist_name}': {e}")
        if "Track not found" in str(e) or e.status == 6: # Status 6 is 'Track not found' or 'Artist not found'
            print(f"(Last.fm could not find the specific track/artist combination)")
    except Exception as e:
        print(f"An unexpected error occurred while getting Last.fm recommendations for '{track_name}': {e}")
    
    return recommendations


DEFAULT_GPT4O_MODEL = "gpt-4o"

def get_holistic_llm_recommendations(liked_songs_enriched_details: list, openai_client: OpenAI, model: str = DEFAULT_GPT4O_MODEL) -> list | None:
    """
    Generates holistic song recommendations using a powerful LLM (e.g., GPT-4o)
    based on a list of the user's liked songs with their enriched details.

    Args:
        liked_songs_enriched_details (list): A list of dictionaries, where each dictionary
                                             contains comprehensive details of a liked song.
        openai_client (OpenAI): An initialized OpenAI client.
        model (str): The OpenAI model to use (e.g., "gpt-4o").

    Returns:
        list | None: A list of 10 recommended songs, each as a dictionary with
                     {'artist': str, 'title': str, 'justification': str}.
                     Returns None if an error occurs or no recommendations are generated.
    """
    if not openai_client:
        print("OpenAI client not available for holistic LLM recommendations.")
        return None

    if not liked_songs_enriched_details:
        print("No liked songs provided for LLM recommendation.")
        return []

    # Prepare the liked songs data for the prompt
    # We might need to be careful about total token count if the list is very long
    # For now, assume it fits. GPT-4o has a large context window.
    try:
        liked_songs_json_str = json.dumps(liked_songs_enriched_details, indent=2)
    except TypeError as e:
        print(f"Error serializing liked_songs_enriched_details to JSON: {e}")
        # Fallback: try a more basic serialization for the prompt
        liked_songs_prompt_repr = []
        for song in liked_songs_enriched_details:
            title = song.get('original_input_title', song.get('title', 'Unknown Title'))
            artist = song.get('original_input_artist', song.get('artist', 'Unknown Artist'))
            genres = song.get('spotify_artist_genres', [])
            themes = song.get('lyrical_analysis', {}).get('detailed_breakdown', {}).get('themes_and_concepts', [])
            theme_names = [t.get('theme') for t in themes if t.get('theme')]
            liked_songs_prompt_repr.append(f"- Title: {title}, Artist: {artist}, Genres: {genres}, Lyrical Themes: {theme_names}")
        liked_songs_json_str = "\n".join(liked_songs_prompt_repr)
        print("Warning: Using simplified representation for liked songs in prompt due to serialization issue.")


    system_prompt = f"""
You are an exceptionally insightful and creative music recommendation expert with a deep understanding of music history, theory, genres, and lyrical content. Your goal is to provide 10 unique and highly relevant song recommendations based on a user's liked songs and their detailed attributes.

IMPORTANT INSTRUCTIONS:
1.  Analyze ALL provided liked songs to understand the user's overall taste profile, including commonalities and diversities in genre, lyrical themes, mood, instrumentation, and production style.
2.  Generate exactly 10 NEW and DISTINCT song recommendations. These should NOT include any of the songs already present in the user's liked list.
3.  For EACH of the 10 recommendations, provide:
    a.  The song's 'artist'.
    b.  The song's 'title'.
    c.  A detailed 'justification' (2-4 sentences) explaining precisely WHY this song is a good recommendation. This justification MUST connect the recommended song's characteristics back to specific attributes, themes, artists, or moods found in ONE OR MORE of the user's liked songs. Be specific (e.g., "This song is recommended because its complex lyrical narrative and progressive rock elements echo 'Song X' by 'Artist Y' from your liked list, while its melancholic mood aligns with 'Song Z'.").
4.  Aim for a mix of recommendations that are:
    a.  Closely aligned with the core of the user's taste.
    b.  Potentially serendipitous discoveries that expand on their taste profile but are still relevant.
5.  The final output MUST be a single, valid JSON array. This array MUST contain exactly 10 JSON objects.
    Each of these 10 objects MUST have the keys "artist", "title", and "justification".
    For example, one object within the array would look like:
    {{ "artist": "Example Artist", "title": "Example Song Title", "justification": "This song is recommended because..." }}
    Your response should be structured as: [ object1, object2, ..., object10 ]

Do not include any other text, explanations, or apologies before or after the JSON array.
"""

    user_prompt = f"""
Based on the following liked songs and their detailed analyses:

{liked_songs_json_str}

Please provide 10 new and distinct song recommendations with justifications, following all instructions above.
"""

    try:
        print(f"Generating holistic recommendations with OpenAI model: {model}...")
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,  # Higher temperature for more creative/serendipitous recommendations
            max_tokens=3500  # Ensure enough tokens for 10 detailed recommendations
            # response_format={"type": "json_object"} # Removed again
        )

        choice = response.choices[0]
        response_content = choice.message.content
        
        if not response_content:
            print(f"LLM ({model}) provided no content for recommendations.")
            print(f"Finish reason: {choice.finish_reason}")
            return []

        # Strip markdown fences if present
        if response_content.strip().startswith("```json"):
            response_content = response_content.strip()
            response_content = response_content[len("```json"):].strip()
            if response_content.endswith("```"):
                response_content = response_content[:-len("```")].strip()
        
        # The prompt asks for a JSON array. If response_format forces an object, 
        # the LLM might wrap the array in a key, e.g. {"recommendations": [...]}
        # We'll try to parse it as a list first, then as an object containing a list.
        try:
            recommendations = json.loads(response_content)
            if isinstance(recommendations, list):
                print(f"Successfully received {len(recommendations)} recommendations as a list.")
                return recommendations
            elif isinstance(recommendations, dict) and any(isinstance(v, list) for v in recommendations.values()):
                # If it's a dict and one of its values is a list, assume that's our recommendation list
                for key, value in recommendations.items():
                    if isinstance(value, list):
                        print(f"Successfully received {len(value)} recommendations from dict key '{key}'.")
                        return value # Return the first list found
                print("LLM returned a dictionary, but no list of recommendations found within it.")
                return []
            else:
                print("LLM response was valid JSON but not in the expected list or dict-wrapped-list format.")
                print(f"LLM Raw Response: {response_content[:500]}...")
                return []

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from LLM recommendations: {e}")
            print(f"LLM Raw Response: {response_content[:500]}...")
            return None

    except Exception as e:
        print(f"An error occurred during LLM recommendation generation: {e}")
        # import traceback
        # print(traceback.format_exc())
        return None


if __name__ == '__main__':
    print("--- Testing Holistic LLM Recommender ---")

    # Mock OpenAI client
    class MockCompletions:
        def create(self, model, messages, temperature, max_tokens, response_format):
            print("\n--- MOCK LLM Recommender Call ---")
            # print(f"Model: {model}")
            # print(f"User Prompt (first 500 chars): {messages[1]['content'][:500]}...")
            
            mock_recs = [
                {
                    "artist": "Porcupine Tree", 
                    "title": "Trains", 
                    "justification": "Given your appreciation for Pink Floyd's progressive elements and narrative depth, 'Trains' offers a modern take on progressive rock with beautiful melodies and introspective lyrics, similar to the emotional depth found in your liked song 'Wish You Were Here'."
                },
                {
                    "artist": "Fleet Foxes", 
                    "title": "Mykonos", 
                    "justification": "The rich vocal harmonies and folk sensibilities in 'Mykonos' might appeal to you if you enjoyed the acoustic and melodic aspects of The Beatles' 'Blackbird'. It shares a timeless, pastoral quality."
                },
                {
                    "artist": "Radiohead", 
                    "title": "Paranoid Android", 
                    "justification": "For fans of complex song structures like Queen's 'Bohemian Rhapsody', Radiohead's 'Paranoid Android' presents a multi-part epic with shifting moods and sophisticated musicianship, exploring themes of alienation."
                },
                # ... add up to 10 mock recommendations
            ]
            # Simulate the LLM wrapping the list in a dictionary key
            # mock_response_data = {"recommendations": mock_recs[:3]}
            # mock_json_response = json.dumps(mock_response_data)
            # Or simulate direct list output if the LLM follows the prompt perfectly
            mock_json_response = json.dumps(mock_recs[:3])

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

    class MockChat:
        def __init__(self):
            self.completions = MockCompletions()

    class MockOpenAIClient:
        def __init__(self):
            self.chat = MockChat()

    mock_client = MockOpenAIClient()

    # Sample enriched liked songs data (highly abridged for example)
    sample_liked_songs = [
        {
            "original_input_title": "Wish You Were Here",
            "original_input_artist": "Pink Floyd",
            "spotify_artist_genres": ["Progressive Rock", "Psychedelic Rock"],
            "lyrical_analysis": {
                "overall_interpretation": "A song about absence, alienation, and the critique of the music industry.",
                "detailed_breakdown": {
                    "themes_and_concepts": [{"theme": "Absence and Loss", "description": "..."}]
                }
            }
        },
        {
            "original_input_title": "Bohemian Rhapsody",
            "original_input_artist": "Queen",
            "spotify_artist_genres": ["Rock", "Glam Rock", "Progressive Rock"],
            "lyrical_analysis": {
                "overall_interpretation": "A multi-part rock opera about a young man confessing a murder.",
                "detailed_breakdown": {
                    "themes_and_concepts": [{"theme": "Guilt and Confession", "description": "..."}]
                }
            }
        }
    ]

    recommendations = get_holistic_llm_recommendations(
        liked_songs_enriched_details=sample_liked_songs,
        openai_client=mock_client
    )

    if recommendations:
        print("\n--- LLM Generated Recommendations ---")
        for i, rec in enumerate(recommendations):
            print(f"{i+1}. {rec.get('title')} by {rec.get('artist')}")
            print(f"   Justification: {rec.get('justification')}")
    elif recommendations == []:
        print("LLM returned no recommendations.")
    else:
        print("Could not retrieve LLM recommendations.")
