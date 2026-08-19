#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1 WIN Bot - Casino & Betting Bot
"""

import os
import json
import random
import logging
import string
import gc
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ======================== SETTINGS ========================
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "123456789").split(",") if id.strip()]
CHANNEL = os.environ.get("CHANNEL", "@onewin")
SUPPORT = "@onewinassist"
TRX_WALLET = os.environ.get("TRX_WALLET", "TEv9t55am7zcCi2Z7dUXtFfKQmofeN7e1r")
USDT_WALLET = os.environ.get("USDT_WALLET", "TEVuvWZ68UbDUdzpd6EqxncsqDVjwyY7cj")

BOT_USERNAME = "onewin_rubot"  # ✅ نام کاربری ربات

MIN_BET = 10
GIFT_AMOUNT = 100
MIN_WITHDRAW = 250
MIN_DEPOSIT = 1000
COMMISSION_PERCENT = 30
INITIAL_BALANCE = 0
INACTIVE_BONUS = 50
INACTIVE_HOURS = 24

BOT_NAME = "1 WIN"

# ======================== WEB SERVER ========================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return jsonify({"status": "running", "bot": "1win"})

@flask_app.route("/health")
def health():
    return jsonify({"status": "ok"})

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ======================== DATABASE ========================
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DATA_FILE = os.path.join(DATA_DIR, "users.json")
ADMIN_CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json")

def load_json(file_path, default=None):
    if default is None:
        default = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

users = load_json(DATA_FILE)
admin_config = load_json(ADMIN_CONFIG_FILE, {
    "deposit_enable_date": "30 August",
    "trx_wallet": TRX_WALLET,
    "usdt_wallet": USDT_WALLET,
    "channels": [{"link": CHANNEL, "enabled": True}],
    "min_bet": MIN_BET,
    "min_deposit": MIN_DEPOSIT,
    "min_withdraw": MIN_WITHDRAW,
    "gift_amount": GIFT_AMOUNT,
    "commission_percent": COMMISSION_PERCENT,
    "bot_enabled": True,
    "games": {"dice": True, "coin": True, "slot": True, "football": True},
    "slot_coeffs": {
        "💎💎💎": 100, "⭐⭐⭐": 50, "777": 20,
        "🍇🍇🍇": 15, "🍋🍋🍋": 10, "🍒🍒🍒": 5, "two_same": 2
    }
})

# ======================== HELPER FUNCTIONS ========================
def format_russian_number(num):
    """Convert number to Russian format with space as thousand separator"""
    return f"{num:,}".replace(",", " ")

def get_user(user_id):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "balance": INITIAL_BALANCE,
            "username": None,
            "free_gift_used": False,
            "referral_code": generate_referral_code(),
            "referred_by": None,
            "referral_count": 0,
            "referral_gift": 0,
            "referral_commission": 0,
            "commission_percent": COMMISSION_PERCENT,
            "banned": False,
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "has_deposited": False,
            "transactions": [],
            "created_at": str(datetime.now()),
            "last_activity": str(datetime.now()),
            "inactive_warning_sent": False
        }
        save_json(DATA_FILE, users)
    return users[uid]

def save_user(user_id, data):
    users[str(user_id)] = data
    save_json(DATA_FILE, users)

def generate_referral_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))

def add_transaction(user_id, amount, trans_type, description=""):
    user = get_user(user_id)
    user["transactions"].append({
        "date": datetime.now().strftime("%Y/%m/%d - %H:%M"),
        "type": trans_type,
        "amount": amount,
        "balance_after": user["balance"],
        "description": description
    })
    if len(user["transactions"]) > 100:
        user["transactions"] = user["transactions"][-100:]
    save_user(user_id, user)

def update_last_activity(user_id):
    """Update user's last activity timestamp"""
    user = get_user(user_id)
    user["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user["inactive_warning_sent"] = False
    save_user(user_id, user)

# ======================== MAIN MENU ========================
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎲 Играть", callback_data="game_menu")],
        [InlineKeyboardButton("👤 Мой счёт", callback_data="my_account")],
        [InlineKeyboardButton("🎁 Получить бонус", callback_data="gift")],
        [InlineKeyboardButton("❓ Как доверять?", callback_data="trust")]
    ]
    
    text = f"""<b>🎰 1 WIN</b>

👤 Пользователь: @{user['username'] or 'Пользователь'}
💰 Баланс: {format_russian_number(user['balance'])} RUB

✅ Вывод в рублях
👥 За каждого приглашённого — {GIFT_AMOUNT} RUB бонус

🆘 Поддержка: {SUPPORT}

Выберите действие из меню:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== START ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    user = get_user(user_id)
    user["username"] = username
    update_last_activity(user_id)
    save_user(user_id, user)
    
    if context.args and context.args[0].startswith("ref_"):
        ref_code = context.args[0][4:]
        for uid, data in users.items():
            if data.get("referral_code") == ref_code and int(uid) != user_id:
                user["referred_by"] = ref_code
                save_user(user_id, user)
                break
    
    channels = admin_config.get("channels", [{"link": CHANNEL, "enabled": True}])
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    channel_count = len(enabled_channels)
    
    if user.get("free_gift_used", False):
        keyboard = [
            [InlineKeyboardButton("🎲 Играть", callback_data="game_menu")],
            [InlineKeyboardButton("👤 Мой счёт", callback_data="my_account")],
            [InlineKeyboardButton("🎁 Получить бонус", callback_data="gift")],
            [InlineKeyboardButton("❓ Как доверять?", callback_data="trust")]
        ]
        text = f"""<b>🎰 1 WIN</b>

👤 Пользователь: @{username or 'Пользователь'}
💰 Баланс: {format_russian_number(user['balance'])} RUB

✅ Вывод в рублях
👥 За каждого приглашённого — {admin_config.get('gift_amount', GIFT_AMOUNT)} RUB бонус

🆘 Поддержка: {SUPPORT}

Выберите действие из меню:"""
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return
    
    keyboard = []
    for i, channel in enumerate(enabled_channels, 1):
        link = channel["link"]
        label = f"📢 Подписаться на канал {i}" if channel_count > 1 else "📢 Подписаться на канал"
        keyboard.append([InlineKeyboardButton(label, url=f"https://t.me/{link[1:]}")])
    keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data="check_gift")])
    
    if channel_count == 1:
        channels_text = f"1️⃣ {enabled_channels[0]['link']}"
        channel_word = "канал"
    else:
        channels_text = "\n".join([f"{i+1}️⃣ {c['link']}" for i, c in enumerate(enabled_channels)])
        channel_word = "каналы"
    
    gift_amount = admin_config.get("gift_amount", GIFT_AMOUNT)
    text = f"""<b>🎁 Бонус за подписку: {gift_amount} RUB</b>

Подпишитесь на наш {channel_word} и получите бонус!

<b>📌 {channel_word.capitalize()} для подписки:</b>

{channels_text}

