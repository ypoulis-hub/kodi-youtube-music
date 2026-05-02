"""YouTube Music cookie-based authentication for Kodi.

The Innertube API requires browser session cookies (SAPISID/SID) for
authenticated access. OAuth Bearer tokens are not accepted.

The user exports cookies from their browser and the add-on uses them.
"""

import os
import time
import hashlib
import http.cookiejar
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
COOKIE_FILE = os.path.join(PROFILE, 'cookies.txt')
ORIGIN = 'https://music.youtube.com'

_cookie_dict = None


def log(msg):
    xbmc.log('[YTMusic] auth: {}'.format(msg), xbmc.LOGINFO)


def _load_cookies():
    """Load cookies from file into a simple dict."""
    global _cookie_dict
    if _cookie_dict is not None:
        return _cookie_dict

    _cookie_dict = {}
    try:
        cj = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
        cj.load(ignore_discard=True, ignore_expires=True)
        for c in cj:
            _cookie_dict[c.name] = c.value
        log('Loaded {} cookies'.format(len(_cookie_dict)))
    except Exception as e:
        log('Cookie load error: {}'.format(e))

    return _cookie_dict


def is_authenticated():
    """Check if we have a valid cookie file with SAPISID."""
    if not os.path.isfile(COOKIE_FILE):
        return False
    cookies = _load_cookies()
    return bool(cookies.get('SAPISID') or cookies.get('__Secure-3PAPISID'))


def get_cookie_header():
    """Build a Cookie header string from the stored cookies."""
    cookies = _load_cookies()
    if not cookies:
        return ''
    return '; '.join('{}={}'.format(k, v) for k, v in cookies.items())


def get_auth_header():
    """Generate SAPISIDHASH Authorization header from cookies."""
    cookies = _load_cookies()
    sapisid = cookies.get('__Secure-3PAPISID') or cookies.get('SAPISID')

    if not sapisid:
        return None

    ts = str(int(time.time()))
    hash_input = '{} {} {}'.format(ts, sapisid, ORIGIN)
    sapisidhash = hashlib.sha1(hash_input.encode()).hexdigest()
    return 'SAPISIDHASH {}_{}'.format(ts, sapisidhash)


def get_page_id():
    """Return the brand account page ID from settings, or empty string."""
    return ADDON.getSetting('page_id') or ''


