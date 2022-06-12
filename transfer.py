import os
import json
import time
import requests
from pathlib import Path
from urllib.parse import urlparse

API = "https://graphql.anilist.co"
FORMAT = "UTF-8"
ROOT = Path.cwd()
CREDS = ROOT / "creds.json"
LISTS = ROOT / "lists"

if not LISTS.exists():
    LISTS.mkdir()


def userAuth(client_id):
    auth_url = f"https://anilist.co/api/v2/oauth/authorize?client_id={client_id}&response_type=token"
    print(f"Open this link in the browser, login to anilist and paste the url after being redirected:\n{auth_url}")
    url = input("Enter the url here: ")
    fragments_split = (urlparse(url)).fragment.split("&")
    access_token = fragments_split[0].split("=")[1]
    return access_token


def initialSetup():
    print("-----Performing initial setup-----")
    CLIENT_ID = input("Enter the api client ID: ")
    CLIENT_SECRET = input("Enter the api client secret: ")
    CLIENT_NAME = input("Enter the api client name: ")

    print("\n-----Authenticate first account-----")
    ACCESS_TOKEN_1 = userAuth(CLIENT_ID)

    print("\n-----Authenticate second account-----")
    ACCESS_TOKEN_2 = userAuth(CLIENT_ID)

    with open("creds.json", "w", encoding=FORMAT) as f:
        json.dump({
            "CLIENT_ID": CLIENT_ID,
            "CLIENT_SECRET": CLIENT_SECRET,
            "CLIENT_NAME": CLIENT_NAME,
            "ACCESS_TOKEN_1": ACCESS_TOKEN_1,
            "ACCESS_TOKEN_2": ACCESS_TOKEN_2
        }, f, indent=4)


def sleepProgress(sleep_time):
    while sleep_time >= 0:
        time.sleep(1)
        print('Waiting... {:2d}'.format(sleep_time), end='\r')
        sleep_time -= 1


def setHeader(access_token):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    return headers


def getUserDetails(headers, ret=True):
    query = '''
        query {
            Viewer {
                id
                name
                mediaListOptions {
                    scoreFormat
                }
            }
        }
    '''
    variables = {}

    res = requests.post(API, json={"query": query, "variables": variables}, headers=headers)
    data = res.json()
    print(f"\nLogged in as {data['data']['Viewer']['name']}")
    if ret:
        return (data["data"]["Viewer"]["id"], data["data"]["Viewer"]["mediaListOptions"]["scoreFormat"])
    return


def downloadUserMediaList(list_type, status, access_token):
    
    headers = setHeader(access_token)
    mediaList = []
    query = '''
        query ($userId: Int, $page: Int, $perPage: Int, $type: MediaType, $status: MediaListStatus, $scoreFormat: ScoreFormat) {
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
                    score (format: $scoreFormat)
                    progress
                    progressVolumes
                    repeat
                    private
                    notes
                    startedAt {
                        year month day
                    }
                    completedAt {
                        year month day
                    }
                    media {
                        id
                        title {
                            romaji english
                        }
                        siteUrl
                    }
                }
            }
        }
    '''

    userId, scoreFormat = getUserDetails(headers)
    variables = {
        "userId": userId,
        "page": 1,
        "perPage": 50,
        "type": list_type,
        "status": status,
        "scoreFormat": scoreFormat
    }

    # While the next page in the response is present, keep requesting for new pages
    while True:
        res = requests.post(API, json={"query": query, "variables": variables}, headers=headers)
        rem = res.headers["X-RateLimit-Remaining"]
        data = res.json()
        print("\nRemaining Requests: ", rem)

        print("Page No: ", variables["page"])

        mediaList += data["data"]["Page"]["mediaList"]
        variables["page"] += 1

        hasNextPage = data["data"]["Page"]["pageInfo"]["hasNextPage"]
        if not hasNextPage:
            break

        if rem == '0':
            print("\nHit rate limit, waiting 30s...")
            sleepProgress(30)
    
    with open(f"./lists/{list_type.lower()}_{status.lower()}.json", "w", encoding=FORMAT) as f:
        print("Total: ", len(mediaList))
        json.dump({
            "total": len(mediaList),
            "mediaList": mediaList
        }, f, indent=4, ensure_ascii=False)


def saveUserMediaList(list_type, access_token, entry, headers):
    
    query = '''
        mutation ($mediaId: Int, $status: MediaListStatus, $score: Float, $progress: Int, $progressVolumes: Int,
        $repeat: Int, $private: Boolean, $notes: String, $startedAt: FuzzyDateInput, $completedAt: FuzzyDateInput) {
            SaveMediaListEntry (mediaId: $mediaId, status: $status, score: $score, progress: $progress,
            progressVolumes: $progressVolumes, repeat: $repeat, private: $private, notes: $notes, startedAt: $startedAt, completedAt: $completedAt) {
                id
                createdAt
                media {
                    title {
                        romaji english
                    }
                }
            }
        }
    '''

    variables = {
        "mediaId": entry['mediaId'],
        "status": entry['status'],
        "score": entry['score'],
        "progress": entry['progress'],
        "progressVolumes": entry['progressVolumes'] or 0,
        "repeat": entry['repeat'],
        "private": entry['private'],
        "notes": entry['notes'],
        "startedAt": entry['startedAt'],
        "completedAt": entry['completedAt']
    }

    res = requests.post(API, json={"query": query, "variables": variables}, headers=headers)
    return (res.headers["X-RateLimit-Remaining"], res.json())


def updateSecondAccount(list_type, status, access_token):
    with open(f"./lists/{list_type.lower()}_{status.lower()}.json", encoding=FORMAT) as f:
        data = json.load(f)
    
    total = data['total']
    print("\nEntries to be updated/created: ", total)

    headers = setHeader(access_token)
    getUserDetails(headers, False)
    sleepProgress(3)

    for i, entry in enumerate(data['mediaList'], start=1):
        rem, res = saveUserMediaList(list_type, access_token, entry, headers)
        print("\nRemaining Requests: ", rem)

        if i == total:
            break

        print("\n-----Entry Updated-----")
        print(f'''
        Entry: {i}
        Id: {res['data']['SaveMediaListEntry']['id']}
        Created At: {res['data']['SaveMediaListEntry']['createdAt']}
        Romaji Title: {res['data']['SaveMediaListEntry']['media']['title']['romaji'] or 'None'}
        English Title: {res['data']['SaveMediaListEntry']['media']['title']['english'] or 'None'}
        ''')

        if rem == 0:
            print("\nHit rate limit, waiting 30s...")
            sleepProgress(30)


def main():
    if not CREDS.exists():
        initialSetup()
    
    with open("creds.json", encoding=FORMAT) as f:
        creds = json.load(f)
    
    ACCESS_TOKEN_1 = creds["ACCESS_TOKEN_1"]
    ACCESS_TOKEN_2 = creds["ACCESS_TOKEN_2"]

    list_type, status = (input("\nEnter list type and status to transfer [ex: 'anime planning' or 'manga current']: ")).upper().split()

    print("\n-----Fetching medialist-----")
    downloadUserMediaList(list_type, status, ACCESS_TOKEN_1)
    print("\nFetched")
    sleepProgress(3)

    print("\n-----Updating second account-----")
    updateSecondAccount(list_type, status, ACCESS_TOKEN_2)
    print("\nUpdated")


if __name__ == "__main__":
    main()
