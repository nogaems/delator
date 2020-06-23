import asyncio
import magic
import chardet
import youtube_dl

import re
import gzip

import config as cfg


class CustomLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

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
        except Exception as error:
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
