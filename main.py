from __future__ import print_function
import os
import discord
import pickle
import os.path
import io
from discord.ext import commands

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseUpload
from discord import File

from helper import createRemoteFolder, get_folder_id_by_name, init_g_drive, upload_file, search_file_in_folder, upload_search_towers, delete_file, download_file
from consts import TOKEN, CHANNEL_NAME, SEARCH_CHANNEL, PEPE, COOKIE, DB_JSON, LAST_UPLOADED_TABLE, UPLOADED_STAGES, TOWER_TYPE
from tinydb import TinyDB, Query, where
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
from exceptions import AlreadyDeleted, WrongChannel

import requests
import re

client = commands.Bot(command_prefix='a!', case_insensitive=True)
client.remove_command('help')

DB = TinyDB(DB_JSON)
User = Query()

service = init_g_drive()
memo = {}
# {userId: fileId}
last_uploaded_memo = {}


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_command_error(ctx, error):
    await ctx.message.add_reaction('👎')
    print(error)


@client.command()
async def rm(ctx, arg=None):
    try:
        if ctx.message.channel.name != CHANNEL_NAME:
            raise WrongChannel
        uploaded_doc = DB.table(LAST_UPLOADED_TABLE).get(
            User.userId == ctx.author.id)
        if uploaded_doc is None:
            raise KeyError
        if uploaded_doc['removed']:
            raise AlreadyDeleted
        delete_file(service, uploaded_doc['file_id'])
        print("Deleted latest file!")
        DB.table(LAST_UPLOADED_TABLE).upsert(
            {'removed': True}, User.userId == ctx.author.id)
        DB.table(UPLOADED_STAGES).remove(
            where('file_id') == uploaded_doc['file_id'])
        await ctx.message.add_reaction('👍')
        await ctx.send(f"Deleted file, original message was: {uploaded_doc['message']}")

        message = await ctx.message.channel.fetch_message(uploaded_doc['message_id'])
        if message is not None:
            await message.delete()

    except KeyError:
        await ctx.message.add_reaction('👎')
        await ctx.author.send("You haven't uploaded a screenshot yet to delete!")
    except AlreadyDeleted:
        await ctx.message.add_reaction('👎')
        await ctx.author.send("You already used this command to delete latest uploaded SS.")
    except WrongChannel:
        await ctx.message.add_reaction('👎')
        await ctx.author.send(f"Can't use command in this channel, only in {CHANNEL_NAME}.")


@client.command(aliases=["lb", "wl", "ml", "gb"])
async def kt(ctx, arg):
    # Check how command was invoked
    folder, prefix = TOWER_TYPE[ctx.invoked_with]
    try:
        uploaded_file_id = await upload_search_towers(
            int(arg), ctx, folder, memo, service, DB)
        if uploaded_file_id is not None:
            DB.table(LAST_UPLOADED_TABLE).upsert(
                {'userId': ctx.author.id, 'file_id': uploaded_file_id, 'message': ctx.message.content, 'message_id': ctx.message.id, 'removed': False}, User.userId == ctx.author.id)
            DB.table(UPLOADED_STAGES).insert({
                'userId': ctx.author.id,
                'file_id': uploaded_file_id,
                'message': ctx.message.content.replace(f"{prefix} {arg}", '')
            })
    except:
        await ctx.message.add_reaction('👎')


@client.command()
async def camp(ctx, arg):
    try:
        chapter, stage = arg.split('-')
        # SEARCH
        if ctx.message.channel.name == SEARCH_CHANNEL and not ctx.message.author.bot:
            return_message = ""
            search_folder = get_folder_id_by_name(chapter, service, memo)
            stage_ids = search_file_in_folder(
                search_folder, stage, service)
            if stage_ids is not None:
                for stage_id, file_name in stage_ids:
                    # return_message += f"Stage link: https://drive.google.com/file/d/{stage_id}\n"
                    if DB is not None:
                        stage_doc = DB.table(UPLOADED_STAGES).get(
                            User.file_id == stage_id)
                    if stage_doc:
                        return_message += f"Upload caption: {stage_doc['message']}\n"

                    try:
                        stage_file = download_file(stage_id, service)
                        sending_file = File(stage_file, f"{file_name}.jpg")
                        await ctx.send(return_message, file=sending_file)
                    except Exception as e:
                        print(e)
                        print(e.args)
            else:
                await ctx.send(f"Couldn't find it, sowwy {PEPE}")
            return

        if not (ctx.message.channel.name == CHANNEL_NAME and not ctx.message.author.bot):
            return

        for attachment in ctx.message.attachments:
            uploaded_file_id = upload_file(service, attachment.url, chapter,
                                           ctx.message.author, stage, memo)
            if uploaded_file_id is not None:
                print(f"Chapter: {chapter} - Stage: {stage}")
                DB.table(LAST_UPLOADED_TABLE).upsert(
                    {'userId': ctx.author.id, 'file_id': uploaded_file_id, 'message': ctx.message.content, 'message_id': ctx.message.id, 'removed': False}, User.userId == ctx.author.id)
                DB.table(UPLOADED_STAGES).insert({
                    'userId': ctx.author.id,
                    'file_id': uploaded_file_id,
                    'message': ctx.message.content.replace(f"a!camp {arg}", '')
                })
                print(ctx.message.content)
                print(ctx.message.content.replace(f"a!camp {arg}", ''))
                await ctx.message.add_reaction('👍')
            else:
                await ctx.message.add_reaction('👎')
    except:
        await ctx.message.add_reaction('👎')


@client.command()
async def help(ctx, arg=None):
    try:
        help_message = f"""
            Use this format to allow the bot to upload to google drive at: https://drive.google.com/drive/u/1/folders/18xAGtAhPDkTlp1ZaoF0XVZ46dmWH2ZQ9

            1. King's tower stages: a!kt <floor>, EX: a!kt 150
            2. Tower of light stages: a!lb <floor>, EX: a!lb 250
            3. Brutal citadel stages: a!ml <floor>, EX: a!ml 250
            4. World tree stages: a!wl <floor>, EX: a!wl 250
            5. Forsaken necropolis stages: a!gb <floor>, EX: a!gb 250
            6. Campaign stages: a!camp Chapter-Stage, EX: a!camp 31-4

            IMPORTANT: If you upload a wrong image, or wrong caption by mistake use a!rm to delete it, only works on last uploaded SS!

            Buy me a coffee if you want! {COOKIE}
        """
        await ctx.send(help_message)
    except:
        await ctx.send(f"idk what happened, {PEPE}")


@client.event
async def on_message(message):
    message.content = message.content.lower()
    await client.process_commands(message)


client.run(TOKEN)
