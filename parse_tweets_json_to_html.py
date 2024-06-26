import datetime
import json
import os
import time

import cv2
import requests
from tqdm import tqdm


def parse_text_for_html(input_text):
    return input_text.encode('ascii', 'xmlcharrefreplace').decode()


def make_containing_dir(fp: str) -> None:
    """ Create the parent directories required for the file `fp` """
    containing_dir = os.path.dirname(fp)
    if not os.path.isdir(containing_dir):
        os.makedirs(containing_dir)


def save_remote_media(remote_url, local_path):
    reattempt = False
    img_data = None

    if os.path.exists(local_path):
        return  # Don't re-download an image
    make_containing_dir(local_path)

    # Download the requested media
    try:
        img_data = requests.get(remote_url).content
    except requests.exceptions.ConnectionError as e:
        print("Attempted download failed, retrying 3 times, 10 seconds apart")
        reattempt = True

    # Automatically retry if Twitter refuses our connection
    if reattempt:
        for _ in range(3):
            time.sleep(10)
            try:
                img_data = requests.get(remote_url).content
            except requests.exceptions.ConnectionError:
                ...  # Try, try again
            if img_data:
                print("Success, continuing")

        raise requests.exceptions.ConnectionError(f"Automatic and manual retries exceeded for downloading {remote_url}")

    with open(local_path, 'wb') as handler:
        handler.write(img_data)


def create_video_thumbnail(video_path, out_path):
    video = cv2.VideoCapture(video_path)
    success, image = video.read()

    if not success:
        print(f"\nError creating local thumbnail for {video_path}")
        print(f"This file is likely broken.")
        return ""  # Don't show a thumbnail if we couldn't make it

    cv2.imwrite(out_path, image)
    return out_path


