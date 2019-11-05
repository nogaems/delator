from nio import (ClientConfig, AsyncClient, SyncResponse)

import asyncio
import aiofiles

import logbook
import sys
import glob
import importlib.util
import re
import os

from log import logger_group
import config as cfg
from command import Command


class Bot:
    commands = {}
    sync_delay = 1000

    def __init__(self, loglevel=None):
        config = ClientConfig(encryption_enabled=True,
                              pickle_key=cfg.pickle_key, store_name=cfg.store_name)
        self.client = AsyncClient(
            cfg.server,
            cfg.user,
            cfg.device_id,
            config=config,
            store_path=cfg.store_path
        )

        logger_group.level = getattr(
            logbook, loglevel) if loglevel else logbook.CRITICAL
        logbook.StreamHandler(sys.stdout).push_application()

        self.logger = logbook.Logger('bot')
        logger_group.add_logger(self.logger)

        self._register_commands()

    def _preserve_name(self, path):
        return path.split('/')[-1].split('.py')[0].strip().replace(' ', '_').replace('-', '')

    def _validate_module(self, module):
        return hasattr(module, 'handler') and callable(module.handler)

    def _process_module(self, module):
        name = self._preserve_name(module.name) if hasattr(module, 'name') and isinstance(
            module.name, str) else module.__name__

        handler = module.handler

        raw_aliases = module.aliases if hasattr(module, 'aliases') and \
            (isinstance(module.aliases, tuple) or isinstance(module.aliases, str)) else ()
        raw_aliases = raw_aliases if isinstance(
            raw_aliases, tuple) else [raw_aliases]
        aliases = ()

        for alias in raw_aliases:
            alias = self._preserve_name(alias.replace('%', ''))
            aliases = (*aliases, alias)

        help = module.help if hasattr(module, 'help') and \
            isinstance(module.help, str) else ''

        return (name, handler, aliases, help)

    def _register_commands(self):
        files_to_import = [fn for fn in glob.glob(
            "./commands/*.py") if not fn.count('__')]
        for file_path in files_to_import:
            try:
                name = self._preserve_name(file_path)
                spec = importlib.util.spec_from_file_location(
                    name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                name = module.name if hasattr(module, 'name') else name

                if not self._validate_module(module):
                    raise ImportError(f'Unable to register command \'{name}\' '
                                      f'(\'{module.__file__}\'). '
                                      'Command module must contain a callable '
                                      'object with name \'handler\'.')

                command = Command(
                    *self._process_module(module), self)

                if not self.commands.get(command.name):
                    self.commands[command.name] = command
                else:
                    raise ImportError(
                        f'Unable to register command \'{command.name}\' '
                        f'(\'{module.__file__}\'). '
                        'A command with this name already exists.')

                for alias in command.aliases:
                    if not self.commands.get(alias):
                        self.commands[alias] = command
                    else:
                        self.logger.warn(f'Unable to register alias \'{alias}\'! '
                                         'An alias with this name already exists '
                                         f'({self.commands[alias]}). Ignoring.')
            except Exception as e:
                self.logger.critical(e)

        if self.commands:
            self.logger.info(
                f'Registered commands: {list(set(self.commands.values()))}')
        else:
            self.logger.warn('No commands added!')

    def _parse_command(self, message):
        match = re.findall(r'^%([\w\d_]*)\s?(.*)$', message)
        if match:
            return (match[0][0], (match[0][1].split()))
        else:
            return (None, None)

    async def _serve_forever(self):
        response = await self.client.login(cfg.password)
        self.logger.info(response)

        next_batch_token_path = f'{cfg.store_path}next_batch_token' if \
            cfg.store_path.endswith('/') else f'{cfg.store_path}/next_batch_token'
        if os.path.isfile(next_batch_token_path):
            async with aiofiles.open(next_batch_token_path, 'r') as next_batch_token:
                self.client.next_batch = await next_batch_token.read()
                await next_batch_token.close()
                self.logger.info(
                    f'Next batch token: {self.client.next_batch}')

        while True:
            sync_response = await self.client.sync(self.sync_delay)

            async with aiofiles.open(next_batch_token_path, 'w') as next_batch_token:
                await next_batch_token.write(sync_response.next_batch)

            if len(sync_response.rooms.join) > 0:
                joins = sync_response.rooms.join
                for room_id in joins:
                    for event in joins[room_id].timeline.events:
                        if hasattr(event, 'body'):
                            command, args = self._parse_command(event.body)
                            if command and command in self.commands:
                                await self.commands[command].run(
                                    args, event, room_id)

    def serve(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._serve_forever())
