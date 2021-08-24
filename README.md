# Valheim World Sync

Sync [Valheim](https://store.steampowered.com/app/892970/Valheim/) world files between a local directory and a Google drive folder.

[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Prerequisites

You'll need the following to run **VWS**.

- Python 3
- pip3
- Virtualenv (optional)
- This repo: `git clone https://github.com/naveen-u/valheim-world-sync.git`
- A Google Drive API project.
  - To create a project and enable an API, refer to [Create a project and enable the API](https://developers.google.com/workspace/guides/create-project).
  - Authorization credentials.
    - [Configure the OAuth consent screen](https://developers.google.com/workspace/guides/create-credentials#configure_the_oauth_consent_screen).
    - [Create a OAuth client ID credential](https://developers.google.com/workspace/guides/create-credentials#create_a_oauth_client_id_credential).
    - [Create Desktop application credentials](https://developers.google.com/workspace/guides/create-credentials#desktop).

## Installation

1. _[Optional]_ Create and activate a virtual environment:

```bash
virtualenv venv
source venv/bin/activate
```

2. Install the required python packages:

```bash
pip3 install -r requirements.txt
```

3. Copy the JSON file with API client credentials (as mentioned [here](https://developers.google.com/workspace/guides/create-credentials#desktop)) to the root of the project. Rename the file to `credentials.json`.

4. Create a `.env` file with the following environment variables:

```
DRIVE_FOLDER=<Google drive folder ID>
LOCAL_FOLDER=<Path to local Valheim worlds directory>
```

`DRIVE_FOLDER` contains the ID of the Google drive folder to sync world files with. The ID of a google drive folder is the last part of the URL when you navigate to that folder on Google drive (for example, the folder at https://drive.google.com/drive/u/1/folders/1mhHDGlTdVwQCgmq8_Okcri5_EDFxcvAG has ID `1mhHDGlTdVwQCgmq8_Okcri5_EDFxcvAG`).

`LOCAL_FOLDER` contains the path to the local Valheim worlds folder. This is usually `C:\Users\<Username>\AppData\LocalLow\IronGate\Valheim\` on Windows

> _Note_: If these environment variables are not provided in a `.env` file and are not present in the environment where the script is run, the script will ask for these values via user input.

## Running the script

```bash
python3 sync.py
```

## Usage

- **VWS** searches both the local and drive folders for Valheim world files, and lists all the worlds found with their sync status. The sync status (already in sync/upload to drive/download from drive) is based on the last modified timestamps of the files.

![A wild screenshot appeared!](https://user-images.githubusercontent.com/29832401/130596352-6637ef69-b103-4a0b-88e6-ffd6ae2a47db.png)

- Select a world to sync and let VWS do its thing.

## Authors

- **Naveen Unnikrishnan** - [naveen-u](https://github.com/naveen-u)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
