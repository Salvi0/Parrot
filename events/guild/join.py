from core import Parrot, Cog
from utilities.database import guild_join, guild_remove
import aiohttp, os

BASE_URL = "https://discord.com/api/webhooks/883368274501460039/"

class GuildJoin(Cog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: Parrot):
        self.bot = bot
        self.channel = None
        self.url = BASE_URL + os.environ('CHANNEL_TOKEN1')

    @Cog.listener()
    async def on_guild_join(self, guild):
        if self.channel is None:
            self.channel = self.bot.get_channel(883368274501460039)
        CONTENT = f"Joined {guild.name} ({guild.id}). Total member in {guild.name}: {guild.member_count}. Server Region: {str(guild.region).replace('_', ' ').title()}. Total server on count {len(self.bot.guilds)}. Total users on count: {len(self.bot.users)}"
        await guild_join(guild.id)
        data = {
            'username': "Parrot",
            'avatar_url': self.bot.user.display_avatar.url,
            'content': CONTENT,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=data) as res:
                if res == 200:
                    pass
                else:
                    await self.channel.send(CONTENT)

    @Cog.listener()
    async def on_guild_remove(self, guild):
        if self.channel is None:
            self.channel = self.bot.get_channel(883368274501460039)
        CONTENT = f"Left {guild.name} ({guild.id}). Total member in {guild.name}: {guild.member_count}. Server Region: {str(guild.region).replace('_', ' ').title()}. Total server on count {len(self.bot.guilds)}. Total users on count: {len(self.bot.users)}"
        await guild_remove(guild.id)
        data = {
            'username': "Parrot",
            'avatar_url': self.bot.user.display_avatar.url,
            'content': CONTENT,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=data) as res:
                if res == 200:
                    pass
                else:
                    await self.channel.send(CONTENT)

    @Cog.listener()
    async def on_guild_update(self, before, after):
        pass


def setup(bot):
    bot.add_cog(GuildJoin(bot))
