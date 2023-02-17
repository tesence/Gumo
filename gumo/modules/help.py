import inspect
import collections

from discord.ext import commands


class CommandConverter(commands.Converter):
    async def convert(self, ctx, argument):
        command = ctx.bot.get_command(argument)

        if command is None or not command.enabled:
            raise commands.BadArgument(f'Command "{argument}" not found.')

        return command

class Help(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx, command: CommandConverter = None):
        if command is None:
            await self._general_help(ctx)
        else:
            await self._command_help(ctx, command)

    async def _general_help(self, ctx):

        categories = collections.defaultdict(list)

        for command in self.bot.walk_commands():

            if not command.enabled or any(x.hidden for x in (command, *command.parents)):
                continue

            try:
                if not await command.can_run(ctx):
                    continue
            except commands.CommandError:
                continue

            categories[command.cog_name].append(command)

        def fmt_commands(name):
            return ', '.join(f'`{x.qualified_name}`' for x in sorted(categories[name], key=lambda x: x.qualified_name))

        usable = '\n'.join(f'**{name}:** {fmt_commands(name)}' for name in sorted(categories))

        msg = inspect.cleandoc(
            """
            Your current permissions allow you to use the following commands:

            {commands}

            Use `{prefix}help <command>` for more information on each command.
            """
        )
        await ctx.send(msg.format(commands=usable, prefix=ctx.prefix))

    async def _command_help(self, ctx, command):

        name = f'{command.full_parent_name} {command.name}'.lstrip()
        signature = f' {command.signature}' if command.signature else ''

        try:
            if not await command.can_run(ctx):
                return
        except commands.CommandError:
            return

        description = command.help + '\n' if command.help else ''

        msg = inspect.cleandoc(
            """
            Usage: `{prefix}{name}{signature}`

            {description}
            """
        )

        await ctx.send(
            msg.format(prefix=ctx.prefix, name=name, signature=signature, description=description)
        )

async def setup(bot):
    await bot.add_cog(Help(bot))
