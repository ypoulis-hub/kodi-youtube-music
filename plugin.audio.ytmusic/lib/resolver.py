"""Stream URL resolver using yt-dlp (direct binary or via system Python)."""

import subprocess
import json
import os
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

# Resolution method: 'ytdlp_cli' (direct binary) or 'python' (subprocess)
_resolve_method = None
_resolve_path = None

# Cache file to persist detection across Kodi plugin invocations
_CACHE_FILE = os.path.join(PROFILE, 'resolver_cache.json')

# Prefetch cache written by the background service (service.py)
_PREFETCH_FILE = os.path.join(PROFILE, 'prefetch_cache.json')


def log(msg):
    xbmc.log('[YTMusic] resolver: {}'.format(msg), xbmc.LOGINFO)


# ── yt-dlp CLI detection ──

def _find_ytdlp_cli():
    """Find a standalone yt-dlp binary on the system.

    Search order:
    1. User-configured custom path (if it points to yt-dlp, not python)
    2. Common install locations per platform
    3. PATH-based lookup
    """
    custom_path = ADDON.getSetting('python_path') or ''
    if custom_path and os.path.isfile(custom_path):
        basename = os.path.basename(custom_path).lower().replace('.exe', '')
        if basename in ('yt-dlp', 'yt_dlp'):
            if _test_ytdlp_cli(custom_path):
                return custom_path

    candidates = ['yt-dlp']
    is_windows = os.name == 'nt'

    # Check addon profile directory first (auto-install location)
    profile_exe = os.path.join(PROFILE, 'bin', 'yt-dlp.exe' if is_windows else 'yt-dlp')
    if os.path.isfile(profile_exe):
        candidates.insert(0, profile_exe)

    if is_windows:
        candidates.append('yt-dlp.exe')
    else:
        for path in ['/usr/local/bin/yt-dlp', '/usr/bin/yt-dlp']:
            if os.path.isfile(path):
                candidates.insert(0, path)

    for candidate in candidates:
        if _test_ytdlp_cli(candidate):
            return candidate

    return None


