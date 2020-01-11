import asyncio
import magic
import chardet

import re
import gzip

import config as cfg

class MessageLinksInfo:
    chunk_size = 100000
    codecs = ['utf8', 'koi8-r', 'cp1251']

    def __init__(self, session):
        self.session = session
        self.magic = magic.Magic(mime=True, uncompress=True)

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
        chunks = []
        for url in urls:
            try:
                async with session.get(url, proxy=cfg.proxy if hasattr(cfg, 'proxy') else None) as response:
                    chunk = await response.content.readany()
                    while hasattr(response.connection, 'closed') and\
                            not response.connection.closed and \
                            len(chunk) < self.chunk_size:
                        chunk += await response.content.readany()
                    chunks.append(chunk)
            except Exception as e:
                chunks.append(e)
        return chunks

    async def _get_info(self, message):
        urls = self._parse_urls(message)
        chunks = None
        if urls:
            chunks = await self._fetch(self.session, urls)
        if chunks:
            info = []
            for chunk in chunks:
                if not isinstance(chunk, bytes):
                    info.append(f'Bad link: {repr(chunk)}')
                else:
                    dcomp = self._decompress(chunk)
                    chunk = dcomp if dcomp else chunk

                    title = self._parse_title(chunk)
                    if isinstance(title, str):
                        info.append(f'Title: {title}')
                    else:
                        file_type = self.magic.from_buffer(chunk)
                        info.append(f'File type: {file_type}')
            return info

    def get_info(self, message):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._get_info(message))