class ParseTweetsJSONtoHTML:
    def __init__(self):
        self._output_html_directory = None
        self._tweets_as_json = None

        with open("config.json") as json_data_file:
            config_data = json.load(json_data_file)
            self.output_json_file_path = config_data.get('OUTPUT_JSON_FILE_PATH')
            self.download_images = config_data.get('DOWNLOAD_IMAGES')
            self.download_videos = config_data.get('DOWNLOAD_VIDEOS')

    def write_tweets_to_html(self):
        with open(self.output_index_path, 'w') as output_html:
            output_html.write('<html><head>')
            output_html.write('<meta name="viewport" content="width=device-width, '
                              'initial-scale=1, minimum-scale=1.0, maximum-scale=1.0" />')
            output_html.write('<title>Liked Tweets Export</title>')
            output_html.write('<link rel="stylesheet" href="styles.css"></head>')
            output_html.write('<body><h1>Liked Tweets</h1><div class="tweet_list">')
            pbar = tqdm(self.tweets_as_json, dynamic_ncols=True)
            for tweet_data in pbar:
                tweet_link = f"https://x.com/_/status/{tweet_data['tweet_id']}"
                pbar.set_description(f"Downloading tweet: {tweet_link}")
                tweet_html = self.create_tweet_html(tweet_data)
                output_html.write(tweet_html)
            output_html.write('</div></body></html>')

    def create_tweet_html(self, tweet_data):
        output_html = '<div class="tweet_wrapper">'

        if self.download_images:
            user_image_src = f'avatars/{tweet_data["user_id"]}.jpg'
            full_path = f"{self.output_html_directory}/{user_image_src}"
            save_remote_media(tweet_data["user_avatar_url"], full_path)
        else:
            user_image_src = tweet_data["user_avatar_url"]

        output_html += '<div class="tweet_author_wrapper">'
        output_html += f"<div class='tweet_author_avatar'><img loading='lazy' src='{user_image_src}'></div>"
        output_html += "<div class='author_context'><div class='tweet_author_handle'>"
        output_html += f"<a href='https://www.twitter.com/{tweet_data['user_handle']}/' target='_blank'>"
        output_html += f"@{parse_text_for_html(tweet_data['user_handle'])}</a></div>"
        output_html += f"<div class='tweet_author_name'>{parse_text_for_html(tweet_data['user_name'])}</div>"
        output_html += '</div></div>\n'

        output_html += f"<div class='tweet_content'>{parse_text_for_html(tweet_data['tweet_content'])}</div>"

        if tweet_data["tweet_video_urls"]:
            output_html += "<div class='tweet_videos_wrapper'>"
            for media_url in tweet_data["tweet_video_urls"]:
                if self.download_videos:
                    # Download video
                    media_name = media_url.split("/")[-1]
                    user_video_path = f'videos/{media_name}'
                    full_path = f"{self.output_html_directory}/{user_video_path}"
                    save_remote_media(media_url, full_path)

                    # Create video thumbnail
                    thumbnail_path = f"{self.output_html_directory}/video_thumbs/{tweet_data['tweet_id']}.jpg"
                    create_video_thumbnail(full_path, thumbnail_path)

                else:
                    user_video_path = media_url

                output_html += f"<div class='tweet_media'><video controls preload='none' "
                output_html += f"poster='{tweet_data['tweet_video_urls'][0]}'><a href='{user_video_path}' "
                output_html += f"target='_blank'>Download video</a><source src='{user_video_path}' "
                output_html += f"type='video/mp4' /></video></div>"
            output_html += "</div>\n"
        else:
            if tweet_data["tweet_media_urls"]:
                output_html += "<div class='tweet_media_wrapper'>"
                for media_url in tweet_data["tweet_media_urls"]:
                    if self.download_images:
                        media_name = media_url.split("/")[-1]
                        user_image_path = f'images/{media_name}'
                        full_path = f"{self.output_html_directory}/{user_image_path}"
                        save_remote_media(media_url, full_path)
                    else:
                        user_image_path = media_url

                    output_html += f"<div class='tweet_media'><a href='{user_image_path}' target='_blank'>"
                    output_html += f"<img loading='lazy' src='{user_image_path}'></a></div>"
                output_html += "</div>\n"

        parsed_datetime = datetime.datetime.strptime(tweet_data['tweet_created_at'], "%a %b %d %H:%M:%S +0000 %Y")
        output_html += f"<div class='tweet_created_at'>{parsed_datetime.strftime('%m/%d/%Y %I:%M%p')}</div>"
        output_html += "<div class='twitter_link'>"
        output_html += f"<a href='https://www.twitter.com/{tweet_data['user_handle']}/status/{tweet_data['tweet_id']}/'"
        output_html += " target='_blank'>Original tweet &#8599;</a> &#8226; "
        individual_tweet_file_path = f"{self.output_html_directory}/tweets/{tweet_data['tweet_id']}.html"
        output_html += f"<a href='tweets/{tweet_data['tweet_id']}.html' target='_blank'>Local version</a>"
        output_html += "</div>"

        output_html += "</div>\n\n"

        make_containing_dir(individual_tweet_file_path)
        with open(individual_tweet_file_path, 'w') as individual_tweet_file:
            individual_tweet_file.write('<html><head>')
            individual_tweet_file.write('<meta name="viewport" content="width=device-width, '
                                        'initial-scale=1, minimum-scale=1.0, maximum-scale=1.0" />')
            individual_tweet_file.write('<title>Liked Tweets Export</title>')
            individual_tweet_file.write('<link rel="stylesheet" href="../styles.css"></head>')
            individual_tweet_file.write('<body><div class="tweet_list">')
            adjusted_html = output_html.replace("avatars", "../avatars")
            adjusted_html = adjusted_html.replace("images", "../images")
            individual_tweet_file.write(adjusted_html)
            individual_tweet_file.write('</div></body></html>')

        return output_html

    @property
    def output_index_path(self):
        return f'{self.output_html_directory}/index.html'

    @property
    def output_html_directory(self):
        if not self._output_html_directory:
            script_dir = os.path.dirname(__file__)
            self._output_html_directory = os.path.join(script_dir, 'html')
        return self._output_html_directory

    @property
    def tweets_as_json(self):
        if not self._tweets_as_json:
            with open(self.output_json_file_path, 'rb') as json_file:
                lines = json_file.readlines()
                self._tweets_as_json = json.loads(lines[0])

        return self._tweets_as_json


if __name__ == "__main__":
    parser = ParseTweetsJSONtoHTML()
    parser.write_tweets_to_html()
