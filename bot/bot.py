import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

class FortniteShopBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.application = Application.builder().token(token).build()
        self.scheduler = AsyncIOScheduler()
        self.last_shop_data = None
        self.vbuck_to_rub = 0.499

    # ---------- Типы предметов и эмодзи ----------
    ITEM_TYPE_EMOJI = {
        'outfit': '👕',          # Костюм
        'pickaxe': '⛏️',         # Инструмент
        'glider': '🪂',           # Планер
        'emote': '💃',            # Эмоция
        'backbling': '🎒',        # Украшение на спину
        'wrap': '🎁',             # Обёртка
        'bundle': '📦',           # Набор
        'music': '🎵',            # Музыка
        'loading': '⏳',          # Экран загрузки
        'spray': '🎨',            # Граффити
        'emoji': '😊',            # Эмодзи (внутриигровые)
        'toy': '🧸',              # Игрушка
        'pet': '🐶',              # Питомец
        'contrail': '✨',         # След
        'unknown': '❓'           # Неизвестно
    }

    ITEM_TYPE_RU = {
        'outfit': 'Костюм',
        'pickaxe': 'Инструмент',
        'glider': 'Планер',
        'emote': 'Эмоция',
        'backbling': 'Украшение',
        'wrap': 'Обёртка',
        'bundle': 'Набор',
        'music': 'Музыка',
        'loading': 'Экран загрузки',
        'spray': 'Граффити',
        'emoji': 'Эмодзи',
        'toy': 'Игрушка',
        'pet': 'Питомец',
        'contrail': 'След',
        'unknown': 'Предмет'
    }

    # ---------- Редкость и эмодзи ----------
    RARITY_EMOJI = {
        'common': '⚪',
        'uncommon': '🟢',
        'rare': '🔵',
        'epic': '🟣',
        'legendary': '🟠',
        'mythic': '🔴'
    }

    def vbucks_to_rubles(self, vbucks: int) -> float:
        return round(vbucks * self.vbuck_to_rub, 2)

    def format_price_with_rub(self, vbucks: int) -> str:
        rubles = self.vbucks_to_rubles(vbucks)
        rub_str = f"{rubles:.2f}".replace('.', ',')
        vb_str = f"{vbucks:,}".replace(",", " ")
        return f"{vb_str} V-Bucks (~{rub_str} ₽)"

    def get_rarity(self, name: str) -> str:
        name_lower = name.lower()
        if 'legendary' in name_lower or 'reaper' in name_lower or 'igris' in name_lower:
            return 'legendary'
        if 'epic' in name_lower or 'jin' in name_lower or 'hao' in name_lower:
            return 'epic'
        if 'rare' in name_lower or 'dino' in name_lower:
            return 'rare'
        if 'uncommon' in name_lower:
            return 'uncommon'
        return 'common'

    # ---------- Получение данных ----------
    async def get_shop_data(self) -> Optional[Dict]:
        try:
            url = "https://fortnite-api.com/v2/shop/br"
            headers = {'User-Agent': 'Mozilla/5.0'}
            params = {'language': 'ru'}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Реальные данные получены")
                return response.json()
            else:
                logger.warning("API недоступно, использую тестовые данные")
                return self.get_test_data()
        except Exception as e:
            logger.error(f"Ошибка API: {e}, использую тестовые данные")
            return self.get_test_data()

    def get_test_data(self) -> Dict:
        """Тестовые данные с указанием типов предметов"""
        return {
            "data": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "daily": [
                    {"items": [
                        {"name": "Sung Jin-Woo", "price": 1800, "type": "outfit"},
                        {"name": "Sung Jin-Woo (Shadow Monarch)", "price": 1800, "type": "outfit"},
                        {"name": "Cha Hae-In", "price": 1800, "type": "outfit"},
                        {"name": "Blood-Red Commander Igris", "price": 1800, "type": "outfit"},
                        {"name": "Kaisel (Glider)", "price": 1200, "type": "glider"},
                        {"name": "Demon King's Longsword (Pickaxe)", "price": 800, "type": "pickaxe"},
                        {"name": "Kamish's Wrath (Wrap)", "price": 500, "type": "wrap"}
                    ]},
                    {"items": [
                        {"name": "Black Dino Ranger", "price": 1500, "type": "outfit"},
                        {"name": "White Dino Ranger", "price": 1500, "type": "outfit"},
                        {"name": "Dino Thunder Bundle", "price": 2400, "type": "bundle"},
                        {"name": "Brachio Staff (Pickaxe)", "price": 800, "type": "pickaxe"},
                        {"name": "Dragon Sword (Pickaxe)", "price": 800, "type": "pickaxe"},
                        {"name": "Brachio Zord (Back Bling)", "price": 500, "type": "backbling"}
                    ]}
                ],
                "featured": [
                    {"items": [
                        {"name": "Mighty Morphing Power Rangers (LEGO)", "price": 1800, "type": "outfit"},
                        {"name": "Skull Raider", "price": 1200, "type": "outfit"},
                        {"name": "The Foundation", "price": 1500, "type": "outfit"},
                        {"name": "Venom Fang & Knight Killer (Pickaxe)", "price": 800, "type": "pickaxe"},
                        {"name": "Wings of Light (Back Bling)", "price": 400, "type": "backbling"},
                        {"name": "Shadow Summoner (Emote)", "price": 400, "type": "emote"},
                        {"name": "S-Rank Scent (Emote)", "price": 400, "type": "emote"}
                    ]}
                ]
            }
        }

    def get_all_items(self, data: Dict) -> List[Dict]:
        shop_data = data.get('data', data)
        items = []
        if 'daily' in shop_data:
            for sec in shop_data['daily']:
                if 'items' in sec:
                    items.extend(sec['items'])
        if 'featured' in shop_data:
            for sec in shop_data['featured']:
                if 'items' in sec:
                    items.extend(sec['items'])
        return items

    # ---------- Форматирование текста с типом предмета ----------
    def format_shop_text(self, data: Dict, section: str = "all") -> str:
        shop_data = data.get('data', data)
        date = shop_data.get('date', datetime.now().strftime("%d.%m.%Y"))
        if isinstance(date, str) and len(date) > 10:
            try:
                date_obj = datetime.strptime(date[:10], "%Y-%m-%d")
                date = date_obj.strftime("%d.%m.%Y")
            except:
                date = datetime.now().strftime("%d.%m.%Y")

        items = []
        if section in ("all", "daily") and 'daily' in shop_data:
            for sec in shop_data['daily']:
                if 'items' in sec:
                    items.extend(sec['items'])
        if section in ("all", "featured") and 'featured' in shop_data:
            for sec in shop_data['featured']:
                if 'items' in sec:
                    items.extend(sec['items'])

        if not items:
            return "😢 В магазине нет предметов"

        # Группировка по имени
        grouped = {}
        for item in items:
            name = item.get('name', 'Без названия')
            price = item.get('price', 0)
            item_type = item.get('type', 'unknown')
            grouped.setdefault(name, []).append((price, item_type))

        # Заголовок
        if section == "all":
            result = f"🛒 **ЕЖЕДНЕВНЫЙ МАГАЗИН ПРЕДМЕТОВ**\n📅 {date}\n\n"
        elif section == "daily":
            result = f"✨ **ЕЖЕДНЕВНЫЕ ПРЕДМЕТЫ**\n📅 {date}\n\n"
        else:
            result = f"🌟 **НОВИНКИ И ИЗБРАННОЕ**\n📅 {date}\n\n"

        result += f"💱 **Курс:** 1 V-Buck = {self.vbuck_to_rub} ₽\n\n"

        for name, price_type_list in grouped.items():
            first_type = price_type_list[0][1]
            type_emoji = self.ITEM_TYPE_EMOJI.get(first_type, self.ITEM_TYPE_EMOJI['unknown'])
            type_name = self.ITEM_TYPE_RU.get(first_type, self.ITEM_TYPE_RU['unknown'])

            rarity = self.get_rarity(name)
            rarity_emoji = self.RARITY_EMOJI.get(rarity, '⚪')

            result += f"{rarity_emoji}{type_emoji} **{name}**  _({type_name})_\n"
            for i, (price, _) in enumerate(price_type_list, 1):
                result += f"   {i}. {self.format_price_with_rub(price)}\n"
            result += "   ─────────────\n"

        return result

    # ---------- Статистика магазина ----------
    def get_shop_stats(self, data: Dict) -> str:
        items = self.get_all_items(data)
        if not items:
            return "😢 Нет данных для статистики."
        total_items = len(items)
        total_value_vb = sum(item['price'] for item in items)
        total_value_rub = self.vbucks_to_rubles(total_value_vb)
        avg_price_vb = total_value_vb / total_items
        avg_price_rub = self.vbucks_to_rubles(avg_price_vb)
        max_item = max(items, key=lambda x: x['price'])
        max_price_vb = max_item['price']
        max_price_rub = self.vbucks_to_rubles(max_price_vb)
        max_name = max_item['name']
        date = data.get('data', data).get('date', '')
        if isinstance(date, str) and len(date) > 10:
            try:
                date_obj = datetime.strptime(date[:10], "%Y-%m-%d")
                date = date_obj.strftime("%d.%m.%Y")
            except:
                date = datetime.now().strftime("%d.%m.%Y")
        else:
            date = datetime.now().strftime("%d.%m.%Y")

        total_vb_str = f"{total_value_vb:,}".replace(",", " ")
        total_rub_str = f"{total_value_rub:.2f}".replace('.', ',')
        avg_vb_str = f"{avg_price_vb:.1f}".replace('.', ',')
        avg_rub_str = f"{avg_price_rub:.2f}".replace('.', ',')

        return (
            f"📊 **Статистика магазина от {date}**\n\n"
            f"📦 Всего предметов: **{total_items}**\n"
            f"💰 Общая стоимость: **{total_vb_str} V-Bucks** (~{total_rub_str} ₽)\n"
            f"📈 Средняя цена: **{avg_vb_str} V-Bucks** (~{avg_rub_str} ₽)\n"
            f"🏆 Самый дорогой: **{max_name}** — {self.format_price_with_rub(max_price_vb)}"
        )

    # ---------- Топ самых дорогих ----------
    def get_top_items(self, data: Dict, n: int = 5) -> str:
        items = self.get_all_items(data)
        if not items:
            return "😢 Нет данных."
        sorted_items = sorted(items, key=lambda x: x['price'], reverse=True)[:n]
        date = data.get('data', data).get('date', '')
        if isinstance(date, str) and len(date) > 10:
            try:
                date_obj = datetime.strptime(date[:10], "%Y-%m-%d")
                date = date_obj.strftime("%d.%m.%Y")
            except:
                date = datetime.now().strftime("%d.%m.%Y")
        else:
            date = datetime.now().strftime("%d.%m.%Y")
        result = f"🏆 **Топ-{n} самых дорогих предметов** ({date})\n\n"
        for i, item in enumerate(sorted_items, 1):
            name = item['name']
            price = item['price']
            item_type = item.get('type', 'unknown')
            type_emoji = self.ITEM_TYPE_EMOJI.get(item_type, self.ITEM_TYPE_EMOJI['unknown'])
            rarity = self.get_rarity(name)
            rarity_emoji = self.RARITY_EMOJI.get(rarity, '⚪')
            result += f"{i}. {rarity_emoji}{type_emoji} {name} — {self.format_price_with_rub(price)}\n"
        return result

    # ---------- Поиск предметов ----------
    def search_items(self, data: Dict, query: str) -> str:
        items = self.get_all_items(data)
        if not items:
            return "😢 Нет данных для поиска."
        query_lower = query.lower()
        found = []
        for item in items:
            if query_lower in item['name'].lower():
                found.append(item)
        if not found:
            return f"😕 По запросу «{query}» ничего не найдено."
        grouped = {}
        for item in found:
            name = item['name']
            price = item['price']
            item_type = item.get('type', 'unknown')
            grouped.setdefault(name, []).append((price, item_type))
        result = f"🔍 **Результаты поиска по запросу «{query}»**\n\n"
        for name, price_type_list in grouped.items():
            first_type = price_type_list[0][1]
            type_emoji = self.ITEM_TYPE_EMOJI.get(first_type, self.ITEM_TYPE_EMOJI['unknown'])
            type_name = self.ITEM_TYPE_RU.get(first_type, self.ITEM_TYPE_RU['unknown'])
            rarity = self.get_rarity(name)
            rarity_emoji = self.RARITY_EMOJI.get(rarity, '⚪')
            result += f"{rarity_emoji}{type_emoji} **{name}**  _({type_name})_\n"
            for price, _ in price_type_list:
                result += f"   • {self.format_price_with_rub(price)}\n"
            result += "   ─────────────\n"
        return result

    # ---------- Информация о курсе ----------
    def get_exchange_info(self) -> str:
        return (
            f"💱 **Курс V-Bucks к рублю**\n\n"
            f"1 V-Buck = {self.vbuck_to_rub} ₽\n"
            f"2 V-Bucks ≈ 1 ₽\n\n"
            f"**Примеры:**\n"
            f"• 100 V-Bucks = {self.vbucks_to_rubles(100):.2f} ₽\n"
            f"• 1000 V-Bucks = {self.vbucks_to_rubles(1000):.2f} ₽\n"
            f"• 2800 V-Bucks (набор) = {self.vbucks_to_rubles(2800):.2f} ₽\n\n"
            f"📊 Данные актуальны на {datetime.now().strftime('%d.%m.%Y')} "
        )

    # ---------- Отправка результатов (редактирование текущего сообщения) ----------
    async def edit_message_with_result(self, query, text, back_callback="menu", extra_buttons=None):
        """Универсальный метод для редактирования сообщения с результатом и добавлением кнопки Назад"""
        keyboard = []
        if extra_buttons:
            keyboard.extend(extra_buttons)
        # Добавляем ряд с кнопкой Назад
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=back_callback)])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    async def show_shop_result(self, query, section: str):
        data = await self.get_shop_data()
        if data:
            self.last_shop_data = data
            text = self.format_shop_text(data, section)
            extra = [
                [InlineKeyboardButton("🛒 Весь магазин", callback_data="shop_all"),
                 InlineKeyboardButton("✨ Ежедневные", callback_data="shop_daily")],
                [InlineKeyboardButton("🌟 Новинки", callback_data="shop_featured"),
                 InlineKeyboardButton("🎲 Случайный предмет", callback_data="random_item")],
                [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
                 InlineKeyboardButton("🏆 Топ-5", callback_data="top")],
                [InlineKeyboardButton("💱 Курс валют", callback_data="exchange"),
                 InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]
            ]
            await self.edit_message_with_result(query, text, "menu", extra)
        else:
            await query.edit_message_text("😢 Не удалось получить данные магазина")

    async def show_random_item_result(self, query):
        data = await self.get_shop_data()
        if not data:
            await query.edit_message_text("😢 Нет данных")
            return
        items = self.get_all_items(data)
        if not items:
            await query.edit_message_text("😢 В магазине нет предметов")
            return
        item = random.choice(items)
        name = item.get('name', 'Без названия')
        price = item.get('price', 0)
        item_type = item.get('type', 'unknown')
        type_emoji = self.ITEM_TYPE_EMOJI.get(item_type, self.ITEM_TYPE_EMOJI['unknown'])
        type_name = self.ITEM_TYPE_RU.get(item_type, self.ITEM_TYPE_RU['unknown'])
        rarity = self.get_rarity(name)
        rarity_emoji = self.RARITY_EMOJI.get(rarity, '⚪')
        text = (
            f"🎲 **Случайный предмет:**\n\n"
            f"{rarity_emoji}{type_emoji} **{name}**  _({type_name})_\n"
            f"💰 {self.format_price_with_rub(price)}"
        )
        await self.edit_message_with_result(query, text, "menu")

    async def show_stats_result(self, query):
        data = await self.get_shop_data()
        if not data:
            await query.edit_message_text("😢 Нет данных")
            return
        text = self.get_shop_stats(data)
        await self.edit_message_with_result(query, text, "menu")

    async def show_top_result(self, query):
        data = await self.get_shop_data()
        if not data:
            await query.edit_message_text("😢 Нет данных")
            return
        text = self.get_top_items(data, 5)
        await self.edit_message_with_result(query, text, "menu")

    async def show_exchange_result(self, query):
        text = self.get_exchange_info()
        await self.edit_message_with_result(query, text, "menu")

    async def show_search_result(self, query, query_text: str):
        data = await self.get_shop_data()
        if not data:
            await query.edit_message_text("😢 Не удалось получить данные магазина.")
            return
        result = self.search_items(data, query_text)
        await self.edit_message_with_result(query, result, "menu")

    # ---------- Главное меню ----------
    async def show_main_menu(self, update_or_query, is_callback=False):
        menu_text = (
            "👋 **Главное меню**\n\n"
            "Выберите действие:"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Весь магазин", callback_data="shop_all"),
             InlineKeyboardButton("✨ Ежедневные", callback_data="shop_daily")],
            [InlineKeyboardButton("🌟 Новинки", callback_data="shop_featured"),
             InlineKeyboardButton("🎲 Случайный предмет", callback_data="random_item")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
             InlineKeyboardButton("🏆 Топ-5", callback_data="top")],
            [InlineKeyboardButton("💱 Курс валют", callback_data="exchange"),
             InlineKeyboardButton("🌐 Официальный сайт", url="https://www.fortnite.com/item-shop")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_callback:
            await update_or_query.edit_message_text(menu_text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update_or_query.message.reply_text(menu_text, parse_mode='Markdown', reply_markup=reply_markup, disable_web_page_preview=True)

    # ---------- Ночное обновление ----------
    async def night_update(self):
        logger.info("🌙 Ночное обновление в 3:00 МСК")
        text = (
            "🌙 **НОЧНОЕ ОБНОВЛЕНИЕ МАГАЗИНА**\n\n"
            f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')} МСК\n"
            "🛒 Магазин Fortnite обновился!\n\n"
            "👇 Выберите раздел:"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Весь магазин", callback_data="shop_all"),
             InlineKeyboardButton("✨ Ежедневные", callback_data="shop_daily")],
            [InlineKeyboardButton("🌟 Новинки", callback_data="shop_featured"),
             InlineKeyboardButton("🎲 Случайный предмет", callback_data="random_item")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
             InlineKeyboardButton("🏆 Топ-5", callback_data="top")],
            [InlineKeyboardButton("💱 Курс валют", callback_data="exchange"),
             InlineKeyboardButton("🌐 Открыть сайт", url="https://www.fortnite.com/item-shop")]
        ]
        await self.application.bot.send_message(
            self.chat_id, text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------- Обработчики команд ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_main_menu(update, is_callback=False)

    async def shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # При команде /shop отправляем новое сообщение с загрузкой, потом редактируем
        msg = await update.message.reply_text("🔄 Загружаю магазин...")
        data = await self.get_shop_data()
        if data:
            self.last_shop_data = data
            text = self.format_shop_text(data, "all")
            extra = [
                [InlineKeyboardButton("🛒 Весь магазин", callback_data="shop_all"),
                 InlineKeyboardButton("✨ Ежедневные", callback_data="shop_daily")],
                [InlineKeyboardButton("🌟 Новинки", callback_data="shop_featured"),
                 InlineKeyboardButton("🎲 Случайный предмет", callback_data="random_item")],
                [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
                 InlineKeyboardButton("🏆 Топ-5", callback_data="top")],
                [InlineKeyboardButton("💱 Курс валют", callback_data="exchange"),
                 InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]
            ]
            keyboard = extra + [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await msg.edit_text("😢 Не удалось получить данные магазина")

    async def daily(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("✨ Загружаю ежедневные...")
        data = await self.get_shop_data()
        if data:
            text = self.format_shop_text(data, "daily")
            extra = [
                [InlineKeyboardButton("🛒 Весь магазин", callback_data="shop_all"),
                 InlineKeyboardButton("✨ Ежедневные", callback_data="shop_daily")],
                [InlineKeyboardButton("🌟 Новинки", callback_data="shop_featured"),
                 InlineKeyboardButton("🎲 Случайный предмет", callback_data="random_item")],
                [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
                 InlineKeyboardButton("🏆 Топ-5", callback_data="top")],
                [InlineKeyboardButton("💱 Курс валют", callback_data="exchange"),
                 InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]
            ]
            keyboard = extra + [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await msg.edit_text("😢 Не удалось получить данные")

    async def featured(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🌟 Загружаю новинки...")
        data = await self.get_shop_data()
        if data:
            text = self.format_shop_text(data, "featured")
            extra = [
                [InlineKeyboardButton("🛒 Весь магазин", callback_data="shop_all"),
                 InlineKeyboardButton("✨ Ежедневные", callback_data="shop_daily")],
                [InlineKeyboardButton("🌟 Новинки", callback_data="shop_featured"),
                 InlineKeyboardButton("🎲 Случайный предмет", callback_data="random_item")],
                [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
                 InlineKeyboardButton("🏆 Топ-5", callback_data="top")],
                [InlineKeyboardButton("💱 Курс валют", callback_data="exchange"),
                 InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]
            ]
            keyboard = extra + [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await msg.edit_text("😢 Не удалось получить данные")

    async def next_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        delta = target - now
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        text = f"⏳ Следующее обновление магазина через **{hours} ч {minutes} мин** (в 3:00 МСК)."
        await update.message.reply_text(text, parse_mode='Markdown')

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("🔍 Введите запрос после команды, например: `/search Jin`", parse_mode='Markdown')
            return
        query = ' '.join(context.args)
        msg = await update.message.reply_text(f"🔍 Ищу «{query}»...")
        data = await self.get_shop_data()
        if not data:
            await msg.edit_text("😢 Не удалось получить данные магазина.")
            return
        result = self.search_items(data, query)
        extra = []  # Для поиска отдельные кнопки не нужны, только Назад
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(result, parse_mode='Markdown', reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "❓ **Помощь**\n\n"
            "**Команды:**\n"
            "/start – главное меню\n"
            "/shop – весь магазин\n"
            "/daily – ежедневные предметы\n"
            "/featured – новинки\n"
            "/random – случайный предмет\n"
            "/stats – статистика магазина\n"
            "/top – топ-5 самых дорогих\n"
            "/exchange – курс V-Bucks к рублю\n"
            "/search <текст> – поиск предмета\n"
            "/nextupdate – время до обновления\n"
            "/help – это сообщение\n\n"
            "🕒 Автоуведомления каждый день в 3:00 МСК\n\n"
            "💰 **Курс:** 1 V-Buck = 0.499 ₽ \n\n"
            "**Типы предметов:**\n"
            "👕 Костюм, ⛏️ Инструмент, 🪂 Планер, 💃 Эмоция, 🎒 Украшение, 🎁 Обёртка, 📦 Набор, 🎵 Музыка и др.\n\n"
            "🌐 [Официальный магазин](https://www.fortnite.com/item-shop)"
        )
        keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="menu")]]
        await update.message.reply_text(text, parse_mode='Markdown',
                                        reply_markup=InlineKeyboardMarkup(keyboard),
                                        disable_web_page_preview=True)

    # ---------- Обработчик кнопок ----------
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "shop_all":
            await query.edit_message_text("🔄 Загружаю весь магазин...")
            await self.show_shop_result(query, "all")
        elif query.data == "shop_daily":
            await query.edit_message_text("✨ Загружаю ежедневные...")
            await self.show_shop_result(query, "daily")
        elif query.data == "shop_featured":
            await query.edit_message_text("🌟 Загружаю новинки...")
            await self.show_shop_result(query, "featured")
        elif query.data == "random_item":
            await query.edit_message_text("🎲 Выбираю случайный предмет...")
            await self.show_random_item_result(query)
        elif query.data == "stats":
            await query.edit_message_text("📊 Считаю статистику...")
            await self.show_stats_result(query)
        elif query.data == "top":
            await query.edit_message_text("🏆 Составляю топ...")
            await self.show_top_result(query)
        elif query.data == "exchange":
            await query.edit_message_text("💱 Загружаю курс...")
            await self.show_exchange_result(query)
        elif query.data == "refresh":
            if self.last_shop_data:
                await query.edit_message_text("🔄 Обновляю...")
                await self.show_shop_result(query, "all")
            else:
                await query.edit_message_text("Сначала загрузите магазин")
        elif query.data == "help":
            text = (
                "❓ **Быстрая помощь**\n\n"
                "🛒 **Весь магазин** – все предметы\n"
                "✨ **Ежедневные** – только ежедневные\n"
                "🌟 **Новинки** – только новинки\n"
                "🎲 **Случайный предмет** – один предмет\n"
                "📊 **Статистика** – общая информация\n"
                "🏆 **Топ-5** – самые дорогие предметы\n"
                "💱 **Курс валют** – информация о курсе\n"
                "🌐 **Официальный сайт** – открыть в браузере\n\n"
                "💰 **Курс:** 1 V-Buck = 0.499 ₽ \n\n"
                "⏰ Автоуведомления в 3:00 МСК\n\n"
                "**Типы предметов:**\n"
                "👕 Костюм, ⛏️ Инструмент, 🪂 Планер, 💃 Эмоция, 🎒 Украшение, 🎁 Обёртка, 📦 Набор, 🎵 Музыка"
            )
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
            await query.edit_message_text(text, parse_mode='Markdown',
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        elif query.data == "menu":
            await self.show_main_menu(query, is_callback=True)

    # ---------- Настройка планировщика и обработчиков ----------
    def setup(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("shop", self.shop))
        self.application.add_handler(CommandHandler("daily", self.daily))
        self.application.add_handler(CommandHandler("featured", self.featured))
        self.application.add_handler(CommandHandler("nextupdate", self.next_update))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("stats", lambda u,c: asyncio.create_task(self.stats_command(u,c))))
        self.application.add_handler(CommandHandler("top", lambda u,c: asyncio.create_task(self.top_command(u,c))))
        self.application.add_handler(CommandHandler("random", lambda u,c: asyncio.create_task(self.random_command(u,c))))
        self.application.add_handler(CommandHandler("exchange", lambda u,c: asyncio.create_task(self.exchange_command(u,c))))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.scheduler.add_job(self.night_update, CronTrigger(hour=0, minute=0, timezone='UTC'), id="night")
        self.scheduler.start()

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("📊 Загружаю статистику...")
        data = await self.get_shop_data()
        if data:
            text = self.get_shop_stats(data)
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
            await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.edit_text("😢 Нет данных")

    async def top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🏆 Загружаю топ...")
        data = await self.get_shop_data()
        if data:
            text = self.get_top_items(data, 5)
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
            await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg.edit_text("😢 Нет данных")

    async def random_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🎲 Выбираю случайный предмет...")
        data = await self.get_shop_data()
        if not data:
            await msg.edit_text("😢 Нет данных")
            return
        items = self.get_all_items(data)
        if not items:
            await msg.edit_text("😢 В магазине нет предметов")
            return
        item = random.choice(items)
        name = item.get('name', 'Без названия')
        price = item.get('price', 0)
        item_type = item.get('type', 'unknown')
        type_emoji = self.ITEM_TYPE_EMOJI.get(item_type, self.ITEM_TYPE_EMOJI['unknown'])
        type_name = self.ITEM_TYPE_RU.get(item_type, self.ITEM_TYPE_RU['unknown'])
        rarity = self.get_rarity(name)
        rarity_emoji = self.RARITY_EMOJI.get(rarity, '⚪')
        text = (
            f"🎲 **Случайный предмет:**\n\n"
            f"{rarity_emoji}{type_emoji} **{name}**  _({type_name})_\n"
            f"💰 {self.format_price_with_rub(price)}"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def exchange_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("💱 Загружаю курс...")
        text = self.get_exchange_info()
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def run(self):
        self.setup()
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("✅ Бот с улучшенной навигацией запущен")
        await asyncio.Event().wait()

async def main():
    if not TOKEN or not CHAT_ID:
        logger.error("❌ Нет TOKEN или CHAT_ID в .env")
        return
    bot = FortniteShopBot(TOKEN, CHAT_ID)
    try:
        await bot.run()
    except KeyboardInterrupt:
        await bot.application.stop()

if __name__ == "__main__":
    asyncio.run(main())
