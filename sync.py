#! /usr/bin/env python3


"""
Sync Valheim world files between the local Valheim worlds directory and a Google Drive folder.

Copyright Naveen Unnikrishnan, August 2021.
Licensed under the MIT License.
"""

import glob
import io
import os
import os.path
import sys
from datetime import datetime, timezone
from enum import Enum
from os import listdir
from typing import Dict, List, Tuple, TypedDict

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from rich import print
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import track
from rich.prompt import IntPrompt, Prompt
from rich.text import Text

# ---------------------------------------------------------------------------- #
#                             ENVIRONMENT VARIABLES                            #
# ---------------------------------------------------------------------------- #

load_dotenv()
DRIVE_FOLDER = os.getenv("DRIVE_FOLDER")
LOCAL_FOLDER = os.getenv("LOCAL_FOLDER")

# ---------------------------------------------------------------------------- #
#                                  DEFINITIONS                                 #
# ---------------------------------------------------------------------------- #


class WorldAction(Enum):
    """
    Enum containing available sync actions for a world.
    """

    SYNCED = "Already in sync"
    UPLOAD = "Upload to drive"
    DOWNLOAD = "Download from drive"


class LocalWorldData(TypedDict):
    """
    Class denoting world data available locally.

    Attributes:
        updated_time (datetime): Time when the world files were last updated.
        file_names (List[str]): List of file names.
    """

    updated_time: datetime
    file_names: List[str]


class DriveWorldData(TypedDict):
    """
    Class denoting world data available on drive.

    Attributes:
        updated_time (datetime): Time when the world files were last updated.
        updated_by (str): Name of user who last updated the world files.
        file_ids (List[Tuple[str, str]]): List of tuples with file IDs and names.
    """

    updated_time: datetime
    updated_by: str
    file_ids: List[Tuple[str, str]]


# ---------------------------------------------------------------------------- #
#                                   CONSTANTS                                  #
# ---------------------------------------------------------------------------- #

API_NAME = "drive"
API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/drive"]
VALHEIM_FILE_EXTS = [".db", ".fwl", ".old"]
DRIVE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
DISPLAY_TIME_FORMAT = "%B %d, %Y at %I:%M:%S %p"
PANEL_STYLE_FOR_ACTION = {
    WorldAction.SYNCED: "bold green1",
    WorldAction.DOWNLOAD: "bold bright_red",
    WorldAction.UPLOAD: "bold deep_sky_blue1",
}


# ---------------------------------------------------------------------------- #
#                                    METHODS                                   #
# ---------------------------------------------------------------------------- #


def sync(world_name: str = None):
    """
    Searches for Valheim world files in the provided local and drive directories,
    and lets the user sync them.

    Args:
        world_name (str, optional): Name of world to be synced. Defaults to None.
    """
    global DRIVE_FOLDER, LOCAL_FOLDER
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                creds = get_new_refresh_token()
        else:
            creds = get_new_refresh_token()
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build(API_NAME, API_VERSION, credentials=creds)

    if DRIVE_FOLDER is None:
        DRIVE_FOLDER = Prompt.ask("  Enter Google drive folder ID")
    if LOCAL_FOLDER is None:
        LOCAL_FOLDER = Prompt.ask("  Enter local folder path")
    drive_worlds = get_worlds_in_drive(service, DRIVE_FOLDER)
    local_worlds = get_worlds_in_folder(LOCAL_FOLDER)
    world_to_be_synced, sync_action = show_sync_menu(
        local_worlds, drive_worlds, world_name
    )
    sync_world(
        service,
        sync_action,
        world_to_be_synced,
        local_worlds.get(world_to_be_synced, {}),
        drive_worlds.get(world_to_be_synced, {}),
    )


def get_new_refresh_token() -> Credentials:
    """
    Get a fresh OAuth token.

    Returns:
        Credentials: Auth credentials
    """
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    return flow.run_local_server(port=0)


