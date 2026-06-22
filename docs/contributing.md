# Contributing

DisMediaPresence is open for public use, forks, and contributions.

## Expectations

- Keep license and attribution notices intact.
- Keep dependencies declared in project metadata instead of vendoring them into the repository.
- Keep secrets, local settings, logs, caches, virtual environments, and generated artifacts out of git.
- Update tests when behavior changes.
- Update docs when setup, configuration, commands, behavior, or support status changes.
- Use semantic versioning for user-visible changes.

## Local Workflow

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
```

## Public Issue Guidance

When reporting a problem, include:

- Operating system and Python version.
- DisMediaPresence version.
- Media source being used.
- Whether Discord is running.
- Redacted diagnostic output from `dmp diagnostics`.

Do not post API keys, tokens, local settings files, or private playback details.
