# Changelog

All notable changes to **YouTube Music for Kodi** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
