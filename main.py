import os
import json
import time
import requests
import questionary
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv, set_key


load_dotenv()

CLIENT_ID = os.getenv('CLIENT_ID')
AUTH_URL = f'https://anilist.co/api/v2/oauth/authorize?client_id={CLIENT_ID}&response_type=token'
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN') or ''
API = 'https://graphql.anilist.co'
FORMAT = 'UTF-8'
ROOT = Path.cwd()
LISTS = ROOT / 'lists'
DELETED_JSON = LISTS / 'deleted.json'

if not LISTS.exists():
    LISTS.mkdir()

def clear_screan():
    print("\033[H\033[2J", end="")

def sleepProgress(sleep_time):
    while sleep_time >= 0:
        time.sleep(1)
        print('Waiting... {:2d}'.format(sleep_time), end='\r')
        sleep_time -= 1

def setHeader():
    global headers
    headers = {
        'Authorization': 'Bearer ' + ACCESS_TOKEN,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

def userAuth():
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        print(f'Open this link in the browser, login to anilist and paste the url after being redirected:\n{AUTH_URL}')
        url = input('Enter the url here: ')
        fragments_split = (urlparse(url)).fragment.split('&')
        # print(fragments_split)
        ACCESS_TOKEN = fragments_split[0].split('=')[1]
        set_key('.env', 'ACCESS_TOKEN', ACCESS_TOKEN)

def getAuthUserId():
    query = '''
        query {
            Viewer {
                id
                name
            }
        }
    '''
    variables = {}

    res = requests.post(API, json={'query': query, 'variables': variables}, headers=headers)
    data = res.json()
    print(f"\nLogged in as {data['data']['Viewer']['name']}")
    return data['data']['Viewer']['id']

def storeUserMediaList(list_type, status):

    mediaList = []
    query = '''
        query ($userId: Int, $page: Int, $perPage: Int, $type: MediaType, $status: MediaListStatus) {
            Page (page: $page, perPage: $perPage) {
                pageInfo {
                    total
                    currentPage
                    hasNextPage
                    perPage
                }

                mediaList (userId: $userId, type: $type, status: $status) {
                    id
                    mediaId
                    status
                    score
                    progress
                    progressVolumes
                    repeat
                    private
                    notes
                    hiddenFromStatusLists
                    media {
                        type
                        format
                        status
                        isAdult
                        episodes
                        chapters
                        title {
                            romaji
                            english
                        }
                    }
                    customLists (asArray: true)
                    startedAt {
                        day
                        month
                        year
                    }
                    completedAt {
                        day
                        month
                        year
                    }
                    updatedAt
                    createdAt
                }
            }
        }
    '''

    variables = {
        'userId': getAuthUserId(),
        'page': 1,
        'perPage': 50,
        'type': list_type,
        'status': status
    }

    flag = True
    
    # While the next page in the response is present, keep requesting for new pages
    while flag:
        res = requests.post(API, json={'query': query, 'variables': variables}, headers=headers)
        data = res.json()
        flag = data['data']['Page']['pageInfo']['hasNextPage']
        print("Page No: ", variables['page'])

        mediaList += data['data']['Page']['mediaList']
        variables['page'] += 1
    
    with open(f'./lists/{list_type.lower()}_{status.lower()}.json', 'w', encoding=FORMAT) as f:
        obj = {}
        obj['total'] = len(mediaList)
        obj['mediaList'] = mediaList
        print('Total: ', len(mediaList))
        json.dump(obj, f, indent=4, ensure_ascii=False)
        # sleepProgress(1)

def deleteCompleteMediaList(list_type, status):
    deleteQuery = '''
    mutation ($id: Int) {
        DeleteMediaListEntry (id: $id) {
            deleted
        }
    }
    '''

    variables = {
        'id': 0
    }

    with open(f'./lists/{list_type.lower()}_{status.lower()}.json', 'r', encoding=FORMAT) as f:
        data = json.load(f)
    
    deleted = {
        'deleted': []
    }

    for entry in data['mediaList']:
        variables['id'] = entry['id']

        res = requests.post(API, json={'query': deleteQuery, 'variables': variables}, headers=headers)
        rem = res.headers['X-RateLimit-Remaining']
        resp = res.json()
        print('Remaining requests: ', rem)

        if rem == '0':
            print('Deleted: ', len(deleted['deleted']))
            print('Hit rate limit, waiting 30s...')
            sleepProgress(30)
        else:
            resp['title'] = entry['media']['title']
            resp['status'] = entry['status']
            resp['type'] = entry['media']['type']
            resp['format'] = entry['media']['format']
            print(json.dumps(resp, indent=4))
            deleted['deleted'].append(resp)

    with open(DELETED_JSON, 'r+', encoding=FORMAT) as f:
        try:
            obj = json.load(f)
        except Exception as e:
            print(e)
            obj = deleted
        else:
            obj['deleted'] += deleted['deleted']
        finally:
            f.seek(0)
            json.dump(obj, f, indent=4, ensure_ascii=False)

    print('Deleted: ', len(deleted['deleted']))

def saveMediaList(list_type, status):
    query = '''
    mutation ($mediaId: Int, $status: MediaListStatus, $score: Float, $progress: Int, $progressVolumes: Int, $repeat: Int,
    $private: Boolean, $notes: String, $hiddenFromStatusLists: Boolean, $customLists: [String],
    $startedAt: FuzzyDateInput, $completedAt: FuzzyDateInput) {
        SaveMediaListEntry (mediaId: $mediaId, status: $status, score: $score, progress: $progress,
        progressVolumes: $progressVolumes, repeat: $repeat, private: $private, notes: $notes,
        hiddenFromStatusLists: $hiddenFromStatusLists, customLists: $customLists, startedAt: $startedAt, completedAt: $completedAt) {
            id
            status
            private
            repeat
            hiddenFromStatusLists
            customLists (asArray: true)
            notes
            media {
                type
                format
                status
                isAdult
                title {
                    romaji
                    english
                }
            }
        }
    }
    '''

    with open(f'./lists/{list_type.lower()}_{status.lower()}.json', 'r', encoding=FORMAT) as f:
        data = json.load(f)
    
    for entry in data['mediaList']:
        variables = {
            'mediaId': entry["mediaId"],
            'status': entry["status"],
            'score': entry["score"],
            'progress': entry["progress"],
            'progressVolumes': 0 if entry["progressVolumes"] == None else entry["progressVolumes"],
            'repeat': entry["repeat"],
            'private': entry["private"],
            'notes': entry["notes"],
            'hiddenFromStatusLists': entry["hiddenFromStatusLists"],
            'customLists': [x["name"] for x in entry["customLists"] if x["enabled"] == True],
            'startedAt': entry["startedAt"],
            'completedAt': entry["completedAt"]
        }

        res = requests.post(API, json={'query': query, 'variables': variables}, headers=headers)
        rem = res.headers['X-RateLimit-Remaining']
        resp = res.json()
        print('Remaining requests: ', rem)

        if rem == '0':
            print('Hit rate limit, waiting 30s...')
            sleepProgress(30)
        else:
            print(json.dumps(resp, indent=4, ensure_ascii=False))
    exit()

def main():
    userAuth()
    setHeader()

    clear_screan()
    getAuthUserId()

    input("Enter to continue..")

    command_options = [
        "Download Media List",
        "Delete Media List",
        "Save(Upload Existing) | Update Media List",
        "Exit"
    ]

    type_options = [
        "Anime",
        "Manga"
    ]

    status_options = [
        "Planning",
        "Current",
        "Paused",
        "Dropped",
        "Completed"
    ]

    while True:
        clear_screan()

        command_choice = questionary.select(
            "Choose an option",
            qmark=">>",
            choices=command_options
        ).ask()

        if command_choice == "Exit":
            break

        choice = command_options.index(command_choice) + 1

        type_choice = questionary.select(
            "Type",
            qmark=">>",
            choices=type_options
        ).ask()

        status_choice = questionary.select(
            "Status",
            qmark=">>",
            choices=status_options
        ).ask()

        list_type = type_choice.upper()
        status = status_choice.upper()

        if choice == 1:
            storeUserMediaList(list_type, status)
            input("\n\nSaved lists to ./lists\nEnter to continue..")

        elif choice == 2:
            if not DELETED_JSON.exists():
                DELETED_JSON.touch()
            deleteCompleteMediaList(list_type, status)
            input("\n\nLogged lists to ./lists\nEnter to continue..")

        elif choice == 3:
            confirm = questionary.confirm(f"Ensure {list_type.lower()}_{status.lower()}.json is in ./lists", qmark=">>").ask()
            if not confirm:
                print("Exiting..")
                break
            saveMediaList(list_type, status)

        elif choice == 4:
            exit()
        else:
            pass

if __name__ == '__main__':
    main()
