
import discord
import time
from datetime import datetime
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import threading
import asyncio
import os

afterhours_start_hour = 23
afterhours_end_hour = 6
tz = timezone('America/Los_Angeles')

class Bouncer(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)
        print('Name:', self.user.name)
        print('ID:', self.user.id)

        self.afterhoursChannels = {}
        self.guildEveryoneRoles = {}

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
        for guild, channel in self.afterhoursChannels.items():
            role = self.guildEveryoneRoles.get(guild, None)
            if role != None:
                await self.setWritePermission(channel, role, True)

    async def setAfterhoursDisabled(self):
        for guild, channel in self.afterhoursChannels.items():
            role = self.guildEveryoneRoles.get(guild, None)
            if role != None:
                await self.setWritePermission(channel, role, False)

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
            for c in g.text_channels:
                if c.name == '🌙afterhours':
                    self.afterhoursChannels[g] = c

        print(self.afterhoursChannels)

    def loadGuildEveryoneRoles(self):
        for g in self.guilds:
            self.guildEveryoneRoles[g] = g.default_role

        print(self.guildEveryoneRoles)

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
    scheduler.add_job(open_channel, trigger='cron', args=(client,), hour=hour_start, id='id_open_channel')
    scheduler.add_job(close_channel, trigger='cron', args=(client,), hour=hour_end, id='id_close_channel')
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
