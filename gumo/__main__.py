import os

from gumo import bot as client


def main():

    bot = client.Bot(command_prefix="!")
    bot.run(os.getenv('GUMO_BOT_TOKEN'), log_handler=None)


if __name__ == '__main__':
    main()
