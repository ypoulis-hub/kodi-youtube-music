"""YTMusic - YouTube Music add-on for Kodi.

Browse and play your YouTube Music Premium library.
Zero external dependencies - uses YouTube Innertube API directly.
"""

import sys
import urllib.parse
import xbmcaddon

from lib.navigation import Router

addon = xbmcaddon.Addon()
handle = int(sys.argv[1])
base_url = sys.argv[0]
args = sys.argv[2][1:] if len(sys.argv) > 2 else ''
params = dict(urllib.parse.parse_qsl(args))

router = Router(handle, base_url)
router.route(params)
