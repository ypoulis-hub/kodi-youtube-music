"""YouTube Music API - thin wrapper around innertube client."""

import xbmc
from lib.innertube import YTMusicClient

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
    # lh3.googleusercontent.com URLs support =wN-hN size params
    if 'lh3.googleusercontent.com' in url:
        # Replace size params like =w120-h120 or =w60-h60-l90-rj with =w544-h544
        import re
        url = re.sub(r'=w\d+.*$', '=w544-h544-l90-rj', url)
    # i.ytimg.com URLs: replace default/mqdefault with maxresdefault
    elif 'i.ytimg.com' in url:
        for quality in ['default', 'mqdefault', 'hqdefault', 'sddefault']:
            if quality in url:
                url = url.replace(quality, 'maxresdefault')
                break
    return url
