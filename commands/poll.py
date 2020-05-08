import secrets
import math
import time
import shlex
import json
import asyncio
from aiohttp import web

name = 'poll'
aliases = ('зщдд')
help = ''' Start, participate and get results of a poll.
%poll start <option1,>
Starts a new poll.
Use space as the separator of options, quote options containing spaces with " or '.
If there is only one <option> specified, 'not <option>' option will be automatically added.
%poll stop <id>
Stops the poll with id <id>. Prints the result. Only creator of a poll can stop it.
%poll <id> <code>
Vote in a poll. Multiple choice is not allowed.
You can vote only once during a poll and can not change your answer.
In order to obtain a vote code you have to send a GET request to a certain endpoint.
Ask a room moderator for details.
'''

# Configuration section.
# There's no actual need to split it up into two files I suppose,
# so I just put it here since there's no sensetive information involved.
host = '127.0.0.1'
port = '1334'
uri = '/delator/poll/'
code_length = 4
poll_timeout = 3600  # in seconds
max_polls_num = 1024
max_codes_num = 1024  # per poll, i.e. means amount of possible participants


async def get_options(request):
    id = request.match_info['id']
    if id in polls:
        options = {'options': polls[id]['options']}
        return web.Response(text=json.dumps(options))
    else:
        return web.Response(text=f'A poll with id {id} does not exist.', status=404)


async def get_code(request):
    id = request.match_info['id']
    answer = request.match_info['answer']
    if id not in polls:
        return web.Response(text=f'A poll with id {id} does not exist.', status=404)
    if len(polls[id]['codes']) > max_codes_num:
        return web.Response(text=f'The maximum amount of participants of this poll exceeded.', status=403)
    if answer not in polls[id]['options']:
        return web.Response(text=f'Invalid answer. Awailable options: {polls[id]["options"]}', status=400)
    num_bytes = code_length // 2 if code_length % 2 == 0 else \
        (code_length + 1) // 2
    while True:
        code = secrets.token_hex(num_bytes)
        code = code if code_length % 2 == 0 else code[1:]
        if code not in polls[id]['codes']:
            break
    polls[id]['codes'][code] = answer
    return web.Response(text=f'Your answer code is {code}. '
                        'Now in order to use it to vote in this poll, send this to the chat:\n'
                        f'%poll {id} {code}\n')


async def init():
    app = web.Application()

    base_uri = uri if uri.endswith('/') else uri + '/'
    options_uri = base_uri + '{id}'
    code_uri = base_uri + '{id}/{answer}'

    app.router.add_get(options_uri, get_options)
    app.router.add_get(code_uri, get_code)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()


async def cleanup():
    while True:
        current_timestamp = time.time()
        ids = list(polls.keys())
        for id in ids:
            if id in polls and current_timestamp - polls[id]['timestamp'] >= poll_timeout:
                polls.pop(id)
        await asyncio.sleep(5)


polls = {}

asyncio.gather(init(), cleanup())


async def handler(args, request):
    if len(args) < 2:
        return await request.reply('See %help poll')
    sender = request.event.sender
    if args[0] == 'start':
        if len(polls) > max_polls_num:
            return await request.reply('The maximum amount of started polls is exceeded. '
                                       'Wait until some of them eventually time out.')
        args = args[1:]
        args = shlex.split(' '.join(args))
        # in case if only one polling option is specified
        if len(args) == 1:
            args.append(f'not {args[0]}')
        num_bytes = math.ceil(math.log(max_polls_num, 2) / 8)
        id = secrets.token_hex(num_bytes)
        while id in polls:
            id = secrets.token_hex(num_bytes)
        polls[id] = {
            'creator': sender,
            'timestamp': time.time(),
            'options': args,
            'codes': {},
            'answers': {}
        }
        return await request.reply(f'Poll <strong>{id}</strong> has been started.', formatted=True)
    if args[0] == 'stop':
        id = args[1]
        if id not in polls:
            return await request.reply(f'A poll with id <strong>{id}</strong> does not exist.',
                                       formatted=True)
        poll = polls[id]
        if poll['creator'] != sender:
            return await request.reply(f'You have to be the creator of this poll in order to stop it.')
        response = f'Poll <strong>{id}</strong> has been stopped.'
        if not len(poll['answers']):
            response += ' No one voted though :('
        else:
            total_votes = len(poll['answers'])
            dist = {}
            all_answers = list(poll['answers'].values())
            present_answers = set(all_answers)
            for answer in present_answers:
                dist[answer] = '{:.2f}%'.format(
                    all_answers.count(answer) * 100 / total_votes)
            response += ' Here is the result:\n'
            response += '\n'.join([f'{p}: <strong>{a}</strong>\n' for p, a
                                   in poll['answers'].items()])
            response += f'Votes distribution: {dist}'
        polls.pop(id)
        return await request.reply(response, formatted=True)
    id = args[0]
    code = args[1]
    if id not in polls:
        return await request.reply(f'A poll with id <strong>{id}</strong> does not exist.', formatted=True)
    if code not in polls[id]['codes']:
        return await request.reply(f'Wrong code.')
    if sender in polls[id]['answers']:
        return await request.reply(f'You are not allowed to vote twice in the same poll.')
    polls[id]['answers'][sender] = polls[id]['codes'][code]
    polls[id]['codes'].pop(code)
    return await request.reply('Voted successfully. '
                               'Now wait until the creator of this poll stops it to find out the result.')
