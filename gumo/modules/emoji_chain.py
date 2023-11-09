"""
Define a module to make the bot join emoji chains when:
- People send the same emoji several times in a row
- People react to a message using the same emoji
"""

import asyncio
import logging
import random
import re

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)

CUSTOM_EMOJI_RE = re.compile(r'<?(?P<animated>a)?:?(?P<name>[A-Za-z0-9\_]+):(?P<id>[0-9]{13,20})>?')


class EmojiChain(commands.Cog, name="Emoji Chain"):
    """Custom Cog"""

    def __init__(self, bot):
        self.bot = bot
        self._threshold = random.randint(3, 7)
        self._timeout = random.randint(0, 20)

    # pylint: disable=missing-function-docstring
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        ctx = await self.bot.get_context(message)

        # Ignore if:
        # - The channel is not a guild text channel
        # - The author is a bot
        # - The message has been sent in another guild
        # - The bot does not have write permission in the channel
        if not isinstance(ctx.channel, discord.TextChannel) or \
           ctx.author.bot or \
           not ctx.channel.permissions_for(ctx.me).send_messages:
            return

        if match := CUSTOM_EMOJI_RE.match(message.content):
            emoji = self.bot.get_emoji(int(match.group('id')))
            # Ignore if:
            # - The emoji is not found (the bot is not in the guild where the emoji is from)
            if not emoji:
                return
        else:
            return

        messages = [message async for message in ctx.history(limit=self._threshold)]

        # ignore if the chat history is too short to be a chain
        if not len(messages) >= self._threshold:
            return

        authors = [message.author.id for message in messages]

        # If one the message has been sent by the bot
        if self.bot.user.id in authors:
            return

        # Send message if:
        # - All X previous messages are the same emoji
        # - All X previous have not been modified
        # - All authors are different
        if all(message.content == str(emoji) for message in messages) and \
           all(not message.edited_at for message in messages) and \
           len(authors) == len(set(authors)):
            await asyncio.sleep(self._timeout)
            await ctx.send(emoji)
            logger.info("Contributed to an emoji chain of %s %s initiated by '%s' in channel #%s", self._threshold,
                        emoji.name, messages[0].author.display_name, ctx.channel)
            self._threshold = random.randint(3, 7)
            self._timeout = random.randint(0, 20)

    # pylint: disable=missing-function-docstring
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = self.bot.get_user(payload.user_id)
        ctx = await self.bot.get_context(message)

        # Ignore if:
        # - The listener is triggered by one of the bot's reactions
        # - The bot does not have reaction permission in the channel
        if user == self.bot.user or not channel.permissions_for(ctx.me).add_reactions:
            return

        emoji = self.bot.get_emoji(payload.emoji.id)

        # Ignore if:
        # - The emoji is not found (the bot is not in the guild where the emoji is from)
        if not emoji:
            return

        # Iterate through all reactions to find the one related to that emoji
        for reaction in message.reactions:

            # If the threshold has been reached for that emoji
            if reaction.emoji == emoji and reaction.count >= self._threshold:

                # Ignore if the bot has already reacted to the chain before
                if self.bot.user in [user async for user in reaction.users()]:
                    continue

                await asyncio.sleep(self._timeout)
                await message.add_reaction(emoji)
                logger.info("Contributed to a reaction emoji chain of %s %s on a message sent by '%s' in channel #%s",
                            self._threshold, emoji.name, message.author.display_name, ctx.channel)
                self._threshold = random.randint(3, 7)
                self._timeout = random.randint(0, 20)

# pylint: disable=missing-function-docstring
async def setup(bot):
    await bot.add_cog(EmojiChain(bot))