def pick_account():
    """Fetch available accounts and let user pick one. Saves page_id to settings."""
    import json
    import urllib.request
    from lib.innertube import BASE_URL, INNERTUBE_API_KEY, INNERTUBE_CLIENT, USER_AGENT

    cookies = _load_cookies()
    if not cookies:
        xbmcgui.Dialog().ok('YTMusic', 'No cookies found. Import cookies first.')
        return

    sapisid = cookies.get('__Secure-3PAPISID') or cookies.get('SAPISID')
    if not sapisid:
        xbmcgui.Dialog().ok('YTMusic', 'No auth cookies found.')
        return

    ts = str(int(time.time()))
    hash_input = '{} {} {}'.format(ts, sapisid, ORIGIN)
    sapisidhash = hashlib.sha1(hash_input.encode()).hexdigest()
    auth = 'SAPISIDHASH {}_{}'.format(ts, sapisidhash)
    cookie_header = '; '.join('{}={}'.format(k, v) for k, v in cookies.items())

    url = '{}/account/accounts_list?key={}&prettyPrint=false'.format(BASE_URL, INNERTUBE_API_KEY)
    body = json.dumps({
        'context': {
            'client': {
                'clientName': INNERTUBE_CLIENT['clientName'],
                'clientVersion': INNERTUBE_CLIENT['clientVersion'],
                'gl': INNERTUBE_CLIENT['gl'],
                'hl': INNERTUBE_CLIENT['hl'],
            },
            'user': {'lockedSafetyMode': False},
        }
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Referer', 'https://music.youtube.com/')
    req.add_header('Origin', 'https://music.youtube.com')
    req.add_header('Cookie', cookie_header)
    req.add_header('Authorization', auth)
    req.add_header('X-Goog-AuthUser', '0')

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        log('Account list error: {}'.format(e))
        xbmcgui.Dialog().ok('YTMusic', 'Failed to fetch accounts: {}'.format(e))
        return

    # Parse accounts
    accounts = []
    actions = result.get('actions', [])
    for action in actions:
        menu = action.get('getMultiPageMenuAction', {}).get('menu', {}).get('multiPageMenuRenderer', {})
        for sec in menu.get('sections', []):
            for content in sec.get('accountSectionListRenderer', {}).get('contents', []):
                for item in content.get('accountItemSectionRenderer', {}).get('contents', []):
                    acct = item.get('accountItem', {})
                    if not acct:
                        continue
                    name_runs = acct.get('accountName', {}).get('runs', [])
                    name = name_runs[0].get('text', '') if name_runs else 'Unknown'
                    selected = acct.get('isSelected', False)

                    # Extract page ID from datasyncIdToken
                    page_id = ''
                    tokens = acct.get('serviceEndpoint', {}).get(
                        'selectActiveIdentityEndpoint', {}).get('supportedTokens', [])
                    for tok in tokens:
                        ds = tok.get('datasyncIdToken', {}).get('datasyncIdToken', '')
                        if ds and '||' in ds:
                            parts = ds.split('||')
                            # If second part exists, first part is page_id for brand account
                            # If second part is empty, it's the main account (no page_id needed)
                            if parts[1]:
                                page_id = parts[0]
                            break

                    accounts.append({
                        'name': name,
                        'page_id': page_id,
                        'selected': selected,
                    })

    if not accounts:
        xbmcgui.Dialog().ok('YTMusic', 'No accounts found.')
        return

    # Build selection list
    labels = []
    for acct in accounts:
        label = acct['name']
        if acct['page_id']:
            label += ' (brand account)'
        if acct['selected']:
            current_page = ADDON.getSetting('page_id') or ''
            if current_page == acct['page_id']:
                label += ' [current]'
        labels.append(label)

    idx = xbmcgui.Dialog().select('Select Account', labels)
    if idx < 0:
        return

    chosen = accounts[idx]
    ADDON.setSetting('page_id', chosen['page_id'])
    from lib import api
    api.reset_client()
    xbmcgui.Dialog().ok('YTMusic', 'Switched to: {}'.format(chosen['name']))


def reset():
    global _cookie_dict
    _cookie_dict = None


def run_cookie_setup():
    """Guide user through cookie export."""
    dialog = xbmcgui.Dialog()
    os.makedirs(PROFILE, exist_ok=True)

    dialog.ok(
        'YTMusic - Cookie Setup',
        'To sign in, you need to export cookies from your browser.\n\n'
        '1. Install a browser extension:\n'
        '   Chrome: "Get cookies.txt LOCALLY"\n'
        '   Firefox: "cookies.txt"\n\n'
        '2. Go to music.youtube.com (make sure you are signed in)\n\n'
        '3. Click the extension and export cookies'
    )

    # Ask user to browse to the cookies.txt file
    cookie_path = dialog.browse(
        1,  # ShowAndGetFile
        'Select your exported cookies.txt file',
        'files',
        '.txt',
        False, False, ''
    )

    if not cookie_path:
        dialog.ok('YTMusic', 'No file selected. Setup cancelled.')
        return False

    cookie_path = xbmcvfs.translatePath(cookie_path)

    # Validate and copy the cookie file
    try:
        cj = http.cookiejar.MozillaCookieJar(cookie_path)
        cj.load(ignore_discard=True, ignore_expires=True)

        has_sapisid = False
        for c in cj:
            if c.name in ('SAPISID', '__Secure-3PAPISID'):
                has_sapisid = True
                break

        if not has_sapisid:
            dialog.ok(
                'YTMusic - Error',
                'The cookie file does not contain YouTube auth cookies.\n'
                'Make sure you are signed in at music.youtube.com before exporting.'
            )
            return False

        # Save cookies to our profile
        cj.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
        reset()

        dialog.ok('YTMusic', 'Cookies imported successfully! You can now browse your library.')
        return True

    except Exception as e:
        log('Cookie import error: {}'.format(e))
        dialog.ok('YTMusic - Error', 'Failed to read cookie file: {}'.format(e))
        return False
