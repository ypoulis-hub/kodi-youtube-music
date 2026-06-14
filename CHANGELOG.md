# Changelog

All notable changes to **YouTube Music for Kodi** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.10] – 2026-06-14

### Changed
- Cover art (album/artist/playlist thumbnails) now requested at much higher resolution. Default bumped from a fixed 544px to **1200px**, with a new **Settings → Library → Cover art resolution** option (544 / 800 / 1200 / 1600px).
- Thumbnail upscaling now covers all Google image hosts (`lh3`–`lh6.googleusercontent.com`, `yt3.ggpht.com`, `yt3.googleusercontent.com`) instead of only `lh3.googleusercontent.com`, and appends a size token to URLs that lacked one — so artist and other-host images upscale too.

### Fixed
- `i.ytimg.com` upscaling bug where `hqdefault` became `hqmaxresdefault` (the `default` substring matched first), producing broken image URLs. Now matched on the full basename.

## [1.0.9] – 2026-05-26

### Fixed
- System freeze / playback stop when pressing Next twice in rapid succession. Kodi spawns parallel plugin invocations for rapid skips, and two simultaneous `setResolvedUrl` callbacks were wedging PAPlayer (sometimes hanging the UI entirely, sometimes ending playback with "EXCEPTION: Kodi is not playing any file"). Superseded invocations now exit silently without touching PAPlayer, so only the latest skip resolves to a stream.

### Changed
- Background service pre-resolves the next playlist track at the **start** of every track (first 8s) in addition to the end. Rapid Next presses now hit the prefetch cache and return instantly instead of waiting 3-4s for yt-dlp.
- Service polling interval tightened from 3s → 2s.
- Prefetch wait inside `get_stream_url` shortened from 30s → ~3s and switched to `xbmc.Monitor().waitForAbort()` (abort-interruptible).
- yt-dlp subprocess timeout reduced 30s → 20s.

## [1.0.8] – 2026-04-25

### Added
- yt-dlp installs into the add-on's own profile directory (`special://profile/.../bin/`) so it does not require a system-wide install
- `script.module.requests` declared as a dependency in `addon.xml`

### Changed
- Removed the `/storage` path heuristic for LibreELEC detection — unreliable on other Linux distros
- Removed `~/.local/bin` from install targets and search paths
- Replaced `urllib.request` with `script.module.requests` for HTTP calls
- Downloads now use `xbmcvfs.copy()` first, with `requests` as fallback

### Fixed
- LibreELEC detection edge cases that previously broke first-run install
- yt-dlp resolution failures on minimal Linux installs

### Tested on
- Windows 10 / 11 with Kodi 21 Omega
- LibreELEC running Kodi 21 Omega

## [1.0.7] – 2026-04-04

### Added
- First public Kodi-forum release of the YTMusic add-on
