import re
import dice

name = 'dice'
aliases = ('d', 'в', 'вшсу')
help = 'Roll a die using dice notation (https://github.com/borntyping/python-dice#notation)'


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
    except Exception as e:
        result = str(e)
    await request.reply(result)
