# Description
Python package to collect some logs of my personal life.
# Installation
- Clone the repo
- Create virtual environment ```python -m venv source /home/rjof/virtual_environments/logme/```
- Activate ```source /home/rjof/virtual_environments/logme/bin/activate```
- ```cd ~/Documents/logme_project```
- Install requirements.txt: ```pip3 install requirements.txt```
- Create the file ```.env``` with your credentials, for example:
```
aTimeLogger_user = your@email.com
aTimeLogger_pass = your_password
```
 - Install the logme module ```pip install -e .```
 - Duolingo package requires a fix:
> @flyinggoatman
>
> I fixed this for my usecase by removing self.jwt = None 
>
> at https://github.com/KartikTalwar/Duolingo/blob/master/duolingo.py#L100, 
>
> which then allowed me to instantiate like
>
> lingo  = duolingo.Duolingo(username='myUsername', jwt='myJWT')
>
> You can grab your JWT by logging in on duolingo.com and then running this JavaScript, which will output the token into the console: 

```document.cookie.match(new RegExp('(^| )jwt_token=([^;]+)'))[0].slice(11);```

# Usage
To create the database
```python -m logme init```

The file _config.ini_ should be created. 
For example in linux it is in 
_/home/<your_user>/.config/logme/config.ini_

Insert configuration for processing data. For example:

```
[Sources]
src = aTimeLogger                                                                                                                                                                       
[LocalPaths]
storage = /home/<your_user>/logme_data
[aTimeLogger]
connection = api
days_to_retrieve_api = 7
```

To process data in your aTimeLogger account:
```
python -m logme source aTimeLogger
```

# Sources
## aTimeLogger app
@todo: description

## duolingo unofficial api
As an example of the use of the api and to use it in the roadmap of this package it's only saved the **achievements** which is when you gain a crown.

The intervals between achievements will be used to generate rules.

## Instagram with instaloader and selenium
Downloads all the posts saved and unsave them from the site.

### Refresh session


Test if the command line connects

```
instaloader --dirname-pattern testInstaoaderCommanLine --login errejotaoefe --count 1 :saved
```

Repairs the command line but not the python connection

Firefox: 

```
cd ~/Documents/seleniumhq.github.io/examples/python/tests/rjof

python3 instaloader_session.py -c /home/rjof/snap/firefox/common/.mozilla/firefox/ycxcs1wp.default/cookies.sqlite -f /home/rjof/.config/instaloader/session-errejotaoefe
```

## Command line
### Download saved from specific date
```
instaloader --dirname-pattern <DIRECTORY_NAME_TO_SAVE> --login errejotaoefe --post-filter="date_utc >= datetime(2024,12,1) and date_utc <= datetime(2024,12,30)" :saved
```

# Storage
The collected data is saved in a sqlite database in the table **logme** with the structure:

*A hash of the row, not in use for the time being*

Column('hash',         String, primary_key = True),

*The activity to which a group belongs, i.e.* **this book**, *belongs to the group* **reading**

Column('in_group',     String),

*The activity*

Column('activity',     String),

*Any comment*

Column('comment',      String),

*Duration in seconds of the activity*

Column('duration_sec', Integer),

*Beginning unix timestamp of the activity*

Column('ts_from',      Integer),

*Finishing unix timestamp of the activity*

Column('ts_to',        Integer),


