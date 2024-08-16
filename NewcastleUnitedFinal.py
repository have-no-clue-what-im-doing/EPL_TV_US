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


#Make a request to API to get Newcastle United schedule and return list.
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

#Make a search using the term "Newcastle v" to list recent upcoming games. Return list of Newcastle games.
#I copied this request using Chrome dev tools. This is something that has a high chance of breaking in the future if Peacock changes anything.
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
    'user-agent': os.getenv("USER_AGENT"),
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
    'term': os.getenv("SEARCH_TERM"),
    'limit': '40',
    'entityType': 'programme,series',
    'contentFormat': 'longform',
    }
   response = requests.get('https://web.clients.peacocktv.com/bff/search/v2', params=params, headers=headers)
   data = json.loads(response.text)
   print(data)
   print(os.getenv("SEARCH_TERM"))
   return data
    
#Iterate through list to see if the matchDate from IsItMatchDay() matches with a game on Peacock. (Peacock sets start time 10 minutes before match start) 
# THIS COULD CHANGE IN THE FUTURE. BE SURE TO UPDATE PEACOCK_START_TIME in the .env
#Add 10 minutes to time to compare
#Return the specific link to that game if there is a match
def SearchPeacock(gameTime):
    data = PeacockRequest()
    peacockTime = int(os.getenv("PEACOCK_START_TIME"))
    matches = data["data"]["search"]["results"]
    tenMinutesUnix = (peacockTime * 60 * 1000)
    for match in matches:
        findMatchTime = []
        for key in match:
            print(key)
            findMatchTime.append(key)
        if "displayStartTime" not in findMatchTime:
            pass
        else:
            print(match)
            startTime = match["displayStartTime"]
            print(startTime)
            time = ConvertUnixTimeToUTC(startTime + tenMinutesUnix)
        
        print(f'this is the time we have: {gameTime}')
        print(f'peackcod time: {time}')
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
        confirmPeacock = print(SearchPeacock(confirmMatch))
        if confirmPeacock == "Error: No matches found":
            return SearchYoutubeTV()
        else:
            return confirmPeacock

#Scrape webpage and return list of EPL games scheduled for the week.
def GetTVProviderData():
    url = "https://www.tvinsider.com/show/premier-league-soccer/"
    headers = {
    'User-Agent': os.getenv("USER_AGENT"),
    'Accept-Language': 'en-US,en;q=0.5',
    }
    r = requests.get(url, headers=headers)
    s = BeautifulSoup(r.content, "html5lib")
    gamesList = s.find("div", class_="games")
    games = gamesList.find_all("div", class_="game")
    return games


#Find Newcastle's game and determine whether game is on NBC or USA. 
def FindTVProvider():
    teamName = os.getenv("TV_INSIDER_TEAM_NAME")
    games = GetTVProviderData()
    for game in games:
        if teamName in game.find("h4").text:
            if "USA Network" in game.find("h5").text:
                return "USA"
            else:
                return "NBC"
    return f"Error, unable to find a {teamName} game for this week"

#If USA, return youtube.tv USA link, and if NBC, return youtube.tv NBC link
def SearchYoutubeTV():
    tvNetwork = FindTVProvider()
    if tvNetwork == "USA":
        return os.getenv("YOUTUBE_TV_USA_URL")
    if tvNetwork == "NBC":
        return os.getenv("YOUTUBE_TV_NBC_URL")
    else:
        return "Error, unable to find YoutubeTV provider"

#Calculate time 15 minutes before start of match     
def GetComputerStartTime():
    matchTime = IsItMatchDay()
    matchObj = datetime.strptime(matchTime, "%Y-%m-%dT%H:%M:%SZ")
    newMatchObj = matchObj - timedelta(minutes=15)
    matchTimeStr = newMatchObj.strftime("%Y-%m-%dT%H:%M:%SZ")
    return matchTimeStr

#Return difference between match start time and computer start time in seconds to use for time.sleep(). 
#We want to wait until 15 minutes before game to turn on computer
def GetSleepTime():
    startTime = GetComputerStartTime()
    convertStartTime = datetime.fromisoformat(startTime)
    print(convertStartTime)
    currentTime = datetime.now(tz=timezone.utc)
    print(currentTime)
    timeDiff = convertStartTime - currentTime
    timeDiffSecs = timeDiff.total_seconds()
    print(timeDiffSecs)
    return timeDiffSecs


#Power on computer using wakeonlan. Note: must run "sudo apt-get install wakeonlan" first for this command to work. Also must enable WOL on host machine
def PowerOnComputerDebian(mac):
    subprocess.run(f"wakeonlan {mac}", shell=True, capture_output=True, text=True)
    return "Computer Powered On"

#Credit: https://stackoverflow.com/questions/72853502/how-to-send-a-wake-on-lan-magic-packet-using-powershell
def PowerOnComputer(mac):
    wakeOnLanCommand = f''' 
    $mac = '{mac}';
    [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | Where-Object {{ $_.NetworkInterfaceType -ne [System.Net.NetworkInformation.NetworkInterfaceType]::Loopback -and $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up }} | ForEach-Object {{
    $networkInterface = $_
    $localIpAddress = ($networkInterface.GetIPProperties().UnicastAddresses | Where-Object {{ $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork }})[0].Address
    $targetPhysicalAddress = [System.Net.NetworkInformation.PhysicalAddress]::Parse(($mac.ToUpper() -replace '[^0-9A-F]',''))
    $targetPhysicalAddressBytes = $targetPhysicalAddress.GetAddressBytes()
    $packet = [byte[]](,0xFF * 102)
    6..101 | Foreach-Object {{ $packet[$_] = $targetPhysicalAddressBytes[($_ % 6)] }}
    $localEndpoint = [System.Net.IPEndPoint]::new($localIpAddress, 0)
    $targetEndpoint = [System.Net.IPEndPoint]::new([System.Net.IPAddress]::Broadcast, 9)
    $client = [System.Net.Sockets.UdpClient]::new($localEndpoint)
    try {{ $client.Send($packet, $packet.Length, $targetEndpoint) | Out-Null }} finally {{ $client.Dispose() }}
    }}
    '''
    subprocess.run(['powershell', '-Command', wakeOnLanCommand], capture_output=True, text=True)
    return "Computer Powered On"


def DeterminePowerMethod(machineType):
    if machineType == "Windows":
        PowerOnComputer(os.getenv("CLIENT_MAC_ADDRESS"))
    elif machineType == "Linux":
        PowerOnComputerDebian(os.getenv("CLIENT_MAC_ADDRESS"))
    else:
        return "Error, machine type not defined"


#Connect to remote computer via ssh and send a restart command
def RestartComputer():
    hostname = os.getenv("CLIENT_IP_ADDRESS")
    port = 22
    username = os.getenv("CLIENT_USERNAME")
    password = 'os.getenv("CLIENT_PASSWORD")'
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

#Determine if there is a match today, and if there is, find the link for the proper network and run it on the remote computer.
def WatchNewcastleMatch():
    getMatchLink = GetStreamingLink()
    if getMatchLink == "No matches today":
        return "No matches today"
    else: 
        print("it working???")
        waitForMatch = GetSleepTime()
        time.sleep(waitForMatch)
        matchLink = GetStreamingLink()
        DeterminePowerMethod(os.getenv("CLIENT_MACHINE_TYPE"))
        time.sleep(120)
        CreateChromeShortcut(matchLink)
        time.sleep(15)
        RestartComputer()
        return "All commands sent successfully, game is ready to watch!"

if __name__ == "__main__":
    print(WatchNewcastleMatch())
    
    

