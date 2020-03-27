import os
import subprocess
from io import BytesIO
from multiprocessing.dummy import Pool
from os.path import expanduser
from pathlib import Path
from typing import Dict
from typing import List
from urllib.parse import ParseResult
from urllib.parse import urlparse
from urllib.request import urlopen

import emoji_data_python
import yaml
from lib.anybar_client import AnyBarClient
from lib.slack_client import SlackClient
from PIL import Image
from PIL import UnidentifiedImageError
from tqdm import tqdm

MENUBAR_IMAGE_SIZE_2X = (44, 44)
WORK_POOL_SIZE = os.cpu_count()
EMOJI_DOWNLOAD_PATH = Path(os.path.join(expanduser("~"), ".AnyBar"))
CONFIG_PATH = Path(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.yml")
)

SKIN_TONES = {
    "skin-tone-2": "1F3FB",
    "skin-tone-3": "1F3FC",
    "skin-tone-4": "1F3FD",
    "skin-tone-5": "1F3FE",
    "skin-tone-6": "1F3FF",
}


class SlackTeamStatus(object):
    _slack = None
    use_emoji: bool = True
    use_avatars: bool = True
    config: dict = {"slack": {"token": None, "teammates": None,}}
    anybar: Dict[str, tuple] = {}
    custom_emoji: Dict[str, str] = {}
    user_avatars: Dict[str, str] = {}

    def __init__(self, logger, use_emoji=True, use_avatars=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_emoji = use_emoji
        self.use_avatars = use_avatars
        self.logger = logger

    def read_config(self) -> bool:
        if not Path.exists(CONFIG_PATH):
            return False
        with open(CONFIG_PATH, "r") as stream:
            config = yaml.safe_load(stream)
        assert config, "empty config"
        self.config = config
        return True

    def save_config(self):
        self.logger.info("Saving configuration file")
        with open(CONFIG_PATH, "w") as stream:
            yaml.dump(self.config, stream)

    @property
    def slack(self):
        if not self._slack:
            self._slack = SlackClient(token=self.token)
        return self._slack

    @property
    def token(self) -> str:
        token = self.config["slack"]["token"]
        assert token, "missing slack token"
        return token

    @token.setter
    def token(self, token: str):
        self.config["slack"]["token"] = token

    @property
    def users(self) -> List[str]:
        users = self.config["slack"]["users"]
        assert users, "missing slack users"
        return users

    @users.setter
    def users(self, users: List[str]):
        self.config["slack"]["users"] = users

    def get_status_mapping(self) -> Dict[str, str]:
        mapping = {
            "away": "red",
            "active": "green",
        }
        assert mapping, "missing status mapping"
        assert mapping["away"], "missing away status mapping"
        assert mapping["active"], "missing active status mapping"
        return mapping

    def local_emoji_path(self, emoji_name: str):
        return os.path.join(EMOJI_DOWNLOAD_PATH, emoji_name + "@2x.png")

    def update_emoji(self, url: str, emoji_name: str = None):
        parsed_emoji_name, extension = self.parse_emoji_url(url)
        if emoji_name is None:
            emoji_name = parsed_emoji_name

        local_path = self.local_emoji_path(emoji_name)
        if not Path.exists(Path(local_path)):
            image_data = BytesIO(urlopen(url).read())
            try:
                img = Image.open(image_data)
                resized = img.resize(MENUBAR_IMAGE_SIZE_2X)
                resized.convert("RGBA").save(local_path, "PNG")
            except UnidentifiedImageError:
                self.logger.warning("Unidentified image at %s", url)
            except Exception as e:
                self.logger.exception(e)

    def update_emoji_map(self, args):
        return self.update_emoji(args[0], args[1] if 1 < len(args) else None)

    def update_standard_emoji(self, emoji_name: str, skin_variation: str = None):
        emoji_data = emoji_data_python.find_by_shortname(emoji_name)
        if not emoji_data:
            self.logger.warning("emoji %s not found", emoji_name)
            return
        elif len(emoji_data) > 1:
            self.logger.warning(
                "multiple emoji found for %s: %s", emoji_name, emoji_data
            )
        emoji_data = emoji_data[0]

        if skin_variation and SKIN_TONES[skin_variation] in emoji_data.skin_variations:
            emoji_data = emoji_data.skin_variations[SKIN_TONES[skin_variation]]
            emoji_name = "-".join(
                (emoji_name, skin_variation or "")
            )  # TODO duplication between here and caller

        if not emoji_data.has_img_apple:
            self.logger.warning("No Apple emoji found for %s", emoji_name)

        url = (
            "https://raw.githubusercontent.com/iamcal/emoji-data/master/img-apple-64/"
            + emoji_data.image
        )
        self.update_emoji(url, emoji_name)

    def parse_emoji_url(self, url: str) -> (str, str):
        parsed_url: ParseResult = urlparse(url)
        path_parts = parsed_url.path.split("/")
        extension = path_parts[-1].split(".")[-1]
        emoji_name = path_parts[-2]
        return emoji_name, extension

    def check_if_exists(self, emoji_name, url):
        self.custom_emoji[emoji_name] = url
        if url.startswith("alias:"):
            return None
        _, extension = self.parse_emoji_url(url)

        local_path = self.local_emoji_path(emoji_name)
        if not Path.exists(Path(local_path)):
            return (url, emoji_name)
        return None

    def check_if_exists_map(self, args):
        return self.check_if_exists(*args)

    def get_custom_emoji(self):
        data = self.slack.web_client.emoji_list()

        work_pool = Pool(WORK_POOL_SIZE)

        emoji_to_download = list(
            filter(
                None,
                work_pool.imap_unordered(
                    self.check_if_exists_map, data["emoji"].items()
                ),
            )
        )
        num_emoji = len(emoji_to_download)

        list(
            tqdm(
                work_pool.imap_unordered(self.update_emoji_map, emoji_to_download),
                desc="Downloading Custom Emoji",
                unit="emoji",
                total=num_emoji,
            )
        )

    def resolve_aliases(self, emoji_name: str):
        if emoji_name not in self.custom_emoji:
            return emoji_name  # This is a standard emoji
        if self.custom_emoji[emoji_name].startswith("alias"):
            aliased_emoji = self.custom_emoji[emoji_name].split(":")[-1]
            return self.resolve_aliases(aliased_emoji)
        else:
            return emoji_name

    def launch_anybar(self, port: int):
        anybar_loc = subprocess.run(
            ["mdfind", 'kMDItemCFBundleIdentifier = "tonsky.AnyBar"'],
            check=True,
            capture_output=True,
        )
        path_to_anybar_dir = anybar_loc.stdout.decode().strip()
        if not anybar_loc.stdout:
            raise RuntimeError(
                "Could not find AnyBar application. Please install https://github.com/tonsky/AnyBar first."
            )
        path_to_anybar_cmd = os.path.join(
            path_to_anybar_dir, "Contents", "MacOS", "AnyBar"
        )
        anybar_instance = subprocess.Popen(
            [path_to_anybar_cmd], env={"ANYBAR_PORT": str(port),}
        )
        return anybar_instance

    def pre_download_emoji(self):
        self.ensure_emoji_path()
        self.get_custom_emoji()

    def ensure_emoji_path(self):
        Path.mkdir(EMOJI_DOWNLOAD_PATH, exist_ok=True)

    def status_update(self, **payload):
        self.logger.debug("Received status update event: ", payload)
        user_id = payload["data"]["user"]
        presence = payload["data"]["presence"]
        user_info_res = self.slack.web_client.users_info(user=user_id)
        assert user_info_res["ok"], "bad response"

        user_name = user_info_res["user"]["name"]
        status_text = user_info_res["user"]["profile"]["status_text"]
        status_emoji = user_info_res["user"]["profile"]["status_emoji"]

        self.logger.info(
            "New status for %s: (%s) %s %s",
            user_name,
            presence,
            status_emoji,
            status_text,
        )

        if self.use_avatars:
            if user_id not in self.user_avatars:
                self.user_avatars[user_id] = user_info_res["user"]["profile"][
                    "image_48"
                ]
                if self.user_avatars[user_id]:
                    self.update_emoji(self.user_avatars[user_id], user_id)

        variation = None
        if self.use_emoji and status_emoji:
            emoji_parts = status_emoji.split(":")

            if len(emoji_parts) == 3:  # Standard emoji
                status_emoji = emoji_parts[1]
            elif len(emoji_parts) == 5:  # Skin tone variant
                status_emoji = emoji_parts[1]
                variation = emoji_parts[3]
            else:
                self.logger.error("Unable to parse emoji %s", status_emoji)
            new_status = self.resolve_aliases(status_emoji)
            if new_status not in self.custom_emoji:
                self.update_standard_emoji(new_status, variation)
            if variation:
                new_status = "-".join((new_status, variation))
        elif presence == "active" and self.use_avatars:
            new_status = user_id
        else:
            new_status = self.get_status_mapping()[presence]

        self.logger.debug("Setting %s icon to %s", user_name, new_status)

        self.anybar[user_id][0].update_status(new_status)

    def emoji_update(self, **payload: dict):
        self.logger.debug("Received emoji update event: ", payload)
        if payload["data"]["subtype"] == "add":
            emoji_name = payload["data"]["name"]
            self.logger.info("Adding new emoji %s", emoji_name)
            self.update_emoji(payload["data"]["value"], emoji_name)

    def start(self):
        if self.use_emoji:
            self.ensure_emoji_path()

        anybar_port = 1738
        for user in self.users:
            anybar_instance = self.launch_anybar(port=anybar_port)
            anybar_client = AnyBarClient(port=anybar_port)
            anybar_port += 1
            self.anybar[user] = (anybar_client, anybar_instance)

        self.slack.add_callback("presence_change", self.status_update)
        self.slack.add_callback("emoji_changed", self.emoji_update)

        def subscribe(**payload: dict):
            self.slack.subscribe_to_presence(self.users)

        self.slack.add_callback("hello", subscribe)

        self.logger.info("SlackTeamStatus updater running. Press Ctrl-C to exit.")
        self.slack.connect()
