import os
import json
import logging
import time
import requests
import questionary
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv, set_key

load_dotenv()
logging.basicConfig(filename="alm.log", level=logging.DEBUG)

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
        logging.info("Authenticated User")

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
    logging.info("Fetching User ID")
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

        error = data.get("errors")
        if error:
            break

        flag = data['data']['Page']['pageInfo']['hasNextPage']
        print("Page No: ", variables['page'])
        logging.info(f"Downloading List {list_type} {status} PAGE {variables['page']}")

        mediaList += data['data']['Page']['mediaList']
        variables['page'] += 1
    
    if error:
        print("[ERROR] Check Logs")
        logging.error(logging.error(json.dumps(error)))
        input("Enter to continue...")
    else:        
        with open(f'./lists/{list_type.lower()}_{status.lower()}.json', 'w', encoding=FORMAT) as f:
            obj = {
                "total": len(mediaList),
                "mediaList": mediaList
            }
            print('Total: ', len(mediaList))
            logging.info(f"Finished Downloading, SIZE {len(mediaList)}")
            json.dump(obj, f, indent=4, ensure_ascii=False)
            logging.info("Saved to file.")

def deleteCompleteMediaList(list_type, status):
    deleteQuery = '''
    mutation ($id: Int) {
        DeleteMediaListEntry (id: $id) {
            deleted
        }
    }
    '''

    with open(f'./lists/{list_type.lower()}_{status.lower()}.json', 'r', encoding=FORMAT) as f:
        data = json.load(f)
    
    deleted = {
        'deleted': []
    }

    mediaList = data.get("mediaList")

    for entry in mediaList:
        variables = {
            "id": entry['id']
        }

        res = requests.post(API, json={'query': deleteQuery, 'variables': variables}, headers=headers)
        rem = res.headers['X-RateLimit-Remaining']
        resp = res.json()

        error = resp.get("errors")
        if error:
            print(f"[ERROR] Check Logs")
            logging.error(f"[ERROR] {json.dumps(error)}")
            break

        print('Remaining requests: ', rem)
        logging.info("Remaining Req: {rem}")

        if rem == '0':
            print('Deleted: ', len(deleted['deleted']))
            print('Hit rate limit, waiting 30s...')
            logging.info("Hit Rate Limit")
            sleepProgress(30)
        else:
            title = entry['media']['title']
            entry_type = entry['media']['type']
            entry_format = entry['media']['format']
            print(f"[DELETED] {title.get('romaji')} {entry_type} {entry_format}")
            logging.info(f"[DELETED] {title.get('romaji')} {entry_type} {entry_format}")
            deleted['deleted'].append({
                "title": title,
                "status": entry["status"],
                "type": entry_type,
                "format": entry_format
            })

    if not error:
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
    logging.info(f"Delete: {len(deleted.get('deleted'))}")

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
    
    mediaList = data.get("mediaList")

    for entry in mediaList:
        variables = {
            'mediaId': entry["mediaId"],
            'status': entry["status"],
            'score': entry["score"],
            'progress': entry["progress"],
            'progressVolumes': 0 if not entry["progressVolumes"] else entry["progressVolumes"],
            'repeat': entry["repeat"],
            'private': entry["private"],
            'notes': None if not entry["notes"] else entry["notes"],
            'hiddenFromStatusLists': entry["hiddenFromStatusLists"],
            'customLists': None if not entry["customLists"] else  [x["name"] for x in entry["customLists"] if x["enabled"] == True],
            'startedAt': entry["startedAt"],
            'completedAt': entry["completedAt"]
        }

        res = requests.post(API, json={'query': query, 'variables': variables}, headers=headers)
        rem = res.headers['X-RateLimit-Remaining']
        resp = res.json()

        error = resp.get("errors")

        if error:
            print(f"[ERROR] Check Logs")
            logging.error(json.dumps(error))
        else:
            print('Remaining requests: ', rem)
            logging.info("Remaining Req: {rem}")

            if rem == '0':
                print('Hit rate limit, waiting 30s...')
                logging.info("Hit Rate Limit")
                sleepProgress(30)
            else:
                savedMedia = resp.get("data").get("SaveMediaListEntry").get("media")
                print(f"[UPDATED] {savedMedia.get('title').get('romaji')} {savedMedia.get('type')} {savedMedia.get('format')}")
                logging.info(json.dumps(resp))

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

        elif choice == 2:
            if not DELETED_JSON.exists():
                DELETED_JSON.touch()
            deleteCompleteMediaList(list_type, status)

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

        input("\nLogged lists to ./lists\nEnter to continue..")

if __name__ == '__main__':
    main()
