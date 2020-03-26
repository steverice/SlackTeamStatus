#!/usr/bin/env python3
import sys

from lib.app import SlackTeamStatus
import argparse
from argparse import ArgumentError
import logging

LOGGER = logging.getLogger("SlackTeamStatus")
LOGGER.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
LOGGER.addHandler(handler)


def main(args):
    app = SlackTeamStatus(
        logger=LOGGER, use_emoji=not args.no_emoji, use_avatars=not args.no_avatars
    )
    if not args.skip_config:
        if not app.read_config():
            LOGGER.info("No config file found. Skipping config file.")
            args.skip_config = True
    if args.skip_config and not args.token:
        raise ArgumentError(
            args.token,
            "You must specify a Slack token. Generate at https://api.slack.com/legacy/custom-integrations/legacy-tokens.",
        )
    if args.skip_config and not args.teammates:
        raise ArgumentError(
            args.teammates,
            "You must specify teammates as a list of Slack user IDs. See https://help.workast.com/hc/en-us/articles/360027461274-How-to-find-a-Slack-user-ID to find user IDs for your teammates.",
        )

    if args.token:
        app.token = args.token
    if args.teammates:
        app.users = args.teammates

    if args.save_config:
        app.save_config()
    if args.download_emoji:
        app.pre_download_emoji()
    app.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
    Slack Team Status updater.
    Keeps your Mac's menu bar updated with the current status of your teammates.
    """
    )
    slack = parser.add_argument_group(title="Slack options")
    slack.add_argument(
        "--token",
        metavar="SLACK_API_TOKEN",
        help="A Slack API token. Generate at https://api.slack.com/legacy/custom-integrations/legacy-tokens",
    )
    slack.add_argument(
        "--teammates",
        nargs="*",
        metavar="USER_ID",
        help="Slack user IDs of teammates you want to monitor. See https://help.workast.com/hc/en-us/articles/360027461274-How-to-find-a-Slack-user-ID",
    )
    app = parser.add_argument_group(title="Application options")
    app.add_argument(
        "--download-emoji",
        action="store_true",
        help="Pre-download all custom emoji from your Slack workspace (may be slow)",
    )
    app.add_argument(
        "--no-emoji",
        action="store_true",
        help="Only use colored status orbs, not emoji",
    )
    app.add_argument(
        "--no-avatars",
        action="store_true",
        help="Use status orb instead of user avatar to represent active state",
    )
    app.add_argument(
        "--save-config",
        action="store_true",
        help="Save configuration options to a YAML file so you do not need to re-enter them",
    )
    app.add_argument(
        "--skip-config",
        action="store_true",
        help="Do not load configuration options from YAML",
    )

    args = parser.parse_args()

    main(args)
