#!/usr/bin/env python3

from my_first_goat.bot import MyFirstGoat
import logzero
import click

log = logzero.logger
logzero.loglevel('INFO')


@click.command()
@click.option('-t', '--test', is_flag=True, help='Send test message to debug user. May be used alone or with -s/-l to '
                                                 'send message only to "debug_user"')
@click.option('-g', '--get', is_flag=True, help='Get snapshot of members from discord and save in database')
@click.option('-s', '--send', is_flag=True, help='Send comparison between two last member snapshots')
@click.option('-l', '--loot', is_flag=True, help='Process loot messages and send summary')
def main(test, get, send, loot):
    """
    Discord bot helping to manage gaming discord server (members and loot messages)
    """
    bot = MyFirstGoat(
        test=test,
        get_members=get,
        send_members=send,
        loot=loot,
    )
    bot.main()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


# TODO: CLI: delete last snapshot
# TODO: CLI: delete snapshots older than X days
# TODO: try poetry

