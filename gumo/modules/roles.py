import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

GUILD_ID = 116250700685508615

PRONOUN_ROLES = ["He/Him", "She/Her", "They/Them"]
RANDO_ROLES = ["Looking For BF Rando", "Looking For WotW Rando"]
RUNNER_ROLES = ["Fronkey", "Moki"]
TOURNAMENT_ROLES = ["Tournament Viewer"]


class RoleButton(discord.ui.Button):

    def __init__(self, guild, role, **kwargs):
        custom_id = f"{guild.id}-role-{role.id}"
        super().__init__(style=discord.ButtonStyle.primary, label=role.name, custom_id=custom_id, **kwargs)
        self.role = role

    async def callback(self, interaction):

        await interaction.response.defer()
        has_role = interaction.user.get_role(self.role.id)
        if has_role:
            await interaction.user.remove_roles(self.role)
            content = f"The role `{self.role.name}` has been removed"
            logger.debug(f"{interaction.user.display_name} removed the role '{self.role}'")
        else:
            await interaction.user.add_roles(self.role)
            content = f"The role `{self.role.name}` has been added"
            logger.debug(f"{interaction.user.display_name} picked the role '{self.role}'")

        await interaction.followup.send(content, ephemeral=True)


class RoleListButton(discord.ui.Button):

    def __init__(self, guild, roles, **kwargs):
        custom_id = f"{guild.id}-role-list"
        super().__init__(style=discord.ButtonStyle.secondary, label="List your current roles", custom_id=custom_id,
                         **kwargs)
        self.roles = roles

    async def callback(self, interaction):
        roles = tuple(filter(None, map(interaction.user.get_role, [role.id for role in self.roles])))

        if not roles:
            await interaction.response.send_message('You have not assigned any roles at the moment!', ephemeral=True)
        else:
            await interaction.response.send_message('You currently have the following roles:\n\n' +
                                                    '\n'.join(f'• `{x}`' for x in roles), ephemeral=True)


class RoleButtonListView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)


class RoleCommands(commands.Cog):

    def __init__(self, bot):
        self.display_name = "Role commands"
        self.bot = bot
        self.views = {}
        self.role_button_list_view = None

    @commands.Cog.listener()
    async def on_ready(self):

        guild = self.bot.get_guild(GUILD_ID)

        role_dict = {role_name: discord.utils.get(guild.roles, name=role_name)
                     for role_name in PRONOUN_ROLES + RANDO_ROLES + RUNNER_ROLES + TOURNAMENT_ROLES}

        # View with pronoun role buttons
        self.views['pronoun'] = RoleButtonListView()
        for role_name in PRONOUN_ROLES:
            button = RoleButton(guild=guild, role=role_dict[role_name])
            self.views['pronoun'].add_item(button)

        # View with runner role buttons
        self.views['runner'] = RoleButtonListView()
        for role_name in RUNNER_ROLES:
            button = RoleButton(guild=guild, role=role_dict[role_name])
            self.views['runner'].add_item(button)

        # View with rando role buttons
        self.views['rando'] = RoleButtonListView()
        for role_name in RANDO_ROLES:
            button = RoleButton(guild=guild, role=role_dict[role_name])
            self.views['rando'].add_item(button)

        # View with rando role buttons
        self.views['tournament'] = RoleButtonListView()
        for role_name in TOURNAMENT_ROLES:
            button = RoleButton(guild=guild, role=role_dict[role_name])
            self.views['tournament'].add_item(button)

        for view in self.views.values():
            self.bot.add_view(view)

        # View of the list button
        self.role_button_list_view = RoleButtonListView()
        button = RoleListButton(guild=guild, roles=role_dict.values())
        self.role_button_list_view.add_item(button)
        self.bot.add_view(self.role_button_list_view)

    @commands.is_owner()
    @commands.command(hidden=True)
    async def role_init(self, ctx):
        output = [
            ("**Self-assignable Roles**\n\nSelect your preferred pronoun(s)", self.views['pronoun'], ),
            ("Pick these roles if you're interested in Blind Forest (Fronkey) or Will of the Wisps (Moki) speedruns. "
             "These roles will be notified of any updates regarding the speedruns, category rules, or leaderboard "
             "updates or discussions.", self.views['runner']),
            ("If you are interested in randomizers, pick a role in order to get pinged when someone is looking for "
             "rando mates to play with.", self.views['rando']),
            ("If you don't want to miss any tournament match, pick this role and get pinged in <#137532566654812160> "
             "when a match is happening.", self.views['tournament']),
            ("Unsure which roles you already have? Click here:", self.role_button_list_view)
        ]

        for message in output:
            await ctx.send(message[0], view=message[1])


async def setup(bot):
    await bot.add_cog(RoleCommands(bot))
