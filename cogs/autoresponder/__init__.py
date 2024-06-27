from __future__ import annotations

import asyncio
import difflib
import re
from typing import Annotated

import async_timeout
from jinja2.sandbox import SandboxedEnvironment

import discord
from core import Cog, Context, Parrot
from discord.ext import commands, tasks

from .jinja_help import TOPICS
from .variables import Variables


class Environment(SandboxedEnvironment):
    intercepted_binops = frozenset(["//", "%", "**", "<<", ">>", "&", "^", "|", "*"])

    def call_binop(self, context, operator: str, left, right):
        disabled_operators = ["//", "%", "**", "<<", ">>", "&", "^", "|", "*"]
        if operator in disabled_operators:
            return self.undefined(f"Undefined binary operator: {operator}", name=operator)

        return super().call_binop(context, operator, left, right)


class AutoResponders(Cog):
    """Autoresponders for your server."""

    def __init__(self, bot: Parrot) -> None:
        self.bot = bot
        self.cache = {}
        self.cooldown = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.channel)
        self.exceeded_cooldown = commands.CooldownMapping.from_cooldown(3, 10, commands.BucketType.channel)

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="\N{ROBOT FACE}")

    @tasks.loop(seconds=300)
    async def check_autoresponders(self) -> None:
        for guild_id, data in self.cache.items():
            await self.update_to_db(guild_id, data)

    async def update_to_db(self, guild_id: int, data: dict) -> None:
        await self.bot.guild_configurations.update_one(
            {"_id": guild_id},
            {"$set": {"autoresponder": data}},
        )

    async def cog_load(self):
        self.check_autoresponders.start()
        async for guild_data in self.bot.guild_configurations.find({"autoresponder": {"$exists": True}}):
            self.cache[guild_data["_id"]] = guild_data["autoresponder"]

    async def cog_unload(self):
        self.check_autoresponders.cancel()

    @commands.group(name="autoresponder", aliases=["ar"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autoresponder(self, ctx: Context) -> None:
        """Autoresponder commands. See `$ar tutorial` for more info.

        You must have Manage Server permission to use this command.
        """
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @autoresponder.command(name="tutorial")
    async def autoresponder_tutorial(self, ctx: Context, *, entity: str | None = None) -> None:
        """Tutorial for autoresponder commands."""
        # get the entity from TOPICS, use difflib to get the closest match
        if entity:
            et = difflib.get_close_matches(entity, TOPICS.keys(), n=1, cutoff=0.5)
            if not et:
                await ctx.reply(f"No tutorial found for that entity {entity}.")
                return

            description = TOPICS[et[0]]
            embed = discord.Embed(
                title="Autoresponder Tutorial",
                description=description,
            )
            await ctx.reply(embed=embed)
            return

        embed = (
            discord.Embed(
                title="Autoresponder Tutorial",
                description=(
                    "Autoresponders are messages that are sent when a user sends a message that matches a certain pattern. "
                    "For example, you can set up an autoresponder that sends a message when a user says `hello`. "
                    "Autoresponders can be used to create commands, or to send a message when a user says a certain word. "
                ),
            )
            .add_field(
                name="Creating an autoresponder",
                value=(
                    "To create an autoresponder, use the command `$ar add <name> <response>`. "
                    "The name of the autoresponder must be unique. "
                ),
                inline=False,
            )
            .add_field(
                name="For make the response more dynamic",
                value=(
                    "You can use Jinja2 template to make the response more dynamic. "
                    "For example, you can use `<@{{ message.author.id }}>` to mention the user who sent the message. "
                    "You can also use `{{ message.author.name }}` to get the name of the user who sent the message. "
                ),
                inline=False,
            )
            .add_field(
                name="Detail Documentation of variables",
                value=(
                    "- [Autoresponder Docs](https://github.com/rtk-rnjn/Parrot/wiki/Autoresponder)\n"
                    "- [Autoresponder Variable Docs](https://github.com/rtk-rnjn/Parrot/wiki/Autoresponder-Variables-Docs)"
                ),
                inline=False,
            )
            .set_footer(
                text=(
                    "To get syntax of jinja2 template, use `$ar tutorial <entity>.\n"
                    "Available entities: `" + "`, `".join(TOPICS.keys()) + "`"
                ),
            )
        )
        await ctx.reply(embed=embed)

    @autoresponder.command(name="variables", aliases=["vars", "var"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_variables(self, ctx: Context) -> None:
        """Show variables that can be used in autoresponder response."""
        var = Variables(message=ctx.message, bot=self.bot)
        variables = await var.build_base()

        def format_var(v: str) -> str:
            return "{{ " + v + " }}"

        des = ""
        for v, _f in variables.items():
            des += f"`{format_var(v):<22}`\n"
        embed = discord.Embed(
            title="Autoresponder Variables",
            description=des,
        )
        await ctx.reply(embed=embed)

    @autoresponder.command(name="ignore")
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_ignore(self, ctx: Context, name: str, entity: discord.Role | discord.TextChannel) -> None:
        """Ignore a role or channel from an autoresponder."""
        if name not in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name does not exist.")
            return

        if isinstance(entity, discord.Role):
            if "ignore_role" not in self.cache[ctx.guild.id][name]:
                self.cache[ctx.guild.id][name]["ignore_role"] = []

            if entity.id in self.cache[ctx.guild.id][name]["ignore_role"]:
                await ctx.reply("That role is already ignored.")
                return

            self.cache[ctx.guild.id][name]["ignore_role"].append(entity.id)
            await ctx.reply(f"Ignored role `{entity.name}` from autoresponder `{name}`.")
        elif isinstance(entity, discord.TextChannel):
            if "ignore_channel" not in self.cache[ctx.guild.id][name]:
                self.cache[ctx.guild.id][name]["ignore_channel"] = []

            if entity.id in self.cache[ctx.guild.id][name]["ignore_channel"]:
                await ctx.reply("That channel is already ignored.")
                return

            self.cache[ctx.guild.id][name]["ignore_channel"].append(entity.id)
            await ctx.reply(f"Ignored channel `{entity.name}` from autoresponder `{name}`.")

    @autoresponder.command(name="add", aliases=["create", "set"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_add(
        self,
        ctx: Context,
        name: str,
        *,
        res: Annotated[str, commands.clean_content | None] = None,
    ) -> None:
        """Add a new autoresponder.

        The name of the autoresponder must be unique.
        """

        if len(name) <= 5:
            await ctx.reply("The name of the autoresponder must be longer than 5 characters.")
            return

        if name in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name already exists.")
            return

        if not res:
            await ctx.reply("You must provide a response.")
            return

        ins = Variables(message=ctx.message, bot=self.bot)
        variables = await ins.build_base()
        content, err = await self.execute_jinja(name, res, from_auto_response=False, **variables)

        if err:
            await ctx.reply(f"Failed to add autoresponder `{name}`.\n\n`{content}`")
            return

        self.cache[ctx.guild.id][name] = {
            "enabled": True,
            "response": res,
            "ignore_role": [],
            "ignore_channel": [],
        }
        await ctx.reply(f"Added autoresponder `{name}`.")

    @autoresponder.command(name="remove", aliases=["delete", "del", "rm"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_remove(self, ctx: Context, name: str) -> None:
        """Remove an autoresponder."""
        if name not in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name does not exist.")
            return

        del self.cache[ctx.guild.id][name]
        await ctx.reply(f"Removed autoresponder `{name}`.")

    @autoresponder.command(name="list", aliases=["ls", "all"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_list(self, ctx: Context) -> None:
        """List all autoresponders."""
        if not self.cache[ctx.guild.id]:
            await ctx.reply("There are no autoresponders.")
            return

        embed = discord.Embed(title="Autoresponders")
        embed.description = "".join(f"`{name}`\n" for name in self.cache[ctx.guild.id])
        await ctx.reply(embed=embed)

    @autoresponder.command(name="edit", aliases=["change", "modify"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_edit(
        self,
        ctx: Context,
        name: str,
        *,
        res: Annotated[str, commands.clean_content | None] = None,
    ) -> None:
        """Edit an autoresponder."""
        if name not in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name does not exist.")
            return

        if not res:
            await ctx.reply("You must provide a response.")
            return

        self.cache[ctx.guild.id][name] = {
            "enabled": self.cache[ctx.guild.id][name].get("enabled", True),
            "response": res,
            "ignore_role": self.cache[ctx.guild.id][name].get("ignore_role", []),
            "ignore_channel": self.cache[ctx.guild.id][name].get("ignore_channel", []),
        }
        await ctx.reply(f"Edited autoresponder `{name}`.")

    @autoresponder.command(name="info", aliases=["show"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_info(self, ctx: Context, name: str) -> None:
        """Show info about an autoresponder."""
        if name not in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name does not exist.")
            return

        embed = discord.Embed(title=name)
        embed.description = self.cache[ctx.guild.id][name]["response"]

        await ctx.reply(embed=embed)

    @autoresponder.command(name="enable", aliases=["on", "boot", "enabled", "start"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_enable(self, ctx: Context, name: str) -> None:
        """Enable an autoresponder."""
        if name not in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name does not exist.")
            return

        if self.cache[ctx.guild.id][name].get("enabled"):
            await ctx.reply("That autoresponder is already enabled.")
            return

        self.cache[ctx.guild.id][name]["enabled"] = True
        await ctx.reply(f"Enabled autoresponder `{name}`.")

    @autoresponder.command(name="disable", aliases=["off", "shutdown", "disabled", "mute", "stop"])
    @commands.has_permissions(manage_guild=True)
    async def autoresponder_disable(self, ctx: Context, name: str) -> None:
        """Disable an autoresponder."""
        if name not in self.cache[ctx.guild.id]:
            await ctx.reply("An autoresponder with that name does not exist.")
            return

        if not self.cache[ctx.guild.id][name].get("enabled"):
            await ctx.reply("That autoresponder is already disabled.")
            return

        self.cache[ctx.guild.id][name]["enabled"] = False
        await ctx.reply(f"Disabled autoresponder `{name}`.")

    @autoresponder.before_invoke
    @autoresponder_add.before_invoke
    @autoresponder_remove.before_invoke
    @autoresponder_list.before_invoke
    @autoresponder_edit.before_invoke
    @autoresponder_info.before_invoke
    @autoresponder_enable.before_invoke
    @autoresponder_disable.before_invoke
    async def ensure_cache(self, ctx: Context) -> None:
        if ctx.guild.id not in self.cache:
            self.cache[ctx.guild.id] = self.bot.guild_configurations_cache[ctx.guild.id].get("autoresponder", {})

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot or not self.cache.get(message.guild.id):
            return

        assert isinstance(message.author, discord.Member)

        var = Variables(message=message, bot=self.bot)
        variables = await var.build_base()

        for name, data in self.cache[message.guild.id].items():
            if not data.get("enabled") or len(name) <= 5:
                continue

            if message.channel.id in data.get("ignore_channel", []):
                continue

            if any(role.id in data.get("ignore_role", []) for role in message.author.roles):
                continue

            response = data["response"]

            content = None

            if self.is_ratelimited(message):
                continue

            try:
                if re.fullmatch(rf"{name}", message.content, re.IGNORECASE):
                    content, _ = await self.execute_jinja(name, response, **variables)
            except re.error:
                if name == message.content:
                    content, _ = await self.execute_jinja(name, response, **variables)

            if content and (str(content).lower().strip(" ") != "none"):
                await message.channel.send(content)

    def is_ratelimited(self, message: discord.Message):
        bucket = self.cooldown.get_bucket(message)
        exceeded_bucket = self.exceeded_cooldown.get_bucket(message)
        if exceeded_bucket and exceeded_bucket.update_rate_limit(message.created_at.timestamp()):
            return True

        return bool(bucket and bucket.update_rate_limit(message.created_at.timestamp()))

    async def execute_jinja(
        self,
        trigger: str,
        response: str,
        *,
        from_auto_response: bool = True,
        **variables,
    ) -> tuple[str, bool]:
        if not hasattr(self, "jinja_env"):
            self.jinja_env = Environment(
                enable_async=True,
                trim_blocks=True,
                lstrip_blocks=True,
                keep_trailing_newline=False,
                autoescape=False,
            )

        trigger = discord.utils.escape_mentions(trigger)
        executing_what = "autoresponder" if from_auto_response else "jinja2"

        try:
            async with async_timeout.timeout(delay=0.3):
                try:
                    template = await asyncio.to_thread(self.jinja_env.from_string, response)
                    return_data = await template.render_async(**variables)
                    if len(return_data) > 1990:
                        return (
                            f"Gave up executing {executing_what} - `{trigger}`.\nReason: `Response is too long`",
                            True,
                        )
                    return return_data, False
                except Exception as e:
                    return (
                        f"Gave up executing {executing_what}.\nReason: `{e.__class__.__name__}: {e}`",
                        True,
                    )
        except Exception as e:
            return (
                f"Gave up executing {executing_what} - `{trigger}`.\nReason: `{e.__class__.__name__}: {e}`",
                True,
            )

    @commands.command(name="jinja", aliases=["j2", "jinja2"])
    async def jinja(self, ctx: Context, *, code: str) -> None:
        """Execute jinja2 code. To practice your Autoresponder skills."""
        if code.startswith(("```jinja", "```", "```py")) and code.endswith("```"):
            code = "\n".join(code.split("\n")[1:-1])

        code = code.strip("`").strip("\n").strip("")

        variables = Variables(message=ctx.message, bot=self.bot)
        variables = await variables.build_base()

        owner = await self.bot.is_owner(ctx.author)

        if not owner:
            variables = {}

        try:
            content, error = await self.execute_jinja("None", code, from_auto_response=False, **variables)
        except Exception as e:
            content = f"Failed to execute jinja2 code.\nReason: `{e.__class__.__name__}: {e}`"

        if not content or content.lower().strip(" ") == "none":
            content = "_No output_"

        await ctx.reply(content)


async def setup(bot: Parrot) -> None:
    await bot.add_cog(AutoResponders(bot))
