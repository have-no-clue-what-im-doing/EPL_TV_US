import requests
import json
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import paramiko
import subprocess

#Make a request to API to get Newcastle United schedule and return list.
def GetFixtures():
    url = "https://api.football-data.org/v4/teams/67/matches"
    token = "53e06e2ba29e4f9aac750911b6d870d7"
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
    utcTime = datetime.utcfromtimestamp(unixInSeconds).replace(tzinfo=timezone.utc)
    utcTimeFormatted = utcTime.strftime('%Y-%m-%dT%H:%M:%SZ')
    return utcTimeFormatted

#Make API request to see if there is a match on this current day. If there is, confirm it is a Premier League game. (Ignore other games like Champions League) If there is a game today, then return a dict of just the data for that game.
def IsItMatchDay():
    matches = GetFixtures()
    for match in matches:
        if match["competition"]["name"] == "Premier League":
            currentDate = GetCurrentDate()
            matchDate = match["utcDate"]
            if currentDate in matchDate:
                return matchDate
    return "No matches today"

#Make a search using the term "Newcastle v" to list recent upcoming games. Return list of Newcastle games.
# I copied this request using Chrome dev tools. This is something that has a high chance of breaking in the future if Peacock changes anything.
def PeacockRequest():
   headers = {
    'authority': 'web.clients.peacocktv.com',
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'no-cache',
    'origin': 'https://www.peacocktv.com',
    'pragma': 'no-cache',
    'referer': 'https://www.peacocktv.com/',
    'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'x-skyott-ab-recs': 'SearchExtensionV2:control;fylength:variation2',
    'x-skyott-activeterritory': 'US',
    'x-skyott-bouquetid': '5566233252361580117',
    'x-skyott-client-version': '4.11.23',
    'x-skyott-device': 'COMPUTER',
    'x-skyott-language': 'en',
    'x-skyott-platform': 'PC',
    'x-skyott-proposition': 'NBCUOTT',
    'x-skyott-provider': 'NBCU',
    'x-skyott-subbouquetid': '0',
    'x-skyott-territory': 'US',
    }
   params = {
    'term': 'newcastle v',
    'limit': '40',
    'entityType': 'programme,series',
    'contentFormat': 'longform',
    }
   response = requests.get('https://web.clients.peacocktv.com/bff/search/v2', params=params, headers=headers)
   data = json.loads(response.text)
   return data
    
#Iterate through list to see if the matchDate from IsItMatchDay matches with a game on Peacock. (Peacock sets start time 10 minutes before match start)
#Add 10 minutes to time to compare
#Return the specific link to that game if there is a match
def SearchPeacock(gameTime):
    data = PeacockRequest()
    matches = data["data"]["search"]["results"]
    tenMinutesUnix = (10 * 60 * 1000)
    for match in matches:
        startTime = match["displayStartTime"]
        time = ConvertUnixTimeToUTC(startTime + tenMinutesUnix)
        if gameTime == time:
            gameLink = match["slug"]
            return "https://peacocktv.com" + gameLink
    return "Error: No matches found"

#First check to see if game is on Peacock, if not, web scrape TVInsider to see if game is on NBC or USA.
def GetStreamingLink():
    confirmMatch = IsItMatchDay()
    if confirmMatch == "No matches today":
        return "No matches today"
    else:
        confirmPeacock = SearchPeacock(confirmMatch)
        if confirmPeacock == "Error: No matches found":
            return SearchYoutubeTV()
        else:
            return confirmPeacock

#Scrape webpage and return list of EPL games scheduled for the week.
def GetTVProviderData():
    url = "https://www.tvinsider.com/show/premier-league-soccer/"
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Accept-Language': 'en-US,en;q=0.5',
    }
    r = requests.get(url, headers=headers)
    s = BeautifulSoup(r.content, "html5lib")
    gamesList = s.find("div", class_="games")
    games = gamesList.find_all("div", class_="game")
    return games


#Find Newcastle's game and determine whether game is on NBC or USA. 
def FindTVProvider():
    games = GetTVProviderData()
    for game in games:
        if "Newcastle" in game.find("h4").text:
            if "USA Network" in game.find("h5").text:
                return "USA"
            else:
                return "NBC"
    return "Error, unable to find a Newcastle game for this week"

