import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import lyricsgenius
import logging
import http.client as http_client
import openai # Added OpenAI import
import inspect # For debugging
import traceback # For detailed error reporting
import httpx # To check version and for OpenAI client

# Attempt to import configuration details
# This allows the script to run even if config.py is not yet fully set up,
# though API calls will fail without valid credentials.
try:
    from .config import (
        SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI, 
        GENIUS_ACCESS_TOKEN, OPENAI_API_KEY,
        LASTFM_API_KEY, LASTFM_SHARED_SECRET
    )
except ImportError:
    print("Warning: Could not import Spotify configuration from .config module.")
    print("Ensure config.py exists in the 'music_recommender' directory and contains your Spotify API credentials.")
    SPOTIPY_CLIENT_ID = None
    SPOTIPY_CLIENT_SECRET = None
    SPOTIPY_REDIRECT_URI = None
    GENIUS_ACCESS_TOKEN = None
    OPENAI_API_KEY = None # Placeholder for when we add OpenAI client
    LASTFM_API_KEY = None
    LASTFM_SHARED_SECRET = None

# Define the scopes your application will need
# Scopes determine what actions your app can perform on behalf of the user.
# - user-library-read: Read user's saved tracks and albums.
# - user-top-read: Read user's top artists and tracks.
# - playlist-modify-public: Create, delete and modify public playlists.
# - playlist-modify-private: Create, delete and modify private playlists.
# - user-follow-read: Check if users are following other artists or users.
# Add more scopes as needed for your project features.
SCOPES = [
    "user-library-read",
    "user-top-read",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-read-private",
    # "user-follow-read", # Example: if you want to check followed artists
]

def get_spotify_client(enable_http_debug=False):
    """Initializes and returns an authenticated Spotify client.
    
    Args:
        enable_http_debug (bool): If True, enables verbose HTTP debug logging.
    """
    if enable_http_debug:
        print("DEBUG: Enabling HTTP debug logging for Spotify requests.")
        http_client.HTTPConnection.debuglevel = 1
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True
    else:
        # Ensure debuglevel is off if not explicitly enabled
        http_client.HTTPConnection.debuglevel = 0
        # Potentially disable other loggers if they were set by a previous call
        logging.getLogger("requests.packages.urllib3").setLevel(logging.WARNING)

    """
    Authenticates with the Spotify API using OAuth and returns a Spotipy client instance.

    The function uses credentials (Client ID, Client Secret, Redirect URI)
    defined in the config.py file. It will prompt the user for authorization
    via a web browser if a token is not already cached or if it's invalid.

    Returns:
        spotipy.Spotify: An authenticated Spotipy client instance.
        None: If authentication fails or configuration is missing.
    """
    if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI]):
        print("Error: Spotify API credentials (Client ID, Secret, Redirect URI) are not configured.")
        print("Please check your music_recommender/config.py file.")
        return None

    # The cache_path ensures the token is stored within our project directory,
    # making it easier to manage and keep out of version control if desired.
    # It's good practice to add ".cache*" to your .gitignore file.
    cache_path = os.path.join(os.path.dirname(__file__), ".spotify_token_cache")
    
    try:
        auth_manager = SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=" ".join(SCOPES),  # Scopes should be a space-separated string
            cache_path=cache_path,
            show_dialog=True, # Forces the auth dialog to show every time, useful for testing, set to False for better UX later
            open_browser=False  # Prevents auto-opening browser, prints URL to console
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        # Test if authentication was successful by making a simple API call
        try:
            sp.current_user() # Example call
            print("Successfully authenticated with Spotify.")
            return sp
        except spotipy.exceptions.SpotifyException as e:
            print(f"Spotify authentication error after creating client: {e}")
            if "User not registered in the Developer Dashboard" in str(e):
                print("Hint: Ensure the Spotify account you are logging in with is added as a 'User' in your app's settings on the Spotify Developer Dashboard (Users and Access section).")
            return None

    except Exception as e:
        print(f"An error occurred during Spotify authentication: {e}")
        return None

