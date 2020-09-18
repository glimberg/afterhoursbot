
import discord
import time
from datetime import datetime
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import threading
import asyncio
import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, create_engine, desc
from sqlalchemy.orm import sessionmaker

afterhours_start_hour = 23
afterhours_end_hour = 6
tz = timezone('America/Los_Angeles')

sqlite_path = os.getenv("SQLITE_PATH")
if sqlite_path == None:
    sqlite_path = 'sqlite:///:memory:'

engine = create_engine(sqlite_path, echo=True)

Base = declarative_base()

class WHOUP(Base):
    __tablename__ = 'who_up'
    user = Column(Integer, primary_key=True)
    nick = Column(String)
    guild = Column(Integer)
    first_count = Column(Integer, default=0)
    last_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)

Base.metadata.create_all(engine)
Session = sessionmaker()
Session.configure(bind=engine)

class Bouncer(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)
        print('Name:', self.user.name)
        print('ID:', self.user.id)
    
        self.afterhoursEnabled = False

        self.afterhoursChannels = {}
        self.guildEveryoneRoles = {}
        self.haveWinner = {}
        self.lastWhoUp = {}

        self.loadGuildEveryoneRoles()
        self.loadAfterhoursChannels()

        now_utc = datetime.now(timezone('UTC'))
        now_la = now_utc.astimezone(tz)

        if now_la.hour >= afterhours_end_hour and now_la.hour < afterhours_start_hour:
            print('Setting afterhours disabled')
            await self.setAfterhoursDisabled()
        else:
            print('Setting afterhours enabled')
            await self.setAfterhoursEnabled()
    

    async def on_guild_join(self, guild):
        print('Joined', guild.name)
        for c in guild.text_channels:
            if c.name == '🌙afterhours':
                self.afterhoursChannels[guild] = c

    async def setAfterhoursEnabled(self):
        self.afterhoursEnabled = True
        for guild, channel in self.afterhoursChannels.items():
            self.haveWinner[guild] = False
            role = self.guildEveryoneRoles.get(guild, None)
            if role != None:
                await self.setWritePermission(channel, role, True)

    async def setAfterhoursDisabled(self):
        self.afterhoursEnabled = False
        for guild, channel in self.afterhoursChannels.items():
            role = self.guildEveryoneRoles.get(guild, None)
            if role != None:
                await self.setWritePermission(channel, role, False)
            if guild in self.lastWhoUp:
                last_up = self.lastWhoUp[guild]
                if last_up != None:
                    self.set_last(last_up.id, guild.id, last_up.name)
        self.lastWhoUp = {}

    async def setWritePermission(self, channel, everyoneRole, writeMessages):
        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = writeMessages
        overwrite.read_messages = True
        await channel.set_permissions(everyoneRole, overwrite=overwrite)

    async def sendMessageToAfterhours(self, message):
        for c in self.afterhoursChannels.values():
            await c.send(content=message)

    def loadAfterhoursChannels(self):
        for g in self.guilds:
            self.haveWinner[g] = False
            for c in g.text_channels:
                if c.name == '🌙afterhours':
                    self.afterhoursChannels[g] = c

        print(self.afterhoursChannels)

    def loadGuildEveryoneRoles(self):
        for g in self.guilds:
            self.guildEveryoneRoles[g] = g.default_role

        print(self.guildEveryoneRoles)

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        now_utc = datetime.now(timezone('UTC'))
        now_la = now_utc.astimezone(tz)
        if now_la.hour >= afterhours_end_hour and now_la.hour < afterhours_start_hour:
            return

        if message.channel == self.afterhoursChannels[message.guild]:
            if ":WHO_UP:" in message.content:
                author = message.author
                self.lastWhoUp[message.guild] = author
                if self.haveWinner[message.guild] == False:
                    self.haveWinner[message.guild] = True
                    await message.channel.send(content='''<@%s> is the first to the afterhours!''' % author.id)
                    print(author.name)
                    self.set_winner(author.id, message.guild.id, author.name)
                whoupCount = message.content.count(':WHO_UP')
                self.inc_whoup(author.id, message.guild.id, author.name, whoupCount)
            elif message.content == '!whoup':
                msg = "__**WHO UP? Top 5**__\n\n"
                s = Session()
                count = 0
                for user in s.query(WHOUP).filter(WHOUP.total_count > 0).order_by(desc(WHOUP.total_count))[0:5]:
                    count += 1
                    msg += "%d. %s: %d\n" % (count, user.nick, user.total_count)
                await message.channel.send(content=msg)
            elif message.content == '!whoupfirst':
                msg = "__**First WHO UP? Top 5**__\n\n"
                s = Session()
                count = 0
                for user in s.query(WHOUP).filter(WHOUP.first_count > 0).order_by(desc(WHOUP.first_count))[0:5]:
                    count += 1
                    msg += "%d. %s: %d\n" % (count, user.nick, user.first_count)
                if count == 0:
                    msg += "Nobody yet!"
                await message.channel.send(content=msg)
            elif message.content == '!whouplast':
                msg = "__**Last To Leave Top 5**__\n\n"
                s = Session()
                count = 0
                for user in s.query(WHOUP).filter(WHOUP.last_count > 0).order_by(desc(WHOUP.last_count))[0:5]:
                    count += 1
                    msg += "%d. %s: %d\n" %(count, user.nick, user.last_count)
                if count == 0:
                    msg += "Nobody yet!"
                await message.channel.send(content=msg)
            elif message.content == '!whoupme':
                author = message.author
                msg = "__**WHO UP! %s**__\n\n" %(author.name)
                s = Session()
                count = 0
                for user in s.query(WHOUP).filter(WHOUP.user == author.id)[0:1]:
                    count += 1
                    msg += "First: %d\n" %(user.first_count)
                    msg += "Last: %d\n" %(user.last_count)
                    msg += "Total: %d\n" %(user.total_count)
                if count == 0:
                    msg += "No WHO UP yet!"
                await message.channel.send(content=msg)


    def set_winner(self, user_id, guild_id, nickname):
        global Session
        s = Session()
        u = s.query(WHOUP).filter(WHOUP.user == user_id, WHOUP.guild == guild_id).first()
        if u == None:
            u = WHOUP(user=user_id, guild=guild_id, nick=nickname, first_count=1)
            s.add(u)
            s.commit()
        else:
            u.first_count += 1
            if u.nick != nickname:
                u.nick = nickname
            s.commit()

    def set_last(self, user_id, guild_id, nickname):
        global Session
        s = Session()
        u = s.query(WHOUP).filter(WHOUP.user == user_id, WHOUP.guild == guild_id).first()
        if u == None:
            u = WHOUP(user=user_id, guild=guild_id, nick=nickname, last_count=1)
            s.add(u)
            s.commit()
        else:
            u.last_count += 1
            if u.nick != nickname:
                u.nick = nickname
            s.commit()

    def inc_whoup(self, user_id, guild_id, nickname, amount):
        global Session
        s = Session()
        u = s.query(WHOUP).filter(WHOUP.user == user_id, WHOUP.guild == guild_id).first()
        if u == None:
            u = WHOUP(user=user_id, guild=guild_id, nick=nickname, total_count=amount)
            s.add(u)
            s.commit()
        else:
            u.total_count += amount
            if u.nick != nickname:
                u.nick = nickname
            s.commit()


