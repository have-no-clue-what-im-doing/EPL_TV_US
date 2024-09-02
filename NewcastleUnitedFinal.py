import logging
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

script_dir = os.path.dirname(os.path.abspath(__file__))
log_file_path = os.path.join(script_dir, "EPL.log")
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')



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

#Get status of the match. Determine if match is in play, paused, or finished
def GetMatchStatus():
    matches = GetFixtures()
    for match in matches:
        if match["competition"]["name"] == "Premier League":
            currentDate = GetCurrentDate()
            matchDate = match["utcDate"]
            if currentDate in matchDate:
                return match["status"]
    return "No matches today, unable to get status"

#Make a search using the term "Newcastle v" to list recent upcoming games. Return list of Newcastle games.
#I copied this request using Chrome dev tools. This is something that has a high chance of breaking in the future if Peacock changes anything.
def PeacockRequest():
   logging.info(f"Sending API request to Peacock...")
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
   return data
    
#Iterate through list to see if the matchDate from IsItMatchDay() matches with a game on Peacock. (Peacock sets start time 10 minutes before match start) 
# THIS COULD CHANGE IN THE FUTURE. BE SURE TO UPDATE PEACOCK_START_TIME in the .env
#Add 10 minutes to time to compare
#Return the specific link to that game if there is a match
def SearchPeacock(gameTime):
    logging.info(f"Iterating through list of games from Peacock API request")
    data = PeacockRequest()
    peacockTime = int(os.getenv("PEACOCK_START_TIME"))
    matches = data["data"]["search"]["results"]
    tenMinutesUnix = (peacockTime * 60 * 1000)
    for match in matches:
        findMatchTime = []
        for key in match:
            findMatchTime.append(key)
        if "displayStartTime" not in findMatchTime:
            pass
        else:
            startTime = match["displayStartTime"]
            time = ConvertUnixTimeToUTC(startTime + tenMinutesUnix)
        if gameTime == time:
            gameLink = match["slug"]
            return "https://peacocktv.com" + gameLink
    logging.error(f"Unable to find match on Peacock")
    return "Error: No matches found"

#First check to see if game is on Peacock, if not, web scrape TVInsider to see if game is on NBC or USA.
def GetStreamingLink():
    confirmMatch = IsItMatchDay()
    if confirmMatch == "No matches today":
        return "No matches today"
    else:
        confirmPeacock = SearchPeacock(confirmMatch)
        if confirmPeacock == "Error: No matches found":
            logging.info("No matches found on Peacock, searching YoutubeTV...")
            return SearchYoutubeTV()
        else:
            logging.info("Match found on Peacock!")
            return confirmPeacock

#Scrape webpage and return list of EPL games scheduled for the week.
def GetTVProviderData():
    logging.info("Web scraping tvinsider for game...")
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
                logging.info("Game found on USA network!")
                return "USA"
            else:
                logging.info("Game found on NBC network!")
                return "NBC"
    logging.error(f"Error, unable to find a {teamName} game for this week")
    return f"Error, unable to find a {teamName} game for this week"

#If USA, return youtube.tv USA link, and if NBC, return youtube.tv NBC link
def SearchYoutubeTV():
    tvNetwork = FindTVProvider()
    if tvNetwork == "USA":
        return os.getenv("YOUTUBE_TV_USA_URL")
    if tvNetwork == "NBC":
        return os.getenv("YOUTUBE_TV_NBC_URL")
    else:
        logging.error(f"Error, unable to find YoutubeTV provider")
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
    currentTime = datetime.now(tz=timezone.utc)
    timeDiff = convertStartTime - currentTime
    timeDiffSecs = timeDiff.total_seconds()
    return timeDiffSecs


#Power on computer using wakeonlan. Note: must run "sudo apt-get install wakeonlan" first for this command to work. Also must enable WOL on host machine
def PowerOnComputerDebian(mac):
    logging.info(f"Powering on computer from Linux machine")
    subprocess.run(f"wakeonlan {mac}", shell=True, capture_output=True, text=True)
    return "Computer Powered On"

#Credit: https://stackoverflow.com/questions/72853502/how-to-send-a-wake-on-lan-magic-packet-using-powershell
def PowerOnComputer(mac):
    logging.info(f"Powering on computer from Windows machine")
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
        logging.error(f"Error, machine type not defined!")
        return "Error, machine type not defined"


