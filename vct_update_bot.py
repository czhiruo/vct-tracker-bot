import os 
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
)
from apscheduler.schedulers.background import BackgroundScheduler
from database import cur, con
import dateutil.parser
import requests
from telegram.helpers import escape_markdown

load_dotenv()

TOKEN = os.getenv('TOKEN')

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger.info('Started')

scheduler = BackgroundScheduler()
scheduler.start()

all_teams = {
    'cn': ['edg', 'xlg', 'blg', 'wolves', 'te', 'ag', 'drg', 'nova', 'tyloo', 'fpx', 'jdg', 'tec'],
    'na': ['100t', 'sen', 'eg', 'nrg', 'furia', 'kru', 'g2', 'mibr', 'loud', '2g', 'lev', 'c9'],
    'pacific': ['dfm', 'ge', 't1', 'zeta', 'drx', 'prx', 'ts', 'talon', 'geng', 'boom', 'nongshim', 'rrq'],
    'emea': ['vitality', 'giantx', 'team liquid', 'bbl', 'kc', 'th', 'apeks', 'fut', 'koi', 'fnatic', 'nv', 'gm']
}


async def start(update: Update, context: CallbackContext) -> None:
    userID = update.effective_user.id
    cur.execute('SELECT teams FROM users WHERE id = ?', (userID,))
    team = cur.fetchone()

    if team:
        await update.message.reply_text(f"You're currently following {team[0]}!")
    else:
        # new user
        keyboard =[
            [InlineKeyboardButton("Yes", callback_data="start_pick_region")],
            [InlineKeyboardButton("No", callback_data="no")]
        ],
        await update.message.reply_text(
            "Welcome! Do you want to pick a team to follow?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_region(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "start_pick_region":
        keyboard =[
        [InlineKeyboardButton("EMEA", callback_data="region_emea")],
        [InlineKeyboardButton("Pacific", callback_data="region_pacific")],
        [InlineKeyboardButton("NA", callback_data="region_na")],
        [InlineKeyboardButton("CN", callback_data="region_cn")]
        ],
        await query.edit_message_text(
            "Choose a region",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_team(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("region_"):
        region = query.data.split("_")[1]
        region_teams = all_teams.get(region, [])

        keyboard = [[InlineKeyboardButton(team.upper(), callback_data=f"team_{team}")]
                    for team in region_teams
        ]
        
        await query.edit_message_text(
            f"Choose a team from {region} region:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def save_team(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data.startswith("team_"):
        team = query.data.split("_")[1]
    
    cur.execute('INSERT OR REPLACE INTO users(id, teams) VALUES (?, ?)', (uid, team))
    con.commit()
    await query.edit_message_text(
            f"You are now following {team}",
        )
    
async def change_team(update: Update, context: CallbackContext) -> None:
    keyboard =[
        [InlineKeyboardButton("EMEA", callback_data="region_emea")],
        [InlineKeyboardButton("Pacific", callback_data="region_pacific")],
        [InlineKeyboardButton("NA", callback_data="region_na")],
        [InlineKeyboardButton("CN", callback_data="region_cn")]
    ]
    await update.message.reply_text(
        "Pick a region to follow:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# async def upcoming(update: Update, context: CallbackContext) -> None:
#     userID = update.effective_user.id
#     cur.execute('SELECT teams FROM users WHERE id = ?', (userID,))
#     user_teams = cur.fetchone()[0].split(',')

async def get_matches(update: Update, context: CallbackContext) -> None:
    response = requests.get("https://vlrggapi.vercel.app/match?q=upcoming")
    try:
        if response.status_code == 200:
            matches_data = response.json()
            has_championship_matches = False
            #only want matches regarding championships
            for match in matches_data["data"]["segments"]:
                event = match["match_event"]
                if 'Champions' not in event:
                    continue
                message = (
                    f"🏆 *{escape_markdown(match['team1'], version=2)} vs {escape_markdown(match['team2'], version=2)}*\n"
                    f"⏰ {escape_markdown(match['time_until_match'], version=2)}\n"
                    f"📅 {escape_markdown(match['unix_timestamp'], version=2)}\n"
                    f"🗺️ {escape_markdown(match['match_series'], version=2)}\n"
                    f"🔗 [Match Details]({escape_markdown(match['match_page'], version=2)})"
                )
                await update.message.reply_text(
                    text=message,
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True
                )
                has_championship_matches = True
            if not has_championship_matches:
                await update.message.reply_text(
                    "There are no upcoming Champion Tour matches",
                    parse_mode='MarkdownV2'
                )
        else:
            await update.message.reply_text("There was an error fetching the matches")
            return
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        await update.message.reply_text("⚠️ Error fetching matches. Please try again later.")

async def get_news(update: Update, context: CallbackContext) -> None:
    try:
        response = requests.get("https://vlrggapi.vercel.app/news")

        if response.status_code == 200:
            news_data = response.json()
            #only want today and yesterday's news
            today = datetime.today().date()
            yesterday = today - timedelta(days=1)
            has_news = False
            for news in news_data["data"]["segments"]:
                news_date = datetime.strptime(news['date'], "%B %d, %Y").date()
                if news_date not in [today, yesterday]:
                    continue
                message = (
                    f"📰 *{escape_markdown(news['title'], version=2)}*\n"
                    f"{escape_markdown(news['date'], version=2)}\n"
                    f"[Read more ↗]({escape_markdown(news['url_path'], version=2)})"
                )
                await update.message.reply_text(
                    text=message,
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True
                )
                has_news = True
            if not has_news:
                await update.message.reply_text(
                    "There are no recent news",
                    parse_mode='MarkdownV2'
                )
        else:
            await update.message.reply_text("Error, could not fetch news at this time.")
            return
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        await update.message.reply_text("⚠️ Error fetching news. Please try again later.")

def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("changeteam", change_team))
    application.add_handler(CommandHandler("upcomingmatches", get_matches))
    application.add_handler(CommandHandler("news", get_news))

    application.add_handler(CallbackQueryHandler(handle_region, pattern="^start_pick_region$"))
    application.add_handler(CallbackQueryHandler(handle_team, pattern="^region_"))
    application.add_handler(CallbackQueryHandler(save_team, pattern="^team_"))
    
    application.run_polling()



if __name__ == '__main__':
    main()

