import requests
import re
from .api_clients import get_spotify_client, get_genius_client, get_lastfm_network, get_openai_client
from .recommender import get_lastfm_recommendations_for_track, calculate_song_content_similarity, get_holistic_llm_recommendations
from .lyrics_analyzer import get_lyrical_insights, get_rich_lyrical_insights
from .llm_enhancer import augment_song_details_with_llm

def search_spotify_track(sp_client, track_name, artist_name=None):
    """Searches for a track on Spotify and returns the top result's ID, name, and artist."""
    if not sp_client:
        return None

    query = f"track:{track_name}"
    if artist_name:
        query += f" artist:{artist_name}"
    
    try:
        results = sp_client.search(q=query, type='track', limit=1)
        items = results.get('tracks', {}).get('items', [])
        if items:
            track = items[0]
            track_id = track.get('id')
            name = track.get('name')
            artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
            return {"id": track_id, "name": name, "artists": artists}
        else:
            print(f"Spotify: Could not find track '{track_name}' by '{artist_name if artist_name else 'any artist'}'")
            return None
    except Exception as e:
        print(f"Spotify: Error searching for track '{track_name}': {e}")
        return None

def get_lyrics(genius_client, track_title, artist_name):
    """Fetches lyrics for a song using the Genius API."""
    if not genius_client:
        # print("DEBUG: Genius client not available for get_lyrics.") # Less verbose for now
        return None
    
    # Sanitize title: remove content in parentheses or brackets, often "Live", "Remastered", etc.
    # Also remove common artist suffixes if they accidentally get included in title
    clean_title = re.sub(r'\s*\(.*\)\s*', '', track_title).strip()
    clean_title = re.sub(r'\s*\[.*?\]\s*', '', clean_title).strip()
    # Simple way to remove artist name from title if it's there as a suffix, common in some DBs
    if artist_name and clean_title.lower().endswith(artist_name.lower()):
        clean_title = clean_title[:-(len(artist_name))].strip()
    if not clean_title:
        clean_title = track_title # fallback if cleaning removed everything

    print(f"Genius: Searching for lyrics for '{clean_title}' by '{artist_name}'...")
    try:
        song = genius_client.search_song(clean_title, artist_name)
        if song and song.lyrics:
            print(f"Genius: Found lyrics for '{track_title}'.")
            lyrics_text = song.lyrics
            
            # Remove the first line if it's just the song title and [Intro/Verse/Chorus/etc.]
            lines = lyrics_text.split('\n')
            if len(lines) > 1:
                # Check if the first line contains the song title (case-insensitive) and a bracketed tag
                # This is a common pattern for Genius lyrics headers
                first_line_lower = lines[0].lower()
                title_in_first_line = any(t.lower() in first_line_lower for t in track_title.split() if len(t) > 2) # Check for significant parts of title
                if title_in_first_line and re.search(r'\[(intro|verse|chorus|bridge|outro|pre-chorus|hook|instrumental|refrain|interlude|skit|spoken word|guitar solo|solo).*\]', first_line_lower, re.IGNORECASE):
                    lyrics_text = '\n'.join(lines[1:])
                # Also remove lines that are just the artist and title again
                elif artist_name.lower() in first_line_lower and track_title.lower() in first_line_lower and len(lines[0]) < (len(artist_name) + len(track_title) + 10):
                     lyrics_text = '\n'.join(lines[1:])
            
            # Remove [Chorus], [Verse], etc. and other bracketed metadata
            lyrics_text = re.sub(r'\[.*?\]', '', lyrics_text)
            # Remove specific Genius promotional text patterns
            lyrics_text = re.sub(r'See .*? LiveGet tickets.*', '', lyrics_text, flags=re.IGNORECASE | re.DOTALL)
            lyrics_text = re.sub(r'\d*EmbedShare URLCopyEmbedCopy', '', lyrics_text, flags=re.IGNORECASE | re.DOTALL)
            lyrics_text = re.sub(r'You might also like', '', lyrics_text, flags=re.IGNORECASE)
            lyrics_text = re.sub(r'Translations.*(\n|\s)*(\[.*?\])?', '', lyrics_text, flags=re.IGNORECASE) # Remove translation headers
            lyrics_text = re.sub(r'Source:.*', '', lyrics_text, flags=re.IGNORECASE) # Remove source attributions
            lyrics_text = re.sub(r'\d+ ContributorsTranslations.*Lyrics', '', lyrics_text, flags=re.IGNORECASE | re.DOTALL) # Complex Genius footer

            # Normalize multiple newlines to one, and strip leading/trailing whitespace from lines
            lyrics_text = '\n'.join([line.strip() for line in lyrics_text.split('\n') if line.strip()]) # Keep non-empty lines
            lyrics_text = re.sub(r'(\n\s*){2,}', '\n\n', lyrics_text).strip() # Max two newlines
            
            if not lyrics_text: # If cleaning resulted in empty string
                print(f"Genius: Lyrics for '{track_title}' became empty after cleaning.")
                return None
            return lyrics_text
        else:
            print(f"Genius: Could not find lyrics for '{track_title}'.")
            return None
    except requests.exceptions.Timeout:
        print(f"Genius: Timeout while searching for lyrics for '{track_title}'.")
        return None
    except Exception as e:
        # For debugging, you might want to log the full error: import logging; logging.exception("Genius error")
        print(f"Genius: An unexpected error occurred searching for lyrics for '{track_title}'. Details: {type(e).__name__}")
        return None


