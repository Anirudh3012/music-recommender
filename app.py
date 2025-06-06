from flask import Flask, render_template, request, jsonify
import json
from music_recommender.api_clients import get_spotify_client, get_genius_client, get_openai_client, get_lyrics_lyricsovh, get_lastfm_network
from music_recommender.main import search_spotify_track, get_lyrics
from music_recommender.lyrics_analyzer import get_lyrical_insights
from music_recommender.llm_enhancer import augment_song_details_with_llm
from music_recommender.recommender import get_holistic_llm_recommendations

app = Flask(__name__)

# Initialize clients once at startup
sp_client = None
genius_client = None
lastfm_network = None
openai_client = None

def initialize_clients():
    global sp_client, genius_client, lastfm_network, openai_client
    sp_client = get_spotify_client(enable_http_debug=False)
    genius_client = get_genius_client()
    lastfm_network = get_lastfm_network()
    openai_client = get_openai_client()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search_songs')
def search_songs():
    query = request.args.get('query', '').strip()
    if not query or not sp_client:
        return jsonify([])

    try:
        results = sp_client.search(q=query, type='track', limit=10)
        suggestions = []
        for track in results['tracks']['items']:
            # Get album art URL (prefer medium size, fallback to largest available)
            album_art_url = None
            if track['album']['images']:
                # Try to get medium-sized image (usually index 1), fallback to first available
                album_art_url = track['album']['images'][1]['url'] if len(track['album']['images']) > 1 else track['album']['images'][0]['url']

            suggestions.append({
                'id': track['id'],
                'name': track['name'],
                'artist': ', '.join([artist['name'] for artist in track['artists']]),
                'display': f"{', '.join([artist['name'] for artist in track['artists']])} - {track['name']}",
                'album_art_url': album_art_url
            })
        return jsonify(suggestions)
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify([])

@app.route('/get_album_art')
def get_album_art():
    artist = request.args.get('artist', '').strip()
    title = request.args.get('title', '').strip()

    if not artist or not title or not sp_client:
        return jsonify({'album_art_url': None})

    try:
        # Search for the track on Spotify to get album art
        search_query = f"artist:{artist} track:{title}"
        results = sp_client.search(q=search_query, type='track', limit=1)

        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            album_images = track['album']['images']
            if album_images:
                # Get the medium-sized image (usually index 1, or fallback to first)
                album_art_url = album_images[1]['url'] if len(album_images) > 1 else album_images[0]['url']
                return jsonify({'album_art_url': album_art_url})

        return jsonify({'album_art_url': None})
    except Exception as e:
        print(f"Album art error for {artist} - {title}: {e}")
        return jsonify({'album_art_url': None})

def generate_streaming_links(artist, title):
    """Generate streaming service links for a song"""
    import urllib.parse

    # Clean up artist and title for URL encoding
    clean_artist = artist.replace(' & ', ' ').replace('&', 'and')
    clean_title = title

    # URL encode for safe usage in URLs
    encoded_artist = urllib.parse.quote_plus(clean_artist)
    encoded_title = urllib.parse.quote_plus(clean_title)
    encoded_query = urllib.parse.quote_plus(f"{clean_artist} {clean_title}")

    links = {
        'spotify': f"https://open.spotify.com/search/{encoded_query}",
        'apple_music': f"https://music.apple.com/search?term={encoded_query}",
        'youtube': f"https://www.youtube.com/results?search_query={encoded_query}"
    }

    # Try to get exact Spotify link if possible
    if sp_client:
        try:
            search_query = f"artist:{clean_artist} track:{clean_title}"
            results = sp_client.search(q=search_query, type='track', limit=1)
            if results['tracks']['items']:
                track = results['tracks']['items'][0]
                spotify_url = track['external_urls'].get('spotify')
                if spotify_url:
                    links['spotify'] = spotify_url
        except Exception as e:
            print(f"Could not get exact Spotify link for {artist} - {title}: {e}")

    return links

