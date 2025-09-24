from typing import List, Optional, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from gspread import Cell

T = TypeVar('T')


def remove_leading_nones(data: List[T]) -> List[T]:
    """
    Removes all leading Nones from the given list.
    """
    i = 0
    while i < len(data) and data[i] is None:
        i += 1
    return data[i:]


def pad_list(data: List[T], length: int, value: T, start=False) -> List[T]:
    difference = length - len(data)
    if difference <= 0:
        return data

    if start:
        return [value] * difference + data
    else:
        return data + [value] * difference


def convert_none_in_list(data: List[Optional[T]], default: T) -> List[T]:
    return [value if value is not None else default for value in data]


def get_from_list_or_default(data: List[T], index: int, default: T) -> T:
    try:
        return data[index]
    except IndexError:
        return default


def clean_sheet_value(value) -> Optional[int]:
    # Handle None values (from SQLite)
    if value is None or value == '':
        return None

    # Convert to string if it's not already
    value_str = str(value)
    value_str = value_str.replace(',', '')
    
    try:
        return int(value_str)
    except ValueError:
        return None


def batch_list(data: List[T], batch_size: int) -> List[List[T]]:
    # calculate the number of batches needed
    num_batches = (len(data) + batch_size - 1) // batch_size

    # create a list of batches
    batches = []
    for i in range(num_batches):
        batch_start = i * batch_size
        batch_end = (i + 1) * batch_size
        batch = data[batch_start:batch_end]
        batches.append(batch)

    return batches


def sum_cell_scores(cells: List['Cell']) -> int:
    total = 0
    for cell in cells:
        value = clean_sheet_value(cell.value)
        if value is None:
            continue
        total = total + value

    return total

