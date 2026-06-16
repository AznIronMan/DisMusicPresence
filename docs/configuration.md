# Configuration

DisMusicPresence uses a local settings file named `dmp.settings`.

Create it with:

```sh
dmp config init
```

Show current settings with secrets redacted:

```sh
dmp config show
```

Update a setting:

```sh
dmp config set discord.client_id YOUR_DISCORD_APPLICATION_CLIENT_ID
```

List supported keys:

```sh
dmp config keys
```

Do not commit `dmp.settings` to git.

## Core Settings

```text
app.poll_interval_seconds
app.source_priority
discord.enabled
discord.client_id
```

Default source priority is:

```text
apple_music,plex
```

## Formatting Settings

```text
format.listening
format.watching_movie
format.watching_episode
```

Default templates:

```text
Listening to ♪ {artist} - {title}
Watching {title}
Watching {show_title} - {episode_code} - {episode_title}
```

Available template fields include:

```text
source
player_state
title
artist
album
show_title
season
episode
episode_code
episode_title
```

## Apple Music Settings

```text
apple_music.enabled
```

Apple Music is supported on macOS only. The first time the app checks Apple Music, macOS may ask for automation permission.

## Plex Settings

```text
plex.enabled
plex.provider
plex.username
plex.user_id
tautulli.url
tautulli.api_key
plex.url
plex.token
```

`plex.provider` supports:

```text
auto
tautulli
plex
```

Use `auto` to prefer Tautulli when configured and fall back to direct Plex server API when needed.

Configure either `plex.username` or `plex.user_id` so the app selects the right user's playback session. This prevents another Plex user's activity from being published.

Example Tautulli setup:

```sh
dmp config set plex.enabled true
dmp config set plex.provider auto
dmp config set plex.username YOUR_PLEX_USERNAME
dmp config set tautulli.url http://YOUR_TAUTULLI_HOST:8181
dmp config set tautulli.api_key YOUR_TAUTULLI_API_KEY
```

Example direct Plex server API setup:

```sh
dmp config set plex.enabled true
dmp config set plex.provider plex
dmp config set plex.username YOUR_PLEX_USERNAME
dmp config set plex.url http://YOUR_PLEX_HOST:32400
dmp config set plex.token YOUR_PLEX_TOKEN
```
