from __future__ import annotations

import asyncio
import pathlib
import random
from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

import arrow
from rapidfuzz import fuzz, process

import discord
from core import Cog
from discord.ext import commands
from utilities.exceptions import ParrotCheckFailure

if TYPE_CHECKING:
    from core import Context, Parrot

T = TypeVar(
    "T",
    bound=discord.Member | discord.Emoji | discord.TextChannel | discord.Role | discord.VoiceChannel,
)

quote_ = pathlib.Path("extra/quote.txt").read_text()
quote = quote_.split("\n")
quote = [i for i in quote if i]  # this is to remove empty lines

QUESTION_MARK = "\N{BLACK QUESTION MARK ORNAMENT}"


class ErrorView(discord.ui.View):
    def __init__(
        self,
        author_id,
        *,
        ctx: Context | None = None,
        error: commands.CommandError | None = None,
    ) -> None:
        super().__init__(timeout=300.0)
        self.author_id = author_id
        self.ctx = ctx
        self.error = error

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("You can't interact with this button", ephemeral=True)
        return False

    @discord.ui.button(label="Show full error", style=discord.ButtonStyle.green)
    async def show_full_traceback(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message(str(self.error), ephemeral=True)


class Cmd(Cog, command_attrs={"hidden": True}):
    """This category is of no use for you, ignore it."""

    def __init__(self, bot: Parrot) -> None:
        self.bot = bot

    @Cog.listener()
    async def on_command(self, ctx: Context):
        """This event will be triggered when the command is being completed; triggered by [discord.User]!."""
        if ctx.author.bot:
            return
        await ctx.database_command_update(success=not ctx.command_failed)

    def _get_object_by_fuzzy(self, *, argument: str, objects: Sequence[T]) -> tuple[T, str, int] | None:
        """Get an object from a list of objects by fuzzy matching."""
        if not argument:
            return None
        CUT_OFF = 90
        names = [o.name for o in objects]
        if data := process.extractOne(argument, names, scorer=fuzz.WRatio, score_cutoff=CUT_OFF):
            result, score, position = data
            return objects[position], result, int(score)

    @Cog.listener()
    async def on_command_error(self, ctx: Context, error: commands.CommandError):  # noqa: PLR0912, PLR0915, C901
        await self.bot.wait_until_ready()
        # elif command has local error handler, return
        if hasattr(ctx.command, "on_error"):
            return

        # get the original exception
        error = getattr(error, "original", error)
        TO_RAISE_ERROR, DELETE_AFTER, RESET_COOLDOWN = False, None, False
        ignore = (
            commands.CommandNotFound,
            discord.NotFound,
            discord.Forbidden,
            commands.PrivateMessageOnly,
            commands.NotOwner,
        )

        if isinstance(error, ignore):
            return

        ERROR_EMBED = discord.Embed(color=discord.Color.light_embed())
        if isinstance(error, commands.BotMissingPermissions):
            missing = [perm.replace("_", " ").replace("guild", "server").title() for perm in error.missing_permissions]
            if len(missing) > 2:
                fmt = f'{", ".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            ERROR_EMBED.description = f"Please provide the following permission(s) to the bot.```\n{fmt}```"
            ERROR_EMBED.set_author(name=(f"{QUESTION_MARK} Bot Missing permissions {QUESTION_MARK}"))
            RESET_COOLDOWN = True

        elif isinstance(error, commands.CommandOnCooldown):
            now = arrow.utcnow().shift(seconds=error.retry_after).datetime
            DELETE_AFTER = error.retry_after
            discord_time = discord.utils.format_dt(now, "R")
            ERROR_EMBED.description = f"You are on command cooldown, please retry **{discord_time}**"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Command On Cooldown {QUESTION_MARK}")

        elif isinstance(error, commands.MissingPermissions):
            if await self.bot.is_owner(ctx.author):
                await ctx.reinvoke()
                return

            missing = [perm.replace("_", " ").replace("guild", "server").title() for perm in error.missing_permissions]
            if len(missing) > 2:
                fmt = f'{"**, **".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)

            ERROR_EMBED.description = f"You need the following permission(s) to the run the command.```\n{fmt}```"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Missing permissions {QUESTION_MARK}")
            RESET_COOLDOWN = True

        elif isinstance(error, commands.MissingRole):
            missing = [error.missing_role]
            if len(missing) > 2:
                fmt = f'{"**, **".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            ERROR_EMBED.description = f"You need the the following role(s) to use the command```\n{fmt}```"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Missing Role {QUESTION_MARK}")
            RESET_COOLDOWN = True

        elif isinstance(error, commands.MissingAnyRole):
            missing = list(error.missing_roles)
            if len(missing) > 2:
                fmt = f'{"**, **".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            ERROR_EMBED.description = f"You need the the following role(s) to use the command```\n{fmt}```"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Missing Role {QUESTION_MARK}")
            RESET_COOLDOWN = True

        elif isinstance(error, commands.NSFWChannelRequired):
            ERROR_EMBED.description = "This command will only run in NSFW marked channel. https://i.imgur.com/oe4iK5i.gif"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} NSFW Channel Required {QUESTION_MARK}")
            ERROR_EMBED.set_image(url="https://i.imgur.com/oe4iK5i.gif")
            RESET_COOLDOWN = True

        elif isinstance(error, commands.BadArgument):
            RESET_COOLDOWN = True
            objects = []
            if isinstance(error, commands.MessageNotFound):
                ERROR_EMBED.description = "Message ID/Link you provied is either invalid or deleted"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Message Not Found {QUESTION_MARK}")

            elif isinstance(error, commands.MemberNotFound):
                ERROR_EMBED.description = "Member ID/Mention/Name you provided is invalid or bot can not see that Member"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Member Not Found {QUESTION_MARK}")
                objects = ctx.guild.members

            elif isinstance(error, commands.UserNotFound):
                ERROR_EMBED.description = "User ID/Mention/Name you provided is invalid or bot can not see that User"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} User Not Found {QUESTION_MARK}")

            elif isinstance(error, commands.ChannelNotFound):
                ERROR_EMBED.description = "Channel ID/Mention/Name you provided is invalid or bot can not see that Channel"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Channel Not Found {QUESTION_MARK}")
                objects = ctx.guild.text_channels + ctx.guild.voice_channels

            elif isinstance(error, commands.RoleNotFound):
                ERROR_EMBED.description = "Role ID/Mention/Name you provided is invalid or bot can not see that Role"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Role Not Found {QUESTION_MARK}")
                objects = ctx.guild.roles

            elif isinstance(error, commands.EmojiNotFound):
                ERROR_EMBED.description = "Emoji ID/Name you provided is invalid or bot can not see that Emoji"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Emoji Not Found {QUESTION_MARK}")
                objects = ctx.guild.emojis
            else:
                ERROR_EMBED.description = f"{error}"
                ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Bad Argument {QUESTION_MARK}")

            if objects:
                if obj := self._get_object_by_fuzzy(argument=error.argument, objects=objects):
                    _, result, score = obj
                    ERROR_EMBED.description += f"\n\nDid you mean `{result}`?"
                    ERROR_EMBED.set_footer(text=f"Confidence: {score}%")

        elif isinstance(
            error,
            commands.MissingRequiredArgument | commands.BadUnionArgument | commands.TooManyArguments,
        ):
            command = ctx.command
            RESET_COOLDOWN = True
            ERROR_EMBED.description = f"Please use proper syntax.```\n{ctx.clean_prefix}{command.qualified_name}{'|' if command.aliases else ''}{'|'.join(command.aliases or '')} {command.signature}```"

            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Invalid Syntax {QUESTION_MARK}")

        elif isinstance(error, commands.BadLiteralArgument):
            ERROR_EMBED.description = (
                f"Please use proper Literals. "
                f"Literal should be any one of the following: `{'`, `'.join(str(i) for i in error.literals)}`"
            )
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Invalid Literal(s) {QUESTION_MARK}")

        elif isinstance(error, commands.MaxConcurrencyReached):
            ERROR_EMBED.description = (
                "This command is already running in this server/channel by you. You have wait for it to finish"
            )
            ERROR_EMBED.set_author(name=(f"{QUESTION_MARK} Max Concurrenry Reached {QUESTION_MARK}"))

        elif isinstance(error, ParrotCheckFailure):
            RESET_COOLDOWN = True
            ERROR_EMBED.description = f"{error.__str__().format(ctx=ctx)}"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Unexpected Error {QUESTION_MARK}")

        elif isinstance(error, commands.CheckAnyFailure):
            RESET_COOLDOWN = True
            ERROR_EMBED.description = " or\n".join([error.__str__().format(ctx=ctx) for error in error.errors])
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Unexpected Error {QUESTION_MARK}")

        elif isinstance(error, commands.CheckFailure):
            RESET_COOLDOWN = True
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Unexpected Error {QUESTION_MARK}")
            ERROR_EMBED.description = "You don't have the required permissions to use this command."

        elif isinstance(error, asyncio.TimeoutError):
            ERROR_EMBED.description = "Command took too long to respond"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Timeout Error {QUESTION_MARK}")

        elif isinstance(error, commands.InvalidEndOfQuotedStringError):
            ERROR_EMBED.description = "Invalid end of quoted string. Expected space after closing quotation mark. Did you forget to close the quotation mark?"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Invalid End Of Quoted String Error {QUESTION_MARK}")

        elif isinstance(error, commands.UnexpectedQuoteError):
            ERROR_EMBED.description = "Unexpected quote mark. Did you forget to close the quotation mark?"
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Unexpected Quote Error {QUESTION_MARK}")

        elif isinstance(error, commands.DisabledCommand):
            ERROR_EMBED.description = "This command is disabled in this server, ask your server admin to enable it."
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Disabled Command {QUESTION_MARK}")

        else:
            ERROR_EMBED.description = (
                f"For some reason **{ctx.command.qualified_name}** is not working. If possible report this error."
            )
            ERROR_EMBED.set_author(name=f"{QUESTION_MARK} Well this is embarrassing! {QUESTION_MARK}")
            TO_RAISE_ERROR = True

        ERROR_EMBED.timestamp = discord.utils.utcnow()

        if RESET_COOLDOWN:
            ctx.command.reset_cooldown(ctx)

        msg: discord.Message | None = await ctx.reply(random.choice(quote), embed=ERROR_EMBED)

        try:
            if msg:
                await ctx.wait_for("message_delete", timeout=10, check=lambda m: m.id == ctx.message.id)
                await msg.delete(delay=0)
        except asyncio.TimeoutError:
            if DELETE_AFTER:
                await msg.delete(delay=max(DELETE_AFTER - 10, 0))

        if TO_RAISE_ERROR:
            raise error


async def setup(bot: Parrot) -> None:
    await bot.add_cog(Cmd(bot))
