import logbook
from log import logger_group


class Storage:
    pass


class Request:
    def __init__(self, event, room_id, bot, storage, logger):
        self.event = event
        self.room_id = room_id
        self.bot = bot
        self.storage = storage
        self.logger = logger

    async def reply(self, text, formatted=None):
        sender = self.event.sender.split('@')[1].split(':')[0]
        content = {
            'body': f'{sender}: {text}',
            'msgtype': 'm.text'
        }
        if formatted:
            content.update({
                'formatted_body': content['body'],
                'format': 'org.matrix.custom.html',
            })
        await self.bot.client.room_send(self.room_id, 'm.room.message', content)


class Command:
    def __init__(self, name, handler, aliases, help, bot):
        self.name = name
        self.handler = handler
        self.aliases = aliases
        self.help = help
        self.bot = bot

        self.storage = Storage()

        self.logger = logbook.Logger(name)
        logger_group.add_logger(self.logger)

    async def run(self, args, event, room_id):
        request = Request(event, room_id, self.bot,
                          self.storage, self.logger)
        try:
            await self.handler(args, request)
        except Exception as e:
            self.logger.critical(e)

    def __repr__(self):
        return repr("%" + self.name) if not self.aliases else \
            f'{repr("%"+self.name)} (with aliases: {", ".join(map(lambda x: repr("%"+x), self.aliases))})'
