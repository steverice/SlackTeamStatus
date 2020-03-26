# Slack Team Status

Keep tabs on your team while working remotely.

## Setup

1. Install [AnyBar](https://github.com/tonsky/AnyBar)
1. Launch AnyBar (`open -a AnyBar`) successfully (register with [Gatekeeper](https://support.apple.com/en-us/HT202491)) and close.
1. Create virtualenv `python3 -m venv .venv`
1. Install requirements `pip install -r requirements.txt`
1. Obtain a [Slack API Token](https://api.slack.com/legacy/custom-integrations/legacy-tokens) for the workspace you want to monitor.
1. Find the [Slack user IDs](https://help.workast.com/hc/en-us/articles/360027461274-How-to-find-a-Slack-user-ID) of your teammates.

## Running

#### First Time
```
./slack_team_status.py --token <YOUR_SLACK_TOKEN> --teammates <USER_ID> <USER_ID> <USER_ID> --save-config
```

#### With Saved Config
Once you've run once and the config has been saved, you can simply run
```
./slack_team_status.py
```

#### Help

To view help and more options, run
```
./slack-team-status.py -h
```