@app.route('/create_spotify_playlist', methods=['POST'])
def create_spotify_playlist():
    data = request.get_json()
    playlist_name = data.get('playlist_name', 'Music Recommender Playlist')
    recommendations = data.get('recommendations', [])
    
    if not recommendations or not sp_client:
        return jsonify({'error': 'No recommendations provided or Spotify client unavailable'})
    
    try:
        # Get current user
        user_info = sp_client.current_user()
        user_id = user_info['id']
        
        # Create playlist
        playlist = sp_client.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=False,
            description='Generated by Music Recommender based on your favorite songs'
        )
        
        # Search and add tracks
        track_uris = []
        not_found = []
        
        for rec in recommendations:
            try:
                # Search for the track
                search_query = f"artist:{rec['artist']} track:{rec['title']}"
                results = sp_client.search(q=search_query, type='track', limit=1)
                
                if results['tracks']['items']:
                    track_uri = results['tracks']['items'][0]['uri']
                    track_uris.append(track_uri)
                else:
                    not_found.append(f"{rec['artist']} - {rec['title']}")
            except Exception as e:
                print(f"Error searching for {rec['artist']} - {rec['title']}: {e}")
                not_found.append(f"{rec['artist']} - {rec['title']}")
        
        # Add tracks to playlist in batches of 100
        if track_uris:
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]
                sp_client.playlist_add_items(playlist['id'], batch)
        
        return jsonify({
            'success': True,
            'playlist_url': playlist['external_urls']['spotify'],
            'playlist_name': playlist['name'],
            'tracks_added': len(track_uris),
            'tracks_not_found': not_found
        })
        
    except Exception as e:
        print(f"Spotify playlist creation error: {e}")
        return jsonify({'error': f'Failed to create Spotify playlist: {str(e)}'})

@app.route('/get_apple_music_auth')
def get_apple_music_auth():
    # This endpoint provides the necessary information for Apple Music authentication
    # Apple Music uses MusicKit JS which requires client-side authentication
    return jsonify({
        'message': 'Apple Music integration requires MusicKit JS authentication on the client side',
        'documentation': 'https://developer.apple.com/documentation/musickit/musickit_js'
    })

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    data = request.get_json()
    selected_songs = data.get('songs', [])

    if not selected_songs or not openai_client:
        return jsonify({'error': 'No songs provided or OpenAI client unavailable'})

    try:
        # Process selected songs
        processed_songs = []
        for song in selected_songs:
            spotify_info = {
                'id': song['id'],
                'name': song['name'],
                'artists': song['artist']
            }

            # Get artist genres
            try:
                track_details = sp_client.track(song['id'])
                artist_id = track_details['artists'][0]['id']
                artist_info = sp_client.artist(artist_id)
                artist_genres = artist_info.get('genres', [])
            except:
                artist_genres = []

            # Get lyrics from LyricsOVH (free alternative)
            lyrics = None
            try:
                lyrics = get_lyrics_lyricsovh(song['artist'], song['name'])
            except:
                pass

            song_data = {
                'original_input_title': song['name'],
                'original_input_artist': song['artist'],
                'spotify_info': spotify_info,
                'artist_genres': artist_genres,
                'lyrics': lyrics,
                'lyrical_insights': None
            }

            # Analyze lyrics if available
            if lyrics and openai_client:
                try:
                    insights = get_lyrical_insights(lyrics)
                    song_data['lyrical_insights'] = insights
                except:
                    pass

            processed_songs.append(song_data)

        # Enrich songs with LLM
        enriched_songs = []
        for song_data in processed_songs:
            try:
                augmented = augment_song_details_with_llm(
                    song_title=song_data['original_input_title'],
                    artist_name=song_data['original_input_artist'],
                    existing_details=song_data,
                    openai_client=openai_client
                )
                if augmented:
                    song_data.update(augmented)
            except:
                pass
            enriched_songs.append(song_data)

        # Generate recommendations
        recommendations = get_holistic_llm_recommendations(
            liked_songs_enriched_details=enriched_songs,
            openai_client=openai_client
        )

        if recommendations:
            # Add streaming links to each recommendation
            for rec in recommendations:
                if 'artist' in rec and 'title' in rec:
                    rec['streaming_links'] = generate_streaming_links(rec['artist'], rec['title'])

            return jsonify({'recommendations': recommendations})
        else:
            return jsonify({'error': 'Could not generate recommendations'})

    except Exception as e:
        print(f"Recommendation error: {e}")
        return jsonify({'error': f'An error occurred: {str(e)}'})

if __name__ == '__main__':
    initialize_clients()
    app.run(host='0.0.0.0', port=3000, debug=True)