"""
RTanks Online Website Scraper
Handles scraping player data from the RTanks ratings website.
"""

import aiohttp
import asyncio
from bs4 import BeautifulSoup
import random
import re
import logging
from urllib.parse import quote
import json

logger = logging.getLogger(__name__)

class RTanksScraper:
    def __init__(self):
        self.base_url = "https://ratings.ranked-rtanks.online"
        self.session = None
        
        # Headers to avoid bot detection
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        
    async def _get_session(self):
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
        return self.session
    
    async def get_player_data(self, username):
        """
        Scrape player data from the RTanks ratings website.
        Returns a dictionary with player information or None if not found.
        """
        try:
            session = await self._get_session()
            
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Try the correct URL pattern for RTanks
            possible_urls = [
                f"{self.base_url}/user/{quote(username)}"
            ]
            
            player_data = None
            for url in possible_urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            player_data = await self._parse_player_data(html, username)
                            if player_data:
                                break
                        elif response.status == 404:
                            continue
                        else:
                            logger.warning(f"Unexpected status code {response.status} for {url}")
                            continue
                            
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout while fetching {url}")
                    continue
                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")
                    continue
            
            if not player_data:
                # Try searching the main page for the player
                player_data = await self._search_player_on_main_page(username)
            
            return player_data
            
        except Exception as e:
            logger.error(f"Error in get_player_data: {e}")
            return None
    
    async def _parse_player_data(self, html, username):
        """Parse player data from HTML response."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            logger.info(f"Parsing data for {username}")
            
            # Initialize player data
            player_data = {
                'username': username,
                'rank': 'Unknown',
                'experience': 0,
                'kills': 0,
                'deaths': 0,
                'kd_ratio': '0.00',
                'gold_boxes': 0,
                'premium': False,
                'group': 'Unknown',
                'is_online': False,
                'status_indicator': '🔴',
              'equipment': {'turrets': [], 'hulls': [], 'protections': []}
            }
            
            # Debug: Log some of the HTML to understand structure
            logger.info(f"HTML contains 'offline': {'offline' in html.lower()}")
            logger.info(f"HTML contains 'online': {'online' in html.lower()}")
            
            # Parse online status from the small circle near player name
            # Parse online status from a hidden span with id="online_status"
            try:
                status_span = soup.find('span', id='online_status')
                if status_span:
                    status_text = status_span.get_text(strip=True).lower()
                    is_online = status_text == 'yes'
                    logger.info(f"{username} detected as {'ONLINE' if is_online else 'OFFLINE'} from span")
                else:
                    is_online = False
                    logger.warning("No <span id='online_status'> found")
            except Exception as e:
                is_online = False
                logger.error(f"Error reading online status from span: {e}")

            player_data['is_online'] = is_online
            player_data['status_indicator'] = '🟢' if is_online else '🔴'
            logger.info(f"{username} detected as {'ONLINE' if is_online else 'OFFLINE'}")
            logger.info(f"{username} detected as {'ONLINE' if is_online else 'OFFLINE'}")
            
            # Parse experience FIRST - Look for current/max format like "105613/125000"
            exp_patterns = [
                r'(\d{1,3}(?:\s?\d{3})*)\s*/\s*(\d{1,3}(?:\s?\d{3})*)',  # Current/max format with spaces
                r'(\d{1,3}(?:,\d{3})*)\s*/\s*(\d{1,3}(?:,\d{3})*)',     # Current/max format with commas
                r'(\d+)\s*/\s*(\d+)',                                     # Simple current/max format
            ]
            
            # First try to find current/max experience format
            exp_found = False
            for pattern in exp_patterns:
                exp_match = re.search(pattern, html)
                if exp_match:
                    current_exp_str = exp_match.group(1).replace(',', '').replace(' ', '')
                    max_exp_str = exp_match.group(2).replace(',', '').replace(' ', '')
                    try:
                        player_data['experience'] = int(current_exp_str)
                        player_data['max_experience'] = int(max_exp_str)
                        exp_found = True
                        logger.info(f"Found experience: {player_data['experience']}/{player_data['max_experience']}")
                        break
                    except ValueError:
                        continue
            
            # If current/max format not found, try single experience value
            if not exp_found:
                single_exp_patterns = [
                    r'Experience[^0-9]*(\d{1,3}(?:,?\d{3})*)',
                    r'Опыт[^0-9]*(\d{1,3}(?:,?\d{3})*)',
                    r'"experience"[^0-9]*(\d{1,3}(?:,?\d{3})*)'
                ]
                
                for pattern in single_exp_patterns:
                    exp_match = re.search(pattern, html, re.IGNORECASE)
                    if exp_match:
                        exp_str = exp_match.group(1).replace(',', '').replace(' ', '')
                        player_data['experience'] = int(exp_str)
                        logger.info(f"Found single experience: {player_data['experience']}")
                        break
            
            # Parse rank - Enhanced detection with experience-based fallback
            rank_patterns = [
                r'(Легенда|Legend)\s*(\d*)',
                r'(Генералиссимус|Generalissimo)',
                r'(Командир бригады|Brigadier Commander)',
                r'(Командир полковник|Colonel Commander)',
                r'(Командир подполковник|Lieutenant Colonel Commander)',
                r'(Командир майор|Major Commander)',
                r'(Командир капитан|Captain Commander)',
                r'(Командир лейтенант|Lieutenant Commander)',
                r'(Командир|Commander)',
                r'(Фельдмаршал|Field Marshal)',
                r'(Маршал|Marshal)',
                r'(Генерал|General)',
                r'(Генерал-лейтенант|Lieutenant General)',
                r'(Генерал-майор|Major General)',
                r'(Бригадир|Brigadier)',
                r'(Полковник|Colonel)',
                r'(Подполковник|Lieutenant Colonel)',
                r'(Майор|Major)',
                r'(Капитан|Captain)',
                r'(Старший лейтенант|First Lieutenant)',
                r'(Лейтенант|Second Lieutenant)',
                r'(Старший прапорщик|Master Warrant Officer)',
                r'(Прапорщик|Warrant Officer)',
                r'(Старшина|Sergeant Major)',
                r'(Старший сержант|First Sergeant)',
                r'(Сержант|Master Sergeant)',
                r'(Младший сержант|Staff Sergeant)',
                r'(Ефрейтор|Sergeant)',
                r'(Старший ефрейтор|Master Corporal)',
                r'(Капрал|Corporal)',
                r'(Гефрейтор|Gefreiter)',
                r'(Рядовой|Private)',
                r'(Новобранец|Recruit)'
            ]
            
            rank_found = False
            for pattern in rank_patterns:
                rank_match = re.search(pattern, html, re.IGNORECASE)
                if rank_match:
                    rank_text = rank_match.group(1)
                    # Map Russian ranks to English
                    rank_mapping = {
                        'Легенда': 'Legend',
                        'Генералиссимус': 'Generalissimo',
                        'Командир бригады': 'Brigadier Commander',
                        'Командир полковник': 'Colonel Commander',
                        'Командир подполковник': 'Lieutenant Colonel Commander',
                        'Командир майор': 'Major Commander',
                        'Командир капитан': 'Captain Commander',
                        'Командир лейтенант': 'Lieutenant Commander',
                        'Командир': 'Commander',
                        'Фельдмаршал': 'Field Marshal',
                        'Маршал': 'Marshal',
                        'Генерал': 'General',
                        'Генерал-лейтенант': 'Lieutenant General',
                        'Генерал-майор': 'Major General',
                        'Бригадир': 'Brigadier',
                        'Полковник': 'Colonel',
                        'Подполковник': 'Lieutenant Colonel',
                        'Майор': 'Major',
                        'Капитан': 'Captain',
                        'Старший лейтенант': 'First Lieutenant',
                        'Лейтенант': 'Second Lieutenant',
                        'Старший прапорщик': 'Master Warrant Officer',
                        'Прапорщик': 'Warrant Officer',
                        'Старшина': 'Sergeant Major',
                        'Старший сержант': 'First Sergeant',
                        'Сержант': 'Master Sergeant',
                        'Младший сержант': 'Staff Sergeant',
                        'Ефрейтор': 'Sergeant',
                        'Старший ефрейтор': 'Master Corporal',
                        'Капрал': 'Corporal',
                        'Гефрейтор': 'Gefreiter',
                        'Рядовой': 'Private',
                        'Новобранец': 'Recruit'
                    }
                    player_data['rank'] = rank_mapping.get(rank_text, rank_text)
                    rank_found = True
                    logger.info(f"Found rank: {player_data['rank']}")
                    break
            
            # Determine rank from experience using correct RTanks values
            # Always use experience-based calculation as the primary method
            if player_data.get('experience', 0) >= 0:
                if player_data['experience'] >= 1600000:
                    # Legend: 1,600,000 (+200,000 each level)  
                    legend_level = 1 + ((player_data['experience'] - 1600000) // 200000)
                    player_data['rank'] = f'Legend {legend_level}'
                elif player_data['experience'] >= 1400000:
                    player_data['rank'] = 'Generalissimo'  # 1,400,000
                elif player_data['experience'] >= 1255000:
                    player_data['rank'] = 'Commander'  # 1,255,000
                elif player_data['experience'] >= 1122000:
                    player_data['rank'] = 'Field Marshal'  # 1,122,000
                elif player_data['experience'] >= 1000000:
                    player_data['rank'] = 'Marshal'  # 1,000,000
                elif player_data['experience'] >= 889000:
                    player_data['rank'] = 'General'  # 889,000
                elif player_data['experience'] >= 787000:
                    player_data['rank'] = 'Lieutenant General'  # 787,000
                elif player_data['experience'] >= 692000:
                    player_data['rank'] = 'Major General'  # 692,000
                elif player_data['experience'] >= 606000:
                    player_data['rank'] = 'Brigadier'  # 606,000
                elif player_data['experience'] >= 527000:
                    player_data['rank'] = 'Colonel'  # 527,000
                elif player_data['experience'] >= 455000:
                    player_data['rank'] = 'Lieutenant Colonel'  # 455,000
                elif player_data['experience'] >= 390000:
                    player_data['rank'] = 'Major'  # 390,000
                elif player_data['experience'] >= 332000:
                    player_data['rank'] = 'Captain'  # 332,000
                elif player_data['experience'] >= 280000:
                    player_data['rank'] = 'First Lieutenant'  # 280,000
                elif player_data['experience'] >= 233000:
                    player_data['rank'] = 'Second Lieutenant'  # 233,000
                elif player_data['experience'] >= 192000:
                    player_data['rank'] = 'Third Lieutenant'  # 192,000
                elif player_data['experience'] >= 156000:
                    player_data['rank'] = 'Warrant Officer 5'  # 156,000
                elif player_data['experience'] >= 125000:
                    player_data['rank'] = 'Warrant Officer 4'  # 125,000
                elif player_data['experience'] >= 98000:
                    player_data['rank'] = 'Warrant Officer 3'  # 98,000
                elif player_data['experience'] >= 76000:
                    player_data['rank'] = 'Warrant Officer 2'  # 76,000
                elif player_data['experience'] >= 57000:
                    player_data['rank'] = 'Warrant Officer 1'  # 57,000
                elif player_data['experience'] >= 41000:
                    player_data['rank'] = 'Sergeant Major'  # 41,000
                elif player_data['experience'] >= 29000:
                    player_data['rank'] = 'First Sergeant'  # 29,000
                elif player_data['experience'] >= 20000:
                    player_data['rank'] = 'Master Sergeant'  # 20,000
                elif player_data['experience'] >= 12300:
                    player_data['rank'] = 'Staff Sergeant'  # 12,300
                elif player_data['experience'] >= 7100:
                    player_data['rank'] = 'Sergeant'  # 7,100
                elif player_data['experience'] >= 3700:
                    player_data['rank'] = 'Master Corporal'  # 3,700
                elif player_data['experience'] >= 1500:
                    player_data['rank'] = 'Corporal'  # 1,500
                elif player_data['experience'] >= 500:
                    player_data['rank'] = 'Gefreiter'  # 500
                elif player_data['experience'] >= 100:
                    player_data['rank'] = 'Private'  # 100
                else:
                    player_data['rank'] = 'Recruit'  # 0-99
                logger.info(f"Determined rank from experience: {player_data['rank']}")
                rank_found = True  # Mark as found since we used experience-based calculation
                
            # Assign max experience based on rank if not already set
            from utils import get_max_experience_for_rank
            if not player_data.get('max_experience') and player_data.get('rank'):
                player_data['max_experience'] = get_max_experience_for_rank(player_data['rank'])
                logger.info(f"Assigned max experience for {player_data['rank']}: {player_data['max_experience']}")
            
            # Calculate dynamic Legend rank based on experience
            if player_data.get('rank', '').startswith('Legend') and player_data.get('experience', 0) >= 1600000:
                # For every 200,000 XP above 1,600,000, add +1 to Legend rank
                legend_level = 1 + ((player_data['experience'] - 1600000) // 200000)
                player_data['rank'] = f'Legend {legend_level}'
            
            # Parse combat stats from the structured data
            # Look for numbers in specific patterns that match the screenshots
            
            # Find all digit patterns and try to match them logically
            all_numbers = re.findall(r'\b(\d+)\b', html)
            logger.info(f"Found numbers in HTML: {all_numbers[:20]}")  # Log first 20 numbers
            
            # Parse kills and deaths from Russian website structure
            # From screenshot: "Уничтожил" (destroyed/kills) and "Падение" (deaths)
            
            # Look for kills pattern - "Уничтожил" in combat stats section with comma-separated numbers
            kills_patterns = [
                r'Уничтожил[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',  # Support both space and comma separators
                r'Destroyed[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',
                r'"destroyed"[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)'
            ]
            
            for pattern in kills_patterns:
                kills_match = re.search(pattern, html, re.IGNORECASE)
                if kills_match:
                    kills_str = kills_match.group(1).replace(',', '').replace(' ', '')
                    player_data['kills'] = int(kills_str)
                    logger.info(f"Found kills: {player_data['kills']} from pattern {pattern}")
                    break
            
            # Look for deaths pattern - "Hit" is the correct field name from the RTanks site
            deaths_patterns = [
                r'Hit\s*(\d{1,3}(?:[\s,]\d{3})*)',  # Match "Hit" followed by number (from RTanks site)
                r'Подбит[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',  # Russian alternative
                r'Падение[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',  # Russian alternative
                r'"deaths"[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)'
            ]
            
            for pattern in deaths_patterns:
                deaths_match = re.search(pattern, html, re.IGNORECASE)
                if deaths_match:
                    deaths_str = deaths_match.group(1).replace(',', '').replace(' ', '')
                    player_data['deaths'] = int(deaths_str)
                    logger.info(f"Found deaths: {player_data['deaths']} from pattern {pattern}")
                    break
            
            # Parse K/D ratio - "У/П" from Russian website
            kd_patterns = [
                r'У/П[^0-9]*(\d+\.?\d*)',
                r'U/P[^0-9]*(\d+\.?\d*)',
                r'"efficiency"[^0-9]*(\d+\.?\d*)',
                r'По эффективности[^0-9]*#\d+[^0-9]*(\d+\.?\d*)'
            ]
            
            for pattern in kd_patterns:
                kd_match = re.search(pattern, html, re.IGNORECASE)
                if kd_match:
                    player_data['kd_ratio'] = kd_match.group(1)
                    logger.info(f"Found K/D: {player_data['kd_ratio']} from pattern {pattern}")
                    break
            
            if not player_data['kd_ratio'] or player_data['kd_ratio'] == '0.00':
                if player_data['deaths'] > 0:
                    kd = player_data['kills'] / player_data['deaths']
                    player_data['kd_ratio'] = f"{kd:.2f}"
            
            # Parse premium status - look for "Yes" near "Premium"
            premium_patterns = [
                r'Premium[^A-Za-z]*Yes',
                r'Премиум[^А-Яа-я]*Да'
            ]
            
            for pattern in premium_patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    player_data['premium'] = True
                    logger.info(f"Found premium: True")
                    break
            
            # Parse group
            group_patterns = [
                r'Group[^A-Za-z]*(\w+)',
                r'Группа[^А-Яа-я]*([А-Яа-я\w]+)'
            ]
            
            for pattern in group_patterns:
                group_match = re.search(pattern, html, re.IGNORECASE)
                if group_match:
                    group_text = group_match.group(1)
                    group_mapping = {
                        'Помощник': 'Helper',
                        'Игрок': 'Player',
                        'Модератор': 'Moderator',
                        'Администратор': 'Administrator'
                    }
                    player_data['group'] = group_mapping.get(group_text, group_text)
                    logger.info(f"Found group: {player_data['group']}")
                    break
            
            # Parse gold boxes - "Поймано золотых ящиков" from Russian website
            gold_patterns = [
                r'Поймано золотых ящиков[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',  # Support space and comma separators
                r'Caught gold boxes[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',
                r'gold boxes[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)',
                r'золотых ящиков[^0-9]*(\d{1,3}(?:[\s,]\d{3})*)'
            ]
            
            for pattern in gold_patterns:
                gold_match = re.search(pattern, html, re.IGNORECASE)
                if gold_match:
                    gold_str = gold_match.group(1).replace(',', '').replace(' ', '')
                    player_data['gold_boxes'] = int(gold_str)
                    logger.info(f"Found gold boxes: {player_data['gold_boxes']} from pattern {pattern}")
                    break
            
            # Parse equipment (looking for "Установленный Да")
            turret_mapping = {
                'Смоки': 'Smoky', 'Рельса': 'Rail', 'Рикошет': 'Ricochet', 
                'Изида': 'Isida', 'Фриз': 'Freeze', 'Огнемет': 'Flamethrower',
                'Гром': 'Thunder', 'Молот': 'Hammer', 'Вулкан': 'Vulcan',
                'Твинс': 'Twins', 'Шафт': 'Shaft', 'Страйкер': 'Striker'
            }
            
            hull_mapping = {
                'Хантер': 'Hunter', 'Мамонт': 'Mammoth', 'Титан': 'Titan',
                'Васп': 'Wasp', 'Викинг': 'Viking', 'Хорнет': 'Hornet',
                'Диктатор': 'Dictator'
            }
            # Parse protection/resistance modules - find all active protections
            try:
                # Look for resistance/protection modules marked as installed
                protection_pattern = r'resistances/([^/]+)/m(\d+)/preview\.png.*?Установленный.*?Да'
                protection_matches = re.findall(protection_pattern, html, re.IGNORECASE | re.DOTALL)
                
                for match in protection_matches:
                    protection_name = match[0].lower().strip()
                    mod_level = match[1]
                    
                    # Map Russian names to English
                    from config import PROTECTION_NAMES
                    english_name = PROTECTION_NAMES.get(protection_name, protection_name.title())
                    
                    protection_entry = f"{english_name} M{mod_level}"
                    if protection_entry not in player_data['equipment']['protections']:
                        player_data['equipment']['protections'].append(protection_entry)
                        
                logger.info(f"Found protections for {username}: {player_data['equipment']['protections']}")
                
            except Exception as e:
                logger.error(f"Error parsing protections for {username}: {e}")
                player_data['equipment']['protections'] = []
            
            logger.info(f"Found turrets for {username}: {player_data['equipment']['turrets']}")
            logger.info(f"Found hulls for {username}: {player_data['equipment']['hulls']}")
            logger.info(f"Found protections for {username}: {player_data['equipment']['protections']}")
            
            return player_data
            
        except Exception as e:
            logger.error(f"Error parsing player data for {username}: {e}")
            return None
    
    async def _search_player_on_main_page(self, username):
        """Search for player on the main leaderboard page."""
        try:
            session = await self._get_session()
            
            # Check both experience and crystals leaderboards
            leaderboard_urls = [
                f"{self.base_url}/",  # Main page with experience leaderboard
            ]
            
            for url in leaderboard_urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Look for the player in the leaderboard
                            player_pattern = rf'href="/user/{re.escape(username)}"[^>]*>.*?{re.escape(username)}'
                            if re.search(player_pattern, html, re.IGNORECASE):
                                logger.info(f"Found {username} on leaderboard, fetching full profile")
                                # Player exists on leaderboard, try to get their full profile
                                profile_url = f"{self.base_url}/user/{quote(username)}"
                                async with session.get(profile_url) as profile_response:
                                    if profile_response.status == 200:
                                        profile_html = await profile_response.text()
                                        return await self._parse_player_data(profile_html, username)
                        
                except Exception as e:
                    logger.error(f"Error searching on {url}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in _search_player_on_main_page: {e}")
            return None
            # Parse equipment from the detailed equipment section
            # Look for equipment cards showing "Installed: Yes" and extract mod levels
            
            # Find all equipment cards in the HTML
            equipment_cards = re.findall(r'<div[^>]*class="[^"]*equipment[^"]*"[^>]*>.*?</div>', html, re.DOTALL | re.IGNORECASE)
            
            for russian_name, english_name in turret_mapping.items():
                # Look for this turret in the HTML with multiple patterns
                patterns = [
                    f'{russian_name}\\s*M(\\d)',  # "Smoky M0", "Rail M1", etc.
                    f'{russian_name}\\s*М(\\d)',  # Russian М instead of M
                    f'{english_name}\\s*M(\\d)'   # English names
                ]
                
                found_equipment = False
                for pattern in patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    for mod_level in matches:
                        # Check if this equipment is installed
                        install_pattern = f'{russian_name}.*?Installed.*?Yes|{english_name}.*?Installed.*?Yes|{russian_name}.*?Установленный.*?Да'
                        if re.search(install_pattern, html, re.DOTALL | re.IGNORECASE):
                            player_data['equipment']['turrets'].append(f"{english_name} M{mod_level}")
                            found_equipment = True
                            logger.info(f"Found turret: {english_name} M{mod_level}")
                
                # If no specific mod level found but equipment is installed, default to M0
                if not found_equipment:
                    install_pattern = f'{russian_name}.*?Installed.*?Yes|{english_name}.*?Installed.*?Yes|{russian_name}.*?Установленный.*?Да'
                    if re.search(install_pattern, html, re.DOTALL | re.IGNORECASE):
                        player_data['equipment']['turrets'].append(f"{english_name} M0")
                        logger.info(f"Found turret (default M0): {english_name}")
            
            for russian_name, english_name in hull_mapping.items():
                # Look for this hull in the HTML with multiple patterns
                patterns = [
                    f'{russian_name}\\s*M(\\d)',  # "Hunter M0", "Mammoth M1", etc.
                    f'{russian_name}\\s*М(\\d)',  # Russian М instead of M
                    f'{english_name}\\s*M(\\d)'   # English names
                ]
                
                found_equipment = False
                for pattern in patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    for mod_level in matches:
                        # Check if this equipment is installed
                        install_pattern = f'{russian_name}.*?Installed.*?Yes|{english_name}.*?Installed.*?Yes|{russian_name}.*?Установленный.*?Да'
                        if re.search(install_pattern, html, re.DOTALL | re.IGNORECASE):
                            player_data['equipment']['hulls'].append(f"{english_name} M{mod_level}")
                            found_equipment = True
                            logger.info(f"Found hull: {english_name} M{mod_level}")
                
                # If no specific mod level found but equipment is installed, default to M0
                if not found_equipment:
                    install_pattern = f'{russian_name}.*?Installed.*?Yes|{english_name}.*?Installed.*?Yes|{russian_name}.*?Установленный.*?Да'
                    if re.search(install_pattern, html, re.DOTALL | re.IGNORECASE):
                        player_data['equipment']['hulls'].append(f"{english_name} M0")
                        logger.info(f"Found hull (default M0): {english_name}")
            
            # If we found meaningful data, return it
            if (player_data['experience'] > 0 or 
                player_data['kills'] > 0 or 
                player_data['rank'] != 'Unknown'):
                return player_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing player data: {e}")
            return None
    
    async def _search_player_on_main_page(self, username):
        """Search for player on the main rankings page."""
        try:
            session = await self._get_session()
            
            async with session.get(self.base_url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for the player in any rankings tables
                tables = soup.find_all('table')
                for table in tables:
                    if hasattr(table, 'find_all'):
                        rows = table.find_all('tr')
                        for row in rows:
                            if username.lower() in row.get_text().lower():
                                # Try to extract data from this row
                                return await self._parse_table_row(row, username)
                
                return None
                
        except Exception as e:
            logger.error(f"Error searching main page: {e}")
            return None
    
    async def _parse_table_row(self, row, username):
        """Parse player data from a table row."""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            player_data = {
                'username': username,
                'rank': 'Legend Premium',  # Default assumption for players on rankings
                'experience': 0,
                'kills': 0,
                'deaths': 0,
                'kd_ratio': '0.00',
                'gold_boxes': 0,
                'premium': True,  # Assume premium if on rankings
                'group': 'Unknown',
                'is_online': False,
                'status_indicator': '⚫',
                'equipment': {'turrets': [], 'hulls': []}
            }
            
            # Try to extract numeric values from cells
            for cell in cells:
                text = cell.get_text().strip()
                numbers = re.findall(r'\d{1,3}(?:,\d{3})*', text)
                if numbers:
                    # Assume the largest number is experience
                    max_num = max([int(num.replace(',', '')) for num in numbers])
                    if max_num > player_data['experience']:
                        player_data['experience'] = max_num
            
            return player_data if player_data['experience'] > 0 else None
            
        except Exception as e:
            logger.error(f"Error parsing table row: {e}")
            return None
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