# --- Genius API Client ---
def get_genius_client():
    """
    Initializes and returns a LyricsGenius client instance.

    Uses the GENIUS_ACCESS_TOKEN defined in config.py.

    Returns:
        lyricsgenius.Genius: An initialized LyricsGenius client instance.
        None: If the access token is missing or an error occurs.
    """
    if not GENIUS_ACCESS_TOKEN:
        print("Error: Genius API Access Token is not configured.")
        print("Please check your music_recommender/config.py file.")
        return None
    
    try:
        # You can adjust verbosity and other options as needed
        # timeout: seconds to wait for API response
        # retries: number of retries for failed requests
        # verbose: True to print status messages, False for quiet operation
        genius = lyricsgenius.Genius(GENIUS_ACCESS_TOKEN, verbose=False, remove_section_headers=True, timeout=15, retries=3)
        print("Successfully initialized Genius client.")
        return genius
    except Exception as e:
        print(f"An error occurred during Genius client initialization: {e}")
        return None

# --- Last.fm API Client ---
import pylast

def get_lastfm_network():
    """
    Initializes and returns a Last.fm Network object for API interaction.

    Uses LASTFM_API_KEY and LASTFM_SHARED_SECRET from config.py.

    Returns:
        pylast.LastFMNetwork: An initialized LastFMNetwork instance.
        None: If credentials are missing or an error occurs.
    """
    if not all([LASTFM_API_KEY, LASTFM_SHARED_SECRET]):
        print("Error: Last.fm API Key or Shared Secret are not configured.")
        print("Please check your music_recommender/config.py file.")
        return None
    
    try:
        network = pylast.LastFMNetwork(
            api_key=LASTFM_API_KEY,
            api_secret=LASTFM_SHARED_SECRET,
        )
        print("Successfully initialized Last.fm network client.")
        return network
    except Exception as e:
        print(f"An error occurred during Last.fm network initialization: {e}")
        return None

# --- OpenAI Client ---
def get_openai_client():
    if not OPENAI_API_KEY:
        print("Error: OpenAI API Key is not configured in config.py.")
        return None
    try:
        # Ensure you are using the correct way to initialize the client
        # based on your openai library version. For v1.0.0 and later:
        print(f"DEBUG: OpenAI module path: {openai.__file__}")
        print(f"DEBUG: OpenAI class: {str(openai.OpenAI)}")
        print(f"DEBUG: OpenAI class __init__ signature: {str(inspect.signature(openai.OpenAI.__init__))}")
        custom_httpx_client = httpx.Client()
        client = openai.OpenAI(api_key=OPENAI_API_KEY, http_client=custom_httpx_client)
        # print("Successfully initialized OpenAI client.") # Keep this quiet for now, main.py will confirm
        return client
    except Exception as e:
        print(f"ERROR: httpx version: {httpx.__version__}")
        print(f"An error occurred during OpenAI client initialization: {e}")
        print("--- Full Traceback --- ")
        traceback.print_exc()
        print("--- End Traceback --- ")
        return None

if __name__ == '__main__':
    # This is for testing the authentication directly if you run this file.
    print("--- Testing Spotify Authentication ---")
    # Pass True to enable HTTP debug logging for this test run
    spotify_client = get_spotify_client(enable_http_debug=True)
    if spotify_client:
        user_profile = spotify_client.current_user()
        if user_profile:
            print(f"Spotify: Authenticated as: {user_profile.get('display_name', 'N/A')} (ID: {user_profile.get('id', 'N/A')})")
        else:
            print("Spotify: Could not retrieve user profile, but client object was created.")
    else:
        print("Spotify: Failed to get client.")

    print("\n--- Testing Genius Client Initialization ---")
    genius_client = get_genius_client()
    if genius_client:
        # You could add a small test here, e.g., search for an artist, but be mindful of API calls.
        # For now, successful initialization is enough.
        print("Genius: Client initialized.")
    else:
        print("Genius: Failed to initialize client.")
