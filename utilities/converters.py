from __future__ import annotations

from utilities.regex import TIME_REGEX
from discord.ext.commands import clean_content
# from utilities import exceptions as ex
from typing import Optional

def convert_time(arguments: str) -> int:
    try:
        total_sec = int(arguments)
        return total_sec
    except ValueError:
        pass
    time_array = TIME_REGEX.findall(arguments)
    total_sec = 0
    for segment in time_array:
        number = int(segment[0])
        multiplier = str(segment[1]).lower()
        if multiplier == 's': total_sec += 1 * number
        if multiplier == 'm': total_sec += 60 * number
        if multiplier == 'h': total_sec += 60 * 60 * number
        if multiplier == 'd': total_sec += 24 * 60 * 60 * number

    return total_sec


def convert_bool(text: str) -> Optional[bool]:
    if text.lower() in ('yes', 'y', 'true', 't', '1', 'enable', 'on', 'o'):
        return True
    elif text.lower() in ('no', 'n', 'false', 'f', '0', 'disable', 'off', 'x'):
        return False
    else:
        return None


def reason_convert(text: clean_content) -> str:
    return text[:450:]
