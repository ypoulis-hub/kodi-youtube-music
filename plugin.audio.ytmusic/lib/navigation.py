"""Kodi navigation / menu building for YTMusic."""

import sys
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from lib import api
from lib.auth import is_authenticated, run_cookie_setup

ADDON = xbmcaddon.Addon()


def log(msg):
    xbmc.log(f'[YTMusic] nav: {msg}', xbmc.LOGINFO)


class Router:
    def __init__(self, handle, base_url):
        self.handle = handle
        self.base_url = base_url

    def build_url(self, **kwargs):
        return f'{self.base_url}?{urllib.parse.urlencode(kwargs)}'

    def route(self, params):
        action = params.get('action', 'main_menu')
        log(f'Routing: action={action} params={params}')

        try:
            handler = getattr(self, f'action_{action}', None)
            if handler:
                handler(params)
            else:
                log(f'Unknown action: {action}')
                self.action_main_menu(params)
        except RuntimeError as e:
            xbmcgui.Dialog().ok('YTMusic - Error', str(e))
        except Exception as e:
            log(f'Error: {e}')
            xbmcgui.Dialog().ok('YTMusic - Error', f'Unexpected error: {e}')

    # ── Main Menu ──

    def action_main_menu(self, params):
        if not is_authenticated():
            self._add_dir('[ Import Cookies to Sign In ]', action='setup_auth')
            xbmcplugin.endOfDirectory(self.handle)
            return

        self._add_dir('Home', action='home', icon='DefaultMusicCompilations.png')
        self._add_dir('Search', action='search_prompt', icon='DefaultMusicSearch.png')
        self._add_dir('Liked Songs', action='liked_songs', icon='DefaultMusicSongs.png')
        self._add_dir('Playlists', action='library_playlists', icon='DefaultMusicPlaylists.png')
        self._add_dir('Albums', action='library_albums', icon='DefaultMusicAlbums.png')
        self._add_dir('Artists', action='library_artists', icon='DefaultMusicArtists.png')
        self._add_dir('Library Songs', action='library_songs', icon='DefaultMusicSongs.png')
        self._add_dir('History', action='history', icon='DefaultMusicRecentlyAdded.png')
        self._add_dir('[ Switch Account ]', action='switch_account', icon='DefaultUser.png')
        xbmcplugin.endOfDirectory(self.handle)

    # ── Auth ──

    def action_setup_auth(self, params):
        run_cookie_setup()
        xbmc.executebuiltin('Container.Refresh')

    def action_import_cookies(self, params):
        run_cookie_setup()
        xbmc.executebuiltin('Container.Refresh')

