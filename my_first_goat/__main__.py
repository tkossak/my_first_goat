#!/usr/bin/env python3

from .bot import MyFirstGoat
import logzero
import click

log = logzero.logger
logzero.loglevel('INFO')


@click.command()
@click.option('-l', '--loot', is_flag=True, help='Process loot messages and send summary')
@click.option('-g', '--get', is_flag=True, help='Get snapshot of members from discord server and save in the database')
@click.option('-s', '--send', is_flag=True, help='Send comparison between two last member snapshots')
@click.option('-t', '--test', is_flag=True, help='Send test message to debug_user. May be used alone or with -s/-l to '
                                                 'send messages only to debug_user')
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

# TODO: display all IDs that the bot sees
# TODO: CLI: delete last snapshot
# TODO: CLI: delete snapshots older than X days
# TODO: scan loot messages only from oldest, not fully paid, message (min 1 months)

