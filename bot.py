from nio import (ClientConfig, AsyncClient, SyncResponse, KeysQueryResponse)
from nio.events.invite_events import InviteMemberEvent

import asyncio
import aiohttp

import logbook
import sys
import glob
import importlib.util
import re
import os
import time

from log import logger_group
import config as cfg
from command import Command
from builtin import MessageLinksInfo, Feeder


class Bot:
    commands = {}
    allowed_users = {}
    cfg = cfg

    sync_delay = 1000

    def __init__(self, loglevel=None):
        config = ClientConfig(encryption_enabled=True,
                              pickle_key=cfg.pickle_key,
                              store_name=cfg.store_name,
                              store_sync_tokens=True)

        if not os.path.exists(cfg.store_path):
            os.makedirs(cfg.store_path)

        timeout = aiohttp.ClientTimeout(total=30)
        self.http_session = aiohttp.ClientSession(
            headers={'User-Agent': cfg.user_agent},
            timeout=timeout
        )

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

        self.mli = MessageLinksInfo(self.http_session)
        self.feeder = Feeder()

        self._register_commands()
        self.client.add_response_callback(self._sync_cb, SyncResponse)
        self.client.add_response_callback(
            self._key_query_cb, KeysQueryResponse)
        self.client.add_event_callback(self._invite_cb, InviteMemberEvent)

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

    async def _serve_feeder(self):
        while True:
            updates = self.feeder.get_updates()
            if len(updates):
                update_start = time.time()
                lines = [
                    f'{u["url"]}\n<strong>{u["title"]}</strong>' for u in updates]
                content = {
                    'body': '\n'.join(lines),
                    'msgtype': 'm.text',
                    'format': 'org.matrix.custom.html'
                }
                content.update({
                    'formatted_body': content['body']
                })

                for room_id in self.client.rooms:
                    await self.client.room_send(room_id, 'm.room.message', content)
                time_to_sleep = cfg.feeder_period - \
                    (time.time() - update_start)
                if time_to_sleep > 0:
                    await asyncio.sleep(time_to_sleep)
            else:
                await asyncio.sleep(cfg.feeder_period)

    async def _serve_forever(self):
        response = await self.client.login(cfg.password)
        self.logger.info(response)
        feeder_task = asyncio.create_task(self._serve_feeder())
        sync_task = asyncio.create_task(
            self.client.sync_forever(1000, full_state=True))
        await asyncio.gather(feeder_task, sync_task)

    async def _key_query_cb(self, response):
        for device in self.client.device_store:
            if device.trust_state.value == 0:
                if device.user_id in cfg.manager_accounts:
                    self.client.verify_device(device)
                    self.logger.info(
                        f'Verified manager\'s device {device.device_id} for user {device.user_id}')
                else:
                    self.client.blacklist_device(device)

    async def _invite_cb(self, room, event):
        if room.room_id not in self.client.rooms and \
           event.sender in cfg.manager_accounts:
            await self.client.join(room.room_id)
            self.logger.info(
                f'Accepted invite to room {room.room_id} from {event.sender}')

    def _is_sender_verified(self, sender):
        devices = [
            d for d in self.client.device_store.active_user_devices(sender)]
        return all(map(lambda d: d.trust_state.value == 1, devices))

    async def _process_links(self, message, room_id):
        info = await self.mli._get_info(message)
        if info:
            nl = '\n'
            content = {
                'body': f'{nl.join(info)}',
                'formatted_body': f'{nl.join(map(lambda i: i.join(["<strong>", "</strong>"]),info))}',
                'format': 'org.matrix.custom.html',
                'msgtype': 'm.text'
            }
            await self.client.room_send(room_id, 'm.room.message', content)

    async def _sync_cb(self, response):
        if len(response.rooms.join) > 0:
            joins = response.rooms.join
            for room_id in joins:
                for event in joins[room_id].timeline.events:
                    if self._is_sender_verified(event.sender) and hasattr(event, 'body'):
                        command, args = self._parse_command(event.body)
                        if command and command in self.commands:
                            await self.commands[command].run(
                                args, event, room_id)
                            self.logger.debug(
                                f'serving command \'{command}\' with arguments {args} in room {room_id}')
                        if event.sender != self.cfg.user:
                            await self._process_links(event.body, room_id)

    def serve(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._serve_forever())