# Notes

 The code base is the application 
 [Build a Command-Line To-Do App With Python and Typer](https://realpython.com/python-typer-cli/)
 and this project is full legacy to be cleaned (I've done this 
 to learn some python).

 You can see this printing the help.

```
python -m logme --help
```

<pre><code>
Usage: logme [OPTIONS] COMMAND [ARGS]...
Options:
  -v, --version         Show the application's version and exit.
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.

Commands:
  <del>add       Add a new to-do with a DESCRIPTION.</del>
  <del>clear     Remove all to-dos.</del>
  <del>complete  Complete a to-do by setting it as done using its TODO_ID.</del>
  init      Initialize the logme database.
  <del>list      List all to-dos.</del>
  <del>remove    Remove a to-do using its TODO_ID.</del>
  source    Process a source.
</code></pre>

## Minimal sqlite queries
```
sqlite3 /home/rjof/.rjof_logme.db

.mode table
```

### unix epoc to date
```
select *, datetime(ts_to, 'unixepoch') as ts_to_date from logme order by ts_to desc limit 10
```

### Pages read (KoreaderStatistics)
```
select activity,count(activity) as pages from logme where in_group = 'Leo' group by activity order by pages;
```

# ChatGPT test
Hi chat,

Please answer this as a 15 years of experience python programmer.

I want to have a python programm to download my digital footprint and files from the following sources duolingo, aTimeLogger, Google Drive, Google Maps, Dropbox, Instagram and Podcast Adict.

I want the program to have switches to select the source and a date switch, for example to download saved posts in Instagram in certain date.

Can you create this program?

## Answer

Certainly! Creating a Python program to download your digital footprint and files from multiple sources like Duolingo, aTimeLogger, Google Drive, Google Maps, Dropbox, Instagram, and Podcast Addict involves several steps. Since each of these services has its own API or method of interaction, we need to structure the program so that it can handle each source individually while providing a user-friendly interface for choosing which services to pull data from and specifying dates for certain platforms.

Here’s a high-level breakdown of how we can approach this task:
Requirements:

    Duolingo: Scrape data from Duolingo or use an unofficial API (if available).
    aTimeLogger: If they have an export API or method (usually JSON or CSV), we can automate the download.
    Google Drive: Use Google Drive API to download files.
    Google Maps: Use Google Maps API for places, reviews, or location data.
    Dropbox: Use Dropbox API to interact with your files.
    Instagram: Use Instagram's unofficial API or scraping method, as their official API might not allow detailed user data extraction.
    Podcast Addict: If it allows exports or has an API, we can automate downloading podcast data.

The solution will likely involve setting up OAuth authentication for services that require it (Google, Dropbox, Instagram, etc.), interacting with APIs, and setting up date filters where applicable.
Libraries & Tools:

    requests: For HTTP requests to APIs (where applicable).
    google-api-python-client: For Google services (Drive, Maps).
    dropbox: For Dropbox.
    instaloader: For downloading Instagram posts (unofficial but works well).
    argparse: For managing switches (command-line arguments).
    datetime: For handling date filters.

The Python Program

Here's a structure for your program using command-line arguments:

```
import argparse
import datetime
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import dropbox
import instaloader
import requests

# Example for Google Drive API authentication (you can expand this for other services)
def google_drive_download(date=None):
    # Authentication and API setup
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive.readonly'])
    
    if not creds or not creds.valid:
        # Handle token refresh
        pass
    
    service = build('drive', 'v3', credentials=creds)
    # List files from Google Drive (you can also filter by modified date)
    results = service.files().list().execute()
    files = results.get('files', [])
    
    if date:
        date_filter = datetime.datetime.strptime(date, "%Y-%m-%d")
        # Filter files by modification date
        files = [file for file in files if datetime.datetime.strptime(file['modifiedTime'], "%Y-%m-%dT%H:%M:%S.%fZ") >= date_filter]
    
    for file in files:
        print(f"Downloading {file['name']}")
        # Implement file download logic here (omitted for brevity)

# Example for Dropbox API authentication and download
def dropbox_download(date=None):
    dbx = dropbox.Dropbox('YOUR_ACCESS_TOKEN')
    files = dbx.files_list_folder('').entries
    
    if date:
        date_filter = datetime.datetime.strptime(date, "%Y-%m-%d")
        files = [file for file in files if datetime.datetime.strptime(file.client_modified, "%Y-%m-%dT%H:%M:%S") >= date_filter]
    
    for file in files:
        print(f"Downloading {file.name}")
        # Implement file download logic here (omitted for brevity)

# Example for Instagram download using instaloader
def instagram_download(date=None):
    loader = instaloader.Instaloader()
    # Login to Instagram (optional but needed for private profiles)
    loader.load_session_from_file("YOUR_USERNAME")
    
    # Get your profile
    profile = instaloader.Profile.from_username(loader.context, "YOUR_USERNAME")
    
    for post in profile.get_posts():
        if date:
            post_date = post.date_utc.date()
            filter_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            if post_date == filter_date:
                print(f"Downloading post from {post_date}")
                loader.download_post(post, target=profile.username)
        else:
            loader.download_post(post, target=profile.username)

# Command-line interface for the user
def main():
    parser = argparse.ArgumentParser(description="Download digital footprint from various sources.")
    parser.add_argument('--source', choices=['google_drive', 'dropbox', 'instagram'], required=True, help='Source to download from')
    parser.add_argument('--date', help='Filter posts or files from a specific date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.source == 'google_drive':
        google_drive_download(date=args.date)
    elif args.source == 'dropbox':
        dropbox_download(date=args.date)
    elif args.source == 'instagram':
        instagram_download(date=args.date)

if __name__ == "__main__":
    main()
```

Breakdown of the Code:

    Authentication: Each service requires its own authentication flow. For Google services, you would use OAuth 2.0, and for Dropbox, you would use an API token. Instagram uses instaloader for scraping public posts, but you can log in for private posts.

    Filtering by Date:
        For Google Drive, Dropbox, and Instagram, you can filter items by their modification or creation date.
        The --date argument allows you to filter posts or files for a specific day in the format YYYY-MM-DD.

    Command-line interface: The argparse library lets the user select which source they want to download from (Google Drive, Dropbox, Instagram) and optionally apply a date filter.

    Downloading Files/Posts: Each function (like google_drive_download, dropbox_download, instagram_download) is tailored to the specific API or library, and you can modify these to download and save the data locally.

Steps for Google Drive Setup:

To work with the Google Drive API, you'll need to set up OAuth credentials from the Google Cloud Console. Here's a brief overview:

    Create a project and enable the Google Drive API.
    Set up OAuth 2.0 credentials.
    Download the credentials JSON file and save it as credentials.json in your project folder.

Steps for Dropbox Setup:

To work with Dropbox, you'll need to create an app in the Dropbox Developer Console and get an access token.
Steps for Instagram Setup:

Use the instaloader library to download posts. You can install it via pip:

```
pip install instaloader
```

Extending the Program for Other Services:

    Duolingo and aTimeLogger: You would need to check if these services have an official or unofficial API. For example, you could scrape data from Duolingo or export CSV files from aTimeLogger if they provide this feature.
    Podcast Addict: If Podcast Addict has a data export feature, you could automate that through API calls or by scraping.

This is a basic framework, and you'll need to expand on it to handle error cases, edge cases, and more robust file handling (downloading files, handling large datasets, etc.). If you encounter specific issues with API interactions or need help with one of the services, feel free to ask!
By messaging ChatGPT, you agree to our Terms and have read our Privacy Policy.
Don't share sensitive info. Chats may be reviewed and used to train our models. Learn more


ChatGPT can make mistakes. Check important info.

