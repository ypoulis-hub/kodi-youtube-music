"""YouTube Music API - thin wrapper around innertube client."""

import re

import xbmc
import xbmcaddon
from lib.innertube import YTMusicClient

ADDON = xbmcaddon.Addon()

# Resolution setting -> pixel size for square Google cover art.
_THUMB_SIZES = {'0': 544, '1': 800, '2': 1200, '3': 1600}


def _thumb_size():
    """User-selected cover-art resolution (px). Defaults to 1200."""
    try:
        return _THUMB_SIZES.get(ADDON.getSetting('thumb_res') or '2', 1200)
    except Exception:
        return 1200

_client = None


def log(msg):
    xbmc.log('[YTMusic] api: {}'.format(msg), xbmc.LOGINFO)


def get_client():
    global _client
    if _client is None:
        from lib.auth import get_auth_header, get_cookie_header, get_page_id
        _client = YTMusicClient(
            auth_header_fn=get_auth_header,
            cookie_header_fn=get_cookie_header,
            page_id=get_page_id(),
        )
    return _client


def reset_client():
    global _client
    _client = None


def get_home():
    return get_client().get_home()


def get_library_playlists(limit=25):
    return get_client().get_library_playlists(limit=limit)


def get_library_songs(limit=25):
    return get_client().get_library_songs(limit=limit)


def get_library_albums(limit=25):
    return get_client().get_library_albums(limit=limit)


def get_library_artists(limit=25):
    return get_client().get_library_artists(limit=limit)


def get_liked_songs(limit=100):
    return get_client().get_liked_songs(limit=limit)


def get_playlist(playlist_id, limit=100):
    return get_client().get_playlist(playlist_id, limit=limit)


def get_album(browse_id):
    return get_client().get_album(browse_id)


def get_artist(channel_id):
    return get_client().get_artist(channel_id)


def search(query, filter_type=None, limit=50):
    return get_client().search(query, filter_type=filter_type, limit=limit)


def get_artist_albums(browse_id, params=''):
    return get_client().get_artist_albums(browse_id, params=params)


def get_watch_playlist(video_id):
    return get_client().get_watch_playlist(video_id)


def get_stream_url(video_id):
    from lib.resolver import get_stream_url as _resolve
    return _resolve(video_id)


def get_history():
    return get_client().get_history()


def get_thumbnails(item):
    thumbs = item.get('thumbnails') or []
    if not thumbs:
        return ''
    best = max(thumbs, key=lambda t: t.get('width', 0) * t.get('height', 0))
    url = best.get('url', '')
    return _upscale_thumbnail(url)


def _upscale_thumbnail(url):
    """Request high-res version of YouTube Music thumbnails."""
    if not url:
        return ''
    size = _thumb_size()
    # Google image-proxy hosts (lh3-lh6.googleusercontent.com, yt3.ggpht.com,
    # yt3.googleusercontent.com, music.youtube.com proxies, etc.) all accept a
    # size token after '='. Forms seen: =w120-h120, =w60-h60-l90-rj, =s226, =s0.
    if 'googleusercontent.com' in url or 'ggpht.com' in url:
        new = '=w{0}-h{1}-l90-rj'.format(size, size)
        if '=' in url:
            url = re.sub(r'=[swh]\d.*$', new, url)
        else:
            url = url + new
    # i.ytimg.com URLs: replace the default-variant basename with maxresdefault
    elif 'ytimg.com' in url:
        url = re.sub(r'/(?:default|mqdefault|hqdefault|sddefault)\.jpg',
                     '/maxresdefault.jpg', url)
    return url
