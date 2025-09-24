import re


def parse_days(day_str):
    day_str = day_str.lower().strip()
    if "weekday" in day_str:
        return list(range(0, 5))
    elif "weekend" in day_str:
        return [5, 6]

    subparts = re.split(r", | and | - | to ", day_str)
    day_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    days = []
    i = 0
    while i < len(subparts):
        current_part = subparts[i].strip()
        if not current_part:
            i += 1
            continue
        if i < len(subparts) - 1:
            next_part = subparts[i + 1].strip()
            current_num = None
            next_num = None
            for name, num in day_map.items():
                if current_part in name:
                    current_num = num
                if next_part in name:
                    next_num = num
            if current_num is not None and next_num is not None:
                if current_num <= next_num:
                    days.extend(range(current_num, next_num + 1))
                else:
                    days.extend(range(current_num, 7))
                    days.extend(range(0, next_num + 1))
                i += 2
                continue
        for name, num in day_map.items():
            if current_part in name:
                days.append(num)
                break
        i += 1
    return sorted(list(set(days)))


def parse_time(time_str):
    time_str = time_str.lower().strip()
    if time_str == "whenever":
        return (0, 24)
    if "onwards" in time_str:
        match = re.match(r"^\s*([+-]?\d+)\s*onwards\s*$", time_str)
        if match:
            return (int(match.group(1)), 24)
    match = re.match(r"^\s*([+-]?\d+)\s*to\s*([+-]?\d+)\s*$", time_str)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return None


def parse_input(input_str):
    segments = re.split(r",\s*", input_str)
    merged_segments = []
    i = 0
    while i < len(segments):
        current = segments[i]
        j = i + 1
        merged = current
        time_found = False
        while j <= len(segments):
            merged_candidate = ", ".join(segments[i:j])
            if re.search(
                r"((?:[+-]?\d+\s*(?:to\s*[+-]?\d+)?)|(?:[+-]?\d+\s*onwards)|whenever)\s*$",
                merged_candidate,
            ):
                merged = merged_candidate
                time_found = True
                break
            j += 1
        if time_found:
            merged_segments.append(merged)
            i = j
        else:
            merged_segments.append(merged)
            i += 1
    availability = []
    for merged_segment in merged_segments:
        match = re.match(
            r"^\s*(.*?)\s+((?:[+-]?\d+\s*to\s*[+-]?\d+)|(?:[+-]?\d+\s*onwards)|whenever)\s*$",
            merged_segment,
        )
        if not match:
            continue
        day_part, time_part = match.groups()
        days = parse_days(day_part)
        time_range = parse_time(time_part)
        if not days or not time_range:
            continue
        start, end = time_range
        for day_num in days:
            start_total = day_num * 24 + start
            start_day = (start_total // 24) % 7
            start_hour = start_total % 24
            end_total = day_num * 24 + end
            end_day = (end_total // 24) % 7
            end_hour = end_total % 24
            availability.append(
                {
                    "start_day": start_day,
                    "start_hour": start_hour,
                    "end_day": end_day,
                    "end_hour": end_hour,
                }
            )
    return availability


def format_availability(availability):
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    formatted = []
    for interval in availability:
        start_day = day_names[interval["start_day"]]
        start_hour = int(interval["start_hour"])
        end_day = day_names[interval["end_day"]]
        end_hour = int(interval["end_hour"])
        start_time = f"{start_hour:02d}:00"
        end_time = f"{end_hour:02d}:00"
        formatted.append(f"{start_day} {start_time} to {end_day} {end_time}")
    return formatted


# # Example usage:
# input_str = "Mondays +1 to +5, Tues - Fri -2 to +4, weekends whenever"
# input_str2 = "Weekdays +2 to +10, Weekends -5 to +6"
# input_str3 = "Monday, tuesday and wednesday +7 onwards"
# input_str4 = "Monday +7 to +8, Tuesday +4 to +7"
# availability = parse_input(input_str)
# formatted = format_availability(availability)
# for entry in formatted:
#     print(entry)