После подписки нажмите кнопку «✅ Я подписался»."""
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def check_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    channels = admin_config.get("channels", [{"link": CHANNEL, "enabled": True}])
    enabled_channels = [c for c in channels if c.get("enabled", True)]
    
    all_member = True
    for channel in enabled_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["link"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                all_member = False
                break
        except:
            all_member = False
            break
    
    if all_member:
        gift_amount = admin_config.get("gift_amount", GIFT_AMOUNT)
        user["free_gift_used"] = True
        user["balance"] += gift_amount
        add_transaction(user_id, gift_amount, "gift", f"Бонус за подписку {gift_amount} RUB")
        save_user(user_id, user)
        
        referrer_code = user.get("referred_by")
        if referrer_code:
            for uid, data in users.items():
                if data.get("referral_code") == referrer_code:
                    referrer_id = int(uid)
                    referrer = get_user(referrer_id)
                    referrer["balance"] += gift_amount
                    referrer["referral_count"] = referrer.get("referral_count", 0) + 1
                    referrer["referral_gift"] = referrer.get("referral_gift", 0) + gift_amount
                    add_transaction(referrer_id, gift_amount, "referral_gift", f"Бонус за приглашение {gift_amount} RUB")
                    save_user(referrer_id, referrer)
                    try:
                        await context.bot.send_message(
                            referrer_id,
                            f"""<b>🎉 Новый пользователь по вашей ссылке!</b>

👤 Новый пользователь: @{user['username'] or user_id}
🎁 Бонус: {gift_amount} RUB добавлен на ваш счет.

<b>📊 Ваша статистика:</b>
👥 Всего приглашений: {referrer.get('referral_count', 0)}
💰 Получено бонусов: {format_russian_number(referrer.get('referral_gift', 0))} RUB""",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"Error sending message to referrer: {e}")
                    break
        
        text = f"""<b>✅ Поздравляем! Подписка подтверждена.</b>

