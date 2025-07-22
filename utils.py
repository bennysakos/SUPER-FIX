"""
Utility functions for the RTanks Discord Bot.
"""

import math
from config import RANK_EMOJIS

def format_number(num):
    """Format a number with appropriate suffixes (K, M, B)."""
    if num == 0:
        return "0"
    
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num/1000:.1f}K"
    elif num < 1000000000:
        return f"{num/1000000:.1f}M"
    else:
        return f"{num/1000000000:.1f}B"

def format_exact_number(num):
    """Format a number with comma separators for exact display."""
    return f"{num:,}"

def get_rank_emoji(rank_name):
    """Get the appropriate emoji for a rank."""
    # Handle dynamic Legend ranks (Legend 1, Legend 2, etc.)
    if rank_name.startswith('Legend'):
        return RANK_EMOJIS.get(31, '🏆')  # All Legend ranks use emoji 31
    
    rank_name = rank_name.lower().replace(' ', '_')
    
    # Map rank names to emoji indices based on the new rank chart
    rank_mapping = {
        'recruit': 1,
        'private': 2,
        'gefreiter': 3,
        'corporal': 4,
        'master_corporal': 5,
        'sergeant': 6,
        'staff_sergeant': 7,
        'master_sergeant': 8,
        'first_sergeant': 9,
        'sergeant_major': 10,
        'warrant_officer_1': 11,
        'warrant_officer_2': 12,
        'warrant_officer_3': 13,
        'warrant_officer_4': 14,
        'warrant_officer_5': 15,
        'third_lieutenant': 16,
        'second_lieutenant': 17,
        'first_lieutenant': 18,
        'captain': 19,
        'major': 20,
        'lieutenant_colonel': 21,
        'colonel': 22,
        'brigadier': 23,
        'major_general': 24,
        'lieutenant_general': 25,
        'general': 26,
        'marshal': 27,
        'field_marshal': 28,
        'commander': 29,
        'generalissimo': 30,
        'legend': 31,
        'legend_premium': 31
    }
    
    emoji_index = rank_mapping.get(rank_name, 31)  # Default to legend
    return RANK_EMOJIS.get(emoji_index, '🏆')

def format_duration(seconds):
    """Format duration in seconds to a readable string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        return f"{days}d {hours}h"

def calculate_kd_ratio(kills, deaths):
    """Calculate K/D ratio safely."""
    if deaths == 0:
        return str(kills) if kills > 0 else "0.00"
    return f"{kills/deaths:.2f}"

def extract_numbers(text):
    """Extract all numbers from a text string."""
    import re
    return [int(match) for match in re.findall(r'\d+', text)]

def sanitize_username(username):
    """Sanitize username for safe URL usage."""
    import re
    return re.sub(r'[^a-zA-Z0-9_-]', '', username)

def get_max_experience_for_rank(rank):
    """Get the maximum experience for a given rank based on the progression chart."""
    rank_experience_map = {
        'Recruit': 400,
        'Private': 1000, 
        'Gefreiter': 2200,
        'Corporal': 4400,
        'Master Corporal': 7700,
        'Sergeant': 12300,
        'Staff Sergeant': 20000,
        'Master Sergeant': 29000,
        'First Sergeant': 41000,
        'Sergeant Major': 57000,
        'Warrant Officer 1': 76000,
        'Warrant Officer 2': 98000,
        'Warrant Officer 3': 125000,
        'Warrant Officer 4': 156000,
        'Warrant Officer 5': 192000,
        'Third Lieutenant': 233000,
        'Second Lieutenant': 280000,
        'First Lieutenant': 332000,
        'Captain': 390000,
        'Major': 455000,
        'Lieutenant Colonel': 527000,
        'Colonel': 606000,
        'Brigadier': 695000,
        'Major General': 787000,
        'Lieutenant General': 889000,
        'General': 1000000,
        'Marshal': 1122000,
        'Field Marshal': 1255000,
        'Commander': 1400000,
        'Generalissimo': 1600000,
        'Legend': 1800000  # Base for Legend 1, increases by 200k each level
    }
    
    # Handle Legend ranks with levels
    if rank.startswith('Legend'):
        if rank == 'Legend':
            return 1800000  # Legend 1 max
        else:
            # Extract level from "Legend X" format
            try:
                level = int(rank.split(' ')[1])
                return 1600000 + (level * 200000)  # Base + level * 200k
            except (IndexError, ValueError):
                return 1800000
    
    return rank_experience_map.get(rank, 0)
