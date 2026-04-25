# YTMusic - Kodi Add-on

YouTube Music player for Kodi. Requires a **YouTube Music Premium** account.

## Features

- Browse: Playlists, Liked Songs, Albums, Artists, Library, History
- Search: Songs, Albums, Artists, Playlists
- Play: High-quality audio streaming via yt-dlp
- Radio: "Play Radio" context menu queues similar tracks
- Home: Personalized recommendations

## Prerequisites

1. **Kodi 19 (Matrix)** or newer (Python 3 required)
2. **Python packages** (install in Kodi's Python or system Python):
   ```
   pip install ytmusicapi yt-dlp
   ```
3. **YouTube Music Premium** account

## Installation

1. Copy the `plugin.audio.ytmusic` folder to your Kodi addons directory:
   - **Windows**: `%APPDATA%\Kodi\addons\`
   - **Linux**: `~/.kodi/addons/`
   - **macOS**: `~/Library/Application Support/Kodi/addons/`

2. Restart Kodi, go to **Add-ons > My add-ons > Music add-ons > YTMusic**

3. On first launch, select **Set Up Authentication** and follow the OAuth flow,
   or use the manual CLI method:
   ```
   ytmusicapi oauth --file "<kodi-profile>/addon_data/plugin.audio.ytmusic/oauth.json"
   ```

## Settings

- **Auth Method**: OAuth (recommended) or Browser Headers
- **Audio Quality**: Best / High (256k) / Medium (128k) / Low (64k)
- **Prefer audio-only**: Skip video streams, save bandwidth
- **yt-dlp path**: Custom path if yt-dlp isn't on PATH

## Troubleshooting

- **"ytmusicapi not installed"**: Run `pip install ytmusicapi` in the Python
  environment Kodi uses.
- **"yt-dlp not found"**: Run `pip install yt-dlp` or set the path in settings.
- **Auth errors**: Delete `oauth.json` from the add-on profile and re-authenticate.
- **No audio**: Check that your Premium subscription is active.
