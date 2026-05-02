"""Lyrics fetcher using LRCLIB (free, open API)."""

import json
import urllib.request
import urllib.parse
import xbmc

USER_AGENT = 'YTMusic Kodi Addon/1.0'


def log(msg):
    xbmc.log('[YTMusic] lyrics: {}'.format(msg), xbmc.LOGINFO)


def get_lyrics(title, artist):
    """Fetch plain lyrics for a song. Returns lyrics text or None."""
    if not title:
        return None

    params = {'track_name': title}
    if artist:
        params['artist_name'] = artist

    url = 'https://lrclib.net/api/get?{}'.format(urllib.parse.urlencode(params))
    req = urllib.request.Request(url)
    req.add_header('User-Agent', USER_AGENT)

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        lyrics = data.get('plainLyrics') or data.get('syncedLyrics')
        if lyrics:
            log('Found lyrics for {} - {}'.format(artist, title))
            # Clean synced lyrics timestamps if using syncedLyrics fallback
            if lyrics.startswith('['):
                import re
                lyrics = re.sub(r'\[\d{2}:\d{2}\.\d{2}\]\s?', '', lyrics)
            return lyrics
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log('No lyrics found for {} - {}'.format(artist, title))
        else:
            log('Lyrics API error: {}'.format(e))
    except Exception as e:
        log('Lyrics fetch error: {}'.format(e))

    # Fallback: search by query
    try:
        search_url = 'https://lrclib.net/api/search?{}'.format(
            urllib.parse.urlencode({'q': '{} {}'.format(artist, title)}))
        req = urllib.request.Request(search_url)
        req.add_header('User-Agent', USER_AGENT)
        resp = urllib.request.urlopen(req, timeout=10)
        results = json.loads(resp.read().decode('utf-8'))
        if results and isinstance(results, list):
            lyrics = results[0].get('plainLyrics') or results[0].get('syncedLyrics')
            if lyrics:
                if lyrics.startswith('['):
                    import re
                    lyrics = re.sub(r'\[\d{2}:\d{2}\.\d{2}\]\s?', '', lyrics)
                return lyrics
    except Exception as e:
        log('Lyrics search error: {}'.format(e))

    return None
