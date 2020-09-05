
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from apiclient import errors
import os
import discord
import pickle
import os.path
import io
import requests
from consts import TOKEN, CHANNEL_NAME, SEARCH_CHANNEL, NOTTI_BANANA, PEPE, COOKIE, REGEX, LAST_UPLOADED_TABLE, UPLOADED_STAGES
from tinydb import Query
from discord import File

SCOPES = ['https://www.googleapis.com/auth/drive']
Stage = Query()


async def upload_search_towers(floor, ctx, tower, memo, service, DB=None):

    if ctx.message.channel.name == SEARCH_CHANNEL and not ctx.message.author.bot:
        return_message = ""
        search_folder = get_folder_id_by_name(
            tower, service, memo)
        stage_ids = search_file_in_folder(
            search_folder, floor, service)
        if stage_ids is not None:
            for stage_id, file_name in stage_ids:
                # return_message += f"Stage link: https://drive.google.com/file/d/{stage_id}\n"
                if DB is not None:
                    stage_doc = DB.table(UPLOADED_STAGES).get(
                        Stage.file_id == stage_id)
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
        pass

    for attachment in ctx.message.attachments:
        uploaded_file_id = upload_file(service, attachment.url, tower,
                                       ctx.message.author, floor, memo)
        if uploaded_file_id is not None:
            print(f"Uploaded floor {floor}")
            await ctx.message.add_reaction('👍')
            return uploaded_file_id
        else:
            await ctx.message.add_reaction('👎')


def download_file(file_id, service):
    request = service.files().get_media(fileId=file_id)
    print(request)
    print(dir(request))
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh


def delete_file(service, file_id):
    """Permanently delete a file, skipping the trash.

    Args:
      service: Drive API service instance.
      file_id: ID of the file to delete.
    """
    try:
        service.files().delete(fileId=file_id).execute()
    except errors.HttpError as error:
        print(f'An error occurred: {error}')


def createRemoteFolder(folderName, drive_service, parentID=None):
    # Create a folder on Drive, returns the newely created folders ID
    body = {
        'name': folderName,
        'mimeType': "application/vnd.google-apps.folder"
    }
    if parentID:
        body['parents'] = [parentID]
    root_folder = drive_service.files().create(body=body).execute()
    return root_folder['id']


def search_file_in_folder(folder_id, stage, drive_service):
    page_token = None
    solutions = []
    while True:
        response = drive_service.files().list(q=f"'{folder_id}' in parents",
                                              spaces='drive',
                                              fields='nextPageToken, files(id, name)',
                                              pageToken=page_token).execute()
        for file in response.get('files', []):
            # Process change
            if file.get('name').startswith(f"{stage}-"):
                print('Found file: %s (%s)' %
                      (file.get('name'), file.get('id')))
                solutions.append((file.get('id'), file.get('name')))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    if len(solutions) != 0:
        return solutions


def get_folder_id_by_name(folder_name, drive_service, memo):
    if folder_name in memo:
        return memo[folder_name]
    page_token = None
    while True:
        response = drive_service.files().list(q=f"mimeType='application/vnd.google-apps.folder' and name = '{folder_name}'",
                                              spaces='drive',
                                              fields='nextPageToken, files(id, name)',
                                              pageToken=page_token).execute()
        for file in response.get('files', []):
            # Process change
            print('Found file: %s (%s)' % (file.get('name'), file.get('id')))
            memo[folder_name] = file.get('id')
            return memo[folder_name]
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break


def init_g_drive():
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
# If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)


def upload_file(service, url, folder, author, stage, memo):
    image = requests.get(url)
    # Get folder
    folder_id = get_folder_id_by_name(folder, service, memo)

    media = MediaIoBaseUpload(io.BytesIO(
        image.content), mimetype='image/jpeg')
    author_name = None
    if author.nick is not None:
        author_name = author.nick
    else:
        author_name = author.name

    uploaded_file = service.files().create(
        media_body=media,
        body={"name": f'{stage}-{author_name}',
              'parents': [folder_id]}
    ).execute()
    if uploaded_file:
        return uploaded_file['id']
    else:
        return None
