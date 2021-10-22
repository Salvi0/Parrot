from utilities.checks import _can_run
from utilities.database import parrot_db
collection = parrot_db['banned_users']

from core import Parrot

bot = Parrot()


@bot.before_invoke
async def bot_before_invoke(ctx):
    if ctx.guild is not None:
        if not ctx.guild.chunked:
            await ctx.guild.chunk()


@bot.check
async def bot_check(ctx):
    if ctx.command is not None:
        _true = await _can_run(ctx)
        if not _true: 
            await ctx.reply(f'{ctx.author.mention} `{ctx.command.qualified_name}` is being disabled in **{ctx.channel.name}** by the staff!')
        return _true

if __name__ == '__main__':
    bot.run()
