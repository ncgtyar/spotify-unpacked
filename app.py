from flask import *
import requests
import urllib.parse
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET')

# Home page
@app.route('/')
def home():
    return render_template('index.html')

# Login transfer page
@app.route('/login')
def login():
    encoded_redirect = urllib.parse.quote(REDIRECT_URI, safe='')
    scope = "user-top-read user-read-currently-playing user-read-private user-read-email"
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={encoded_redirect}"
        f"&scope={scope}"
    )
    return render_template('login.html', auth_url=auth_url)

# Inter page in between login and stats, so we can refresh the stats page
@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_res = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    token_data = token_res.json()
    access_token = token_data.get('access_token')
    if not access_token:
        return "Failed to login. Please try again."
    
    # Store token so we can refresh the page
    session['access_token'] = access_token
    return redirect(url_for('stats'))

# Stats page
@app.route('/stats')
def stats():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))
        
    # Default to long term
    term = request.args.get('term', 'long_term') 
    headers = {"Authorization": f"Bearer {access_token}"}
    user_profile = {"name": "Spotify User", "image": ""} # Default if error
    try:
        user_res = requests.get("https://api.spotify.com/v1/me", headers=headers)
        if user_res.status_code == 200:
            u_data = user_res.json()
            user_profile["name"] = u_data.get('display_name') or u_data.get('id') or "Explorer"
            images = u_data.get('images', [])
            if isinstance(images, list) and len(images) > 0:
                user_profile["image"] = images[0].get('url', '')
    except Exception as e:
        print(f"Profile error: {e}")

    # Artists
    artists_res = requests.get(f"https://api.spotify.com/v1/me/top/artists?limit=50&time_range={term}", headers=headers)
    artists_data = artists_res.json().get('items', []) if artists_res.status_code == 200 else []
    formatted_artists = []
    for artist in artists_data:
        img_url = artist['images'][0]['url'] if artist.get('images') else ""
        formatted_artists.append({
            "name": artist.get('name'),
            "image": img_url,
            "info": ", ".join(artist.get('genres', [])[:2]).title()
        })

    # Songs + Albums
    tracks_res = requests.get(f"https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={term}", headers=headers)
    tracks_data = tracks_res.json().get('items', []) if tracks_res.status_code == 200 else []
    formatted_tracks = []
    formatted_albums = []
    seen_albums = set()

    # Loop through songs to build album ranking (native album ranking does not exist in the API)
    for track in tracks_data:
        track_img = track['album']['images'][0]['url'] if track['album'].get('images') else ""
        formatted_tracks.append({"name": track.get('name'), "image": track_img, "info": track['artists'][0]['name']})
        album = track.get('album', {})
        if album.get('id') not in seen_albums:
            formatted_albums.append({
                "name": album.get('name'), 
                "image": album['images'][0]['url'] if album.get('images') else "", 
                "info": album['artists'][0]['name']
            })
            seen_albums.add(album['id'])

    now_playing = None # Default if error
    try:
        np_res = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
        if np_res.status_code == 200:
            data = np_res.json()
            if data and data.get('item'):
                now_playing = {
                    "name": data['item']['name'],
                    "artist": data['item']['artists'][0]['name'],
                    "image": data['item']['album']['images'][0]['url']
                }
    except: pass

    return render_template('stats.html',
        user=user_profile,
        artists=formatted_artists,
        albums=formatted_albums[:50], 
        tracks=formatted_tracks,
        now_playing=now_playing,
        current_term=term)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    #0.0.0.0 variable allows listening to outside of the local machine, useful for testing on mobile devices etc.