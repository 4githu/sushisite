# Personal player

This service keeps its own SQLite database (`player.db`). It only uses the existing Sushi `mainauth` cookie to obtain a numeric user ID. Set `PERSONAL_PLAYER_DB_PATH` to relocate the database when splitting the service from the main backend. The schema is created on first access.

## Required configuration

- `YOUTUBE_API_KEY` is optional. It enables public playlist and single-video imports without connecting a Google account. Restrict the key to the YouTube Data API and the server's IP addresses in production. With a connected Google account, its OAuth token handles these requests instead.
- Existing Google OAuth client ID and secret used by `auth/google_oauth.py`: enable YouTube Data API v3 for that Google Cloud project and allow the `youtube.readonly` scope. The existing `/auth/google/callback` redirect URI is reused.
- Existing `GOOGLE_TOKEN_ENCRYPTION_KEY` (or the existing JWT secret fallback) encrypts Google refresh tokens at rest.

Google authorization is required when no `YOUTUBE_API_KEY` is configured. Private playlists require connecting the owning Google account. The player stores imported playlist contents as an editable snapshot; removing the Google connection does not remove already imported tracks.

The player uses the YouTube IFrame API for playback and supported playback rates. It does not alter advertisements, isolate audio, download videos, or substitute video metadata. YouTube does not expose the user's homepage recommendations through the Data API, so the connected account view lists playlists owned by the user rather than claiming to show YouTube recommendations.

On 2026-10-20, a live IFrame API check with YouTube's example video `M7lc1UVf-VE` reported available rates from 0.25 to 2. Calling `setPlaybackRate(4)` and `setPlaybackRate(8)` both resulted in an actual rate of 2. The UI retains higher requested rates as experiments, shows the currently available rates, and reports the actual rate from the player event. Availability can vary by video and YouTube implementation.
