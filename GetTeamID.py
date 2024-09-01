import requests
import os
from dotenv import load_dotenv

def GetTeamIDs():
    load_dotenv()
    url = "http://api.football-data.org/v4/competitions/PL/teams" 
    token = os.getenv("FOOTBALL_TEAM_API_ENDPOINT_TOKEN")
    headers = {
    'X-Auth-Token': token,
    'Content-Type': 'application/json',
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    teams = data["teams"]
    team_info = ""
    for team in teams:
        line = f"{team['name']}: {team['id']}"
        if team_info:  
                team_info += "\n" + line  
        else:
            team_info = line
    return team_info

teamIDs = GetTeamIDs()
print(teamIDs)

