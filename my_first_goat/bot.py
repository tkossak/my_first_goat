import string
import discord
import sqlite3
import time
from collections import namedtuple, defaultdict
import logzero
import datetime as dt
import re
import textwrap
from fs.appfs import UserDataFS, UserConfigFS
from typing import Union
import toml
from pathlib import Path
from .__version__ import __version__

__package_name__ = 'my_first_goat'
log = logzero.logger


class MyFirstGoat:

    # if bot can't figure out how much money is owned it sends this:
    HOW_MUCH_NONE = '???'
    # characters used in money values:
    MONEY_CHARS = string.digits + ',.kmKM'
    data_home = UserDataFS(__package_name__, create=True)
    config_home = UserConfigFS(__package_name__, create=True)

    def __init__(
        self,
        test: bool,
        get_members: bool,
        send_members: bool,
        loot: bool,
        search_server: str,
        search_channel: str,
        search_user: str,
        display_info: bool,
    ):
        self.cli_test = test
        self.cli_get = get_members
        self.cli_send = send_members
        self.cli_loot = loot
        self.search_server = search_server.lower() if search_server else None
        self.found_servers = set()
        self.search_channel = search_channel.lower() if search_channel else None
        self.search_user = search_user.lower() if search_user else None
        self.if_display_info = display_info

        self.config_file_name = 'config.toml'
        self.db_file_name = 'members.sqlite'

        self._server = None
        self.members = []  # list of Member obj: DGS members with 'Member' role
        self.members_all_guild = []
        self.members_all_guild_mentions_str = []
        self.members_all_server = []
        # TODO: move to config file
        self.guild_roles = {'Member', 'Officer', 'Admin'}
        self.con = None
        self.cur = None
        self.setup_db()
        self.text_summary = None
        self.text_full = None
        self.client: discord.Client = None

        # IDs from config file:
        self.discord_bot_token = None
        self.discord_server_id = None
        self.discord_user_send_id = None
        self.discord_user_debug_id = None
        self.discord_loot_channel_id = None
        self.discord_general_channel_id = None
        self.search_roles = None
        if self.setup_config():
            quit(0)

        self.discord_user_debug: Union[discord.User, None] = discord.User(
            id=self.discord_user_debug_id
        )
        self.discord_user_send: Union[discord.User, None] = discord.User(
            id=self.discord_user_send_id
        )
        self.discord_loot_channel: Union[discord.Channel, None] = None
        self.discord_general_channel: Union[discord.Channel, None] = None

        if self.cli_test:
            self.discord_user_send = self.discord_user_debug
            self.discord_general_channel_id = None

    def setup_db(self):
        db_file_name = self.db_file_name
        # self.con = sqlite3.connect('members.sqlite')
        log.info(f'DB path: {MyFirstGoat.data_home.getsyspath(db_file_name)}')
        self.con = sqlite3.connect(MyFirstGoat.data_home.getsyspath('members.sqlite'))
        self.cur = self.con.cursor()
        self.cur.execute(
            '''CREATE TABLE IF NOT EXISTS members
               (
                datetime    INTEGER,
                server_id   VARCHAR(128),
                server_name VARCHAR(128),
                user_id     VARCHAR(128),
                user_name   VARCHAR(200),
                user_display_name   VARCHAR(200),

                PRIMARY KEY (datetime, server_id, user_id)
               )'''
        )

    def setup_config(self) -> bool:
        config_template_file_name = 'config_template.toml'
        config_file_name = self.config_file_name
        if_init = False
        if MyFirstGoat.config_home.exists(config_file_name):
            # load config file
            conf = toml.loads(MyFirstGoat.config_home.gettext(config_file_name))
            self.discord_server_id = str(conf['server']['server_id'])
            self.discord_bot_token = conf['bot']['token']
            self.discord_user_send_id = str(conf['server']['user_send'])
            self.discord_user_debug_id = str(conf['server']['user_debug'])
            self.discord_loot_channel_id = str(conf['server']['channel_loot_from_id'])
            self.discord_general_channel_id = str(conf['server']['channel_loot_to_id'])

            if isinstance(conf['server']['role_to_monitor'], str):
                self.search_roles = {conf['server']['role_to_monitor']}
            else:
                self.search_roles = set(conf['server']['role_to_monitor'])
        else:
            # create config file from template
            config_template_file_path = (
                Path(__file__).parent / 'data' / config_template_file_name
            )
            config_str = config_template_file_path.read_text()
            MyFirstGoat.config_home.settext(config_file_name, config_str)
            print(
                f'Config data was copied to {MyFirstGoat.config_home.getsyspath(config_file_name)}'
            )
            print('Edit this file and rerun the bot.')
            if_init = True
        log.info(f'Config path: {MyFirstGoat.config_home.getsyspath(config_file_name)}')
        return if_init

    @property
    def server(self):
        if not self._server:
            self._server = self.client.get_server(id=self.discord_server_id)
        return self._server

    async def bot_send_loot_messages(self):
        log.info('START get loot')
        await self.bot_download_members_list()
        # how_much is +1 after this value
        # write values in list with LOWERCASE
        # case INSENSITIVE comparison with message
        hw_words_plus_1 = ['splits:', 'split:', 'each:']
        hw_words_minus_1 = ['each.']
        hw_words_plus_1_minus_1 = ['each', 'split', 'splits']
        hw_words_plus_1_the_end = ['so']

        def get_how_much_per_person(msg_list):
            msg_lower = [word.lower() for word in msg_list]

            # check only +1:
            val = check_how_much_plus_n(
                msg_lower=msg_lower, searched_words=hw_words_plus_1, n=1
            )
            if val:
                return val

            # check only -1:
            val = check_how_much_plus_n(
                msg_lower=msg_lower, searched_words=hw_words_minus_1, n=-1
            )
            if val:
                return val

            # check +1 then -1:
            val = check_how_much_plus_n(
                msg_lower=msg_lower, searched_words=hw_words_plus_1_minus_1, n=1
            )
            if val:
                return val
            val = check_how_much_plus_n(
                msg_lower=msg_lower, searched_words=hw_words_plus_1_minus_1, n=-1
            )
            if val:
                return val

            # check +1 - least priority:
            val = check_how_much_plus_n(
                msg_lower=msg_lower, searched_words=hw_words_plus_1_the_end, n=1
            )
            if val:
                return val

            return MyFirstGoat.HOW_MUCH_NONE

        def check_how_much_plus_n(msg_lower: list, searched_words: list, n: int):
            '''

            :param msg_lower: list of words (in lower case)
            :param searched_words: words to look for (that indicate money)
            :param n: where mony is, relative to the word
            :return:
            '''
            for part_ind, partw in enumerate(msg_lower):
                if partw not in searched_words:
                    continue
                if 0 <= part_ind + n < len(msg_lower):
                    val = msg_lower[part_ind + n]
                    if check_if_money_value(val):
                        return val.strip(' ,.')
            return None

        def check_if_money_value(val: str) -> bool:
            at_least_one_digit = any(c in string.digits for c in val)
            all_chars_are_allowed = all(c in MyFirstGoat.MONEY_CHARS for c in val)
            return val and at_least_one_digit and all_chars_are_allowed

        paid_strings = [b'\xf0\x9f\x92\xb0'.decode(), 'paid']
        msg_ids_to_ignore = []
        Entry = namedtuple('Entry', 'creditor how_much created')
        debtors = defaultdict(list)

        self.discord_loot_channel: discord.Channel = self.server.get_channel(
            channel_id=self.discord_loot_channel_id
        )
        # async for msg in self.client.logs_from(
        #         channel=self.discord_loot_channel,
        #         after=dt.datetime(2018, 2, 23),
        #         before=dt.datetime(2018, 2, 25)
        # ):
        # TODO: store minimum date in config table
        min_date = dt.datetime.today() - dt.timedelta(days=180)
        async for msg in self.client.logs_from(
            channel=self.discord_loot_channel, limit=999999, after=min_date
        ):
            # get mentions for 1 message:
            author_metion = msg.author.mention.replace('<@!', '<@')
            if (
                msg.id in msg_ids_to_ignore
                or author_metion not in self.members_all_guild_mentions_str
            ):
                continue

            # standardize mentions:
            msg_clean_content = msg.content.replace('<@!', '<@')
            # remove spaces between 'splits' and ':'
            msg_clean_content = re.sub(r'(splits?)\s+:', r'\1:', msg_clean_content)
            # remove spaces between 'total' and ':'
            msg_clean_content = re.sub(r'(totals?)\s+:', r'\1:', msg_clean_content)
            # insert space after mention:
            msg_clean_content = re.sub(r'(<@\d+>)([^\s])', r'\1 \2', msg_clean_content)
            # insert space before mention:
            msg_clean_content = re.sub(r'([^\s])(<@\d+>)', r'\1 \2', msg_clean_content)
            msgl = msg_clean_content.split()

            # if money digits are split (by space) then join them:
            tmp_msgl = []
            cur_money = ''
            for part in msgl:
                if check_if_money_value(part):
                    cur_money += part
                else:
                    if cur_money:
                        tmp_msgl.append(cur_money)
                        cur_money = ''
                    tmp_msgl.append(part)
            if cur_money:
                tmp_msgl.append(cur_money)
            msgl = tmp_msgl
            del tmp_msgl

            how_much_per_person = None
            if msg.mentions:
                how_much_per_person = get_how_much_per_person(msgl)
            for creditor_obj in msg.mentions:
                creditor_mention = creditor_obj.mention.replace('<@!', '<@')
                i = msgl.index(creditor_mention)

                if creditor_mention not in self.members_all_guild_mentions_str:
                    continue

                if i + 1 < len(msgl) and msgl[i + 1].lower() in paid_strings:
                    # paid
                    pass
                elif msg.author == creditor_obj:
                    # creditor is the same person as author of the message
                    pass
                else:
                    # NOT paid
                    debtors[msg.author].append(
                        Entry(
                            creditor=creditor_obj.mention,
                            how_much=how_much_per_person,
                            created=msg.timestamp,
                        )
                    )
        log.info(
            f'Oldest message: '
            + str(min(d.created for key, val in debtors.items() for d in val))
        )

        def get_msg_lines_gen():
            nonlocal debtors
            yield textwrap.dedent(
                f'''
                Where's my wonga bro?
                If you don't collect your money for over 30 days, it goes to guild bank (marked with :warning: icon).
                All times are in UTC (game time).
                Only people with Member/Officer/Admin roles are displayed.
                If you paid already, mark it in your message in {self.discord_loot_channel.mention}.
                Any remarks about the bot direct to github.com/tkossak/my_first_goat'''
            )
            for debtor, creditors in sorted(
                debtors.items(),
                key=lambda x: max(e.created for e in x[1]),
                reverse=True,
            ):
                yield f'\n{debtor.mention}:'
                count = len(creditors)
                for ind, creditor in enumerate(
                    sorted(
                        creditors, key=lambda x: (x.created, x.creditor), reverse=True
                    ),
                    1,
                ):
                    if (dt.date.today() - creditor.created.date()) > dt.timedelta(
                        days=30
                    ):
                        over_month = ' :warning:'
                    else:
                        over_month = ''
                    ret = (
                        ('├' if ind < count else '└')
                        + f'  {creditor.creditor} - `${creditor.how_much}`  '
                        + f'❲{creditor.created.strftime("%b %d, %H:%M:%S")}{over_month}❳'
                    )
                    yield ret

        cur_msg = []  # single message: list of str
        msgs = []  # all messages: list of str
        for line in get_msg_lines_gen():
            if len(line) > 2000:
                raise Exception('Line longer thatn 2k chars!')
            cur_msg_length = sum(len(l) + 1 for l in cur_msg)
            new_line_length = len(line) + 1
            if cur_msg_length + new_line_length > 2000:
                msgs.append('\n'.join(cur_msg) + '\n')
                cur_msg.clear()
            cur_msg.append(line)
        msgs.append('\n'.join(cur_msg))

        # print('\n'.join(msgs))
        log.debug('sending msg_text...')
        channel_general = self.client.get_channel(id=self.discord_general_channel_id)
        for single_msg in msgs:
            if self.cli_test:
                await self.client.send_message(
                    destination=self.discord_user_debug, content=single_msg
                )
            else:
                await self.client.send_message(
                    destination=channel_general, content=single_msg
                )
        log.info('END get loot')

    async def bot_test_message(self):
        await self.client.send_message(
            destination=self.discord_user_debug,
            content=f'my_first_goat, version: {__version__}'
        )

    async def bot_download_members_list(self):
        if self.members:
            return
        if self.server.large:
            await self.client.request_offline_members(self.server)

        for m in self.server.members:
            roles = set(r.name for r in m.roles)
            # if any(self.search_roles == r.name for r in m.roles):
            if roles & self.search_roles:
                self.members.append(m)
                self.members_all_guild.append(m)
                self.members_all_server.append(m)
            elif roles & self.guild_roles:
                self.members_all_guild.append(m)
                self.members_all_server.append(m)
            else:
                self.members_all_server.append(m)

        for m in self.members_all_guild:
            self.members_all_guild_mentions_str.append(m.mention.replace('<@!', '<@'))

        log.info(f'members downloaded: {len(self.members)}')

    async def bot_download_and_save_members_in_db(self):
        # server = self.client.get_server(id=self.discord_server_id)
        # # get Server obj:
        # for s in client.servers:  # servers that the bot is logged in
        #     if s.name == self.search_server_name:
        #         server = s
        #         break
        await self.bot_download_members_list()

        rows_to_insert = []
        cur_epoch_time = int(time.time())
        for m in self.members:
            rows_to_insert.append(
                (
                    cur_epoch_time,
                    self.server.id,
                    self.server.name,
                    m.id,
                    m.name,
                    m.display_name,
                )
            )

        # Insert list to DB:
        self.cur.executemany(
            'INSERT INTO members VALUES(?, ?, ? ,?, ?, ?)', rows_to_insert
        )
        self.con.commit()
        log.info('saved in db')

    async def bot_send_members_status(self):
        log.info('Sending message with members')
        await self.client.send_message(
            destination=self.discord_user_send, content=self.text_full
        )

    def bot_run(self):
        self.client = client = discord.Client()

        @client.event
        async def on_ready():
            log.info('Bot logged')

            if self.cli_test and not self.cli_loot and not self.cli_send:
                await self.bot_test_message()

            if self.cli_get:
                await self.bot_download_and_save_members_in_db()

            if self.cli_get or self.cli_send:
                self.compare_snapshots_and_prepare_msg()

            if self.cli_send:
                await self.bot_send_members_status()

            if self.cli_loot:
                await self.bot_send_loot_messages()

            if self.search_server:
                await self.bot_search_server()
            if self.search_channel:
                await self.bot_search_channel()
            if self.search_user:
                await self.bot_search_user()

            log.info('logging out')
            await client.logout()

        client.run(self.discord_bot_token)

    async def bot_search_server(self):
        print('Server id/names found:')
        self.found_servers.clear()
        for ser in self.client.servers:
            if self.search_server in ser.name.lower():
                self.found_servers.add(ser)
                print(f'{ser.id} - {ser.name}')
        print()

    async def bot_search_channel(self):
        print('Channel id/names found:')
        servers_to_search = (
            self.found_servers if self.found_servers else self.client.servers
        )
        for ser in servers_to_search:
            for channel in ser.channels:
                if self.search_channel in channel.name.lower():
                    print(
                        f'{channel.id} - {ser.name}/{channel.name} ({str(channel.type)})'
                    )
        print()

    async def bot_search_user(self):
        print('User id/names found:')
        servers_to_search = (
            self.found_servers if self.found_servers else self.client.servers
        )
        for ser in servers_to_search:
            for user in ser.members:
                if self.search_user in user.display_name.lower():
                    print(f'{user.id} - {ser.name}/{user.name}')
        print()

    def compare_snapshots_and_prepare_msg(self):
        if self.text_summary or self.text_full:
            return

        # get last day and previus day:
        self.cur.execute('select max(datetime) from members')
        day_b = self.cur.fetchone()[0]  # last day
        if not day_b:
            msg = 'No data in DB!'
            self.text_summary = self.text_full = msg
            log.error(msg)
            # raise Exception('No data in DB!')
            print(msg, 'Re-run the bot with --get switch')
            quit(0)

        self.cur.execute(
            'select max(datetime) from members where datetime != ?', (day_b,)
        )
        day_a = self.cur.fetchone()[0]  # day before the last

        if not day_a:
            day_a = day_b

        cols = ['user_id', 'jest_a', 'jest_b', 'display_name_a', 'display_name_b']
        sql = '''
              SELECT ifnull(a.user_id, b.user_id) as user_id
                    ,CASE WHEN a.user_id is not null then 1 else 0 END as czy_jest_w_a
                    ,CASE WHEN b.user_id is not null then 1 else 0 END as czy_jest_w_b
                    ,a.user_display_name as display_name_a
                    ,b.user_display_name as display_name_b
                FROM members a
                LEFT JOIN members b
                     ON a.user_id = b.user_id
                     AND b.datetime = :day_b
               WHERE a.datetime = :day_a

              UNION ALL

              SELECT ifnull(a.user_id, b.user_id) as user_id
                    ,CASE WHEN a.user_id is not null then 1 else 0 END as czy_jest_w_a
                    ,CASE WHEN b.user_id is not null then 1 else 0 END as czy_jest_w_b
                    ,a.user_display_name as display_name_a
                    ,b.user_display_name as display_name_b
                FROM members b
                LEFT JOIN members a
                     ON b.user_id = a.user_id
                     AND a.datetime = :day_a
               WHERE b.datetime = :day_b
                 AND a.user_id IS NULL
        '''

        all_current_members = []
        new_members = []
        del_members = []
        renamed_members = []

        for r in self.cur.execute(sql, dict(day_a=day_a, day_b=day_b)):
            user = dict(zip(cols, r))
            if user['jest_b']:
                all_current_members.append(user)
            if (
                user['jest_a']
                and user['jest_b']
                and user['display_name_a'] != user['display_name_b']
            ):
                renamed_members.append(user)
            if not user['jest_a'] and user['jest_b']:
                new_members.append(user)
            if user['jest_a'] and not user['jest_b']:
                del_members.append(user)
        all_current_members = sorted(
            all_current_members, key=lambda x: x['display_name_b'].lower()
        )
        renamed_members = sorted(
            renamed_members, key=lambda x: x['display_name_b'].lower()
        )
        new_members = sorted(new_members, key=lambda x: x['display_name_b'].lower())
        del_members = sorted(del_members, key=lambda x: x['display_name_a'].lower())

        # PREPARE
        text = textwrap.dedent(
            '''
        **CURRENT MEMBER STATUS:**
        Previous snapshot: {prev_date}
        Current  snapshot: {cur_date}

        ----- New members: {new_count}
        {new_members}{new_members_line}
        ----- Removed members: {del_count}
        {del_members}{del_members_line}
        ----- Renamed members: {ren_count}
        {ren_members}{ren_members_line}
        ----- All current members: {all_count}
        '''
        )

        max_old_name_length = (
            max(len(m['display_name_a']) for m in renamed_members)
            if renamed_members
            else 0
        )
        new_members_txt = self.text_codify_for_discord(
            '\n'.join(m['display_name_b'] for m in new_members) if new_members else ''
        )
        del_members_txt = self.text_codify_for_discord(
            '\n'.join(m['display_name_a'] for m in del_members) if del_members else ''
        )
        ren_members_txt = self.text_codify_for_discord(
            '\n'.join(
                f'{m["display_name_a"].ljust(max_old_name_length)} => {m["display_name_b"]}'
                for m in renamed_members
            )
            if renamed_members
            else ''
        )
        all_members_txt = self.text_codify_for_discord(
            '\n'.join(m['display_name_b'] for m in all_current_members)
            if all_current_members
            else ''
        )
        text = text.format(
            cur_date=time.ctime(day_b),
            prev_date=time.ctime(day_a),
            new_count=len(new_members),
            new_members=new_members_txt,
            new_members_line='\n' if new_members else '',
            del_count=len(del_members),
            del_members=del_members_txt,
            del_members_line='\n' if del_members else '',
            ren_count=len(renamed_members),
            ren_members=ren_members_txt,
            ren_members_line='\n' if renamed_members else '',
            all_count=len(all_current_members),
        )

        self.text_summary = text
        self.text_full = text + all_members_txt
        text_to_print = self.text_full
        print(text_to_print.replace('`', ''))

    def display_info(self):
        config_file_name = self.config_file_name
        db_file_name = self.db_file_name
        print(f'DB file: {MyFirstGoat.data_home.getsyspath(db_file_name)}')
        print(
            f'Configuration file: {MyFirstGoat.config_home.getsyspath(config_file_name)}'
        )

    @staticmethod
    def text_codify_for_discord(text: str) -> str:
        if not text:
            return text
        elif text.count('\n') == 0:
            return '`' + text + '`'
        if text.count('\n') > 0:
            return '```\n' + text + '```'

    def main(self):
        log.info('START')
        try:
            if self.if_display_info:
                self.display_info()
            elif (
                self.cli_get
                or self.cli_send
                or self.cli_loot
                or self.cli_test
                or self.search_server
                or self.search_channel
                or self.search_user
            ):
                self.bot_run()
            else:
                # self.compare_snapshots_and_prepare_msg()
                self.display_info()
        finally:
            log.info('END')


# TODO: change self.members to async property
