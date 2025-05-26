
from flask import Flask, render_template, request, jsonify
import json
from music_recommender.api_clients import get_spotify_client, get_genius_client, get_lastfm_network, get_openai_client
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
            suggestions.append({
                'id': track['id'],
                'name': track['name'],
                'artist': ', '.join([artist['name'] for artist in track['artists']]),
                'display': f"{', '.join([artist['name'] for artist in track['artists']])} - {track['name']}"
            })
        return jsonify(suggestions)
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify([])

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
            
            # Get lyrics
            lyrics = None
            if genius_client:
                primary_artist = song['artist'].split(',')[0].strip()
                lyrics = get_lyrics(genius_client, song['name'], primary_artist)
            
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
            return jsonify({'recommendations': recommendations})
        else:
            return jsonify({'error': 'Could not generate recommendations'})
            
    except Exception as e:
        print(f"Recommendation error: {e}")
        return jsonify({'error': f'An error occurred: {str(e)}'})

if __name__ == '__main__':
    initialize_clients()
    app.run(host='0.0.0.0', port=5000, debug=True)
