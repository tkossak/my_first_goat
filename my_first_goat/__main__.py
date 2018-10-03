#!/usr/bin/env python3

from .bot import MyFirstGoat
from . import __version__
import logzero
import click

log = logzero.logger
logzero.loglevel('ERROR')


@click.command()
@click.version_option(version=__version__.__version__)
@click.option(
    '--info', is_flag=True, help='Display info about configuration/database file'
)
@click.option(
    '-l', '--loot', is_flag=True, help='Process loot messages and send summary'
)
@click.option(
    '-g',
    '--get',
    is_flag=True,
    help='Get snapshot of members from discord server and save in the database',
)
@click.option(
    '-s',
    '--send',
    is_flag=True,
    help='Send comparison between two last member snapshots',
)
@click.option(
    '-t',
    '--test',
    is_flag=True,
    help='Send test message to debug_user. May be used alone or with -s/-l to '
    'send messages only to debug_user',
)
@click.option('--search-server', help='search for servers containing given phrase')
@click.option('--search-channel', help='search for channel IDs containing given phrase')
@click.option('--search-user', help='display /IDs containing given phrase')
@click.option('-v', '--verbose', is_flag=True, help='Be verbose')
def main(
    test, get, send, loot, search_server, search_channel, search_user, info, verbose
):
    '''
    Discord bot helping to manage gaming discord server (members and loot messages)
    '''
    if verbose:
        logzero.loglevel('INFO')

    bot = MyFirstGoat(
        test=test,
        get_members=get,
        send_members=send,
        loot=loot,
        search_server=search_server,
        search_channel=search_channel,
        search_user=search_user,
        display_info=info,
    )
    bot.main()
    return 0


if __name__ == '__main__':
    import sys

    sys.exit(main())

# TODO: CLI: delete last snapshot
# TODO: CLI: delete snapshots older than X days
# TODO: scan loot messages only from oldest, not fully paid, message (min 1 months)
