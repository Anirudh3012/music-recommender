# Music Recommender Project

A Python-based application to generate personalized music playlists based on user's liked songs.
It analyzes lyrical content, audio features, artist, and label information.

## Setup

1.  **Clone the repository (if applicable).**
2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate 
    # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure API Keys:**
    *   Rename `music_recommender/config.py.template` to `music_recommender/config.py`.
    *   Fill in your API keys in `music_recommender/config.py`.
        *   OpenAI API Key
        *   Spotify Client ID
        *   Spotify Client Secret
        *   Spotify Redirect URI (e.g., http://localhost:8888/callback - ensure this is added to your app settings on the Spotify Developer Dashboard)
        *   Genius API Access Token (Optional, if using LyricsGenius)

## Usage

```bash
python music_recommender/main.py
```
