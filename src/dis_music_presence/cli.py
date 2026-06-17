from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .discord_ipc import DiscordConfigError, DiscordError, DiscordIpcClient, check_discord
from .formatter import PresenceFormatter
from .models import ActivityKind, MediaActivity, MediaType
from .runtime import PresenceRuntime, build_providers
from .settings import DEFAULT_SETTINGS, SettingsError, init_settings, load_settings, set_setting


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    try:
        return args.handler(args)
    except (SettingsError, DiscordError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dmp", description="DisMusicPresence CLI")
    parser.add_argument("--settings", default="dmp.settings", help="Path to local settings file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    subparsers = parser.add_subparsers(dest="command")

    version = subparsers.add_parser("version", help="Show the application version.")
    version.set_defaults(handler=_cmd_version)

    config = subparsers.add_parser("config", help="Manage local settings.")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_init = config_sub.add_parser("init", help="Create local settings.")
    config_init.add_argument("--force", action="store_true", help="Overwrite existing settings.")
    config_init.set_defaults(handler=_cmd_config_init)
    config_show = config_sub.add_parser("show", help="Show settings with secrets redacted.")
    config_show.set_defaults(handler=_cmd_config_show)
    config_set = config_sub.add_parser("set", help="Set one setting.")
    config_set.add_argument("key", choices=sorted(DEFAULT_SETTINGS), help="Setting key.")
    config_set.add_argument("value", help="Setting value.")
    config_set.set_defaults(handler=_cmd_config_set)
    config_keys = config_sub.add_parser("keys", help="List supported setting keys.")
    config_keys.set_defaults(handler=_cmd_config_keys)

    diagnostics = subparsers.add_parser("diagnostics", help="Check local configuration and source support.")
    diagnostics.set_defaults(handler=_cmd_diagnostics)

    probe = subparsers.add_parser("probe", help="Poll enabled sources once without updating Discord.")
    probe.set_defaults(handler=_cmd_probe)

    run = subparsers.add_parser("run", help="Run the presence bridge.")
    run.add_argument("--once", action="store_true", help="Poll once and exit.")
    run.add_argument("--dry-run", action="store_true", help="Print runtime decisions without updating Discord.")
    run.set_defaults(handler=_cmd_run)

    test_presence = subparsers.add_parser("test-presence", help="Publish a short test presence to Discord.")
    test_presence.add_argument("--text", default="DisMusicPresence test", help="Text to publish.")
    test_presence.set_defaults(handler=_cmd_test_presence)

    return parser


def _cmd_version(args: argparse.Namespace) -> int:
    print(__version__)
    return 0


def _cmd_config_init(args: argparse.Namespace) -> int:
    path = init_settings(args.settings, force=args.force)
    print(f"Initialized settings: {path}")
    return 0


def _cmd_config_show(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    for key, value in settings.redacted().items():
        print(f"{key}={value}")
    return 0


def _cmd_config_set(args: argparse.Namespace) -> int:
    set_setting(args.settings, args.key, args.value)
    print(f"Updated {args.key}")
    return 0


def _cmd_config_keys(args: argparse.Namespace) -> int:
    for key in sorted(DEFAULT_SETTINGS):
        print(key)
    return 0


def _cmd_diagnostics(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    print(f"Settings: {settings.path}")

    discord = check_discord(settings.get("discord.client_id"))
    discord_state = _state_label(discord.available, discord.configured)
    print(f"Discord: {discord_state} - {discord.message}")

    for provider in build_providers(settings):
        cap = provider.capability()
        source_state = _source_state(cap.enabled, cap.supported, cap.configured)
        print(f"{cap.name}: {source_state} - {cap.message}")
        for line in provider.diagnostics():
            print(f"  {line}")
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    formatter = PresenceFormatter(settings)
    for provider in build_providers(settings):
        activity = provider.poll()
        formatted = formatter.format(activity)
        line = formatted.text if formatted else activity.message
        print(f"{provider.name}: {activity.kind.value} - {line}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    runtime = PresenceRuntime(settings, dry_run=args.dry_run)
    if args.once:
        print(runtime.tick())
        runtime.shutdown()
        return 0
    runtime.run_forever()
    return 0


def _cmd_test_presence(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    activity = MediaActivity(
        kind=ActivityKind.LISTENING,
        source="DisMusicPresence",
        media_type=MediaType.MUSIC,
        title=args.text,
        artist="Test",
        player_state="playing",
    )
    presence = PresenceFormatter(settings).format(activity)
    if presence is None:
        raise DiscordConfigError("Could not create test presence.")
    client = DiscordIpcClient(settings.get("discord.client_id"))
    try:
        client.connect()
        client.set_activity(presence)
    finally:
        client.close()
    print(f"Published test presence: {presence.text}")
    return 0


def _state_label(available: bool, configured: bool) -> str:
    if available:
        return "available"
    if configured:
        return "unavailable"
    return "unconfigured"


def _source_state(enabled: bool, supported: bool, configured: bool) -> str:
    if not enabled:
        return "disabled"
    if not supported:
        return "unsupported"
    if not configured:
        return "unconfigured"
    return "configured"
