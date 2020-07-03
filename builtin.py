import asyncio
import magic
import chardet
import youtube_dl
import feedparser

import logbook
from log import logger_group

import re
import gzip
import json
import os
import time

import config as cfg


class CustomLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        raise Exception

    def error(self, msg):
        pass


class MessageLinksInfo:
    chunk_size = 100000
    codecs = ['utf8', 'koi8-r', 'cp1251']

    def __init__(self, session):
        self.session = session
        self.magic = magic.Magic(mime=True, uncompress=True)
        self.ytdl = youtube_dl.YoutubeDL({
            'skip_download': True,
            'logger': CustomLogger()
        })

    def _parse_urls(self, message):
        regex = r'http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_~@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        match = re.findall(regex, message)
        return match

    def _decompress(self, data):
        try:
            return gzip.decompress(data)

        except OSError:
            return None

    def _parse_title(self, html):
        decoded = ''
        detected = chardet.detect(html)
        try:
            decoded = html.decode(detected['encoding'])
        except:
            # fallback method
            for codec in self.codecs:
                try:
                    decoded = html.decode(codec)
                    break
                except Exception as e:
                    decoded = e

        if not isinstance(decoded, str):
            return decoded
        regex = r'<title[\s\S^<]*>([\s\S]*)<\/title>'
        match = re.findall(regex, decoded, re.IGNORECASE)
        return match[0] if match else match

    async def _fetch(self, session, urls):
        entities = []
        for url in urls:
            title = self._ytdl_extract_title(url)
            if title:
                entities.append(title)
            else:
                try:
                    async with session.get(url, proxy=cfg.proxy if hasattr(cfg, 'proxy') else None) as response:
                        chunk = await response.content.readany()
                        while hasattr(response.connection, 'closed') and \
                                not response.connection.closed and \
                                len(chunk) < self.chunk_size:
                            chunk += await response.content.readany()
                        entities.append(chunk)
                except Exception as e:
                    entities.append(e)
        return entities

    def _ytdl_extract_title(self, url):
        try:
            extracted = self.ytdl.extract_info(url)
            return extracted['title']
        except Exception:
            return None

    async def _get_info(self, message):
        urls = self._parse_urls(message)
        entities = None
        if urls:
            entities = await self._fetch(self.session, urls)
        if entities:
            info = []
            for entity in entities:
                if isinstance(entity, str):
                    info.append(f'Title: {entity}')
                elif isinstance(entity, bytes):
                    dcomp = self._decompress(entity)
                    entity = dcomp if dcomp else entity

                    title = self._parse_title(entity)
                    if isinstance(title, str):
                        info.append(f'Title: {title}')
                    else:
                        file_type = self.magic.from_buffer(entity)
                        info.append(f'File type: {file_type}')
                else:
                    info.append(f'Bad link: {repr(entity)}')
            return info

    def get_info(self, message):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._get_info(message))


class Feed:
    def __init__(self, url):
        self.url = url
        feed = feedparser.parse(url)
        if feed.bozo:
            self.error = f'{feed.bozo_exception}'
        else:
            self.error = None
            self.feed = feed
            self.last_update = time.localtime()

    def get_update(self):
        update = []
        feed = feedparser.parse(self.url)
        for entry in feed.entries:
            if hasattr(entry, 'published_parsed'):
                to_compare_with = entry.published_parsed
            elif hasattr(entry, 'updated_parsed'):
                to_compare_with = entry.updated_parsed
            else:
                to_compare_with = time.gmtime(0)

            if to_compare_with > self.last_update:
                update.append({
                    'title': entry.title,
                    'url': entry.link
                })
                self.last_update = to_compare_with
        return update


class Feeder:
    def __init__(self):
        self.logger = logbook.Logger('feeder')
        logger_group.add_logger(self.logger)

        self.urls_file = os.path.join(cfg.store_path, 'feeds.json')
        urls_dump = self._load_urls()
        urls_dump = list(set(urls_dump)) if urls_dump is not None else []
        self.feeds = {}

        if not urls_dump:
            self._dump_urls()
        else:
            for url in urls_dump:
                error = self.add_feed(url)
                if error:
                    self.logger.error(
                        f'Unable to add a feed with url "{url}": {error}')
                else:
                    feed = self.feeds[url].feed
                    self.logger.info(
                        f'loaded up feed {feed.href} with title "{feed.feed.title}"')

    def _load_urls(self):
        if os.path.exists(self.urls_file):
            try:
                urls = json.load(open(self.urls_file))
                if not isinstance(urls, list):
                    self.logger.error(f'{self.urls_file}: wrong format')
                    return None
                if len(urls):
                    for url in urls:
                        if not isinstance(url, str):
                            self.logger.error(
                                f'{self.urls_file}: url must be str, not {type(url)}')
                            return None
                return urls
            except Exception as error:
                self.logger.error(f'{self.urls_file}: {error}')
                return None
        else:
            self.logger.warning(f'{self.urls_file}: file does not exist,'
                                ' assuming there are no feeds added to the bot')
            return None

    def _dump_urls(self):
        json.dump(list(self.feeds.keys()), open(self.urls_file, 'w'))

    def add_feed(self, url):
        if url in self.feeds:
            return 'This feed is already on the list.'
        feed = Feed(url)
        if feed.error:
            return feed.error
        else:
            self.feeds[url] = feed
            self._dump_urls()

    def del_feed(self, url):
        if url in self.feeds:
            self.feeds.pop(url)
            self._dump_urls()
        else:
            return 'This feed is not on the list.'

    def get_updates(self):
        updates = []
        for feed in self.feeds.values():
            updates += feed.get_update()
        return updates