async def open_channel(client):
    print("Opening Afterhours Channel")
    await client.setAfterhoursEnabled()
    await client.sendMessageToAfterhours("@everyone 🌙afterhours **IS NOW OPEN**")

async def close_channel(client):
    await asyncio.sleep(30)
    print("Closing afterhours channel")
    await client.sendMessageToAfterhours("🌙afterhours **IS NOW CLOSED**.  You don't have to go home but you can't stay here.")
    await client.setAfterhoursDisabled()

def scheduler(client):
    global afterhours_start_hour
    global afterhours_end_hour
    hour_start = os.getenv('AFTERHOURS_START_HOUR', '23')
    hour_end   = os.getenv('AFTERHOURS_END', '6')
    afterhours_start_hour = int(hour_start)
    afterhours_end_hour = int(hour_end)


    print("Starting Job Scheduler")
    scheduler = AsyncIOScheduler()
    scheduler.configure(timezone=tz)
    scheduler.add_job(open_channel, trigger='cron', args=(client,), hour=hour_start, id='id_open_channel', misfire_grace_time=300, coalesce=True)
    scheduler.add_job(close_channel, trigger='cron', args=(client,), hour=hour_end, id='id_close_channel', misfire_grace_time=300, coalesce=True)
    scheduler.start()

def main():
    token = os.getenv('DISCORD_TOKEN', None)
    if token == None:
        print("ERROR: DISCORD_TOKEN is not set")
    client = Bouncer()
    scheduler(client)
    client.run(token)

if __name__ == "__main__":
    main()
