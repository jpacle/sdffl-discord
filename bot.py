import discord
from discord.ext import commands
import requests
from dotenv import load_dotenv
import os
import json
#import sys

load_dotenv() 

# Bot setup
intents = discord.Intents.default()
intents.messages = True  # Enables processing of message events
intents.message_content = True  # Allows the bot to read the content of messages
bot = commands.Bot(command_prefix="!", intents=intents)

# ESPN API details
LEAGUE_ID = "409380"
SEASON_ID = "2024"  # Update for the current season
ESPN_S2 = os.environ.get("ESPN_S2")
SWID = os.environ.get("SWID")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

def get_team_name_map(league_id):
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2024/segments/0/leagues/{LEAGUE_ID}?view=mTeam&view=mSettings"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    cookies = {
        "espn_s2": ESPN_S2,
        "SWID": SWID
    }
    response = requests.get(url, headers=headers, cookies=cookies)
    response.raise_for_status()
    data = response.json()

    team_name_map = {}
    for team in data["teams"]:
        # Construct the team name:
        # If you have location and nickname fields:
        # full_name = f"{team['location']} {team['nickname']}"
        
        # If there's only 'abbrev' or a direct 'teamName' field, use that instead.
        full_name = team.get("location", "") + " " + team.get("nickname", "")
        if not full_name.strip():
            # fallback if no location/nickname combo found
            full_name = team.get("name", f"Team {team['id']}")
        
        team_name_map[team["id"]] = full_name.strip()

    return team_name_map

def get_team_points(team_id):
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2024/segments/0/leagues/{LEAGUE_ID}?view=mTeam&view=mStandings&view=mMatchupScore0"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    cookies = {
        "espn_s2": ESPN_S2,
        "SWID": SWID
    }
    response = requests.get(url, headers=headers, cookies=cookies)
    response.raise_for_status()
    league_data = response.json()
    
    for team in league_data["teams"]:
        if team["id"] == team_id:
            # Extract pointsFor from the record
            return team["record"]["overall"]["pointsFor"]
    
    return "Team not found."

def get_team_current_week_score(team_id):
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2024/segments/0/leagues/{LEAGUE_ID}?view=mMatchupScore&view=mLiveScoring"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    cookies = {
        "espn_s2": ESPN_S2,
        "SWID": SWID
    }
    response = requests.get(url, headers=headers, cookies=cookies)
    response.raise_for_status()
    league_data = response.json()

    # Get the current week from league_data
    current_week = league_data["status"]["currentMatchupPeriod"]

    # Iterate through the schedule to find the current week's match for this team
    for game in league_data.get("schedule", []):
        if game.get("matchupPeriodId") == current_week:
            # Check home team
            if "home" in game and game["home"].get("teamId") == team_id:
                return game["home"]["totalPointsLive"]
            # Check away team
            if "away" in game and game["away"].get("teamId") == team_id:
                return game["away"]["totalPointsLive"]

    # If the team did not play or no data found, return 0.0
    return 0.0

def get_team_week_score(team_id, week):
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2024/segments/0/leagues/{LEAGUE_ID}?view=mMatchupScore0"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, cookies={"espn_s2": ESPN_S2, "SWID": SWID})
    response.raise_for_status()
    league_data = response.json()

    current_week = league_data["status"]["currentMatchupPeriod"]

    for game in league_data.get("schedule", []):
        if game.get("matchupPeriodId") == week:
            home_team = game.get("home", {})
            away_team = game.get("away", {})

            # Function to extract points considering week vs. current week
            def get_points(data):
                if week < current_week:
                    # Past week, final scores should be in totalPoints
                    return data.get("totalPoints", 0.0)
                elif week == current_week:
                    # Current week: try live points, else final
                    return data.get("totalPointsLive", data.get("totalPoints", 0.0))
                else:
                    # Future week: no actual score, check if projections exist
                    return data.get("totalProjectedPoints", 0.0)

            if home_team.get("teamId") == team_id:
                return get_points(home_team)
            if away_team.get("teamId") == team_id:
                return get_points(away_team)

    return 0.0

@bot.command(name="last", help="Show the teams fighting for last")
async def last(ctx):
    # Define the team IDs you want to fetch
    team_ids = [3, 6, 7, 8, 12]  # Adjust as needed

    # Get team names mapping
    team_names = get_team_name_map(LEAGUE_ID)

    # Collect (team_name, points) for each team, adding the current week score
    team_points_list = []
    for tid in team_ids:
        # Get total season points
        points = get_team_points(tid)
        # Get current week's score and add it to total
        current_week_score = get_team_current_week_score(tid)
        total_with_current = points + current_week_score

        team_name = team_names.get(tid, f"Team {tid}")
        team_points_list.append((team_name, total_with_current))

    # Sort by points descending
    team_points_list.sort(key=lambda x: x[1], reverse=True)

    # Format the response with two decimal places
    response_lines = [f"{t[0]}: {t[1]:.2f}" for t in team_points_list]
    response_message = "Points For Selected Teams (Highest to Lowest):\n" + "\n".join(response_lines)

    await ctx.send(response_message)

previous_champions = {
    2007: "Hashi Pacle",
    2008: "Shawn Sta.Ines",
    2009: "Jay Magpantay",
    2010: "John Pacle",
    2011: "Rommel Tan",
    2012: "Joel Carino",
    2013: "Hashi Pacle",
    2014: "John Pacle",
    2015: "Mark Talob",
    2016: "Rommel Tan",
    2017: "Cartier Carter",
    2018: "Ronald Alonzo",
    2019: "Shawn Sta.Ines",
    2020: "Cartier Carter",
    2021: "Shawn Sta.Ines",
    2022: "Mark Talob",
    2023: "Hashi Pacle"
}

@bot.command(name="champs", help="Displays all previous champions of the league.")
async def champions_command(ctx):
    if not previous_champions:
        await ctx.send("No previous champions data available.")
        return

    # Format the champions list
    response_lines = ["**Previous League Champions:**"]
    # Sort by year so it’s neat and consistent
    for season in sorted(previous_champions.keys()):
        champion = previous_champions[season]
        response_lines.append(f"**{season}**: {champion}")

    response_message = "\n".join(response_lines)
    await ctx.send(response_message)

@bot.command(name="GG", help="Replies with a greeting.")
async def hello_command(ctx):
    await ctx.send("Channeling the fantasy football gods and increasing your odds of winning!")

bot.run(BOT_TOKEN)

