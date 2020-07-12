name = 'rss'
help = '''%rss list | add <url> | del <url>
Manage the list of feeds that bot will follow and post updates from.
RSS and Atom are both supported. Addition/deletion is only available for manager accounts.'''


async def handler(args, request):
    if not len(args) or (len(args) == 1 and args[0] == 'list'):
        if not len(request.bot.feeder.feeds):
            await request.reply('The list is empty!')
        else:
            items = [f'{feed.title} ({feed.link})'
                     for feed in [feed.feed.feed
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
            error = request.bot.feeder.del_feed(args[1])
            response = error if error else 'Deleted!'
            await request.reply(response)
        else:
            await request.reply(help)
    else:
        await request.reply(help)