def show_sync_menu(
    local_worlds: Dict[str, LocalWorldData],
    drive_worlds: Dict[str, DriveWorldData],
    world_name: str,
) -> Tuple[str, WorldAction]:
    """
    Shows sync menu with sync action for each available world and get user input.

    Args:
        local_worlds (Dict[str, LocalWorldData]): Map of worlds to local world data.
        drive_worlds (Dict[str, DriveWorldData]): Map of worlds to world data on drive.

    Returns:
        Tuple[str, WorldAction]: Tuple of world to be synced and required sync action.
    """
    worlds_list = list(local_worlds.keys() | drive_worlds.keys())
    i = 1
    world_action_map = {}
    panels = []
    for world in worlds_list:
        drive_world_data = drive_worlds.get(
            world, {"updated_time": None, "updated_by": None, "file_ids": []}
        )
        local_world_data = local_worlds.get(
            world, {"updated_time": None, "file_names": []}
        )
        drive_world_time = drive_world_data["updated_time"]
        drive_world_user = drive_world_data["updated_by"]
        local_world_time = local_world_data["updated_time"]
        action = get_action_required(local_world_time, drive_world_time)
        world_action_map[world] = action
        style = PANEL_STYLE_FOR_ACTION.get(action, "")
        header = Text(f"[{i}]. {world} ({action.value})", style=style)
        line1 = Padding(
            "Not on drive"
            if drive_world_time is None
            else f"Last updated on drive by {drive_world_user} on {get_local_time_string_from_utc(drive_world_time)}",
            (0, 6),
        )
        line2 = Padding(
            "Not on system"
            if local_world_time is None
            else f"Last updated on system on {get_local_time_string_from_utc(local_world_time)}",
            (0, 6),
        )
        panels.append(Panel(Group(header, line1, line2), border_style="bright_black"))
        i += 1
    print()
    print(Panel(Group(*panels), title="Valheim Worlds"))
    if world_name not in world_action_map and world_name is not None:
        print_padded(f"World {world_name} was not found among the available files!")
        print()
        world_name = None
    if world_name is None:
        world_index = (
            IntPrompt.ask(
                f"  Enter world to sync, or 0 to quit",
                choices=[str(x) for x in range(0, i)],
                default=0,
            )
            - 1
        )
        if world_index < 0 or world_index > i - 1:
            print_padded("Buh-bye!")
            exit(0)
        world_to_be_synced = worlds_list[world_index]
    else:
        world_to_be_synced = world_name
    return world_to_be_synced, world_action_map[world_to_be_synced]


def get_action_required(
    local_world_time: datetime, drive_world_time: datetime
) -> WorldAction:
    """
    Get required sync action.

    Args:
        local_world_time (datetime): Last updated time for world files on local machine.
        drive_world_time (datetime): Last updated time for world files on drive.

    Returns:
        WorldAction: Action required for sync.
    """
    if local_world_time is None:
        return WorldAction.DOWNLOAD
    elif drive_world_time is None:
        return WorldAction.UPLOAD
    elif local_world_time < drive_world_time:
        return WorldAction.DOWNLOAD
    elif local_world_time > drive_world_time:
        return WorldAction.UPLOAD
    return WorldAction.SYNCED


def sync_world(
    drive_service: Resource,
    action: WorldAction,
    world: str,
    local_world_data: LocalWorldData,
    drive_world_data: DriveWorldData,
):
    """
    Sync drive and local files according to provided sync action.

    Args:
        drive_service (Resource): Service with which to access Google Drive API.
        action (WorldAction): Upload/download/already in sync.
        world (str): World name.
        local_world_data (LocalWorldData): Data pertaining to local world files.
        drive_world_data (DriveWorldData): Data pertaining to world files on drive.
    """
    if action == WorldAction.SYNCED:
        print_padded(f"World {world} is already in sync!")
    elif action == WorldAction.DOWNLOAD:
        print_padded(f"Deleting existing {world} files on local machine...")
        for filename in track(
            glob.glob(f"{os.path.join(LOCAL_FOLDER, world)}*"),
            description="Deleting files from local machine",
            transient=True,
        ):
            os.remove(filename)
        print_padded(f"Finished deleting {world} from local machine.")
        print_padded(f"Downloading {world} files from drive...")
        download_files(drive_service, drive_world_data)
        print_padded(f"Finished downloading {world} from drive.")
    else:
        print_padded(f"Deleting existing {world} files from drive...")
        delete_files(drive_service, drive_world_data.get("file_ids", []))
        print_padded(f"Finished deleting {world} from drive.")
        print_padded(f"Uploading {world} files to drive...")
        upload_files(drive_service, local_world_data)
        print_padded(f"Finished uploading {world} to drive.")


def delete_files(drive_service: Resource, files: List[Tuple[str, str]]):
    """
    Delete given list of files from drive.

    Args:
        drive_service (Resource): Service with which to access Google Drive API.
        files (List[Tuple[str, str]]): List of files (tuple of file ID and name).
    """
    for file_id, file_name in track(
        files, description="Deleting files from drive", transient=True
    ):
        drive_service.files().delete(fileId=file_id).execute()


def upload_files(drive_service: Resource, local_world_data: LocalWorldData):
    """
    Upload given files to drive.

    Args:
        drive_service (Resource): Service with which to access Google Drive API.
        files (List[str]): List of file names.
    """
    files = local_world_data.get("file_names", [])
    last_updated_time = local_world_data.get("updated_time", datetime.now())
    for file in track(files, description="Uploading files to drive", transient=True):
        file_metadata = {
            "name": file,
            "parents": [DRIVE_FOLDER],
            "modifiedTime": last_updated_time.strftime(DRIVE_TIME_FORMAT),
        }
        media_content = MediaFileUpload(
            os.path.join(LOCAL_FOLDER, file), mimetype="application/octet-stream"
        )
        file = (
            drive_service.files()
            .create(body=file_metadata, media_body=media_content)
            .execute()
        )


