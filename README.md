# YTMusic — YouTube Music for Kodi

`plugin.audio.ytmusic` — Browse and play your YouTube Music Premium library directly in Kodi. No external dependencies — uses the YouTube Innertube API directly.

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/donate/?business=ypoulis%40gmail.com&currency_code=EUR)

---

## Features

- Home feed with personalized recommendations
- Full library: playlists, albums, artists, liked songs, history
- Search with filters (songs, albums, artists, playlists)
- Artist pages with top songs, albums, and singles
- Lyrics display
- Radio / watch playlist (auto-queues similar tracks)
- Brand account switching
- Background stream prefetching for gapless-ish playback
- Audio quality selection (Best / 256kbps / 128kbps / 64kbps)

## Requirements

- Kodi 21 (Omega) or later
- YouTube Music Premium subscription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) installed on the system (or auto-installed by the add-on)

## Installation

1. Download the zip from the `v1.0.7/` folder
2. In Kodi: **Settings → Add-ons → Install from zip file**
3. Navigate to the downloaded zip and install
4. Follow the authentication steps below

## Authentication

This add-on uses browser cookies for authentication — no passwords are stored.

1. Install a browser cookie export extension:
   - Chrome: *Get cookies.txt LOCALLY*
   - Firefox: *cookies.txt*
2. Log in to [music.youtube.com](https://music.youtube.com)
3. Export cookies to a `cookies.txt` file (Mozilla/Netscape format)
4. In Kodi, go to **Add-on Settings → Authentication → Re-import cookies.txt** and select the file

## Settings

| Setting | Description |
|--------|-------------|
| Brand Account Page ID | For YouTube brand/channel accounts (leave empty for personal account) |
| Re-import cookies.txt | Import a new cookies file |
| Audio Quality | Best / High (256kbps) / Medium (128kbps) / Low (64kbps) |
| Items per page | 25 / 50 / 100 |
| Custom Python path | Override yt-dlp Python path (leave empty for auto-detect) |
| Debug logging | Enable verbose logging to Kodi log |

## License

MIT

---

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/donate/?business=ypoulis%40gmail.com&currency_code=EUR)