def run_recommender():
    print("--- Music Recommender Initializing ---")
    
    # 1. Initialize Spotify, Genius, and Last.fm clients
    sp_client = get_spotify_client(enable_http_debug=False) 
    if not sp_client:
        print("Exiting: Spotify client failed to initialize.")
        return

    genius_client = get_genius_client()
    if not genius_client:
        print("Warning: Genius client failed to initialize. Lyrics will not be fetched.")
        # Depending on requirements, you might choose to exit if Genius is essential
        # For now, we'll allow proceeding without lyrics if Genius fails.

    lastfm_network = get_lastfm_network()
    openai_client = get_openai_client() # Initialize OpenAI client

    # --- User's Liked Songs (Input) ---
    liked_songs_input = []
    print("Enter your liked songs one by one (format: Artist - Title).")
    print("Press Enter on an empty line when you're done.")
    while True:
        user_input_song = input("Song (Artist - Title): ").strip()
        if not user_input_song:
            break
        parts = user_input_song.split('-', 1)
        if len(parts) == 2:
            artist = parts[0].strip()
            title = parts[1].strip()
            liked_songs_input.append((title, artist)) # Store as (title, artist) tuple
            print(f"Added: '{title}' by '{artist}'")
        else:
            print("Invalid format. Please use 'Artist - Title'. Example: Pink Floyd - Wish You Were Here")

    if not liked_songs_input:
        print("No songs entered. Exiting.")
        return

    print("\n--- Processing Liked Songs ---")
    processed_liked_songs_data = [] # This will store dictionaries for each processed song

    for i, (original_title_from_input, original_artist_from_input) in enumerate(liked_songs_input):
        title_part = original_title_from_input
        artist_part = original_artist_from_input
        track_name_query = title_part.strip("'\"") # Use title_part
        artist_name_query = artist_part.strip("'\"") # Use artist_part
        
        # Construct the query string for current_song_data
        current_query_string = f"{track_name_query} - {artist_name_query}"
        current_song_data = {"query": current_query_string, "original_input_title": title_part, "original_input_artist": artist_part, "spotify_info": None, "lyrics": None, "artist_genres": [], "lyrical_insights": None}

        print(f"\nProcessing: '{track_name_query}' by '{artist_name_query}'")
        spotify_track_info = search_spotify_track(sp_client, track_name_query, artist_name_query)
        
        if spotify_track_info and spotify_track_info.get('id'):
            print(f"  Spotify: Found: {spotify_track_info['name']} - {spotify_track_info['artists']} (ID: {spotify_track_info['id']})")
            current_song_data["spotify_info"] = spotify_track_info

            # Fetch artist details to get genres
            try:
                artist_id = sp_client.track(spotify_track_info['id'])['artists'][0]['id']
                artist_info = sp_client.artist(artist_id)
                current_song_data["artist_genres"] = artist_info.get('genres', [])
                print(f"    Artist Genres: {', '.join(current_song_data['artist_genres']) if current_song_data['artist_genres'] else 'N/A'}")
            except Exception as e:
                print(f"  Spotify: Error fetching artist genre details for {spotify_track_info['name']}: {e}")

            # Fetch lyrics if Genius client is available
            if genius_client:
                # Use the primary artist from Spotify for Genius search for better accuracy
                primary_artist_name = spotify_track_info['artists'].split(',')[0].strip()
                lyrics = get_lyrics(genius_client, spotify_track_info['name'], primary_artist_name)
                if lyrics:
                    current_song_data["lyrics"] = lyrics
                    lyrics_insights = None
                    if lyrics and openai_client: # Only analyze if lyrics and client are available
                        print(f"Analyzing lyrics for '{spotify_track_info['name']}' with OpenAI...")
                        lyrics_insights = get_lyrical_insights(lyrics)
                    current_song_data["lyrical_insights"] = lyrics_insights if lyrics_insights else {"themes": [], "sentiments": [], "keywords": [], "overall_summary": "Analysis not performed or failed."}
                # else: # Already printed by get_lyrics
                    # print(f"  Genius: No lyrics found for {spotify_track_info['name']}.")
        else:
            print(f"  Spotify: Could not find a match for '{current_query_string}'.")
        
        processed_liked_songs_data.append(current_song_data)

    # Filter out songs that weren't found on Spotify for further processing
    valid_liked_songs = [s for s in processed_liked_songs_data if s["spotify_info"]]
    if not valid_liked_songs:
        print("\nCould not identify any of your liked songs on Spotify for further processing. Exiting.")
        return

    print(f"\n--- Summary of Successfully Processed Liked Songs ({len(valid_liked_songs)} found) ---")
    for song_data in valid_liked_songs:
        print(f"  Song: {song_data['spotify_info']['name']} - {song_data['spotify_info']['artists']}")
        print(f"    Spotify ID: {song_data['spotify_info']['id']}")
        print(f"    Genres: {', '.join(song_data['artist_genres']) if song_data['artist_genres'] else 'N/A'}")
        if song_data["lyrics"]:
            print(f"    Lyrics: Retrieved (approx. {len(song_data['lyrics'])} chars)")
            insights = song_data.get('lyrical_insights')
            if insights and insights.get('overall_summary') != "Analysis not performed or failed." and insights.get('overall_summary') != "Lyrics were empty.":
                print(f"      Lyrical Summary: {insights.get('overall_summary', 'N/A')}")
                if insights.get('themes'):
                    print(f"      Themes: {', '.join(insights.get('themes'))}")
                if insights.get('sentiments'):
                    print("      Sentiments:")
                    for sent in insights.get('sentiments'):
                        print(f"        - {sent.get('sentiment_type', 'N/A')}: {sent.get('description', 'N/A')}")
                if insights.get('keywords'):
                    print(f"      Keywords: {', '.join(insights.get('keywords'))}")
            elif insights and insights.get('overall_summary') == "Lyrics were empty.":
                 print("      Lyrical Insights: Lyrics were empty, analysis skipped.")
            else:
                print("      Lyrical Insights: Not available or analysis failed.")
        else:
            print("    Lyrics: Not found or Genius client unavailable.")
            print("      Lyrical Insights: Not performed (no lyrics).")

    # --- Deeply Enrich Liked Songs with LLM for Holistic Recommendations ---
    fully_enriched_liked_songs_for_llm = []
    if openai_client and valid_liked_songs:
        print("\n--- Deeply Enriching Liked Songs with LLM for Holistic Recommendations ---")
        for song_details_for_llm_step in valid_liked_songs:
            # Create a shallow copy. If augment_song_details_with_llm or get_rich_lyrical_insights modifies nested dicts in place,
            # this could affect original valid_liked_songs. Consider deepcopy if that's an issue.
            enriched_song_copy = {k: v for k, v in song_details_for_llm_step.items()} 

            song_title_for_log = enriched_song_copy.get('original_input_title', enriched_song_copy.get('spotify_info', {}).get('name', 'Unknown Title'))

            print(f"LLM Enhancer: Augmenting details for '{song_title_for_log}'...")
            try:
                # Extract title and artist for the function call
                current_song_title = enriched_song_copy.get('spotify_name', enriched_song_copy.get('original_input_title', 'Unknown Title'))
                current_artist_name = enriched_song_copy.get('spotify_artists', enriched_song_copy.get('original_input_artist', 'Unknown Artist'))
                
                augmented_attributes = augment_song_details_with_llm(
                    song_title=current_song_title,
                    artist_name=current_artist_name,
                    existing_details=enriched_song_copy, 
                    openai_client=openai_client
                )
                if augmented_attributes:
                    enriched_song_copy.update(augmented_attributes)
                    print(f"LLM Enhancer: Successfully augmented details for '{song_title_for_log}'.")
                else:
                    print(f"LLM Enhancer: No new details augmented for '{song_title_for_log}'.")
            except Exception as e_aug:
                print(f"LLM Enhancer: Error augmenting details for '{song_title_for_log}': {e_aug}")

            if enriched_song_copy.get('lyrics'):
                print(f"LLM Lyrics: Getting rich lyrical insights for '{song_title_for_log}'...")
                try:
                    # Extract title and artist for the function call
                    current_song_title_for_lyrics = enriched_song_copy.get('spotify_name', enriched_song_copy.get('original_input_title', 'Unknown Title'))
                    current_artist_name_for_lyrics = enriched_song_copy.get('spotify_artists', enriched_song_copy.get('original_input_artist', 'Unknown Artist'))

                    rich_insights = get_rich_lyrical_insights(
                        lyrics_text=enriched_song_copy['lyrics'],
                        song_title=current_song_title_for_lyrics,
                        artist_name=current_artist_name_for_lyrics,
                        openai_client=openai_client
                    )
                    if rich_insights:
                        enriched_song_copy['rich_lyrical_analysis'] = rich_insights
                        print(f"LLM Lyrics: Successfully got rich insights for '{song_title_for_log}'.")
                    else:
                        print(f"LLM Lyrics: Could not get rich insights for '{song_title_for_log}'.")
                except Exception as e_lyrics_rich:
                    print(f"LLM Lyrics: Error getting rich insights for '{song_title_for_log}': {e_lyrics_rich}")
            else:
                print(f"Skipping rich lyrical analysis for '{song_title_for_log}' as lyrics are missing.")
            
            fully_enriched_liked_songs_for_llm.append(enriched_song_copy)
    else:
        if not openai_client:
            print("\nSkipping deep LLM enrichment of liked songs: OpenAI client not available.")
        if not valid_liked_songs:
            print("\nSkipping deep LLM enrichment of liked songs: No valid liked songs to process.")
        # Ensure fully_enriched_liked_songs_for_llm is defined for the next section even if skipped
        if 'fully_enriched_liked_songs_for_llm' not in locals(): # Check if it was initialized
             fully_enriched_liked_songs_for_llm = []

    # --- Holistic LLM-Powered Recommendations ---
    if openai_client and fully_enriched_liked_songs_for_llm:
        print("\n--- Generating Holistic LLM-Powered Recommendations ---")
        try:
            holistic_recs = get_holistic_llm_recommendations(
                liked_songs_enriched_details=fully_enriched_liked_songs_for_llm,
                openai_client=openai_client
            )
            if holistic_recs:
                print("\n--- Top Holistic LLM Music Recommendations ---")
                for i, rec in enumerate(holistic_recs):
                    print(f"  {i+1}. {rec.get('title', 'N/A')} by {rec.get('artist', 'N/A')}")
                    print(f"     Justification: {rec.get('justification', 'N/A')}")
            elif holistic_recs == []:
                print("The LLM did not generate any holistic recommendations.")
            else:
                # This case is typically hit if get_holistic_llm_recommendations returns None (error)
                print("Could not generate holistic LLM recommendations due to an internal error or empty response.")
        except Exception as e_holistic:
            print(f"An unexpected error occurred during holistic LLM recommendation generation: {e_holistic}")
    elif not openai_client:
        print("\nSkipping holistic LLM recommendations: OpenAI client not available.")
    elif not fully_enriched_liked_songs_for_llm:
        print("\nSkipping holistic LLM recommendations: No deeply enriched liked songs available.")

    print("\n--- Music Recommender Process Finished --- \n")

if __name__ == "__main__":
    run_recommender()