🎁 {gift_amount} RUB бонус добавлен на ваш счет.
💰 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Играть", callback_data="game_menu")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]), parse_mode="HTML")
    else:
        keyboard = []
        for i, channel in enumerate(enabled_channels, 1):
            link = channel["link"]
            label = f"📢 Подписаться на канал {i}" if len(enabled_channels) > 1 else "📢 Подписаться на канал"
            keyboard.append([InlineKeyboardButton(label, url=f"https://t.me/{link[1:]}")])
        keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data="check_gift")])
        
        await query.edit_message_text(
            "❌ Вы ещё не подписались на все каналы!\n\nПожалуйста, подпишитесь на все каналы выше, затем нажмите «Я подписался».",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ======================== GAMES MENU ========================
async def game_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    update_last_activity(user_id)
    
    games = admin_config.get("games", {})
    keyboard = []
    
    if games.get("dice", True):
        keyboard.append([InlineKeyboardButton("🎲 Кости", callback_data="dice_game")])
    if games.get("coin", True):
        keyboard.append([InlineKeyboardButton("🪙 Орёл или решка", callback_data="coin_game")])
    if games.get("slot", True):
        keyboard.append([InlineKeyboardButton("🎰 Слоты", callback_data="slot_game")])
    if games.get("football", True):
        keyboard.append([InlineKeyboardButton("⚽ Футбол", callback_data="football_game")])
    
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
    
    await query.edit_message_text("<b>🎮 Игры 1 WIN</b>\n\nВыберите игру:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== DICE GAME ========================
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="dice_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="dice_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="dice_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="dice_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="dice_bet_200"),
         InlineKeyboardButton("500 RUB", callback_data="dice_bet_500")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    text = f"""<b>🎲 Игра в кости</b>

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
📌 Выберите сумму ставки:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def dice_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        text = f"""❌ Недостаточно средств!

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
🎯 Сумма ставки: {amount} RUB"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="dice_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]), parse_mode="HTML")
        return
    
    context.user_data["dice_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("🎯 Чётное | Коэф. 2", callback_data="dice_coef_even")],
        [InlineKeyboardButton("🎯 Нечётное | Коэф. 2", callback_data="dice_coef_odd")],
        [InlineKeyboardButton("🎯 Сумма ≥ 10 | Коэф. 3", callback_data="dice_coef_high")],
        [InlineKeyboardButton("🎯 Обе кости одинаковые | Коэф. 5", callback_data="dice_coef_same")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    
    text = f"""<b>🎲 Выбор коэффициента</b>

💰 Сумма ставки: {amount} RUB

<b>📌 Выберите один из коэффициентов:</b>

• Чётное — сумма 2 костей чётная (коэф. 2)
• Нечётное — сумма 2 костей нечётная (коэф. 2)
• Сумма 10 или больше — сумма 2 костей ≥ 10 (коэф. 3)
• Обе кости одинаковые — выпало одинаковое число (коэф. 5)"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def dice_coef_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    bet_amount = context.user_data.get("dice_amount", 0)
    if bet_amount == 0:
        await query.edit_message_text("❌ Ошибка! Пожалуйста, начните заново.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Игра в кости", callback_data="dice_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]))
        return
    
    choice = query.data.split("_")[2]
    context.user_data["dice_choice"] = choice
    
    text = f"""<b>🎲 Бросок костей...</b>

💰 Сумма ставки: {bet_amount} RUB
🎯 Ваш выбор: {choice}

⏳ Пожалуйста, подождите..."""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Бросить кости", callback_data="dice_roll")]
    ]), parse_mode="HTML")

async def dice_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    bet_amount = context.user_data.get("dice_amount", 0)
    choice = context.user_data.get("dice_choice", "")
    
    if bet_amount == 0 or choice == "":
        await query.edit_message_text("❌ Ошибка! Пожалуйста, начните заново.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Игра в кости", callback_data="dice_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]))
        return
    
    await query.edit_message_text("🎲 Бросок костей...")
    
    dice1 = await query.message.reply_dice(emoji="🎲")
    dice2 = await query.message.reply_dice(emoji="🎲")
    
    value1 = dice1.dice.value
    value2 = dice2.dice.value
    total = value1 + value2
    
    is_win = False
    coefficient = 0
    win_description = ""
    
    if choice == "even":
        coefficient = 2
        is_win = (total % 2 == 0)
        win_description = f"сумма {total} чётная"
    elif choice == "odd":
        coefficient = 2
        is_win = (total % 2 == 1)
        win_description = f"сумма {total} нечётная"
    elif choice == "high":
        coefficient = 3
        is_win = (total >= 10)
        win_description = f"сумма {total} (≥ 10)"
    elif choice == "same":
        coefficient = 5
        is_win = (value1 == value2)
        win_description = f"кости одинаковые! ({value1} и {value2})"
    else:
        coefficient = 0
        is_win = False
    
    choice_names = {
        "even": "Чётное",
        "odd": "Нечётное",
        "high": "Сумма ≥ 10",
        "same": "Обе кости одинаковые"
    }
    choice_name = choice_names.get(choice, choice)
    
    if is_win:
        win_amount = bet_amount * coefficient
        user["balance"] += win_amount
        user["total_wins"] = user.get("total_wins", 0) + 1
        
        result_text = f"""<b>🎉 Поздравляем! Вы выиграли!</b>

<b>🎲 Результат броска костей:</b>
Кость 1: {value1} | Кость 2: {value2}
📊 Сумма: {total}
🎯 Ваш выбор: {choice_name}
✅ Результат: {win_description}
📊 Коэффициент: {coefficient}×
💰 Ставка: {bet_amount} RUB
🏆 Выигрыш: {win_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, win_amount, "win", f"Выигрыш в кости - {choice_name}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        
        result_text = f"""<b>😔 К сожалению... Вы проиграли.</b>

<b>🎲 Результат броска костей:</b>
Кость 1: {value1} | Кость 2: {value2}
📊 Сумма: {total}
🎯 Ваш выбор: {choice_name}
💰 Ставка: {bet_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, -bet_amount, "bet", f"Проигрыш в кости - {choice_name}")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["dice_amount"] = 0
    context.user_data["dice_choice"] = ""
    
    keyboard = [
        [InlineKeyboardButton("🎲 Ещё раз", callback_data="dice_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== COIN GAME ========================
async def coin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="coin_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="coin_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="coin_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="coin_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="coin_bet_200"),
         InlineKeyboardButton("500 RUB", callback_data="coin_bet_500")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    text = f"""<b>🪙 Орёл или решка</b>

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
📊 Коэффициент: <b>2.5</b>

📌 Выберите сумму ставки:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def coin_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        text = f"""❌ Недостаточно средств!

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
🎯 Сумма ставки: {amount} RUB"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="coin_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]), parse_mode="HTML")
        return
    
    context.user_data["coin_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("🦅 Орёл", callback_data="coin_predict_heads")],
        [InlineKeyboardButton("📍 Решка", callback_data="coin_predict_tails")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    
    text = f"""<b>🪙 Орёл или решка</b>

💰 Сумма ставки: {amount} RUB
📊 Коэффициент: <b>2.5</b>

📌 Чётное = Орёл 🦅 | Нечётное = Решка 📍

Сделайте выбор:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def coin_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    bet_amount = context.user_data.get("coin_amount", 0)
    if bet_amount == 0:
        await query.edit_message_text("❌ Ошибка! Пожалуйста, начните заново.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Орёл или решка", callback_data="coin_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]))
        return
    
    choice = query.data.split("_")[2]
    
    await query.edit_message_text("🪙 Бросок монеты...")
    dice_message = await query.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    
    is_heads = dice_value in [2, 4, 6]
    result_name = "Орёл 🦅" if is_heads else "Решка 📍"
    is_win = (choice == "heads" and is_heads) or (choice == "tails" and not is_heads)
    
    if is_win:
        win_amount = int(bet_amount * 2.5)
        user["balance"] += win_amount
        user["total_wins"] = user.get("total_wins", 0) + 1
        result_text = f"""<b>🎉 Поздравляем! Вы выиграли!</b>

🪙 Результат: {result_name}
🎲 Число кубика: {dice_value} ({'Чётное' if is_heads else 'Нечётное'})
💰 Ставка: {bet_amount} RUB
📊 Коэффициент: 2.5×
🏆 Выигрыш: {win_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, win_amount, "win", "Выигрыш в орёл или решка")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        result_text = f"""<b>😔 К сожалению... Вы проиграли.</b>

🪙 Результат: {result_name}
🎲 Число кубика: {dice_value} ({'Чётное' if is_heads else 'Нечётное'})
💰 Ставка: {bet_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, -bet_amount, "bet", "Проигрыш в орёл или решка")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["coin_amount"] = 0
    
    keyboard = [
        [InlineKeyboardButton("🪙 Ещё раз", callback_data="coin_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== SLOT GAME ========================
async def slot_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="slot_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="slot_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="slot_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="slot_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="slot_bet_200"),
         InlineKeyboardButton("500 RUB", callback_data="slot_bet_500")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    slot_coeffs = admin_config.get("slot_coeffs", {})
    text = f"""<b>🎰 Слоты</b>

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
<b>📊 Коэффициенты:</b>
💎💎💎 = {slot_coeffs.get('💎💎💎', 100)}× | ⭐⭐⭐ = {slot_coeffs.get('⭐⭐⭐', 50)}×
777 = {slot_coeffs.get('777', 20)}× | 🍇🍇🍇 = {slot_coeffs.get('🍇🍇🍇', 15)}×
🍋🍋🍋 = {slot_coeffs.get('🍋🍋🍋', 10)}× | 🍒🍒🍒 = {slot_coeffs.get('🍒🍒🍒', 5)}×
2 одинаковых = {slot_coeffs.get('two_same', 2)}×

📌 Выберите сумму ставки:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def slot_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        text = f"""❌ Недостаточно средств!

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
🎯 Сумма ставки: {amount} RUB"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="slot_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]), parse_mode="HTML")
        return
    
    context.user_data["slot_amount"] = amount
    
    text = f"""<b>🎰 Слоты</b>

💰 Сумма ставки: {amount} RUB

Нажмите кнопку чтобы запустить слоты:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Запустить слоты", callback_data="slot_spin")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]), parse_mode="HTML")

async def slot_spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    bet_amount = context.user_data.get("slot_amount", 0)
    
    if bet_amount == 0:
        await query.edit_message_text("❌ Ошибка! Пожалуйста, начните заново.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Слоты", callback_data="slot_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]))
        return
    
    await query.edit_message_text("🎰 Запуск слотов...")
    dice_message = await query.message.reply_dice(emoji="🎰")
    dice_value = dice_message.dice.value
    
    slot_emojis = ["🍇", "🍋", "7", "BAR"]
    result = [
        slot_emojis[(dice_value - 1) // 16 % 4],
        slot_emojis[(dice_value - 1) // 4 % 4],
        slot_emojis[(dice_value - 1) % 4]
    ]
    combo = "".join(result)
    
    slot_coeffs = admin_config.get("slot_coeffs", {})
    coefficient = slot_coeffs.get(combo, 0)
    if coefficient == 0 and (result[0] == result[1] or result[1] == result[2] or result[0] == result[2]):
        coefficient = slot_coeffs.get("two_same", 2)
    
    if coefficient > 0:
        win_amount = bet_amount * coefficient
        user["balance"] += win_amount
        user["total_wins"] = user.get("total_wins", 0) + 1
        result_text = f"""<b>🎉 Поздравляем! Вы выиграли!</b>

🎰 Результат слотов:
[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]

📊 Комбинация: {combo}
🎯 Коэффициент: {coefficient}×
💰 Ставка: {bet_amount} RUB
🏆 Выигрыш: {win_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, win_amount, "win", f"Выигрыш в слотах - {combo}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        result_text = f"""<b>😔 К сожалению... Вы проиграли.</b>

🎰 Результат слотов:
[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]

📊 Комбинация: {combo}
🎯 Коэффициент: 0×
💰 Ставка: {bet_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, -bet_amount, "bet", "Проигрыш в слотах")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["slot_amount"] = 0
    
    keyboard = [
        [InlineKeyboardButton("🎰 Ещё раз", callback_data="slot_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== FOOTBALL GAME ========================
async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="football_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="football_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="football_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="football_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="football_bet_200"),
         InlineKeyboardButton("500 RUB", callback_data="football_bet_500")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    text = f"""<b>⚽ Футбол</b>

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
📊 Коэффициент: <b>2.5</b>

📌 Выберите сумму ставки:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def football_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        text = f"""❌ Недостаточно средств!

💰 Ваш баланс: {format_russian_number(user['balance'])} RUB
🎯 Сумма ставки: {amount} RUB"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="football_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]), parse_mode="HTML")
        return
    
    context.user_data["football_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("⚽️ Будет гол (коэф. 2.5)", callback_data="football_predict_goal")],
        [InlineKeyboardButton("❌ Гола не будет (коэф. 2.5)", callback_data="football_predict_miss")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    
    text = f"""<b>⚽ Прогноз на футбол</b>

💰 Сумма ставки: {amount} RUB
📊 Коэффициент: <b>2.5</b>

Мяч летит к воротам!"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def football_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    bet_amount = context.user_data.get("football_amount", 0)
    prediction = query.data.split("_")[2]
    
    if bet_amount == 0:
        await query.edit_message_text("❌ Ошибка! Пожалуйста, начните заново.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Футбол", callback_data="football_game")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]))
        return
    
    await query.edit_message_text("⚽ Удар...")
    dice_message = await query.message.reply_dice(emoji="⚽")
    dice_value = dice_message.dice.value
    
    is_goal = dice_value >= 4
    result_text = "Гол ✅" if is_goal else "Гола нет ❌"
    is_win = (prediction == "goal" and is_goal) or (prediction == "miss" and not is_goal)
    
    if is_win:
        win_amount = int(bet_amount * 2.5)
        user["balance"] += win_amount
        user["total_wins"] = user.get("total_wins", 0) + 1
        result_msg = f"""<b>🎉 Поздравляем! Вы выиграли!</b>

⚽ Результат удара: {result_text}
🎯 Прогноз: {'Будет гол' if prediction == 'goal' else 'Гола не будет'} ✅
💰 Ставка: {bet_amount} RUB
📊 Коэффициент: 2.5×
🏆 Выигрыш: {win_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, win_amount, "win", "Выигрыш в футболе")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        result_msg = f"""<b>😔 К сожалению... Вы проиграли.</b>

⚽ Результат удара: {result_text}
🎯 Прогноз: {'Будет гол' if prediction == 'goal' else 'Гола не будет'}
💰 Ставка: {bet_amount} RUB

💳 Новый баланс: {format_russian_number(user['balance'])} RUB"""
        add_transaction(user_id, -bet_amount, "bet", "Проигрыш в футболе")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["football_amount"] = 0
    
    keyboard = [
        [InlineKeyboardButton("⚽ Ещё раз", callback_data="football_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== MY ACCOUNT ========================
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    total_bets = user.get("total_bets", 0)
    wins = user.get("total_wins", 0)
    losses = user.get("total_losses", 0)
    win_rate = round((wins / total_bets * 100) if total_bets > 0 else 0, 1)
    
    text = f"""<b>👤 Мой счёт</b>

🆔 Номер пользователя: {user_id}
👥 Успешных приглашений: {user.get('referral_count', 0)}
📊 Всего ставок: {total_bets} | Побед: {wins} | Поражений: {losses}
📈 Процент побед: {win_rate}%
💰 Баланс: {format_russian_number(user['balance'])} RUB"""
    
    keyboard = [
        [InlineKeyboardButton("💳 Пополнить", callback_data="deposit")],
        [InlineKeyboardButton("🏦 Вывести", callback_data="withdraw")],
        [InlineKeyboardButton("📜 История", callback_data="transactions")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== DEPOSIT ========================
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    trx_wallet = admin_config.get("trx_wallet", TRX_WALLET)
    usdt_wallet = admin_config.get("usdt_wallet", USDT_WALLET)
    
    bonus_text = ""
    if not user.get("has_deposited", False):
        bonus_text = "<b>🎁 Бонус за первое пополнение: 50% до 2 500 RUB</b>\n\n"
    
    text = f"""<b>💳 Пополнение баланса</b>

💰 Минимальная сумма пополнения: {MIN_DEPOSIT} RUB

{bonus_text}
━━━━━━━━━━━━━━━━━━━━━━
<b>📌 Банковская карта для пополнения:</b>
❌ Временно недоступна.

━━━━━━━━━━━━━━━━━━━━━━
<b>🟣 TRX-кошелёк (TRC20):</b>
<code>{trx_wallet}</code>

📋 Нажмите на адрес, чтобы скопировать

━━━━━━━━━━━━━━━━━━━━━━
<b>🟢 USDT-кошелёк (TRC20):</b>
<code>{usdt_wallet}</code>

📋 Нажмите на адрес, чтобы скопировать

━━━━━━━━━━━━━━━━━━━━━━
<b>📌 Важная информация:</b>
• Минимальная сумма пополнения: {MIN_DEPOSIT} RUB
• Используйте сеть TRC20
• После пополнения отправьте скриншот администратору
• Все пополнения проверяются и подтверждаются вручную

━━━━━━━━━━━━━━━━━━━━━━
<b>📌 Администратор для отправки скриншота:</b>

🆔 {SUPPORT}

📋 Нажмите на ID и отправьте скриншот

🆘 Поддержка: {SUPPORT}"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== WITHDRAW ========================
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    if not user.get("has_deposited", False):
        text = """<b>❌ Вывод средств недоступен!</b>

Вы ещё не пополняли баланс.

📌 Вывод доступен только после <b>первого пополнения</b>.

Пополните баланс через «💳 Пополнить»."""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Пополнить", callback_data="deposit")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]), parse_mode="HTML")
        return
    
    balance = user["balance"]
    min_withdraw = admin_config.get("min_withdraw", MIN_WITHDRAW)
    
    keyboard = []
    amounts = [250, 500, 1000, 2000, 5000]
    row = []
    for amount in amounts:
        if amount >= min_withdraw and amount <= balance:
            row.append(InlineKeyboardButton(f"{amount} RUB", callback_data=f"withdraw_{amount}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
        text = f"""<b>🏦 Вывод средств</b>

💰 Доступный баланс: {format_russian_number(balance)} RUB
📌 Минимальная сумма вывода: {min_withdraw} RUB

❌ Недостаточно средств для вывода!"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
    
    text = f"""<b>🏦 Вывод средств</b>

💰 Доступный баланс: {format_russian_number(balance)} RUB
📌 Минимальная сумма вывода: {min_withdraw} RUB

📌 Выберите сумму:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def withdraw_amount_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    amount = int(query.data.split("_")[1])
    context.user_data["withdraw_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("💳 Номер карты", callback_data="withdraw_card")],
        [InlineKeyboardButton("🟣 Адрес кошелька (TRX)", callback_data="withdraw_wallet")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    
    text = f"""✅ Сумма {amount} RUB зарегистрирована для вывода.

Выберите один из способов:"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def withdraw_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["withdraw_method"] = "card"
    await query.edit_message_text(
        "<b>💳 Вывод на карту</b>\n\nВведите номер карты (16 цифр):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]]),
        parse_mode="HTML"
    )

async def withdraw_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["withdraw_method"] = "wallet"
    await query.edit_message_text(
        "<b>🟣 Вывод на TRX-кошелёк</b>\n\nВведите адрес TRX-кошелька:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]]),
        parse_mode="HTML"
    )

async def handle_withdraw_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    info = update.message.text.strip()
    amount = context.user_data.get("withdraw_amount", 0)
    method = context.user_data.get("withdraw_method", "unknown")
    
    user["balance"] -= amount
    add_transaction(user_id, -amount, "withdraw", f"Вывод - {method}")
    save_user(user_id, user)
    
    method_name = "Номер карты" if method == "card" else "Адрес кошелька"
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"""<b>🏦 Новый запрос на вывод</b>

👤 Пользователь: @{user['username'] or user_id}
💰 Сумма: {amount} RUB
📌 Способ: {method_name}
📋 Информация: {info}""",
                parse_mode="HTML"
            )
        except:
            pass
    
    await update.message.reply_text(
        f"""<b>✅ Запрос на вывод зарегистрирован!</b>

💰 Сумма: {amount} RUB
🕒 Запрос отправлен на обработку.
По вопросам обращайтесь: {SUPPORT}""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]),
        parse_mode="HTML"
    )

# ======================== TRANSACTIONS ========================
async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    trans = user.get("transactions", [])[-10:]
    if not trans:
        text = "<b>📜 История транзакций</b>\n\nНет транзакций."
    else:
        text = "<b>📜 История транзакций</b>\n\n"
        for t in trans[-10:]:
            emoji = "💰" if t["amount"] > 0 else "💸"
            text += f"{t['date']} | {emoji} {format_russian_number(t['amount'])} RUB | Баланс: {format_russian_number(t['balance_after'])} RUB\n"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Мой счёт", callback_data="my_account")]]), parse_mode="HTML")

# ======================== GIFT ========================
async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    update_last_activity(user_id)
    
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user['referral_code']}"
    commission_percent = user.get("commission_percent", COMMISSION_PERCENT)
    
    text = f"""<b>🎁 Бонус и комиссия</b>

<b>📌 Ваш процент комиссии:</b> {commission_percent}%

👤 За каждого приглашённого — {admin_config.get('gift_amount', GIFT_AMOUNT)} RUB бонус
💰 С каждого пополнения реферала — {commission_percent}% комиссия

<b>🔗 Ваша реферальная ссылка:</b>
<code>{link}</code>

📋 Нажмите на ссылку, чтобы скопировать

<b>📊 Ваша статистика:</b>
👥 Успешных приглашений: {user.get('referral_count', 0)}
💰 Получено бонусов: {format_russian_number(user.get('referral_gift', 0))} RUB
💸 Получено комиссии: {format_russian_number(user.get('referral_commission', 0))} RUB"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ======================== TRUST ========================
async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    update_last_activity(user_id)
    
    text = f"""<b>❓ Как доверять?</b>

Мы понимаем, что доверие к онлайн-сервису может быть сложным.

Чтобы вы могли начать с уверенностью, мы дарим <b>{admin_config.get('gift_amount', GIFT_AMOUNT)} RUB бонус</b> при подписке на наш канал.

Мы стремимся предоставить приятный и честный игровой опыт для всех пользователей. ❤️"""
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]]), parse_mode="HTML")

# ======================== CHECK INACTIVE USERS ========================
async def check_inactive_users(app: Application):
    """Check users who haven't played for 24 hours and send them a bonus"""
    bot = app.bot
    now = datetime.now()
    
    for uid, data in users.items():
        if data.get("banned", False):
            continue
        
        if data.get("inactive_warning_sent", False):
            continue
        
        last_activity = data.get("last_activity")
        if not last_activity:
            last_activity = data.get("created_at", now.strftime("%Y-%m-%d %H:%M:%S"))
        
        try:
            last_time = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
            diff = (now - last_time).total_seconds() / 3600
            
            if diff >= INACTIVE_HOURS:
                user = get_user(uid)
                user["balance"] += INACTIVE_BONUS
                user["inactive_warning_sent"] = True
                add_transaction(uid, INACTIVE_BONUS, "gift", f"Бонус за неактивность {INACTIVE_BONUS} RUB")
                save_user(uid, user)
                
                try:
                    await bot.send_message(
                        chat_id=int(uid),
                        text=f"""<b>🎰 1 WIN</b>

👋 Здравствуйте! Мы заметили, что вы давно не играли.

🎲 Для вас доступны новые игры и призы!

💰 В качестве подарка на ваш счёт начислено {INACTIVE_BONUS} RUB для начала игры!

🆘 Поддержка: {SUPPORT}

👉 Для начала нажмите /start""",
                        parse_mode="HTML"
                    )
                    print(f"✅ Message sent to inactive user {uid} with bonus {INACTIVE_BONUS} RUB")
                except Exception as e:
                    print(f"❌ Failed to send message to user {uid}: {e}")
        except Exception as e:
            print(f"❌ Error processing user {uid}: {e}")

# ======================== ADMIN PANEL ========================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("🔙 Close", callback_data="admin_close")]
    ]
    await update.message.reply_text("<b>👑 1 WIN Admin Panel</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total = len(users)
    total_balance = sum(u["balance"] for u in users.values())
    banned = sum(1 for u in users.values() if u.get("banned", False))
    text = f"""<b>📊 Statistics</b>

👥 Total users: {total}
🚫 Banned users: {banned}
💰 Total balance: {format_russian_number(total_balance)} RUB"""
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]), parse_mode="HTML")

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🔍 Search User", callback_data="admin_search")],
        [InlineKeyboardButton("💸 Balance", callback_data="admin_balance")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("📨 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎁 Global Gift", callback_data="admin_global_gift")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
    ]
    await query.edit_message_text("<b>👥 Users Management</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📅 Change Deposit Date", callback_data="admin_set_date")],
        [InlineKeyboardButton("🔄 Change Wallets", callback_data="admin_set_wallets")],
        [InlineKeyboardButton("🎯 Change Limits", callback_data="admin_change_limits")],
        [InlineKeyboardButton("🎲 Manage Games", callback_data="admin_manage_games")],
        [InlineKeyboardButton("🔌 Bot Status", callback_data="admin_toggle_bot")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
    ]
    await query.edit_message_text("<b>⚙️ Settings</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_panel(update, context)

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔐 Admin panel closed.")

async def admin_toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = admin_config.get("bot_enabled", True)
    admin_config["bot_enabled"] = not current
    save_json(ADMIN_CONFIG_FILE, admin_config)
    status_text = "✅ Enabled" if admin_config["bot_enabled"] else "❌ Disabled"
    await query.edit_message_text(
        f"""<b>🔌 Bot status changed!</b>

📌 New status: {status_text}""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Toggle", callback_data="admin_toggle_bot")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )

async def admin_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>📅 Change Deposit Date</b>

📌 Current date: {admin_config.get('deposit_enable_date', '30 August')}

Enter new date:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_set_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>🔄 Change Wallets</b>

🟣 Current TRX wallet:
<code>{admin_config.get('trx_wallet', TRX_WALLET)}</code>

🟢 Current USDT wallet:
<code>{admin_config.get('usdt_wallet', USDT_WALLET)}</code>

Select wallet to change:""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Change TRX", callback_data="admin_edit_trx")],
            [InlineKeyboardButton("✏️ Change USDT", callback_data="admin_edit_usdt")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )

async def admin_edit_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>✏️ Change TRX Wallet</b>

📌 Current address:
<code>{admin_config.get('trx_wallet', TRX_WALLET)}</code>

Enter new TRX address:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_edit_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>✏️ Change USDT Wallet</b>

📌 Current address:
<code>{admin_config.get('usdt_wallet', USDT_WALLET)}</code>

Enter new USDT address:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_change_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>🎯 Change Limits</b>

💰 Minimum bet: {admin_config.get('min_bet', MIN_BET)} RUB
💰 Minimum deposit: {admin_config.get('min_deposit', MIN_DEPOSIT)} RUB
💰 Minimum withdraw: {admin_config.get('min_withdraw', MIN_WITHDRAW)} RUB

Select limit to change:""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Min Bet", callback_data="admin_edit_min_bet")],
            [InlineKeyboardButton("✏️ Min Deposit", callback_data="admin_edit_min_deposit")],
            [InlineKeyboardButton("✏️ Min Withdraw", callback_data="admin_edit_min_withdraw")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )

async def admin_edit_min_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>✏️ Change Minimum Bet</b>

📌 Current minimum bet: {admin_config.get('min_bet', MIN_BET)} RUB

Enter new amount:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_edit_min_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>✏️ Change Minimum Deposit</b>

📌 Current minimum deposit: {admin_config.get('min_deposit', MIN_DEPOSIT)} RUB

Enter new amount:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_edit_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"""<b>✏️ Change Minimum Withdraw</b>

📌 Current minimum withdraw: {admin_config.get('min_withdraw', MIN_WITHDRAW)} RUB

Enter new amount:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_manage_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = admin_config.get("games", {})
    text = "<b>🎲 Manage Games</b>\n\nCurrent status:\n"
    for game, status in games.items():
        text += f"✅ {game}: {'Enabled' if status else 'Disabled'}\n"
    
    keyboard = []
    for game in games.keys():
        keyboard.append([InlineKeyboardButton(f"🔄 Toggle {game}", callback_data=f"admin_toggle_game_{game}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_toggle_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split("_")[3]
    games = admin_config.get("games", {})
    games[game] = not games.get(game, True)
    admin_config["games"] = games
    save_json(ADMIN_CONFIG_FILE, admin_config)
    
    await query.edit_message_text(
        f"""✅ Game {game} toggled successfully.
📌 New status: {'Enabled' if games[game] else 'Disabled'}""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Manage Games", callback_data="admin_manage_games")]]),
        parse_mode="HTML"
    )

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>🚫 Ban User</b>\n\nEnter user ID:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>📨 Broadcast</b>\n\nEnter your message:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_global_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>🎁 Global Gift</b>\n\nEnter amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>💸 Balance Management</b>\n\nEnter user ID:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>🔍 Search User</b>\n\nEnter user ID:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

# ======================== ADMIN COMMANDS ========================
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    action = context.user_data.get("admin_action")
    
    if action == "ban":
        try:
            target = int(text)
            user = get_user(target)
            if target in ADMIN_IDS:
                await update.message.reply_text("❌ Cannot ban admin.")
                return
            user["banned"] = not user.get("banned", False)
            save_user(target, user)
            status = "banned" if user["banned"] else "unbanned"
            await update.message.reply_text(f"✅ User {status} successfully.")
            if user["banned"]:
                try:
                    await context.bot.send_message(target, "⛔ Your account has been banned!")
                except:
                    pass
        except:
            await update.message.reply_text("❌ Invalid ID.")
    
    elif action == "broadcast":
        success = 0
        fail = 0
        for uid, data in users.items():
            if data.get("banned", False):
                continue
            try:
                await context.bot.send_message(int(uid), f"{text}", parse_mode="HTML")
                success += 1
            except:
                fail += 1
        await update.message.reply_text(
            f"""<b>✅ Broadcast sent!</b>

👥 Success: {success}
❌ Failed: {fail}""",
            parse_mode="HTML"
        )
    
    elif action == "gift":
        try:
            amount = int(text)
            if amount < 0:
                await update.message.reply_text("❌ Amount cannot be negative.")
                return
            success = 0
            fail = 0
            for uid, data in users.items():
                if data.get("banned", False):
                    continue
                user = get_user(uid)
                user["balance"] += amount
                add_transaction(uid, amount, "gift", f"Global gift {amount} RUB")
                save_user(uid, user)
                try:
                    await context.bot.send_message(
                        uid,
                        f"""<b>🎁 Special Gift from 1 WIN!</b>

💰 {amount} RUB added to your balance.

💳 New balance: {format_russian_number(user['balance'])} RUB""",
                        parse_mode="HTML"
                    )
                    success += 1
                except:
                    fail += 1
            await update.message.reply_text(
                f"""<b>✅ Global gift sent!</b>

💰 Amount: {amount} RUB
👥 Success: {success}
❌ Failed: {fail}""",
                parse_mode="HTML"
            )
        except:
            await update.message.reply_text("❌ Enter a valid number.")
    
    elif action == "balance":
        try:
            target = int(text)
            user = get_user(target)
            text = f"""<b>👤 User Info</b>

🆔 ID: {target}
👤 Username: @{user['username'] or 'User'}
💰 Balance: {format_russian_number(user['balance'])} RUB
📊 Status: {'🚫 Banned' if user.get('banned', False) else '✅ Active'}
💳 Deposited: {'✅ Yes' if user.get('has_deposited', False) else '❌ No'}"""
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Balance", callback_data=f"admin_add_{target}")],
                [InlineKeyboardButton("➖ Remove Balance", callback_data=f"admin_remove_{target}")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
            ]), parse_mode="HTML")
        except:
            await update.message.reply_text("❌ Invalid ID.")
    
    elif action == "search":
        try:
            target = int(text)
            user = get_user(target)
            text = f"""<b>👤 User Info</b>

🆔 ID: {target}
👤 Username: @{user['username'] or 'User'}
💰 Balance: {format_russian_number(user['balance'])} RUB
📊 Status: {'🚫 Banned' if user.get('banned', False) else '✅ Active'}
💳 Deposited: {'✅ Yes' if user.get('has_deposited', False) else '❌ No'}
📅 Joined: {user.get('created_at', 'Unknown')}"""
            await update.message.reply_text(text)
        except:
            await update.message.reply_text("❌ Invalid ID.")
    
    elif action == "edit_min_bet":
        try:
            new = int(text)
            if new < 0:
                await update.message.reply_text("❌ Amount cannot be negative.")
                return
            admin_config["min_bet"] = new
            save_json(ADMIN_CONFIG_FILE, admin_config)
            await update.message.reply_text(f"✅ Minimum bet changed.\n💰 New minimum bet: {new} RUB")
        except:
            await update.message.reply_text("❌ Enter a valid number.")
    
    elif action == "edit_min_deposit":
        try:
            new = int(text)
            if new < 0:
                await update.message.reply_text("❌ Amount cannot be negative.")
                return
            admin_config["min_deposit"] = new
            save_json(ADMIN_CONFIG_FILE, admin_config)
            await update.message.reply_text(f"✅ Minimum deposit changed.\n💰 New minimum deposit: {new} RUB")
        except:
            await update.message.reply_text("❌ Enter a valid number.")
    
    elif action == "edit_min_withdraw":
        try:
            new = int(text)
            if new < 0:
                await update.message.reply_text("❌ Amount cannot be negative.")
                return
            admin_config["min_withdraw"] = new
            save_json(ADMIN_CONFIG_FILE, admin_config)
            await update.message.reply_text(f"✅ Minimum withdraw changed.\n💰 New minimum withdraw: {new} RUB")
        except:
            await update.message.reply_text("❌ Enter a valid number.")
    
    elif action == "edit_trx":
        admin_config["trx_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ TRX wallet updated.\n🟣 New address: <code>{text}</code>", parse_mode="HTML")
    
    elif action == "edit_usdt":
        admin_config["usdt_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ USDT wallet updated.\n🟢 New address: <code>{text}</code>", parse_mode="HTML")
    
    elif action == "set_date":
        admin_config["deposit_enable_date"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ Date updated.\n📅 New date: {text}")
    
    context.user_data["admin_action"] = None

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_add_user"] = target
    context.user_data["admin_action"] = "admin_add"
    
    await query.edit_message_text(
        f"""<b>➕ Add Balance</b>

👤 User: @{get_user(target)['username'] or target}
💰 Current balance: {format_russian_number(get_user(target)['balance'])} RUB

Enter amount:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def admin_remove_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_remove_user"] = target
    context.user_data["admin_action"] = "admin_remove"
    
    await query.edit_message_text(
        f"""<b>➖ Remove Balance</b>

👤 User: @{get_user(target)['username'] or target}
💰 Current balance: {format_russian_number(get_user(target)['balance'])} RUB

Enter amount:""",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")]]),
        parse_mode="HTML"
    )

async def handle_admin_balance_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    action = context.user_data.get("admin_action")
    try:
        amount = int(update.message.text.strip())
        if amount < 0:
            await update.message.reply_text("❌ Amount cannot be negative.")
            return
    except:
        await update.message.reply_text("❌ Enter a valid number.")
        return
    
    if action == "admin_add":
        target = context.user_data.get("admin_add_user")
        user = get_user(target)
        user["balance"] += amount
        add_transaction(target, amount, "deposit", f"Added by admin {amount} RUB")
        user["has_deposited"] = True
        save_user(target, user)
        await update.message.reply_text(
            f"""<b>✅ Balance added.</b>

👤 User: @{user['username'] or target}
💰 Amount: {amount} RUB
💰 New balance: {format_russian_number(user['balance'])} RUB""",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_message(
                target,
                f"""<b>✅ Balance increased!</b>

💰 Amount: {amount} RUB
💰 New balance: {format_russian_number(user['balance'])} RUB""",
                parse_mode="HTML"
            )
        except:
            pass
    
    elif action == "admin_remove":
        target = context.user_data.get("admin_remove_user")
        user = get_user(target)
        if user["balance"] < amount:
            await update.message.reply_text(f"❌ Insufficient balance!\n💰 Balance: {format_russian_number(user['balance'])} RUB")
            return
        user["balance"] -= amount
        add_transaction(target, -amount, "admin_remove", f"Removed by admin {amount} RUB")
        save_user(target, user)
        await update.message.reply_text(
            f"""<b>✅ Balance removed.</b>

👤 User: @{user['username'] or target}
💰 Amount: {amount} RUB
💰 New balance: {format_russian_number(user['balance'])} RUB""",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_message(
                target,
                f"""<b>⚠️ Balance decreased!</b>

💰 Amount: {amount} RUB
💰 New balance: {format_russian_number(user['balance'])} RUB""",
                parse_mode="HTML"
            )
        except:
            pass
    
    context.user_data["admin_action"] = None
    context.user_data["admin_add_user"] = None
    context.user_data["admin_remove_user"] = None

# ======================== BROADCAST COMMANDS ========================
async def jayeze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send bonus to all users"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            """<b>❌ Usage:</b>
/jayeze amount

Example: /jayeze 100
Sends 100 RUB to all users.""",
            parse_mode="HTML"
        )
        return
    
    try:
        amount = int(args[0])
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be greater than 0.")
            return
        if amount > 100000:
            await update.message.reply_text("❌ Maximum amount per gift is 100 000 RUB.")
            return
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return
    
    success = 0
    fail = 0
    total_cost = 0
    
    msg = await update.message.reply_text(f"📨 Sending {amount} RUB to all users...")
    
    for uid, data in users.items():
        if data.get("banned", False):
            continue
        try:
            user = get_user(uid)
            user["balance"] += amount
            add_transaction(uid, amount, "gift", f"Global gift {amount} RUB")
            save_user(uid, user)
            success += 1
            total_cost += amount
            
            try:
                await context.bot.send_message(
                    int(uid),
                    f"""<b>🎁 Special Gift from 1 WIN!</b>

💰 {amount} RUB added to your balance.
💳 New balance: {format_russian_number(user['balance'])} RUB

🎉 Enjoy our games!""",
                    parse_mode="HTML"
                )
            except:
                pass
        except:
            fail += 1
    
    await msg.edit_text(
        f"""<b>✅ Global gift sent successfully!</b>

💰 Amount per user: {amount} RUB
👥 Success: {success}
💰 Total cost: {format_russian_number(total_cost)} RUB
❌ Failed: {fail}""",
        parse_mode="HTML"
    )

async def ersal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast message to all users"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return
    
    text = update.message.text.replace("/ersal", "").strip()
    
    if not text:
        await update.message.reply_text(
            """<b>❌ Usage:</b>
/ersal your message

Example: /ersal Hello everyone!""",
            parse_mode="HTML"
        )
        return
    
    success = 0
    fail = 0
    
    msg = await update.message.reply_text("📨 Sending broadcast...")
    
    for uid, data in users.items():
        if data.get("banned", False):
            continue
        try:
            await context.bot.send_message(
                int(uid),
                f"{text}",
                parse_mode="HTML"
            )
            success += 1
        except:
            fail += 1
    
    await msg.edit_text(
        f"""<b>✅ Broadcast sent!</b>

👥 Success: {success}
❌ Failed: {fail}""",
        parse_mode="HTML"
    )

async def amar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 20 users by balance and referrals"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return
    
    user_list = []
    for uid, data in users.items():
        user_list.append({
            "id": uid,
            "username": data.get("username", "User"),
            "balance": data.get("balance", 0),
            "referral_count": data.get("referral_count", 0),
            "total_bets": data.get("total_bets", 0),
            "total_wins": data.get("total_wins", 0)
        })
    
    if not user_list:
        await update.message.reply_text("❌ No users found.")
        return
    
    sorted_by_balance = sorted(user_list, key=lambda x: x["balance"], reverse=True)[:20]
    
    text = "<b>🏆 Top 20 Users by Balance:</b>\n\n"
    for i, user in enumerate(sorted_by_balance, 1):
        username = user["username"] if user["username"] else f"User {user['id'][:8]}"
        text += f"{i}. @{username} — 💰 {format_russian_number(user['balance'])} RUB\n"
    
    sorted_by_referral = sorted(user_list, key=lambda x: x["referral_count"], reverse=True)[:20]
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "<b>👥 Top 20 Users by Referrals:</b>\n\n"
    for i, user in enumerate(sorted_by_referral, 1):
        username = user["username"] if user["username"] else f"User {user['id'][:8]}"
        text += f"{i}. @{username} — 👥 {user['referral_count']}\n"
    
    total_users = len(user_list)
    total_balance = sum(u["balance"] for u in user_list)
    total_bets = sum(u["total_bets"] for u in user_list)
    total_wins = sum(u["total_wins"] for u in user_list)
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"""<b>📊 Bot Statistics:</b>
👥 Total users: {total_users:,}
💰 Total balance: {format_russian_number(total_balance)} RUB
🎯 Total bets: {total_bets:,}
🏆 Total wins: {total_wins:,}"""
    
    await update.message.reply_text(text, parse_mode="HTML")

# ======================== UNKNOWN ========================
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Unknown command. Please use the menu.")

# ======================== MAIN ========================
def main():
    logging.basicConfig(level=logging.INFO)
    
    gc.enable()
    gc.set_threshold(700, 10, 5)
    
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("✅ Flask web server started")
    
    app = Application.builder().token(TOKEN).build()
    
    # ======================== REGISTER HANDLERS ========================
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("jayeze", jayeze))
    app.add_handler(CommandHandler("ersal", ersal))
    app.add_handler(CommandHandler("amar", amar))
    
    # Main callbacks
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(game_menu, pattern="^game_menu$"))
    app.add_handler(CallbackQueryHandler(check_gift, pattern="^check_gift$"))
    
    # Dice game
    app.add_handler(CallbackQueryHandler(dice_game, pattern="^dice_game$"))
    app.add_handler(CallbackQueryHandler(dice_bet_selected, pattern="^dice_bet_"))
    app.add_handler(CallbackQueryHandler(dice_coef_selected, pattern="^dice_coef_"))
    app.add_handler(CallbackQueryHandler(dice_roll, pattern="^dice_roll$"))
    
    # Coin game
    app.add_handler(CallbackQueryHandler(coin_game, pattern="^coin_game$"))
    app.add_handler(CallbackQueryHandler(coin_bet_selected, pattern="^coin_bet_"))
    app.add_handler(CallbackQueryHandler(coin_predict, pattern="^coin_predict_"))
    
    # Slot game
    app.add_handler(CallbackQueryHandler(slot_game, pattern="^slot_game$"))
    app.add_handler(CallbackQueryHandler(slot_bet_selected, pattern="^slot_bet_"))
    app.add_handler(CallbackQueryHandler(slot_spin, pattern="^slot_spin$"))
    
    # Football game
    app.add_handler(CallbackQueryHandler(football_game, pattern="^football_game$"))
    app.add_handler(CallbackQueryHandler(football_bet_selected, pattern="^football_bet_"))
    app.add_handler(CallbackQueryHandler(football_predict, pattern="^football_predict_"))
    
    # Account
    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(deposit, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(withdraw, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(withdraw_amount_selected, pattern="^withdraw_"))
    app.add_handler(CallbackQueryHandler(withdraw_card, pattern="^withdraw_card$"))
    app.add_handler(CallbackQueryHandler(withdraw_wallet, pattern="^withdraw_wallet$"))
    app.add_handler(CallbackQueryHandler(transactions, pattern="^transactions$"))
    
    # Other
    app.add_handler(CallbackQueryHandler(gift, pattern="^gift$"))
    app.add_handler(CallbackQueryHandler(trust, pattern="^trust$"))
    
    # Admin
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_settings, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_close, pattern="^admin_close$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_bot, pattern="^admin_toggle_bot$"))
    app.add_handler(CallbackQueryHandler(admin_set_date, pattern="^admin_set_date$"))
    app.add_handler(CallbackQueryHandler(admin_set_wallets, pattern="^admin_set_wallets$"))
    app.add_handler(CallbackQueryHandler(admin_edit_trx, pattern="^admin_edit_trx$"))
    app.add_handler(CallbackQueryHandler(admin_edit_usdt, pattern="^admin_edit_usdt$"))
    app.add_handler(CallbackQueryHandler(admin_change_limits, pattern="^admin_change_limits$"))
    app.add_handler(CallbackQueryHandler(admin_edit_min_bet, pattern="^admin_edit_min_bet$"))
    app.add_handler(CallbackQueryHandler(admin_edit_min_deposit, pattern="^admin_edit_min_deposit$"))
    app.add_handler(CallbackQueryHandler(admin_edit_min_withdraw, pattern="^admin_edit_min_withdraw$"))
    app.add_handler(CallbackQueryHandler(admin_manage_games, pattern="^admin_manage_games$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_game, pattern="^admin_toggle_game_"))
    app.add_handler(CallbackQueryHandler(admin_ban, pattern="^admin_ban$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_global_gift, pattern="^admin_global_gift$"))
    app.add_handler(CallbackQueryHandler(admin_balance, pattern="^admin_balance$"))
    app.add_handler(CallbackQueryHandler(admin_search, pattern="^admin_search$"))
    app.add_handler(CallbackQueryHandler(admin_add_balance, pattern="^admin_add_"))
    app.add_handler(CallbackQueryHandler(admin_remove_balance, pattern="^admin_remove_"))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_balance_action))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    # ======================== SCHEDULER FOR INACTIVE USERS ========================
    scheduler = BackgroundScheduler()
    
    async def scheduled_check():
        await check_inactive_users(app)
    
    def run_async_job():
        asyncio.run(scheduled_check())
    
    scheduler.add_job(
        run_async_job,
        CronTrigger(hour=10, minute=0),  # Every day at 10:00 AM
        id="check_inactive_users",
        replace_existing=True
    )
    scheduler.start()
    print("✅ Scheduler for inactive users started")
    
    print("🤖 1 WIN bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