# ── Home ──

    def action_home(self, params):
        sections = api.get_home()
        for section in sections:
            title = section.get('title', 'Untitled')
            contents = section.get('contents', [])
            if contents:
                self._add_dir('--- {} ---'.format(title), action='noop', selectable=False)
                for item in contents:
                    self._add_music_item(item)
        xbmcplugin.endOfDirectory(self.handle)

    # ── Library ──

    def action_library_playlists(self, params):
        playlists = api.get_library_playlists(limit=self._page_limit())
        for pl in playlists:
            pl_id = pl.get('playlistId', '')
            title = pl.get('title', 'Untitled')
            thumb = api.get_thumbnails(pl)
            count = pl.get('count', '')
            label = f'{title} ({count})' if count else title
            self._add_dir(label, action='playlist', playlist_id=pl_id, thumb=thumb)
        xbmcplugin.endOfDirectory(self.handle)

    def action_library_albums(self, params):
        albums = api.get_library_albums(limit=self._page_limit())
        for album in albums:
            browse_id = album.get('browseId', '')
            title = album.get('title', 'Untitled')
            artist = self._artist_name(album)
            thumb = api.get_thumbnails(album)
            label = f'{title} - {artist}' if artist else title
            self._add_dir(label, action='album', browse_id=browse_id, thumb=thumb)
        xbmcplugin.endOfDirectory(self.handle)

    def action_library_artists(self, params):
        artists = api.get_library_artists(limit=self._page_limit())
        for artist in artists:
            channel_id = artist.get('browseId', '')
            name = artist.get('artist', 'Unknown')
            thumb = api.get_thumbnails(artist)
            self._add_dir(name, action='artist', channel_id=channel_id, thumb=thumb)
        xbmcplugin.endOfDirectory(self.handle)

    def action_library_songs(self, params):
        songs = api.get_library_songs(limit=self._page_limit())
        for song in songs:
            self._add_song(song)
        xbmcplugin.endOfDirectory(self.handle)

    # ── Liked Songs ──

    def action_liked_songs(self, params):
        result = api.get_liked_songs(limit=self._page_limit())
        tracks = result.get('tracks', [])
        for track in tracks:
            self._add_song(track)
        xbmcplugin.endOfDirectory(self.handle)

    # ── Playlist ──

    def action_playlist(self, params):
        playlist_id = params.get('playlist_id', '')
        result = api.get_playlist(playlist_id, limit=self._page_limit())
        tracks = result.get('tracks', [])
        for track in tracks:
            self._add_song(track)
        xbmcplugin.endOfDirectory(self.handle)

    # ── Album ──

    def action_album(self, params):
        browse_id = params.get('browse_id', '')
        result = api.get_album(browse_id)
        tracks = result.get('tracks', [])
        for track in tracks:
            self._add_song(track)
        xbmcplugin.endOfDirectory(self.handle)

    # ── Artist ──

    def action_artist(self, params):
        channel_id = params.get('channel_id', '')
        artist = api.get_artist(channel_id)

        # Top songs
        top_songs = artist.get('songs', {})
        if top_songs:
            browse_id = top_songs.get('browseId')
            results = top_songs.get('results', [])
            if results:
                self._add_dir(f'--- Top Songs ---', action='noop', selectable=False)
                for song in results:
                    self._add_song(song)

        # Albums
        albums = artist.get('albums', {})
        if albums:
            results = albums.get('results', [])
            if results:
                self._add_dir('--- Albums ({}) ---'.format(len(results)),
                              action='noop', selectable=False)
                for album in results:
                    bid = album.get('browseId', '')
                    title = album.get('title', 'Untitled')
                    year = album.get('year', '')
                    label = f'{title} ({year})' if year else title
                    thumb = api.get_thumbnails(album)
                    self._add_dir(label, action='album', browse_id=bid, thumb=thumb)

        # Singles
        singles = artist.get('singles', {})
        if singles:
            results = singles.get('results', [])
            if results:
                self._add_dir('--- Singles & EPs ({}) ---'.format(len(results)),
                              action='noop', selectable=False)
                for single in results:
                    bid = single.get('browseId', '')
                    title = single.get('title', 'Untitled')
                    thumb = api.get_thumbnails(single)
                    self._add_dir(title, action='album', browse_id=bid, thumb=thumb)

        xbmcplugin.endOfDirectory(self.handle)

    def action_artist_albums(self, params):
        browse_id = params.get('browse_id', '')
        browse_params = params.get('params', '')
        items = api.get_artist_albums(browse_id, params=browse_params)
        for item in items:
            bid = item.get('browseId', '')
            title = item.get('title', 'Untitled')
            artist = self._artist_name(item)
            year = item.get('year', '')
            label = f'{title} ({year})' if year else title
            if artist:
                label = f'{title} - {artist}'
            thumb = api.get_thumbnails(item)
            self._add_dir(label, action='album', browse_id=bid, thumb=thumb)
        xbmcplugin.endOfDirectory(self.handle)

    def action_show_lyrics(self, params):
        title = params.get('title', '')
        artist = params.get('artist', '')
        if not title:
            xbmcgui.Dialog().ok('YTMusic', 'No song selected.')
            return

        from lib.lyrics import get_lyrics
        lyrics = get_lyrics(title, artist)
        if lyrics:
            xbmcgui.Dialog().textviewer(
                '{} - {}'.format(artist, title) if artist else title,
                lyrics,
            )
        else:
            xbmcgui.Dialog().ok('YTMusic', 'No lyrics found for this song.')

    def action_switch_account(self, params):
        from lib.auth import pick_account
        pick_account()
        xbmc.executebuiltin('Container.Refresh')

    def action_noop(self, params):
        pass

    # ── History ──

    def action_history(self, params):
        songs = api.get_history()
        for song in songs:
            self._add_song(song)
        xbmcplugin.endOfDirectory(self.handle)

    # ── Search ──

    def action_search_prompt(self, params):
        kb = xbmc.Keyboard('', 'Search YouTube Music')
        kb.doModal()
        if kb.isConfirmed():
            query = kb.getText().strip()
            if query:
                self._add_dir('All Results', action='search', query=query, filter='',
                              icon='DefaultMusicSearch.png')
                self._add_dir('Songs', action='search', query=query, filter='songs',
                              icon='DefaultMusicSongs.png')
                self._add_dir('Albums', action='search', query=query, filter='albums',
                              icon='DefaultMusicAlbums.png')
                self._add_dir('Artists', action='search', query=query, filter='artists',
                              icon='DefaultMusicArtists.png')
                self._add_dir('Playlists', action='search', query=query, filter='playlists',
                              icon='DefaultMusicPlaylists.png')
        xbmcplugin.endOfDirectory(self.handle)

    def action_search(self, params):
        query = params.get('query', '')
        filter_type = params.get('filter', '') or None
        results = api.search(query, filter_type=filter_type, limit=self._page_limit())

        for item in results:
            rtype = item.get('resultType', item.get('category', ''))
            if rtype == 'song':
                self._add_song(item)
            elif rtype == 'video':
                self._add_song(item)
            elif rtype == 'album':
                bid = item.get('browseId', '')
                title = item.get('title', 'Untitled')
                artist = self._artist_name(item)
                thumb = api.get_thumbnails(item)
                label = f'{title} - {artist}' if artist else title
                self._add_dir(label, action='album', browse_id=bid, thumb=thumb)
            elif rtype == 'artist':
                bid = item.get('browseId', '')
                name = item.get('artist', item.get('title', 'Unknown'))
                thumb = api.get_thumbnails(item)
                self._add_dir(name, action='artist', channel_id=bid, thumb=thumb)
            elif rtype == 'playlist':
                pl_id = item.get('browseId', item.get('playlistId', ''))
                title = item.get('title', 'Untitled')
                thumb = api.get_thumbnails(item)
                self._add_dir(title, action='playlist', playlist_id=pl_id, thumb=thumb)
            else:
                self._add_song(item)

        xbmcplugin.endOfDirectory(self.handle)

    # ── Playback ──

    def action_play(self, params):
        video_id = params.get('video_id', '')
        title = params.get('title', '')
        artist = params.get('artist', '')
        thumb = params.get('thumb', '')

        if not video_id:
            xbmcgui.Dialog().ok('YTMusic', 'No video ID provided.')
            return

        pbar = xbmcgui.DialogProgress()
        pbar.create('YTMusic', f'Resolving stream for: {title or video_id}')

        try:
            stream_url, info = api.get_stream_url(video_id)
        except RuntimeError as e:
            pbar.close()
            xbmcgui.Dialog().ok('YTMusic - Playback Error', str(e))
            return

        pbar.close()

        li = xbmcgui.ListItem(title or info.get('title', 'Unknown'))
        li.setInfo('music', {
            'title': title or info.get('title', ''),
            'artist': artist or info.get('artist', info.get('uploader', '')),
            'duration': info.get('duration', 0),
        })
        if thumb:
            li.setArt({'thumb': thumb, 'icon': thumb, 'fanart': thumb, 'poster': thumb})
        li.setPath(stream_url)

        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def action_play_radio(self, params):
        """Play a track and queue its radio/watch playlist."""
        video_id = params.get('video_id', '')
        self.action_play(params)

        try:
            watch = api.get_watch_playlist(video_id)
            tracks = watch.get('tracks', [])
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            for track in tracks[1:]:  # Skip first (currently playing)
                tid = track.get('videoId', '')
                if not tid:
                    continue
                tname = track.get('title', '')
                tartist = self._artist_name(track)
                tthumb = api.get_thumbnails(track)
                url = self.build_url(action='play', video_id=tid,
                                     title=tname, artist=tartist, thumb=tthumb)
                li = xbmcgui.ListItem(tname)
                li.setInfo('music', {'title': tname, 'artist': tartist})
                if tthumb:
                    li.setArt({'thumb': tthumb})
                playlist.add(url, li)
        except Exception as e:
            log(f'Could not queue radio: {e}')

    # ── Helpers ──

    def _add_dir(self, label, icon=None, thumb=None, selectable=True, **url_params):
        url = self.build_url(**url_params)
        li = xbmcgui.ListItem(label)
        if thumb:
            li.setArt({'thumb': thumb, 'icon': thumb, 'fanart': thumb, 'poster': thumb})
        elif icon:
            li.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=url,
            listitem=li,
            isFolder=True,
        )

    def _add_song(self, song):
        video_id = song.get('videoId', '')
        if not video_id:
            return

        title = song.get('title', 'Unknown')
        artist = self._artist_name(song)
        album = song.get('album', {})
        album_name = album.get('name', '') if isinstance(album, dict) else str(album)
        duration_str = song.get('duration', '')
        duration_sec = self._parse_duration(duration_str)
        thumb = api.get_thumbnails(song)

        label = f'{artist} - {title}' if artist else title

        url = self.build_url(
            action='play',
            video_id=video_id,
            title=title,
            artist=artist,
            thumb=thumb,
        )

        li = xbmcgui.ListItem(label)
        li.setInfo('music', {
            'title': title,
            'artist': artist,
            'album': album_name,
            'duration': duration_sec,
        })
        li.setProperty('IsPlayable', 'true')
        if thumb:
            li.setArt({'thumb': thumb, 'icon': thumb, 'fanart': thumb, 'poster': thumb})

        # Context menu
        radio_url = self.build_url(
            action='play_radio',
            video_id=video_id,
            title=title,
            artist=artist,
            thumb=thumb,
        )
        lyrics_url = self.build_url(
            action='show_lyrics',
            title=title,
            artist=artist,
        )
        li.addContextMenuItems([
            ('Show Lyrics', f'RunPlugin({lyrics_url})'),
            ('Play Radio', f'RunPlugin({radio_url})'),
        ])

        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=url,
            listitem=li,
            isFolder=False,
        )

    def _add_music_item(self, item):
        """Add a generic music item (song, album, artist, playlist) from home/browse."""
        video_id = item.get('videoId')
        browse_id = item.get('browseId', '')
        playlist_id = item.get('playlistId', '')
        title = item.get('title', 'Unknown')
        thumb = api.get_thumbnails(item)

        if video_id:
            self._add_song(item)
        elif browse_id.startswith('MPRE'):
            # Album
            artist = self._artist_name(item)
            label = '{} - {}'.format(title, artist) if artist else title
            self._add_dir(label, action='album', browse_id=browse_id, thumb=thumb)
        elif browse_id.startswith('UC') or browse_id.startswith('MPLA'):
            # Artist
            self._add_dir(title, action='artist', channel_id=browse_id, thumb=thumb)
        elif playlist_id or browse_id.startswith('VL'):
            # Playlist
            pl_id = playlist_id or browse_id
            if pl_id.startswith('VL'):
                pl_id = pl_id[2:]
            self._add_dir(title, action='playlist', playlist_id=pl_id, thumb=thumb)
        else:
            # Fallback: treat as a directory with browse_id
            if browse_id:
                self._add_dir(title, action='album', browse_id=browse_id, thumb=thumb)
            else:
                self._add_dir(title, action='noop', thumb=thumb)

    def _artist_name(self, item):
        artists = item.get('artists')
        if artists and isinstance(artists, list):
            return ', '.join(a.get('name', '') for a in artists if a.get('name'))
        return item.get('artist', '')

    def _parse_duration(self, dur_str):
        if not dur_str or not isinstance(dur_str, str):
            return 0
        parts = dur_str.split(':')
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(parts[0])
        except ValueError:
            return 0

    def _page_limit(self):
        idx = int(ADDON.getSetting('items_per_page') or '1')
        return [25, 50, 100][idx]