#Connect to remote computer via ssh and send a restart command
def RestartComputer():
    logging.info(f"Restarting computer...")
    hostname = os.getenv("CLIENT_IP_ADDRESS")
    port = 22
    username = os.getenv("CLIENT_USERNAME")
    password = os.getenv("CLIENT_PASSWORD")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)
    ssh.exec_command("shutdown /f /r /t 0")
    ssh.close()
    return "Computer has been restarted! Game is ready to watch!"

def ShutdownComputer():
    logging.info(f"Shutting down computer...")
    hostname = os.getenv("CLIENT_IP_ADDRESS")
    port = 22
    username = os.getenv("CLIENT_USERNAME")
    password = os.getenv("CLIENT_PASSWORD")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)
    ssh.exec_command("shutdown /f /s /t 0")
    ssh.close()
    return "Computer has been shutdown"

#Create a Chrome shortcut with the match link in the Windows Startup Folder using Powershell. 
def CreateChromeShortcut(link):
    hostname = os.getenv("CLIENT_IP_ADDRESS")
    port = 22
    username = os.getenv("CLIENT_USERNAME")
    password = os.getenv("CLIENT_PASSWORD")
    powershellScript = f'''
    $chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    $targetURL = "{link}"
    $shortcutPath = "C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\Newcastle.lnk"
    $wshShell = New-Object -ComObject WScript.Shell
    $shortcut = $wshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $chromePath
    $shortcut.Arguments = "$targetURL --start-fullscreen --autoplay-policy=no-user-gesture-required"
    $shortcut.Description = "Google Chrome - Fullscreen"
    $shortcut.IconLocation = "$chromePath,0"
    $shortcut.WorkingDirectory = "C:\\Program Files\\Google\\Chrome\\Application"
    $shortcut.Save()
    '''

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)
    temp_script_path = f"C:\\Users\\{username}\\AppData\\Local\\Temp\\create_shortcut.ps1"
    sftp = ssh.open_sftp()
    with sftp.file(temp_script_path, 'w') as script_file:
        script_file.write(powershellScript)
    sftp.close()
    ssh.exec_command(f'powershell -ExecutionPolicy Bypass -File "{temp_script_path}"')
    ssh.exec_command(f'del "{temp_script_path}"')
    ssh.close()
    logging.info(f"Created Chrome Shortcut to this URL: {link}")
    return "Created Chrome Shortcut"

def CheckForFinishedMatch(interval):
    if GetMatchStatus() == "FINISHED":
        logging.info("Match is complete, shutting down...")
        ShutdownComputer()
    else:
        time.sleep(interval)
        CheckForFinishedMatch(interval)
        

#Determine if there is a match today, and if there is, find the link for the proper network and run it on the remote computer.
def WatchNewcastleMatch():
    logging.info(f"Getting match link.")
    getMatchLink = GetStreamingLink()
    if getMatchLink == "No matches today":
        logging.info(f"There are no matches today.")
        return "No matches today"
    else: 
        logging.info(f"Calculating when match will start / if already started")
        waitForMatch = GetSleepTime()
        if waitForMatch > 0:
            logging.info(f"Match will start in {waitForMatch} seconds")
            time.sleep(waitForMatch)
        if waitForMatch <= 0 and GetMatchStatus() == "FINISHED":
            logging.info(f"Match has already been played out. No match to watch")
            return "Match has already been played out. No match to watch"
        else:
            logging.info(f"Beginning machine start up")
            logging.info(f"Determining client OS")
            DeterminePowerMethod(os.getenv("CLIENT_MACHINE_TYPE"))
            logging.info(f"Waiting 2 minutes while computer boots")
            time.sleep(120)
            logging.info(f"Creating Chrome shortcut")
            CreateChromeShortcut(getMatchLink)
            logging.info(f"Waiting 15 seconds before restarting...")
            time.sleep(15)
            logging.info(f"Restarting computer...")
            RestartComputer()
            logging.info(f"All commands sent successfully, game is ready to watch!")
            shutdown = os.getenv("SHUT_DOWN_MACHINE")
            if shutdown == "True":
                logging.info(f"Shutting down machine after match has been enabled. Checking every 10 minutes...")
                CheckForFinishedMatch(600)

if __name__ == "__main__":
    WatchNewcastleMatch()
    
    
    

