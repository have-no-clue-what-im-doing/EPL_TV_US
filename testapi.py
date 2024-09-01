import requests
import json
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import paramiko
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()


def GetFixtures():
    footballID = os.getenv("FOOTBALL_TEAM_ID")
    url = f"https://api.football-data.org/v4/teams/{footballID}/matches" #"http://api.football-data.org/v4/competitions/PL/teams" 
    token = os.getenv("FOOTBALL_TEAM_API_ENDPOINT_TOKEN")
    headers = {
    'X-Auth-Token': token,
    'Content-Type': 'application/json',
    }
    response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    matchData = data["matches"]
    return matchData

#Get current time in UTC and format it so it can be compared to the time format that is returned in the GetFixtures matchData.
def GetCurrentTimeUTC():
    currentTimeUTC = datetime.now(timezone.utc)
    formatTime = currentTimeUTC.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatTime

#Get just the year, month, and day.
def GetCurrentDate():
    currentTimeUTC = datetime.now(timezone.utc)
    formatDate = currentTimeUTC.strftime("%Y-%m-%d")
    return formatDate

#Convert the current time to UTC and format it.
def ConvertUnixTimeToUTC(time):
    unixInSeconds = time / 1000
    utcTime = datetime.fromtimestamp(unixInSeconds, tz=timezone.utc)
    
    utcTimeFormatted = utcTime.strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'UTC TIME: {utcTimeFormatted}')
    return utcTimeFormatted

#Make API request to see if there is a match on this current day. If there is, confirm it is a Premier League game. 
#(Ignore other games like Champions League) If there is a game today, then return a dict of just the data for that game.
def IsItMatchDay():
    matches = GetFixtures()
    for match in matches:
        if match["competition"]["name"] == "Premier League":
            currentDate = GetCurrentDate()
            matchDate = match["utcDate"]
            if currentDate in matchDate:
                return matchDate
    return "No matches today"

def GetMatchStatus():
    matches = GetFixtures()
    for match in matches:
        if match["competition"]["name"] == "Premier League":
            currentDate = GetCurrentDate()
            matchDate = match["utcDate"]
            if currentDate in matchDate:
                return match["status"], match
    return "No matches today, unable to get status"


def BetterMatch():
    #497433
    url = f"http://api.football-data.org/v4/matches/327117" #"http://api.football-data.org/v4/competitions/PL/teams" 
    token = os.getenv("FOOTBALL_TEAM_API_ENDPOINT_TOKEN")
    headers = {
    'X-Auth-Token': token,
    'Content-Type': 'application/json',
    }
    response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    matchData = data
    return matchData

#print(IsItMatchDay())

print(GetMatchStatus())

#print(BetterMatch())