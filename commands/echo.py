name = 'echo'
aliases = ('ping')
help = 'echo command'


async def handler(args, request):
    response = '' if args == [] else ' '.join(args)
    await request.reply(response)
