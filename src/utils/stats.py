from integrations import Sheet
from utils.time_utils import get_first_date, get_string_for_week


def get_first_date_column(sheet: Sheet) -> int:
    date = get_first_date()
    return sheet.worksheet.find(get_string_for_week(date, True)).col
