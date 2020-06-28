import re
import dice

name = 'dice'
aliases = ('d', 'в', 'вшсу')
help = '''Roll a die using dice notation (https://github.com/borntyping/python-dice#notation)
In order to prevent chat from being wiped by rolling a large amount of dices (by mistake or on purpose), the output is truncated to be up to 1024 symbols in length.'''

max_characters = 1024


async def handler(args, request):
    if args == []:
        return await request.reply('Empty expression. Type "%help dice" to learn more.')
    expression = ' '.join(args)
    expression = re.sub('в', 'd', expression)
    try:
        die = dice.roll(expression, raw=True)
        result = dice.utilities.verbose_print(die)
        lines = result.split('\n')
        result = ''.join(map(lambda s: s.strip(), lines))
        if len(result) > max_characters:
            result = result[:max_characters - 1] + '…'
    except Exception as e:
        result = str(e)
    await request.reply(result)
