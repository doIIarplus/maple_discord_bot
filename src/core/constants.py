from enum import Enum


GUILD_ID = 1228053292261572628
SPREADSHEET_KEY = "1PwsQO7qgv9-LwIKur4BTJ15La0fYsYsPKJAX_Xdh0II"
WORKSHEET_NAME = "GPQ"
LEFT_WORKSHEET_NAME = "LeftorKicked"
REMINDER_CHANNEL_ID = 1228053295382265934
MACRO_CHANNEL_ID = 1288037434680152074
WELCOME_CHANNEL_ID = 1228053294463582350

class Timezones(Enum):
    CET = "Europe/Paris"
    BRT = "America/Sao_Paulo"
    SGT = "Asia/Singapore"
    BST_UK = "Europe/London"
    EST = "America/New_York"
    PST = "America/Los_Angeles"
    AEST = "Australia/Sydney"


TIMEZONE_MAP = {
    "UTC": "Etc/UTC",
    "GMT": "Etc/GMT",
    # US Timezones
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    # Europe
    "CET": "Europe/Paris",
    "CEST": "Europe/Paris",
    "BST": "Europe/London",  # British Summer Time
    "WEST": "Europe/Lisbon",
    # Asia
    "SGT": "Asia/Singapore",
    "JST": "Asia/Tokyo",
    "KST": "Asia/Seoul",
    "IST": "Asia/Kolkata",  # India Standard Time
    # Australia
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
    "ACST": "Australia/Adelaide",
    "AWST": "Australia/Perth",
    # South America
    "BRT": "America/Sao_Paulo",
    "ART": "America/Argentina/Buenos_Aires",
}