def _test_ytdlp_cli(candidate):
    """Test if a yt-dlp binary is functional."""
    try:
        result = subprocess.run(
            [candidate, '--version'],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            log('Found yt-dlp CLI: {} (v{})'.format(candidate, result.stdout.strip()))
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return False


# ── Python + yt-dlp detection ──

def _find_system_python():
    """Find system Python 3 with yt-dlp installed (not Kodi's bundled one).

    Search order:
    1. User-configured custom path (from addon settings)
    2. Platform-specific common install locations
    3. Generic PATH-based candidates (python3, python, py)
    """
    custom_path = ADDON.getSetting('python_path') or ''
    if custom_path and os.path.isfile(custom_path):
        if _test_python(custom_path):
            return custom_path
        log('Custom python_path set but yt-dlp not found: {}'.format(custom_path))

    candidates = ['python3', 'python']
    is_windows = os.name == 'nt'

    if is_windows:
        candidates.append('py')
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        if local_appdata:
            python_base = os.path.join(local_appdata, 'Programs', 'Python')
            if os.path.isdir(python_base):
                for sub in os.listdir(python_base):
                    exe = os.path.join(python_base, sub, 'python.exe')
                    if os.path.isfile(exe):
                        candidates.insert(0, exe)
            # Also check pythoncore (Windows Store / winget)
            for entry in os.listdir(local_appdata):
                if entry.lower().startswith('python'):
                    sub = os.path.join(local_appdata, entry)
                    if os.path.isdir(sub):
                        for item in os.listdir(sub):
                            exe = os.path.join(sub, item, 'python.exe')
                            if os.path.isfile(exe):
                                candidates.insert(0, exe)
    else:
        for path in ['/usr/bin/python3', '/usr/local/bin/python3']:
            if os.path.isfile(path):
                candidates.insert(0, path)

    for candidate in candidates:
        if _test_python(candidate):
            return candidate

    return None


def _test_python(candidate):
    """Test if a Python executable has yt-dlp available."""
    try:
        result = subprocess.run(
            [candidate, '-c', 'import yt_dlp; print("ok")'],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode == 0 and 'ok' in result.stdout:
            log('Found system Python with yt-dlp: {}'.format(candidate))
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return False


# ── Resolver cache ──

def _load_cache():
    """Load cached resolver method/path from a previous plugin invocation."""
    try:
        with open(_CACHE_FILE, 'r') as f:
            cache = json.load(f)
        method = cache.get('method')
        path = cache.get('path')
        if method and path and os.path.isfile(path):
            log('Using cached resolver: {} ({})'.format(method, path))
            return method, path
    except (IOError, ValueError, KeyError):
        pass
    return None, None


def _save_cache(method, path):
    """Persist resolver detection so subsequent calls skip subprocess probes."""
    try:
        # Resolve to absolute path for reliable cache lookups
        if not os.path.isabs(path):
            import shutil
            resolved = shutil.which(path)
            if resolved:
                path = resolved
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, 'w') as f:
            json.dump({'method': method, 'path': path}, f)
    except IOError:
        pass


def _clear_cache():
    """Remove cached resolver (e.g. after a resolution failure)."""
    try:
        os.remove(_CACHE_FILE)
    except OSError:
        pass


# ── Resolver init ──

def _init_resolver():
    """Detect the best available method: direct yt-dlp CLI first, then Python."""
    global _resolve_method, _resolve_path

    # Fast path: reuse cached detection from a previous plugin invocation
    method, path = _load_cache()
    if method:
        _resolve_method = method
        _resolve_path = path
        return

    # Try direct yt-dlp binary first (no Python needed)
    ytdlp = _find_ytdlp_cli()
    if ytdlp:
        _resolve_method = 'ytdlp_cli'
        _resolve_path = ytdlp
        log('Using yt-dlp CLI method: {}'.format(ytdlp))
        _save_cache('ytdlp_cli', ytdlp)
        return

    # Fall back to Python + yt-dlp module
    python = _find_system_python()
    if python:
        _resolve_method = 'python'
        _resolve_path = python
        log('Using Python method: {}'.format(python))
        _save_cache('python', python)
        return

    log('No yt-dlp resolution method found')

    # Offer to download yt-dlp automatically
    if _auto_install_ytdlp():
        ytdlp = _find_ytdlp_cli()
        if ytdlp:
            _resolve_method = 'ytdlp_cli'
            _resolve_path = ytdlp
            log('Using yt-dlp CLI after auto-install: {}'.format(ytdlp))
            _save_cache('ytdlp_cli', ytdlp)
            return

    log('No yt-dlp resolution method available')


def _auto_install_ytdlp():
    """Offer to download yt-dlp binary (works on both Linux and Windows)."""
    dialog = xbmcgui.Dialog()
    is_windows = os.name == 'nt'

    ok = dialog.yesno(
        'YTMusic - yt-dlp not found',
        'yt-dlp is required to play music but was not found on this system.\n\n'
        'Would you like to download and install it automatically?',
    )
    if not ok:
        return False

    # Always install into the addon's own profile directory — works on all
    # platforms (Windows, Linux, LibreELEC, Android) without touching system paths
    if is_windows:
        filename = 'yt-dlp.exe'
        download_url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'
    else:
        filename = 'yt-dlp'
        download_url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp'
    install_dir = os.path.join(PROFILE, 'bin')

    install_path = os.path.join(install_dir, filename)

    pbar = xbmcgui.DialogProgress()
    pbar.create('YTMusic', 'Downloading yt-dlp...')

    try:
        os.makedirs(install_dir, exist_ok=True)

        # Download using xbmcvfs to stay within Kodi's own file handling
        tmp_path = xbmcvfs.translatePath('special://temp/yt-dlp-download')
        if xbmcvfs.copy(download_url, tmp_path):
            xbmcvfs.copy(tmp_path, install_path)
            xbmcvfs.delete(tmp_path)
        else:
            # Fallback to requests if xbmcvfs cannot handle the URL
            import requests
            r = requests.get(download_url, timeout=120)
            r.raise_for_status()
            with open(install_path, 'wb') as f:
                f.write(r.content)

        if not is_windows:
            os.chmod(install_path, 0o755)

        pbar.close()

        # Verify it works
        if _test_ytdlp_cli(install_path):
            dialog.ok('YTMusic', 'yt-dlp installed successfully!')
            return True
        else:
            dialog.ok('YTMusic', 'yt-dlp was downloaded but failed to run.')
            return False

    except Exception as e:
        pbar.close()
        log('yt-dlp auto-install error: {}'.format(e))
        dialog.ok('YTMusic', 'Installation failed: {}'.format(e))
        return False


def _get_resolver():
    """Return (method, path) for stream resolution."""
    if _resolve_method is None:
        _init_resolver()
    return _resolve_method, _resolve_path


# ── Stream resolution ──

def _check_prefetch_file(video_id):
    """Read the prefetch cache file if it matches the requested video_id."""
    try:
        with open(_PREFETCH_FILE, 'r') as f:
            cache = json.load(f)
        if cache.get('video_id') == video_id:
            age = time.time() - cache.get('timestamp', 0)
            if age < 300:  # Valid for 5 minutes
                log('Using pre-resolved stream for {}'.format(video_id))
                try:
                    os.remove(_PREFETCH_FILE)
                except OSError:
                    pass
                return cache['stream_url'], cache['info']
            else:
                log('Prefetch cache expired for {}'.format(video_id))
    except (IOError, ValueError, KeyError):
        pass
    return None


def _load_prefetch(video_id):
    """Check prefetch cache; if the service is still resolving, wait briefly.

    The wait is intentionally short and abort-interruptible so a user pressing
    Next again doesn't get stuck behind a blocking sleep inside Kodi's player
    thread. If the service hasn't finished in ~3s, we bail out and let the
    caller resolve directly — the service's result is simply discarded.
    """
    result = _check_prefetch_file(video_id)
    if result:
        return result

    # Check if the background service is currently resolving this video_id
    marker = _PREFETCH_FILE + '.resolving'
    try:
        with open(marker, 'r') as f:
            resolving_vid = f.read().strip()
    except IOError:
        return None

    if resolving_vid != video_id:
        return None

    log('Service is pre-resolving {} — waiting briefly...'.format(video_id))
    monitor = xbmc.Monitor()
    for _ in range(3):  # Wait up to ~3 seconds, abort-interruptible
        if monitor.waitForAbort(1):
            return None
        result = _check_prefetch_file(video_id)
        if result:
            return result
        if not os.path.isfile(marker):
            # Service finished but no cache — resolution must have failed
            break

    log('Prefetch wait timed out for {} — resolving directly'.format(video_id))
    return None


def get_stream_url(video_id, _skip_prefetch=False):
    """Resolve a stream URL using the best available method."""
    # Check if the background service already resolved this track
    if not _skip_prefetch:
        prefetch = _load_prefetch(video_id)
        if prefetch:
            return prefetch

    method, path = _get_resolver()

    if not method:
        raise RuntimeError(
            'Cannot find yt-dlp. Install it via:\n'
            '  Linux: sudo apt install yt-dlp  or  pipx install yt-dlp\n'
            '  Windows: pip install yt-dlp\n'
            'Or set a custom path in addon settings (Advanced > Custom Python path).'
        )

    url = 'https://music.youtube.com/watch?v={}'.format(video_id)
    log('Resolving stream for video_id={} (method={})'.format(video_id, method))

    if method == 'ytdlp_cli':
        return _resolve_via_cli(path, url)
    else:
        return _resolve_via_python(path, url)


def _resolve_via_cli(ytdlp_path, url):
    """Resolve stream by calling yt-dlp binary directly."""
    try:
        result = subprocess.run(
            [ytdlp_path, '-f', 'bestaudio', '-j', '--no-playlist', url],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError('Stream resolution timed out.')

    if result.returncode != 0:
        log('yt-dlp CLI error: {}'.format(result.stderr[:300]))
        raise RuntimeError('yt-dlp failed: {}'.format(result.stderr[:200]))

    try:
        data = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        log('Bad yt-dlp output: {}'.format(result.stdout[:200]))
        raise RuntimeError('yt-dlp returned invalid output.')

    stream_url = data.get('url', '')
    if not stream_url:
        raise RuntimeError('No stream URL returned by yt-dlp.')

    info = {
        'url': stream_url,
        'title': data.get('title', ''),
        'artist': data.get('artist', data.get('uploader', '')),
        'duration': data.get('duration', 0),
        'bitrate': data.get('abr', 0),
    }

    log('Resolved: {} ({} bps)'.format(stream_url[:80], info.get('bitrate', '?')))
    return stream_url, info


def _resolve_via_python(python_path, url):
    """Resolve stream by calling yt-dlp as a Python module."""
    script = (
        'import yt_dlp, json, sys; '
        'ydl_opts = {"format": "bestaudio", "quiet": True, "no_warnings": True, "noplaylist": True}; '
        'ydl = yt_dlp.YoutubeDL(ydl_opts); '
        'info = ydl.extract_info(sys.argv[1], download=False); '
        'print(json.dumps({"url": info.get("url",""), "title": info.get("title",""), '
        '"artist": info.get("artist", info.get("uploader","")), '
        '"duration": info.get("duration",0), '
        '"bitrate": info.get("abr",0)}))'
    )

    try:
        result = subprocess.run(
            [python_path, '-c', script, url],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError('Stream resolution timed out.')

    if result.returncode != 0:
        log('yt-dlp error: {}'.format(result.stderr[:300]))
        raise RuntimeError('yt-dlp failed: {}'.format(result.stderr[:200]))

    try:
        info = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        log('Bad yt-dlp output: {}'.format(result.stdout[:200]))
        raise RuntimeError('yt-dlp returned invalid output.')

    stream_url = info.get('url', '')
    if not stream_url:
        raise RuntimeError('No stream URL returned by yt-dlp.')

    log('Resolved: {} ({} bps)'.format(stream_url[:80], info.get('bitrate', '?')))
    return stream_url, info