#If USA, return youtube.tv USA link, and if NBC, return youtube.tv NBC link
def SearchYoutubeTV():
    tvNetwork = FindTVProvider()
    if tvNetwork == "USA":
        return "https://tv.youtube.com/watch/M2YyNsA47Lw?utm_servlet=prod&rd_rsn=asi&zipcode=45103&onboard=1&vp=0gEEEgIwAQ%3D%3D"
    if tvNetwork == "NBC":
        return "https://tv.youtube.com/watch/by5X_xkztY8?utm_servlet=prod&rd_rsn=asi&zipcode=45103&onboard=1&vp=0gEEEgIwAQ%3D%3D"
    else:
        return "Error, unable to find YoutubeTV provider"

#Calculate time 15 minutes before start of match
def GetComputerStartTime():
    matchTime = IsItMatchDay()
    matchObj = datetime.strptime(matchTime, "%Y-%m-%dT%H:%M:%SZ")
    newMatchObj = matchObj - timedelta(minutes=15)
    matchTimeStr = newMatchObj.strftime("%Y-%m-%dT%H:%M:%SZ")
    return matchTimeStr

#Return difference between match start time and computer start time in seconds to use for time.sleep(). We want to wait until 15 minutes before game to turn on computer
def GetSleepTime():
    startTime = GetComputerStartTime()
    convertStartTime = datetime.strptime(startTime, "%Y-%m-%dT%H:%M:%SZ")
    currentTime = datetime.utcnow()
    timeDiff = convertStartTime - currentTime
    timeDiffSecs = timeDiff.total_seconds()
    return timeDiffSecs

#Power on computer using wakeonlan. Note: must run "sudo apt-get install wakeonlan" first for this command to work. Also must enable WOL on host machine
def PowerOnComputer(mac):
    subprocess.run(f"wakeonlan {mac}", shell=True, capture_output=True, text=True)
    return "Computer Powered On"

#Connect to remote computer via ssh and send a restart command
def RestartComputer():
    hostname = '192.168.1.114'
    port = 22
    username = 'Broderic'
    password = 'newcastle123'
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)
    ssh.exec_command("shutdown /f /r /t 0")
    ssh.close()
    return "Computer has been restarted! Game is ready to watch!"

#Create a Chrome shortcut with the match link in the Windows Startup Folder using Powershell. 
def CreateChromeShortcut(link):
    hostname = '192.168.1.114'
    port = 22
    username = 'broderic'
    password = 'newcastle123'
    powershellCommands = f'''
    $chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
    $targetURL = "{link}";
    $shortcutPath = "C:\\Users\\Broderic\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\Newcastle.lnk";
    $wshShell = New-Object -ComObject WScript.Shell;
    $shortcut = $wshShell.CreateShortcut($shortcutPath);
    $shortcut.TargetPath = $chromePath;
    $shortcut.Arguments = "$targetURL --start-fullscreen";
    $shortcut.Description = "Google Chrome - Fullscreen";
    $shortcut.IconLocation = "$chromePath,0";
    $shortcut.WorkingDirectory = "C:\\Program Files\\Google\\Chrome\\Application";
    $shortcut.Save();
    '''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)
    ssh.exec_command(powershellCommands)
    ssh.close()
    print(f"Created Chrome Shortcut to this url: {link}")
    return "Created Chrome Shortcut"

#Determine if there is a match today, and if there is, find the link for the proper network and run it on the remote computer
def WatchNewcastleMatch():
    getMatchLink = GetStreamingLink()
    if getMatchLink == "No matches today":
        return "No matches today"
    else: 
        waitForMatch = GetSleepTime()
        time.sleep(waitForMatch)
        matchLink = GetStreamingLink()
        PowerOnComputer("d8:bb:c1:0d:25:bb")
        time.sleep(45)
        CreateChromeShortcut(matchLink)
        time.sleep(15)
        RestartComputer()
        return "All commands sent successfully, game is ready to watch!"

if __name__ == "__main__":
    print(WatchNewcastleMatch())




