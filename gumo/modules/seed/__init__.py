from gumo.modules.seed.core import BFRandomizer


async def setup(bot):
    await bot.add_cog(BFRandomizer(bot))
