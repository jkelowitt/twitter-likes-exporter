import re


def remove_tag_param(url):
    return re.sub(r'\?tag=\d*', '', url)


def get_resolution(item):
    match = re.search(r'vid/(\d*x\d*)', item)
    if match:
        resolution = match.group(1)
        width, height = map(int, resolution.split('x'))
        return width * height
    return 0


def get_item_with_max_resolution(array):
    array_of_videos = list(filter(lambda item: '.mp4' in item, array))
    item_with_max_res = array_of_videos[0]
    for item in array_of_videos[1:]:
        item_res = get_resolution(item)
        item_with_max_res_res = get_resolution(item_with_max_res)
        if item_res > item_with_max_res_res:
            item_with_max_res = item
    return item_with_max_res


class TweetParser:
    def __init__(self, raw_tweet_json):
        self.is_valid_tweet = True
        self.raw_tweet_json = raw_tweet_json
        self._media_urls = None
        self._video_urls = None

        _tweet_id = raw_tweet_json['entryId'].split('-')[1]
        _twitter_link = f"https://x.com/_/status/{_tweet_id}"

        empty_item_content = not raw_tweet_json["content"].get("itemContent", None)
        if empty_item_content:
            self.is_valid_tweet = False
            # print(f"Tried to retrieve ({_twitter_link}), but it wasn't actually a tweet")  # Who cares?
            return

        if "result" not in raw_tweet_json["content"]["itemContent"]["tweet_results"]:
            self.is_valid_tweet = False
            # print(f"\nTried to retrieve ({_twitter_link}), and failed to get any data")
            return

        self.key_data = raw_tweet_json["content"]["itemContent"]["tweet_results"]["result"]

        legacy_tweet = not self.key_data.get("legacy", None)
        if legacy_tweet:
            self.is_valid_tweet = False
            # print(f"\nTried to retrieve ({_twitter_link}), but it's a legacy (?) tweet")
            return

    def tweet_as_json(self):
        return {
            "tweet_id": self.tweet_id,
            "user_id": self.user_id,
            "user_handle": self.user_handle,
            "user_name": self.user_name,
            "user_avatar_url": self.user_avatar_url,
            "tweet_content": self.tweet_content,
            "tweet_media_urls": self.media_urls,
            "tweet_video_urls": self.video_urls,
            "tweet_created_at": self.tweet_created_at
        }

    @property
    def tweet_id(self):
        return self.key_data["legacy"]["id_str"]

    @property
    def tweet_content(self):
        return self.key_data["legacy"]["full_text"]

    @property
    def tweet_created_at(self):
        return self.key_data["legacy"]["created_at"]

    @property
    def user_id(self):
        return self.key_data["legacy"]["user_id_str"]

    @property
    def user_handle(self):
        return self.user_data["screen_name"]

    @property
    def user_name(self):
        return self.user_data["name"]

    @property
    def user_avatar_url(self):
        return self.user_data["profile_image_url_https"]

    @property
    def user_data(self):
        return self.key_data["core"]["user_results"]["result"]["legacy"]

    @property
    def media_urls(self):
        if self._media_urls is None:
            self._media_urls = []
            media_entries = self.key_data["legacy"]["entities"].get("media", [])
            for entry in media_entries:
                self._media_urls.append(entry["media_url_https"])
        return self._media_urls

    @property
    def video_urls(self):
        if self._video_urls is None:
            self._video_urls = []
            if "extended_entities" in self.key_data["legacy"]:
                media_entries = self.key_data["legacy"]["extended_entities"].get("media", [])
                for entry in media_entries:
                    if "video_info" in entry:
                        best_video_url = get_item_with_max_resolution(
                            list(map(lambda item: item['url'], entry["video_info"]["variants"])))
                        if best_video_url is None:
                            for variant in entry["video_info"]["variants"]:
                                if ".mp4" in variant["url"]:
                                    self._video_urls.append(remove_tag_param(variant["url"]))
                        else:
                            self._video_urls.append(remove_tag_param(best_video_url))
        return self._video_urls