def download_files(drive_service: Resource, drive_world_data: DriveWorldData):
    """
    Download given file IDs from drive.

    Args:
        drive_service (Resource): Service with which to access Google Drive API.
        files (List[Tuple[str, str]]): List of tuples of file IDs and names to download.
    """
    files = drive_world_data.get("file_ids", [])
    last_updated_time = (
        drive_world_data.get("updated_time", datetime.now())
        .replace(tzinfo=timezone.utc)
        .astimezone(tz=None)
        .timestamp()
    )
    for file_id, file_name in track(
        files, description="Downloading files from drive", transient=True
    ):
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        with open(os.path.join(LOCAL_FOLDER, file_name), "wb") as f:
            f.write(fh.read())
            f.close()
        os.utime(
            os.path.join(LOCAL_FOLDER, file_name),
            (last_updated_time, last_updated_time),
        )


def get_worlds_in_drive(
    drive_service: Resource, drive_folder: str
) -> Dict[str, DriveWorldData]:
    """
    Get a map from world names to last modified times and user for files in the given drive folder.

    Args:
        drive_service (Resource): Service with which to access Google Drive API.
        drive_folder (str): ID of the Google Drive folder.

    Returns:
        Dict[str, DriveWorldData]: A map from world names to a world data on drive.
    """
    page_token = None
    world_map: dict[str, DriveWorldData] = {}
    while True:
        response = (
            drive_service.files()
            .list(
                q=f"'{drive_folder}' in parents",
                spaces="drive",
                fields="nextPageToken, files(id, name, modifiedTime, lastModifyingUser(displayName, me), trashed)",
                pageToken=page_token,
            )
            .execute()
        )
        for file in response.get("files", []):
            file_name = file.get("name")
            if is_valheim_world_file(file_name) and not file.get("trashed"):
                world_name = file_name.split(".")[0]

                last_modified_time = datetime.strptime(
                    file.get("modifiedTime"), DRIVE_TIME_FORMAT
                )

                world_data = world_map.get(
                    world_name,
                    {"updated_time": None, "updated_by": None, "file_ids": []},
                )
                world_data["file_ids"].append((file.get("id"), file_name))
                if (
                    world_data["updated_time"] is None
                    or world_data["updated_time"] < last_modified_time
                ):
                    world_map[world_name] = {
                        "updated_time": last_modified_time.replace(microsecond=0),
                        "updated_by": "me"
                        if file.get("lastModifyingUser").get("me")
                        else file.get("lastModifyingUser").get("displayName"),
                    }
                world_map[world_name]["file_ids"] = world_data["file_ids"]
        page_token = response.get("nextPageToken", None)
        if page_token is None:
            break
    return world_map


def get_worlds_in_folder(folder: str) -> Dict[str, LocalWorldData]:
    """
    Get a map from world names to last modified times for files in the given folder.

    Args:
        folder (str): Folder path.

    Returns:
        Dict[str, LocalWorldData]: Map from world names to local world data.
    """
    files = [
        f
        for f in listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and is_valheim_world_file(f)
    ]
    world_map: dict[str, LocalWorldData] = {}
    for file in files:
        world_name = file.split(".")[0]
        world_data = world_map.get(world_name, {"updated_time": None, "file_names": []})
        file_modified_time = get_modified_time(folder, file)
        world_data["file_names"].append(file)
        if (
            world_data["updated_time"] is None
            or world_data["updated_time"] < file_modified_time
        ):
            world_map[world_name] = {
                "updated_time": file_modified_time.replace(microsecond=0)
            }
        world_map[world_name]["file_names"] = world_data["file_names"]
    return world_map


def get_modified_time(folder: str, file: str) -> datetime:
    """
    Get last modified datetime object for a file in a given folder.

    Args:
        folder (str): Folder path.
        file (str): File name.

    Returns:
        datetime: The datetime object with the last modified time.
    """
    epoch_time = os.path.getmtime(os.path.join(folder, file))
    return datetime.utcfromtimestamp(epoch_time)


def is_valheim_world_file(file_name: str) -> bool:
    """
    Checks if given file has one of the valid Valheim world file extensions.

    Args:
        file_name (str): Name of file.

    Returns:
        bool: True if file has a valid extension; false otherwise.
    """
    return os.path.splitext(file_name)[-1].lower() in VALHEIM_FILE_EXTS


def print_padded(string: str):
    """
    Utility method to print to console with a fixed padding.

    Args:
        string (str): Text to print.
    """
    print(Padding(string, (0, 2)))


def get_local_time_string_from_utc(time: datetime) -> str:
    """
    Get date and time string in the local timezone from a UTC datetime object.
    String is formatted to DISPLAY_TIME_FORMAT.

    Args:
        time (datetime): UTC datetime object.

    Returns:
        str: Date-time string.
    """
    return (
        time.replace(tzinfo=timezone.utc)
        .astimezone(tz=None)
        .strftime(DISPLAY_TIME_FORMAT)
    )


# ---------------------------------------------------------------------------- #
#                                    SCRIPT                                    #
# ---------------------------------------------------------------------------- #

if __name__ == "__main__":
    world = None
    if len(sys.argv) > 1:
        world = sys.argv[1]
    sync(world)
