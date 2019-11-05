name = 'help'
aliases = 'h'
help = 'this command'


async def handler(args, request):
    if args == []:
        await request.reply(f"Available commands: {', '.join(map(str, set(request.bot.commands.values())))}. "
                            '%help <command> for details.')
    else:
        response = ''
        for cmd in args:
            cmd = cmd.replace('%', '') if cmd.startswith('%') else cmd
            if request.bot.commands.get(cmd):
                command = request.bot.commands[cmd]
                response += f'[{command.name}]: {command.help}\n'
        if response:
            await request.reply(response)
