# Usage

## Initialize Settings

```sh
dmp config init
```

Set the Discord application client ID:

```sh
dmp config set discord.client_id YOUR_DISCORD_APPLICATION_CLIENT_ID
```

## Check Diagnostics

```sh
dmp diagnostics
```

Diagnostics report whether settings exist, Discord IPC is available, and each source is configured, disabled, unsupported, or unavailable. Secrets are not printed.

## Probe Sources

Poll enabled sources once without updating Discord:

```sh
dmp probe
```

## Run The Bridge

```sh
dmp run
```

Run once and exit:

```sh
dmp run --once
```

Run without updating Discord:

```sh
dmp run --dry-run
```

## Publish A Test Presence

```sh
dmp test-presence
```

This requires Discord to be running and `discord.client_id` to be configured.

## Apple Music Notes

Apple Music support is macOS-only. If macOS asks for automation permission, allow the terminal or app host running DisMusicPresence to control Music.

Paused or stopped Apple Music playback does not publish stale listening presence.

## Plex Notes

Plex support can use Tautulli or direct Plex server API.

For Tautulli:

```sh
dmp config set plex.enabled true
dmp config set plex.provider auto
dmp config set plex.username YOUR_PLEX_USERNAME
dmp config set tautulli.url http://YOUR_TAUTULLI_HOST:8181
dmp config set tautulli.api_key YOUR_TAUTULLI_API_KEY
```

For direct Plex server API:

```sh
dmp config set plex.enabled true
dmp config set plex.provider plex
dmp config set plex.username YOUR_PLEX_USERNAME
dmp config set plex.url http://YOUR_PLEX_HOST:32400
dmp config set plex.token YOUR_PLEX_TOKEN
```

Movies format as `Watching Movie Name`. TV episodes format as `Watching Show Name - SxxExx - Episode Name`.
