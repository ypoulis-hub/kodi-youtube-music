"""Direct YouTube Music Innertube API client using only Python stdlib.

Compatible with Python 3.8+ (Kodi 21).
No external dependencies required.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import os
import time
import xbmc

# Innertube API endpoints
BASE_URL = 'https://music.youtube.com/youtubei/v1'
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'

# Innertube API key for WEB_REMIX (YouTube Music)
INNERTUBE_API_KEY = 'AIzaSyC9XL3ZjWddXya6X74dJoCTL-WEYFDNX30'

# Innertube client config for YouTube Music (web)
INNERTUBE_CLIENT = {
    'clientName': 'WEB_REMIX',
    'clientVersion': '1.20250312.01.00',
    'gl': 'US',
    'hl': 'en',
}

# OAuth client credentials — user must provide their own via Settings
# (Google Cloud project with YouTube Data API v3 enabled)
OAUTH_CLIENT_ID = None
OAUTH_CLIENT_SECRET = None

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def log(msg):
    xbmc.log('[YTMusic] innertube: {}'.format(msg), xbmc.LOGINFO)


def _make_context():
    return {
        'client': INNERTUBE_CLIENT.copy(),
        'user': {'lockedSafetyMode': False},
    }


def _post(endpoint, body, auth_header=None, cookie_header=None, page_id=None):
    """Make a POST request to the Innertube API."""
    url = '{}/{}?key={}&prettyPrint=false'.format(BASE_URL, endpoint, INNERTUBE_API_KEY)

    if 'context' not in body:
        body['context'] = _make_context()

    data = json.dumps(body).encode('utf-8')

    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Referer', 'https://music.youtube.com/')
    req.add_header('Origin', 'https://music.youtube.com')
    req.add_header('X-Origin', 'https://music.youtube.com')
    req.add_header('X-YouTube-Client-Name', '67')
    req.add_header('X-YouTube-Client-Version', INNERTUBE_CLIENT['clientVersion'])

    if cookie_header:
        req.add_header('Cookie', cookie_header)

    if auth_header:
        req.add_header('Authorization', auth_header)
        req.add_header('X-Goog-AuthUser', '0')

    if page_id:
        req.add_header('X-Goog-PageId', page_id)

    log('POST {} auth={} cookies={} page_id={}'.format(endpoint, bool(auth_header), bool(cookie_header), bool(page_id)))

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        log('HTTP {} for {}: {}'.format(e.code, endpoint, err_body[:500]))
        raise RuntimeError('API error {}: {}'.format(e.code, err_body[:200]))
    except urllib.error.URLError as e:
        raise RuntimeError('Network error: {}'.format(e.reason))


class OAuthManager:
    """Handle OAuth token storage and refresh."""

    def __init__(self, token_file, client_id, client_secret):
        self.token_file = token_file
        self.client_id = client_id
        self.client_secret = client_secret
        self._token_data = None

    def is_authenticated(self):
        return os.path.isfile(self.token_file)

    def has_credentials(self):
        return bool(self.client_id and self.client_secret)

    def get_access_token(self):
        """Return a valid access token, refreshing if needed."""
        data = self._load()
        if not data:
            return None

        # Check if expired (with 60s buffer)
        expires_at = data.get('expires_at', 0)
        if time.time() > expires_at - 60:
            data = self._refresh(data)
            if not data:
                return None

        return data.get('access_token')

    def start_device_flow(self):
        """Start OAuth device flow. Returns (verification_url, user_code, device_code)."""
        body = json.dumps({
            'client_id': self.client_id,
            'scope': 'https://www.googleapis.com/auth/youtube',
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://oauth2.googleapis.com/device/code',
            data=body, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        return (
            result['verification_url'],
            result['user_code'],
            result['device_code'],
            result.get('interval', 5),
            result.get('expires_in', 1800),
        )

    def poll_for_token(self, device_code, interval=5, timeout=300):
        """Poll until user completes auth or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(interval)

            body = json.dumps({
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'device_code': device_code,
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            }).encode('utf-8')

            req = urllib.request.Request(
                OAUTH_TOKEN_URL, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    token_data = json.loads(resp.read().decode('utf-8'))

                # Success
                token_data['expires_at'] = time.time() + token_data.get('expires_in', 3600)
                self._save(token_data)
                return True

            except urllib.error.HTTPError as e:
                err_body = json.loads(e.read().decode('utf-8'))
                error = err_body.get('error', '')
                if error == 'authorization_pending':
                    continue
                elif error == 'slow_down':
                    interval += 2
                    continue
                else:
                    log('OAuth poll error: {}'.format(err_body))
                    return False

        return False

    def _load(self):
        if self._token_data:
            return self._token_data
        if not os.path.isfile(self.token_file):
            return None
        try:
            with open(self.token_file, 'r') as f:
                self._token_data = json.load(f)
            return self._token_data
        except Exception as e:
            log('Failed to load token: {}'.format(e))
            return None

    def _save(self, data):
        self._token_data = data
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        with open(self.token_file, 'w') as f:
            json.dump(data, f)

    def _refresh(self, data):
        refresh_token = data.get('refresh_token')
        if not refresh_token:
            return None

        body = json.dumps({
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }).encode('utf-8')

        req = urllib.request.Request(
            OAUTH_TOKEN_URL, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                new_data = json.loads(resp.read().decode('utf-8'))

            new_data['refresh_token'] = refresh_token
            new_data['expires_at'] = time.time() + new_data.get('expires_in', 3600)
            self._save(new_data)
            return new_data
        except Exception as e:
            log('Token refresh failed: {}'.format(e))
            return None


class YTMusicClient:
    """YouTube Music API client using Innertube with cookie auth."""

    def __init__(self, auth_header_fn=None, cookie_header_fn=None, page_id=None):
        self._auth_header_fn = auth_header_fn
        self._cookie_header_fn = cookie_header_fn
        self._page_id = page_id

    def _call(self, endpoint, body):
        auth = self._auth_header_fn() if self._auth_header_fn else None
        cookies = self._cookie_header_fn() if self._cookie_header_fn else None
        return _post(endpoint, body, auth_header=auth, cookie_header=cookies, page_id=self._page_id)

    # ── Browse ──

    def get_home(self):
        """Get home page content, following continuations."""
        body = {'browseId': 'FEmusic_home'}
        resp = self._call('browse', body)
        sections = self._parse_browse_sections(resp)

        # Follow continuations to get more sections (e.g. "Mixed for you")
        tab = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                'tabs', 0, 'tabRenderer', 'content', 'sectionListRenderer'])
        if tab:
            conts = tab.get('continuations', [])
            for _ in range(3):  # Max 3 continuation pages
                if not conts:
                    break
                ctoken = self._nav(conts, [0, 'nextContinuationData', 'continuation'])
                if not ctoken:
                    break
                cont_body = {'continuation': ctoken}
                cont_resp = self._call('browse', cont_body)
                cont_data = self._nav(cont_resp, ['continuationContents', 'sectionListContinuation'], {})
                more_sections = self._parse_continuation_sections(cont_data)
                sections.extend(more_sections)
                conts = cont_data.get('continuations', [])

        return sections

    def get_library_playlists(self, limit=25):
        body = {'browseId': 'FEmusic_liked_playlists'}
        resp = self._call('browse', body)
        return self._parse_playlist_items(resp)

    def get_library_songs(self, limit=25):
        body = {'browseId': 'FEmusic_liked_videos'}
        resp = self._call('browse', body)
        return self._parse_liked_songs(resp)

    def get_library_albums(self, limit=25):
        body = {'browseId': 'FEmusic_liked_albums'}
        resp = self._call('browse', body)
        return self._parse_album_items(resp)

    def get_library_artists(self, limit=25):
        body = {'browseId': 'FEmusic_library_corpus_track_artists'}
        resp = self._call('browse', body)
        return self._parse_artist_items(resp)

    def get_liked_songs(self, limit=100):
        body = {'browseId': 'VLLM'}
        resp = self._call('browse', body)
        return self._parse_playlist_tracks(resp)

    def get_playlist(self, playlist_id, limit=100):
        if not playlist_id.startswith('VL'):
            playlist_id = 'VL' + playlist_id
        body = {'browseId': playlist_id}
        resp = self._call('browse', body)
        return self._parse_playlist_tracks(resp)

    def get_album(self, browse_id):
        body = {'browseId': browse_id}
        resp = self._call('browse', body)
        return self._parse_album_tracks(resp)

    def get_artist(self, channel_id):
        # Strip MPLA prefix — library artists use MPLAUC... but the full
        # artist page (with albums/singles sections) requires just UC...
        if channel_id.startswith('MPLA'):
            channel_id = channel_id[4:]
        body = {'browseId': channel_id}
        resp = self._call('browse', body)
        return self._parse_artist_page(resp)

    def get_history(self):
        body = {'browseId': 'FEmusic_history'}
        resp = self._call('browse', body)
        return self._parse_history(resp)

    # ── Search ──

    def search(self, query, filter_type=None, limit=50):
        body = {'query': query}
        if filter_type:
            param_map = {
                'songs': 'EgWKAQIIAWoOEAMQBBAJEAoQBRAREBU%3D',
                'albums': 'EgWKAQIYAWoOEAMQBBAJEAoQBRAREBU%3D',
                'artists': 'EgWKAQIgAWoOEAMQBBAJEAoQBRAREBU%3D',
                'playlists': 'EgWKAQIoAWoOEAMQBBAJEAoQBRAREBU%3D',
            }
            if filter_type in param_map:
                body['params'] = param_map[filter_type]

        resp = self._call('search', body)
        results, ctoken = self._parse_search_results(resp, filter_type)

        # Follow continuations to get more results
        while ctoken and len(results) < limit:
            cont_body = {'continuation': ctoken}
            cont_resp = self._call('search', cont_body)
            more, ctoken = self._parse_search_continuation(cont_resp, filter_type)
            results.extend(more)

        return results[:limit]

    # ── Playback ──

    def get_stream_url(self, video_id):
        """Get a playable audio stream URL for a video ID."""
        # Use the Android Music client for direct stream URLs
        body = {
            'context': {
                'client': {
                    'clientName': 'ANDROID_MUSIC',
                    'clientVersion': '6.42.52',
                    'androidSdkVersion': 30,
                    'gl': 'US',
                    'hl': 'en',
                },
                'user': {'lockedSafetyMode': False},
            },
            'videoId': video_id,
            'playbackContext': {
                'contentPlaybackContext': {
                    'signatureTimestamp': 20073,
                }
            },
            'racyCheckOk': True,
            'contentCheckOk': True,
        }

        token = self.oauth.get_access_token()
        resp = _post('player', body, auth_token=token)

        status = resp.get('playabilityStatus', {})
        if status.get('status') != 'OK':
            reason = status.get('reason', 'Unknown playback error')
            raise RuntimeError('Playback blocked: {}'.format(reason))

        # Find best audio stream
        formats = resp.get('streamingData', {}).get('adaptiveFormats', [])
        audio_formats = [f for f in formats if f.get('mimeType', '').startswith('audio/')]

        if not audio_formats:
            # Fall back to regular formats
            formats = resp.get('streamingData', {}).get('formats', [])
            audio_formats = formats

        if not audio_formats:
            raise RuntimeError('No audio streams found for {}'.format(video_id))

        # Sort by bitrate, pick highest
        audio_formats.sort(key=lambda f: f.get('bitrate', 0), reverse=True)
        best = audio_formats[0]

        stream_url = best.get('url')
        if not stream_url:
            # May need to decipher signatureCipher — for Premium accounts
            # with OAuth this usually isn't needed
            cipher = best.get('signatureCipher', '')
            if cipher:
                params = dict(urllib.parse.parse_qsl(cipher))
                stream_url = params.get('url')
                # Note: without signature deciphering this may not work
                # for non-Premium content, but Premium OAuth should get direct URLs

        if not stream_url:
            raise RuntimeError('Could not extract stream URL')

        info = {
            'title': resp.get('videoDetails', {}).get('title', ''),
            'artist': resp.get('videoDetails', {}).get('author', ''),
            'duration': int(resp.get('videoDetails', {}).get('lengthSeconds', 0)),
            'bitrate': best.get('bitrate', 0),
            'mime': best.get('mimeType', ''),
        }

        return stream_url, info

    def get_watch_playlist(self, video_id):
        """Get radio/up-next queue for a track."""
        body = {
            'videoId': video_id,
            'isAudioOnly': True,
            'tunerSettingValue': 'AUTOMIX_SETTING_NORMAL',
            'playlistId': 'RDAMVM{}'.format(video_id),
        }
        resp = self._call('next', body)
        return self._parse_watch_playlist(resp)

    # ── Parsing helpers ──

    def _nav(self, data, keys, default=None):
        """Safely navigate nested dicts/lists."""
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and isinstance(key, int) and key < len(data):
                data = data[key]
            else:
                return default
            if data is None:
                return default
        return data

    def _get_text(self, obj):
        """Extract text from a 'runs' text object."""
        if not obj:
            return ''
        if isinstance(obj, str):
            return obj
        runs = obj.get('runs', [])
        if runs:
            return ''.join(r.get('text', '') for r in runs)
        return obj.get('text', obj.get('simpleText', ''))

    def _get_thumbnails(self, obj):
        """Extract thumbnail list."""
        if not obj:
            return []
        thumbs = obj.get('thumbnails', [])
        if not thumbs and isinstance(obj, dict):
            thumbs = self._nav(obj, ['thumbnail', 'thumbnails'], [])
        return thumbs

    def _get_best_thumb(self, thumbs):
        if not thumbs:
            return ''
        best = max(thumbs, key=lambda t: t.get('width', 0) * t.get('height', 0))
        return best.get('url', '')

    def _parse_browse_sections(self, resp):
        """Parse home/browse response into sections."""
        sections = []
        tab = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                'tabs', 0, 'tabRenderer', 'content',
                                'sectionListRenderer', 'contents'], [])
        for section in tab:
            shelf = self._nav(section, ['musicShelfRenderer'])
            if not shelf:
                shelf = self._nav(section, ['musicCarouselShelfRenderer'])
            if not shelf:
                continue

            title = self._get_text(self._nav(shelf, ['header', 'musicCarouselShelfBasicHeaderRenderer', 'title']))
            if not title:
                title = self._get_text(self._nav(shelf, ['header', 'musicShelfRenderer', 'title']))

            items = []
            for content in shelf.get('contents', []):
                item = self._parse_music_item(content)
                if item:
                    items.append(item)

            if items:
                sections.append({'title': title or 'Untitled', 'contents': items})

        return sections

    def _parse_continuation_sections(self, cont_data):
        """Parse sections from a continuation response."""
        sections = []
        for section in cont_data.get('contents', []):
            shelf = self._nav(section, ['musicShelfRenderer'])
            if not shelf:
                shelf = self._nav(section, ['musicCarouselShelfRenderer'])
            if not shelf:
                continue

            title = self._get_text(self._nav(shelf, ['header', 'musicCarouselShelfBasicHeaderRenderer', 'title']))
            if not title:
                title = self._get_text(self._nav(shelf, ['header', 'musicShelfRenderer', 'title']))

            items = []
            for content in shelf.get('contents', []):
                item = self._parse_music_item(content)
                if item:
                    items.append(item)

            if items:
                sections.append({'title': title or 'Untitled', 'contents': items})

        return sections

    def _parse_music_item(self, content):
        """Parse a single music item from various renderer types."""
        for renderer_key in ['musicTwoRowItemRenderer', 'musicResponsiveListItemRenderer',
                             'musicTwoColumnItemRenderer']:
            renderer = content.get(renderer_key)
            if renderer:
                return self._extract_item(renderer)
        return None

    def _extract_item(self, renderer):
        """Extract song/album/artist/playlist info from a renderer."""
        title = self._get_text(self._nav(renderer, ['title']))
        if not title:
            cols = self._nav(renderer, ['flexColumns'], [])
            if cols:
                title = self._get_text(self._nav(cols, [0, 'musicResponsiveListItemFlexColumnRenderer', 'text']))

        subtitle = self._get_text(self._nav(renderer, ['subtitle']))

        thumbs = self._get_thumbnails(self._nav(renderer, ['thumbnailRenderer', 'musicThumbnailRenderer', 'thumbnail']))
        if not thumbs:
            thumbs = self._get_thumbnails(self._nav(renderer, ['thumbnail', 'musicThumbnailRenderer', 'thumbnail']))

        # Extract navigation endpoint for IDs
        nav = self._nav(renderer, ['navigationEndpoint'])
        video_id = self._nav(nav, ['watchEndpoint', 'videoId'])
        browse_id = self._nav(nav, ['browseEndpoint', 'browseId'])
        playlist_id = self._nav(nav, ['watchEndpoint', 'playlistId'])

        # Also check overlay for playback
        if not video_id:
            video_id = self._nav(renderer, ['overlay', 'musicItemThumbnailOverlayRenderer',
                                             'content', 'musicPlayButtonRenderer',
                                             'playNavigationEndpoint', 'watchEndpoint', 'videoId'])

        item = {
            'title': title or '',
            'artists': [{'name': subtitle}] if subtitle else [],
            'thumbnails': thumbs,
        }
        if video_id:
            item['videoId'] = video_id
        if browse_id:
            item['browseId'] = browse_id
        if playlist_id:
            item['playlistId'] = playlist_id

        return item

    def _parse_playlist_items(self, resp):
        """Parse library playlists response."""
        items = []
        contents = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'sectionListRenderer', 'contents'], [])
        for section in contents:
            grid = self._nav(section, ['gridRenderer', 'items'])
            if not grid:
                grid = self._nav(section, ['musicShelfRenderer', 'contents'])
            if not grid:
                continue
            for item in grid:
                parsed = self._parse_music_item(item)
                if not parsed:
                    # Try grid item
                    renderer = item.get('musicTwoRowItemRenderer')
                    if renderer:
                        parsed = self._extract_item(renderer)
                if parsed:
                    pl_id = parsed.get('playlistId') or parsed.get('browseId', '')
                    if pl_id.startswith('VL'):
                        pl_id = pl_id[2:]
                    items.append({
                        'playlistId': pl_id,
                        'title': parsed.get('title', ''),
                        'thumbnails': parsed.get('thumbnails', []),
                        'count': '',
                    })
        return items

    def _parse_playlist_tracks(self, resp):
        """Parse tracks from a playlist browse response."""
        tracks = []

        # Try twoColumnBrowseResultsRenderer (used by VLLM / playlist pages)
        two_col = self._nav(resp, ['contents', 'twoColumnBrowseResultsRenderer'])
        if two_col:
            sections = self._nav(two_col, ['secondaryContents', 'sectionListRenderer', 'contents'], [])
            for section in sections:
                shelf = self._nav(section, ['musicPlaylistShelfRenderer'])
                if not shelf:
                    shelf = self._nav(section, ['musicShelfRenderer'])
                if not shelf:
                    continue
                for content in shelf.get('contents', []):
                    renderer = content.get('musicResponsiveListItemRenderer')
                    if not renderer:
                        continue
                    track = self._parse_track_renderer(renderer)
                    if track:
                        tracks.append(track)
            if tracks:
                return {'tracks': tracks}

        # Fallback: singleColumnBrowseResultsRenderer
        contents = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'sectionListRenderer', 'contents'], [])
        for section in contents:
            shelf = self._nav(section, ['musicShelfRenderer'])
            if not shelf:
                shelf = self._nav(section, ['musicPlaylistShelfRenderer'])
            if not shelf:
                continue
            for content in shelf.get('contents', []):
                renderer = content.get('musicResponsiveListItemRenderer')
                if not renderer:
                    continue
                track = self._parse_track_renderer(renderer)
                if track:
                    tracks.append(track)

        return {'tracks': tracks}

    def _parse_liked_songs(self, resp):
        return self._parse_playlist_tracks(resp)

    def _parse_track_renderer(self, renderer):
        """Parse a musicResponsiveListItemRenderer into a track dict."""
        cols = renderer.get('flexColumns', [])
        title = ''
        artist = ''
        album = ''
        duration = ''

        if len(cols) > 0:
            title = self._get_text(self._nav(cols, [0, 'musicResponsiveListItemFlexColumnRenderer', 'text']))
        if len(cols) > 1:
            # Column 1 may contain "Artist · Album · Duration" as separate runs
            # Extract just the artist name from the first run(s) before the separator
            col1_text = self._nav(cols, [1, 'musicResponsiveListItemFlexColumnRenderer', 'text'])
            if col1_text:
                runs = col1_text.get('runs', [])
                if runs:
                    # Collect artist names (runs before first ' · ' separator)
                    artist_parts = []
                    for run in runs:
                        text = run.get('text', '')
                        if text in (' · ', ' • ', ' & ', ', '):
                            # Check if next runs are still artists or metadata
                            # If this run has a navigation endpoint, it's an artist link
                            if not run.get('navigationEndpoint'):
                                # Separator without link — could be artist separator or metadata separator
                                # Check if the PREVIOUS run had a browse endpoint (artist)
                                # and if next run also has one
                                artist_parts.append(text)
                                continue
                            artist_parts.append(text)
                        elif run.get('navigationEndpoint', {}).get('browseEndpoint', {}).get('browseId', '').startswith('UC'):
                            # This is an artist link
                            artist_parts.append(text)
                        elif not run.get('navigationEndpoint') and text.strip() in (' · ', ' • '):
                            break  # Stop at metadata separator
                        else:
                            artist_parts.append(text)
                    artist = ''.join(artist_parts).split(' · ')[0].split(' • ')[0].strip()
                if not artist:
                    artist = self._get_text(col1_text)
        if len(cols) > 2:
            album = self._get_text(self._nav(cols, [2, 'musicResponsiveListItemFlexColumnRenderer', 'text']))

        # Get duration from fixed columns
        fixed_cols = renderer.get('fixedColumns', [])
        if fixed_cols:
            duration = self._get_text(self._nav(fixed_cols, [0, 'musicResponsiveListItemFixedColumnRenderer', 'text']))

        # Get video ID
        video_id = self._nav(renderer, ['overlay', 'musicItemThumbnailOverlayRenderer',
                                         'content', 'musicPlayButtonRenderer',
                                         'playNavigationEndpoint', 'watchEndpoint', 'videoId'])
        if not video_id:
            video_id = self._nav(renderer, ['playlistItemData', 'videoId'])

        thumbs = self._get_thumbnails(self._nav(renderer, ['thumbnail', 'musicThumbnailRenderer', 'thumbnail']))

        if not video_id:
            return None

        return {
            'videoId': video_id,
            'title': title,
            'artists': [{'name': artist}] if artist else [],
            'album': {'name': album},
            'duration': duration,
            'thumbnails': thumbs,
        }

    def _parse_album_items(self, resp):
        """Parse library albums."""
        items = []
        contents = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'sectionListRenderer', 'contents'], [])
        for section in contents:
            grid = self._nav(section, ['gridRenderer', 'items'])
            if not grid:
                shelf = self._nav(section, ['musicShelfRenderer', 'contents'])
                grid = shelf if shelf else []
            for item in grid:
                parsed = self._parse_music_item(item)
                if not parsed:
                    for key in item:
                        if 'Renderer' in key:
                            parsed = self._extract_item(item[key])
                            break
                if parsed:
                    items.append({
                        'browseId': parsed.get('browseId', ''),
                        'title': parsed.get('title', ''),
                        'artists': parsed.get('artists', []),
                        'thumbnails': parsed.get('thumbnails', []),
                    })
        return items

    def _parse_album_tracks(self, resp):
        """Parse album browse response, inheriting album thumbnail for tracks."""
        result = self._parse_playlist_tracks(resp)

        # Extract album-level thumbnail from header
        album_thumb = []
        two_col = self._nav(resp, ['contents', 'twoColumnBrowseResultsRenderer'])
        if two_col:
            sections = self._nav(two_col, ['tabs', 0, 'tabRenderer', 'content',
                                            'sectionListRenderer', 'contents'], [])
            for section in sections:
                header = self._nav(section, ['musicResponsiveHeaderRenderer'])
                if header:
                    album_thumb = self._get_thumbnails(
                        self._nav(header, ['thumbnail', 'musicThumbnailRenderer', 'thumbnail']))
                    break

        # Apply album thumbnail to tracks that don't have their own
        if album_thumb:
            for track in result.get('tracks', []):
                if not track.get('thumbnails'):
                    track['thumbnails'] = album_thumb

        return result

    def _parse_artist_items(self, resp):
        """Parse library artists."""
        items = []
        contents = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'sectionListRenderer', 'contents'], [])
        for section in contents:
            shelf = self._nav(section, ['musicShelfRenderer', 'contents'])
            if not shelf:
                grid = self._nav(section, ['gridRenderer', 'items'])
                shelf = grid if grid else []
            for item in shelf:
                parsed = self._parse_music_item(item)
                if not parsed:
                    for key in item:
                        if 'Renderer' in key:
                            parsed = self._extract_item(item[key])
                            break
                if parsed:
                    items.append({
                        'browseId': parsed.get('browseId', ''),
                        'artist': parsed.get('title', ''),
                        'thumbnails': parsed.get('thumbnails', []),
                    })
        return items

    def _parse_artist_page(self, resp):
        """Parse artist page."""
        result = {'songs': {}, 'albums': {}, 'singles': {}}
        tabs = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer', 'tabs'], [])
        if not tabs:
            return result

        content = self._nav(tabs, [0, 'tabRenderer', 'content', 'sectionListRenderer', 'contents'], [])

        for section in content:
            shelf = self._nav(section, ['musicShelfRenderer'])
            carousel = self._nav(section, ['musicCarouselShelfRenderer'])
            active = shelf or carousel
            if not active:
                continue

            header = self._nav(active, ['header'])
            title = ''
            browse_all_id = ''
            browse_all_params = ''
            if header:
                for key in header:
                    h = header[key]
                    if not isinstance(h, dict):
                        continue
                    title = self._get_text(self._nav(h, ['title']))
                    # Extract "More" / browse all endpoint
                    more_btn = self._nav(h, ['moreContentButton', 'buttonRenderer',
                                              'navigationEndpoint', 'browseEndpoint'])
                    if more_btn:
                        browse_all_id = more_btn.get('browseId', '')
                        browse_all_params = more_btn.get('params', '')
                    if title:
                        break

            title_lower = title.lower()

            # If there's a browse-all endpoint for albums/singles, fetch ALL items
            if browse_all_id and ('album' in title_lower or 'single' in title_lower):
                log('Fetching all items for "{}" via {}'.format(title, browse_all_id))
                items = self.get_artist_albums(browse_all_id, params=browse_all_params)
            else:
                items = []
                for c in active.get('contents', []):
                    parsed = self._parse_music_item(c)
                    if parsed:
                        items.append(parsed)

            section_data = {'results': items}

            if 'song' in title_lower:
                result['songs'] = section_data
            elif 'album' in title_lower:
                result['albums'] = section_data
            elif 'single' in title_lower:
                result['singles'] = section_data

        return result

    def get_artist_albums(self, browse_id, params=''):
        """Get all albums/singles for an artist via browse-all endpoint."""
        body = {'browseId': browse_id}
        if params:
            body['params'] = params
        resp = self._call('browse', body)
        items = []
        contents = self._nav(resp, ['contents', 'singleColumnBrowseResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'sectionListRenderer', 'contents'], [])
        for section in contents:
            grid = self._nav(section, ['gridRenderer', 'items'])
            if not grid:
                grid = self._nav(section, ['musicShelfRenderer', 'contents'])
            if not grid:
                continue
            for item in grid:
                parsed = self._parse_music_item(item)
                if not parsed:
                    for key in item:
                        if 'Renderer' in key:
                            parsed = self._extract_item(item[key])
                            break
                if parsed:
                    items.append(parsed)
        return items

    def _parse_history(self, resp):
        """Parse history into flat track list."""
        tracks = []
        result = self._parse_playlist_tracks(resp)
        return result.get('tracks', [])

    def _parse_search_results(self, resp, filter_type=None):
        """Parse search response. Returns (results, continuation_token)."""
        results = []
        ctoken = None
        contents = self._nav(resp, ['contents', 'tabbedSearchResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'sectionListRenderer', 'contents'], [])

        for section in contents:
            # Handle musicCardShelfRenderer (top/featured result)
            card = self._nav(section, ['musicCardShelfRenderer'])
            if card:
                card_item = self._parse_card_shelf(card, filter_type)
                if card_item:
                    results.append(card_item)
                # Card shelf may also have sub-items
                for sub in card.get('contents', []):
                    renderer = sub.get('musicResponsiveListItemRenderer')
                    if renderer:
                        item = self._parse_search_item(renderer, filter_type)
                        if item:
                            results.append(item)
                continue

            shelf = self._nav(section, ['musicShelfRenderer'])
            if not shelf:
                continue

            for content in shelf.get('contents', []):
                renderer = content.get('musicResponsiveListItemRenderer')
                if not renderer:
                    continue
                item = self._parse_search_item(renderer, filter_type)
                if item:
                    results.append(item)

            # Get continuation token
            conts = shelf.get('continuations', [])
            if conts:
                ctoken = self._nav(conts, [0, 'nextContinuationData', 'continuation'])

        return results, ctoken

    def _parse_search_continuation(self, resp, filter_type=None):
        """Parse search continuation response. Returns (results, continuation_token)."""
        results = []
        ctoken = None
        shelf = self._nav(resp, ['continuationContents', 'musicShelfContinuation'], {})

        for content in shelf.get('contents', []):
            renderer = content.get('musicResponsiveListItemRenderer')
            if not renderer:
                continue
            item = self._parse_search_item(renderer, filter_type)
            if item:
                results.append(item)

        conts = shelf.get('continuations', [])
        if conts:
            ctoken = self._nav(conts, [0, 'nextContinuationData', 'continuation'])

        return results, ctoken

    def _parse_search_item(self, renderer, filter_type=None):
        """Parse a single search result item."""
        item = self._parse_track_renderer(renderer)
        if not item:
            return None

        browse_id = self._nav(renderer, ['navigationEndpoint', 'browseEndpoint', 'browseId'])
        if browse_id:
            if browse_id.startswith('UC') or browse_id.startswith('MPLA'):
                item['resultType'] = 'artist'
                item['browseId'] = browse_id
            elif browse_id.startswith('MPREb'):
                item['resultType'] = 'album'
                item['browseId'] = browse_id
            elif browse_id.startswith('VL') or browse_id.startswith('PL'):
                item['resultType'] = 'playlist'
                item['browseId'] = browse_id
            else:
                item['resultType'] = 'song'
        else:
            item['resultType'] = filter_type or 'song'
        return item

    def _parse_card_shelf(self, card, filter_type=None):
        """Parse a musicCardShelfRenderer (featured search result)."""
        title = self._get_text(self._nav(card, ['title']))
        subtitle = self._get_text(self._nav(card, ['subtitle']))
        thumbs = self._get_thumbnails(self._nav(card, ['thumbnail', 'musicThumbnailRenderer', 'thumbnail']))

        nav = self._nav(card, ['title', 'runs', 0, 'navigationEndpoint'])
        browse_id = self._nav(nav, ['browseEndpoint', 'browseId'], '')
        video_id = self._nav(nav, ['watchEndpoint', 'videoId'], '')

        item = {
            'title': title,
            'artists': [{'name': subtitle}] if subtitle else [],
            'thumbnails': thumbs,
        }

        if video_id:
            item['videoId'] = video_id
            item['resultType'] = 'song'
        elif browse_id:
            item['browseId'] = browse_id
            if browse_id.startswith('UC') or browse_id.startswith('MPLA'):
                item['resultType'] = 'artist'
            elif browse_id.startswith('MPREb'):
                item['resultType'] = 'album'
            elif browse_id.startswith('VL') or browse_id.startswith('PL'):
                item['resultType'] = 'playlist'
            else:
                item['resultType'] = filter_type or 'song'
        else:
            item['resultType'] = filter_type or 'song'

        return item if (video_id or browse_id) else None

    def _parse_watch_playlist(self, resp):
        """Parse watch/next response for radio queue."""
        tracks = []
        playlist = self._nav(resp, ['contents', 'singleColumnMusicWatchNextResultsRenderer',
                                     'tabbedRenderer', 'watchNextTabbedResultsRenderer',
                                     'tabs', 0, 'tabRenderer', 'content',
                                     'musicQueueRenderer', 'content',
                                     'playlistPanelRenderer', 'contents'], [])

        for item in playlist:
            renderer = item.get('playlistPanelVideoRenderer')
            if not renderer:
                continue

            video_id = renderer.get('videoId', '')
            title = self._get_text(renderer.get('title'))

            artists_text = ''
            long_text = self._nav(renderer, ['longBylineText'])
            if long_text:
                artists_text = self._get_text(long_text)
            else:
                short_text = self._nav(renderer, ['shortBylineText'])
                if short_text:
                    artists_text = self._get_text(short_text)

            duration = self._get_text(self._nav(renderer, ['lengthText']))
            thumbs = self._get_thumbnails(renderer.get('thumbnail'))

            if video_id:
                tracks.append({
                    'videoId': video_id,
                    'title': title,
                    'artists': [{'name': artists_text}] if artists_text else [],
                    'duration': duration,
                    'thumbnails': thumbs,
                })

        return {'tracks': tracks}
