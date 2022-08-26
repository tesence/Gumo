import asyncio
import logging
import random
import re

import discord
from discord.ext import commands


logger = logging.getLogger(__name__)

CUSTOM_EMOJI_RE = re.compile(r'<?(?P<animated>a)?:?(?P<name>[A-Za-z0-9\_]+):(?P<id>[0-9]{13,20})>?')
GUILD_ID = 116250700685508615


class EmojiChain(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._threshold = random.randint(3, 7)
        self._timeout = random.randint(0, 20)

    @commands.Cog.listener()
    async def on_message(self, message):

        ctx = await self.bot.get_context(message)

        # Ignore if:
        # - The channel is not a guild text channel
        # - The author is a bot
        # - The message has been sent in another guild
        # - The bot does not have write permission in the channel
        if not isinstance(ctx.channel, discord.TextChannel) or \
           ctx.author.bot or \
           message.guild.id != GUILD_ID or \
           not ctx.channel.permissions_for(ctx.me).send_messages:
            return

        if match := CUSTOM_EMOJI_RE.match(message.content):
            emoji = self.bot.get_emoji(int(match.group('id')))
            # Ignore if:
            # - The emoji is not found (the bot is not in the guild where the emoji is from)
            # - The emoji is not from the guild
            if not emoji or emoji.guild_id != GUILD_ID:
                return
        else:
            return

        messages = await ctx.history(limit=self._threshold).flatten()

        # ignore if the chat history is too short to be a chain
        if not len(messages) >= self._threshold:
            return

        user_messages = [message for message in messages if not message.author.bot]
        authors = [message.author.id for message in user_messages]
        # Send message if:
        # - All X previous messages are the same emoji
        # - All X previous have not been modified
        # - All authors are different
        if all(message.content == str(emoji) for message in user_messages) and \
           all(not message.edited_at for message in user_messages) and \
           len(authors) == len(set(authors)):
            await asyncio.sleep(self._timeout)
            await ctx.send(emoji)
            logger.debug(f"Contributed to an emoji chain of {self._threshold} {emoji.name} initiated by "
                         f"'{user_messages[0].author.display_name}' in channel '#{ctx.channel}'")
            self._threshold = random.randint(3, 7)
            self._timeout = random.randint(0, 20)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = self.bot.get_user(payload.user_id)
        ctx = await self.bot.get_context(message)

        # Ignore if:
        # - The listener is triggered by one of the bot's reactions
        # - The bot does not have reaction permission in the channel
        # - The message has been sent in another guild
        if user == self.bot.user or \
           not channel.permissions_for(ctx.me).add_reactions or \
           not message.guild.id == GUILD_ID:
            return

        emoji = self.bot.get_emoji(payload.emoji.id)

        # Ignore if:
        # - The emoji is not found (the bot is not in the guild where the emoji is from)
        # - The emoji is not from the guild
        if not emoji or emoji.guild_id != GUILD_ID:
            return

        # Iterate through all reactions to find the one related to that emoji
        for reaction in message.reactions:

            # If the threshold has been reached for that emoji
            if reaction.emoji == emoji and reaction.count >= self._threshold:

                # Ignore if the bot has already reacted to the chain before
                if self.bot.user in await  [user async for user in reaction.users()]:
                    continue

                await asyncio.sleep(self._timeout)
                await message.add_reaction(emoji)
                logger.debug(f"Contributed to a reaction emoji chain of {self._threshold} {emoji.name} on a message "
                             f"sent by {message.author.display_name}' in channel '#{ctx.channel}'")
                self._threshold = random.randint(3, 7)
                self._timeout = random.randint(0, 20)


async def setup(bot):
    await bot.add_cog(EmojiChain(bot))
