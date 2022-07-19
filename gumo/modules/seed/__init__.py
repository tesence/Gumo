from gumo.modules.seed.core import BFRandomizer


def setup(bot):
    bot.add_cog(BFRandomizer(bot))
