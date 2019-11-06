help = ''' %olm verify/blacklist <user>
Only specified in configuration file users are allowed to perform this command.'''


async def handler(args, request):
    if request.event.sender in request.bot.cfg.manager_accounts:
        if len(args) == 2:
            action, user_id = args
            action_list = ['verify', 'blacklist']
            if action in action_list:
                action_fn = request.bot.client.verify_device if action == 'verify' \
                    else request.bot.client.blacklist_device
                device_list = []
                for device in request.bot.client.device_store:
                    if device.user_id == user_id:
                        result = action_fn(device)
                        if result:
                            device_list.append(device.device_id)
                            request.logger.info(f'Verified device {device.device_id} '
                                                f'for user {device.user_id}')
                if device_list:
                    await request.reply(f'These devices of user {user_id} were '
                                        f"{'verified' if action == 'verify' else 'blacklisted'}: "
                                        f"{', '.join(device_list)}.")

            else:
                request.reply('awailable actions for %olm command: '
                              f'{", ".join(action_list)}.')
        else:
            await request.reply(help)
