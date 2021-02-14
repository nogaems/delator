from lxml import html
from urllib.parse import unquote
import re

import config as cfg


name = 'search'
aliases = ('s', 'ы')  # Russian users are gonna appreciate that
help = 'Search for a query using DuckDuckGo search engine. '\
    'Multiple arguments will be concatenated. '\
    'Calling without arguments will show the next result (if there are any).'


async def fetch_html(url, session):
    async with session.get(url, proxy=cfg.proxy if hasattr(cfg, 'proxy') else None) as response:
        return await response.text()


def parse_html(document):
    links = list(map(lambda s: unquote(s).split('uddg=')[-1],
                     document.xpath('//h2[contains(@class, "result__title")]/a/@href')))
    titles = list(map(lambda e: e.text_content().strip(),
                      document.xpath('//h2[contains(@class, "result__title")]')))
    snippets = list(map(lambda e: e.text_content().strip(),
                        document.xpath('//a[contains(@class, "result__snippet")]')))
    return (links, titles, snippets)


def compose_url(args):
    endpoint = 'https://duckduckgo.com/html/'
    return f"{endpoint}?q={'+'.join(args)}"


def compose_response(result):
    prefix = 'Result from DuckDuckGo: '
    return f'{prefix}no results' if not result else \
        f'{prefix}\n<strong>Title: {result["title"]}<strong>\n{result["snippet"]}\n{result["link"]}'


def cut_off_extra_spacing(s):
    return re.sub('\n\s*\n', '', s)


async def handler(args, request):
    if args:
        try:
            text = await fetch_html(compose_url(args),
                                    request.bot.http_session)
        except Exception as e:
            request.logger.critical('something went wrong during fetching '
                                    f'request from the search engine: {e}')
            await request.reply(f'{e}')

        document = html.fromstring(text)

        if not hasattr(request.storage, 'search_results'):
            request.storage.search_results = {}
        sr = request.storage.search_results
        if request.room_id not in sr:
            sr[request.room_id] = {}
        sr[request.room_id][request.event.sender] = {
            'results': [], 'pointer': 0
        }

        for link, title, snippet in zip(*parse_html(document)):
            if 'ad_provider' in link or 'Ad\n' in title:
                continue
            title = cut_off_extra_spacing(title)
            snippet = cut_off_extra_spacing(snippet)
            sr[request.room_id][request.event.sender]['results'].append({
                'link': link,
                'title': title,
                'snippet': snippet
            })
    try:
        srd = request.storage.search_results[request.room_id][request.event.sender]
        if srd['results']:
            result = srd['results'][srd['pointer']]
            srd['pointer'] += 1
        else:
            result = None
        response = compose_response(result)
    except (AttributeError, KeyError):
        response = 'you must specify your search query first'
    except IndexError:
        response = 'the end of results list, try to refine your query'
        del request.storage.search_results[request.room_id][request.event.sender]
    await request.reply(response, formatted=True)
