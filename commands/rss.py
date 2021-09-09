name = 'rss'
help = '''%rss list | add <url> | del <url>
Manage the list of feeds that bot will follow and post updates from.
RSS and Atom are both supported. Addition/deletion is only available for manager accounts.'''


async def handler(args, request):
    if not len(args) or (len(args) == 1 and args[0] == 'list'):
        if not len(request.bot.feeder.feeds):
            await request.reply('The list is empty!')
        else:
            items = [f'{feed.feed.title} ({feed.feed.link})' if not feed.error else
                     f'{feed.href} (error: {feed.error})'
                     for feed in [feed.feed
                                  for feed in request.bot.feeder.feeds.values()]]
            items = '\n'.join(
                [f'<strong>{n}<strong>: {items[n]}' for n in range(len(items))])
            await request.reply(f'feeds list:\n{items}', formatted=True)
    elif request.event.sender in request.bot.cfg.manager_accounts and len(args) == 2:
        if args[0] == 'add':
            error = request.bot.feeder.add_feed(args[1])
            response = error if error else 'Added!'
            await request.reply(response)
        elif args[0] == 'del':
            try:
                rss_num = int(args[1])
                rss_link = list(request.bot.feeder.feeds.keys())[rss_num]
            except ValueError:
                rss_link = args[1]
            except IndexError:
                total_num = len(request.bot.feeder.feeds)
                response = f'There {"is" if total_num == 1 else "are"} only {total_num}' \
                    f' element{"s" if total_num > 1 else ""} on the list!' if total_num else \
                    'The list is empty!'
                await request.reply(response)
                return
            error = request.bot.feeder.del_feed(rss_link)
            response = error if error else 'Deleted!'
            await request.reply(response)
        else:
            await request.reply(help)
    else:
        await request.reply(help)
