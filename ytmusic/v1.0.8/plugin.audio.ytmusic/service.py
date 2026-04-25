"""YTMusic background service - pre-resolves upcoming tracks for gapless playback."""

import json
import os
import time
import urllib.parse
import xbmc
import xbmcaddon
import xbmcvfs


ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
PREFETCH_FILE = os.path.join(PROFILE, 'prefetch_cache.json')

# Pre-resolve when this many seconds remain in the current track
PREFETCH_THRESHOLD = 45


def log(msg):
    xbmc.log('[YTMusic] service: {}'.format(msg), xbmc.LOGINFO)


def _get_next_video_id():
    """Get the video_id of the next track in the music playlist via JSON-RPC."""
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    pos = playlist.getposition()
    if pos < 0 or pos + 1 >= playlist.size():
        return None

    request = json.dumps({
        'jsonrpc': '2.0',
        'method': 'Playlist.GetItems',
        'params': {
            'playlistid': 0,
            'properties': ['file'],
            'limits': {'start': pos + 1, 'end': pos + 2}
        },
        'id': 1
    })
    response = json.loads(xbmc.executeJSONRPC(request))
    items = response.get('result', {}).get('items', [])
    if not items:
        return None

    file_url = items[0].get('file', '')
    if 'plugin.audio.ytmusic' not in file_url:
        return None

    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(file_url).query))
    return params.get('video_id') or None


def _save_prefetch(video_id, stream_url, info):
    """Save pre-resolved stream URL to cache file."""
    try:
        os.makedirs(os.path.dirname(PREFETCH_FILE), exist_ok=True)
        with open(PREFETCH_FILE, 'w') as f:
            json.dump({
                'video_id': video_id,
                'stream_url': stream_url,
                'info': info,
                'timestamp': time.time(),
            }, f)
    except IOError:
        pass


class YTMusicService(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.player = xbmc.Player()
        self._last_prefetched = None

    def run(self):
        log('Service started')
        while not self.abortRequested():
            if self.player.isPlayingAudio():
                self._check_prefetch()
            if self.waitForAbort(3):
                break
        log('Service stopped')

    def _check_prefetch(self):
        try:
            total = self.player.getTotalTime()
            elapsed = self.player.getTime()
            remaining = total - elapsed

            if total > 30 and 0 < remaining <= PREFETCH_THRESHOLD:
                next_vid = _get_next_video_id()
                if next_vid and next_vid != self._last_prefetched:
                    self._prefetch(next_vid)
        except RuntimeError:
            pass  # Player stopped between checks

    def _prefetch(self, video_id):
        log('Pre-resolving next track: {}'.format(video_id))
        self._last_prefetched = video_id
        marker = PREFETCH_FILE + '.resolving'
        try:
            with open(marker, 'w') as f:
                f.write(video_id)
        except IOError:
            pass
        try:
            from lib.resolver import get_stream_url
            stream_url, info = get_stream_url(video_id, _skip_prefetch=True)
            _save_prefetch(video_id, stream_url, info)
            log('Pre-resolved OK: {}'.format(video_id))
        except Exception as e:
            log('Pre-resolve failed: {}'.format(e))
        finally:
            try:
                os.remove(marker)
            except OSError:
                pass


if __name__ == '__main__':
    YTMusicService().run()
