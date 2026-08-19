#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1win Bot - Casino & Betting Bot
"""

import os
import json
import random
import logging
import string
import gc
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ======================== SETTINGS ========================
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "123456789").split(",") if id.strip()]
CHANNEL = os.environ.get("CHANNEL", "@onewin")
SUPPORT = "@onewin_sup"
TRX_WALLET = os.environ.get("TRX_WALLET", "TEv9t55am7zcCi2Z7dUXtFfKQmofeN7e1r")
USDT_WALLET = os.environ.get("USDT_WALLET", "TEVuvWZ68UbDUdzpd6EqxncsqDVjwyY7cj")

MIN_BET = 10
GIFT_AMOUNT = 100
MIN_WITHDRAW = 250
MIN_DEPOSIT = 1000  # تغییر به ۱۰۰۰ روبل
COMMISSION_PERCENT = 30
INITIAL_BALANCE = 0

BOT_NAME = "one win"

# ======================== WEB SERVER ========================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return jsonify({"status": "running", "bot": "onewin"})

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
            "created_at": str(datetime.now())
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

# ======================== MAIN MENU ========================
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎲 Играть", callback_data="game_menu")],
        [InlineKeyboardButton("👤 Мой счёт", callback_data="my_account")],
        [InlineKeyboardButton("🎁 Получить бонус", callback_data="gift")],
        [InlineKeyboardButton("❓ Как доверять?", callback_data="trust")]
    ]
    
    text = f"🎰 **one win**\n\n" \
           f"👤 Пользователь: @{user['username'] or 'Пользователь'}\n" \
           f"💰 Баланс: {format_russian_number(user['balance'])} RUB\n\n" \
           f"✅ Вывод в рублях\n" \
           f"👥 За каждого приглашённого — {GIFT_AMOUNT} RUB бонус\n\n" \
           f"🆘 Поддержка: {SUPPORT}\n\n" \
           f"Выберите действие из меню:"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== START ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    user = get_user(user_id)
    user["username"] = username
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
        await update.message.reply_text(
            f"🎰 **one win**\n\n"
            f"👤 Пользователь: @{username or 'Пользователь'}\n"
            f"💰 Баланс: {format_russian_number(user['balance'])} RUB\n\n"
            f"✅ Вывод в рублях\n"
            f"👥 За каждого приглашённого — {admin_config.get('gift_amount', GIFT_AMOUNT)} RUB бонус\n\n"
            f"🆘 Поддержка: {SUPPORT}\n\n"
            f"Выберите действие из меню:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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
        channel_word3 = "канал"
    else:
        channels_text = "\n".join([f"{i+1}️⃣ {c['link']}" for i, c in enumerate(enabled_channels)])
        channel_word = "каналы"
        channel_word3 = "каналы"
    
    gift_amount = admin_config.get("gift_amount", GIFT_AMOUNT)
    text = f"🎁 **Бонус за подписку: {gift_amount} RUB**\n\n"
    text += f"Подпишитесь на наш {channel_word} и получите бонус!\n\n"
    text += f"📌 **{channel_word.capitalize()} для подписки:**\n\n{channels_text}\n\n"
    text += f"После подписки нажмите кнопку «✅ Я подписался»."
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def check_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
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
                            f"🎉 **Новый пользователь по вашей ссылке!**\n\n"
                            f"👤 Новый пользователь: @{user['username'] or user_id}\n"
                            f"🎁 Бонус: {gift_amount} RUB добавлен на ваш счет.\n\n"
                            f"📊 **Ваша статистика:**\n"
                            f"👥 Всего приглашений: {referrer.get('referral_count', 0)}\n"
                            f"💰 Получено бонусов: {format_russian_number(referrer.get('referral_gift', 0))} RUB",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"Error sending message to referrer: {e}")
                    break
        
        await query.edit_message_text(
            f"✅ **Поздравляем! Подписка подтверждена.**\n\n"
            f"🎁 {gift_amount} RUB бонус добавлен на ваш счет.\n"
            f"💰 Новый баланс: {format_russian_number(user['balance'])} RUB",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Играть", callback_data="game_menu")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
    else:
        keyboard = []
        for i, channel in enumerate(enabled_channels, 1):
            link = channel["link"]
            label = f"📢 Подписаться на канал {i}" if len(enabled_channels) > 1 else "📢 Подписаться на канал"
            keyboard.append([InlineKeyboardButton(label, url=f"https://t.me/{link[1:]}")])
        keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data="check_gift")])
        
        await query.edit_message_text(
            f"❌ Вы ещё не подписались на все каналы!\n\n"
            f"Пожалуйста, подпишитесь на все каналы выше, затем нажмите «Я подписался».",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ======================== GAMES MENU ========================
async def game_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
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
    
    await query.edit_message_text("🎮 **Игры one win**\n\nВыберите игру:", reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== DICE GAME ========================
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="dice_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="dice_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="dice_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="dice_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="dice_bet_200")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"🎲 **Игра в кости**\n\n"
        f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
        f"📌 Выберите сумму ставки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def dice_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ Недостаточно средств!\n"
            f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
            f"🎯 Сумма ставки: {amount} RUB",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="dice_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["dice_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("🎯 Чётное | Коэф. 2", callback_data="dice_coef_even")],
        [InlineKeyboardButton("🎯 Нечётное | Коэф. 2", callback_data="dice_coef_odd")],
        [InlineKeyboardButton("🎯 Сумма ≥ 10 | Коэф. 3", callback_data="dice_coef_high")],
        [InlineKeyboardButton("🎯 Обе кости одинаковые | Коэф. 5", callback_data="dice_coef_same")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"🎲 **Выбор коэффициента**\n\n"
        f"💰 Сумма ставки: {amount} RUB\n\n"
        f"📌 Выберите один из коэффициентов:\n\n"
        f"• **Чётное** — сумма 2 костей чётная (коэф. 2)\n"
        f"• **Нечётное** — сумма 2 костей нечётная (коэф. 2)\n"
        f"• **Сумма 10 или больше** — сумма 2 костей ≥ 10 (коэф. 3)\n"
        f"• **Обе кости одинаковые** — выпало одинаковое число (коэф. 5)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def dice_coef_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    bet_amount = context.user_data.get("dice_amount", 0)
    if bet_amount == 0:
        await query.edit_message_text(
            "❌ Ошибка! Пожалуйста, начните заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Игра в кости", callback_data="dice_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    choice = query.data.split("_")[2]
    context.user_data["dice_choice"] = choice
    
    await query.edit_message_text(
        f"🎲 **Бросок костей...**\n\n"
        f"💰 Сумма ставки: {bet_amount} RUB\n"
        f"🎯 Ваш выбор: {choice}\n\n"
        f"⏳ Пожалуйста, подождите...",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Бросить кости", callback_data="dice_roll")]
        ])
    )

async def dice_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    bet_amount = context.user_data.get("dice_amount", 0)
    choice = context.user_data.get("dice_choice", "")
    
    if bet_amount == 0 or choice == "":
        await query.edit_message_text(
            "❌ Ошибка! Пожалуйста, начните заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Игра в кости", callback_data="dice_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    await query.edit_message_text("🎲 **Бросок костей...**")
    
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
        
        result_text = f"🎉 **Поздравляем! Вы выиграли!**\n\n"
        result_text += f"🎲 **Результат броска костей:**\n"
        result_text += f"Кость 1: {value1} | Кость 2: {value2}\n"
        result_text += f"📊 Сумма: {total}\n"
        result_text += f"🎯 Ваш выбор: {choice_name}\n"
        result_text += f"✅ Результат: {win_description}\n"
        result_text += f"📊 Коэффициент: {coefficient}×\n"
        result_text += f"💰 Ставка: {bet_amount} RUB\n"
        result_text += f"🏆 Выигрыш: {win_amount} RUB\n\n"
        result_text += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, win_amount, "win", f"Выигрыш в кости - {choice_name}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        
        result_text = f"😔 **К сожалению... Вы проиграли.**\n\n"
        result_text += f"🎲 **Результат броска костей:**\n"
        result_text += f"Кость 1: {value1} | Кость 2: {value2}\n"
        result_text += f"📊 Сумма: {total}\n"
        result_text += f"🎯 Ваш выбор: {choice_name}\n"
        result_text += f"💰 Ставка: {bet_amount} RUB\n\n"
        result_text += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, -bet_amount, "bet", f"Проигрыш в кости - {choice_name}")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["dice_amount"] = 0
    context.user_data["dice_choice"] = ""
    
    keyboard = [
        [InlineKeyboardButton("🎲 Ещё раз", callback_data="dice_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== COIN GAME ========================
async def coin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="coin_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="coin_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="coin_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="coin_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="coin_bet_200")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"🪙 **Орёл или решка**\n\n"
        f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
        f"📊 Коэффициент: **2.5**\n\n"
        f"📌 Выберите сумму ставки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def coin_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ Недостаточно средств!\n"
            f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
            f"🎯 Сумма ставки: {amount} RUB",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="coin_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["coin_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("🦅 Орёл", callback_data="coin_predict_heads")],
        [InlineKeyboardButton("📍 Решка", callback_data="coin_predict_tails")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"🪙 **Орёл или решка**\n\n"
        f"💰 Сумма ставки: {amount} RUB\n"
        f"📊 Коэффициент: **2.5**\n\n"
        f"📌 Чётное = Орёл 🦅 | Нечётное = Решка 📍\n\n"
        f"Сделайте выбор:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def coin_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    bet_amount = context.user_data.get("coin_amount", 0)
    if bet_amount == 0:
        await query.edit_message_text(
            "❌ Ошибка! Пожалуйста, начните заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Орёл или решка", callback_data="coin_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    choice = query.data.split("_")[2]
    
    await query.edit_message_text("🪙 **Бросок монеты...**")
    dice_message = await query.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    
    is_heads = dice_value in [2, 4, 6]
    result_name = "Орёл 🦅" if is_heads else "Решка 📍"
    is_win = (choice == "heads" and is_heads) or (choice == "tails" and not is_heads)
    
    if is_win:
        win_amount = int(bet_amount * 2.5)
        user["balance"] += win_amount
        user["total_wins"] = user.get("total_wins", 0) + 1
        result_text = f"🎉 **Поздравляем! Вы выиграли!**\n\n"
        result_text += f"🪙 Результат: {result_name}\n"
        result_text += f"🎲 Число кубика: {dice_value} ({'Чётное' if is_heads else 'Нечётное'})\n"
        result_text += f"💰 Ставка: {bet_amount} RUB\n"
        result_text += f"📊 Коэффициент: 2.5×\n"
        result_text += f"🏆 Выигрыш: {win_amount} RUB\n\n"
        result_text += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, win_amount, "win", "Выигрыш в орёл или решка")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        result_text = f"😔 **К сожалению... Вы проиграли.**\n\n"
        result_text += f"🪙 Результат: {result_name}\n"
        result_text += f"🎲 Число кубика: {dice_value} ({'Чётное' if is_heads else 'Нечётное'})\n"
        result_text += f"💰 Ставка: {bet_amount} RUB\n\n"
        result_text += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, -bet_amount, "bet", "Проигрыш в орёл или решка")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["coin_amount"] = 0
    
    keyboard = [
        [InlineKeyboardButton("🪙 Ещё раз", callback_data="coin_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== SLOT GAME ========================
async def slot_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="slot_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="slot_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="slot_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="slot_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="slot_bet_200")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    slot_coeffs = admin_config.get("slot_coeffs", {})
    await query.edit_message_text(
        f"🎰 **Слоты**\n\n"
        f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
        f"📊 **Коэффициенты:**\n"
        f"💎💎💎 = {slot_coeffs.get('💎💎💎', 100)}× | ⭐⭐⭐ = {slot_coeffs.get('⭐⭐⭐', 50)}×\n"
        f"777 = {slot_coeffs.get('777', 20)}× | 🍇🍇🍇 = {slot_coeffs.get('🍇🍇🍇', 15)}×\n"
        f"🍋🍋🍋 = {slot_coeffs.get('🍋🍋🍋', 10)}× | 🍒🍒🍒 = {slot_coeffs.get('🍒🍒🍒', 5)}×\n"
        f"2 одинаковых = {slot_coeffs.get('two_same', 2)}×\n\n"
        f"📌 Выберите сумму ставки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def slot_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ Недостаточно средств!\n"
            f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
            f"🎯 Сумма ставки: {amount} RUB",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="slot_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["slot_amount"] = amount
    
    await query.edit_message_text(
        f"🎰 **Слоты**\n\n"
        f"💰 Сумма ставки: {amount} RUB\n\n"
        f"Нажмите кнопку чтобы запустить слоты:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎰 Запустить слоты", callback_data="slot_spin")],
            [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
        ])
    )

async def slot_spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("slot_amount", 0)
    
    if bet_amount == 0:
        await query.edit_message_text(
            "❌ Ошибка! Пожалуйста, начните заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Слоты", callback_data="slot_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    await query.edit_message_text("🎰 **Запуск слотов...**")
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
        result_text = f"🎉 **Поздравляем! Вы выиграли!**\n\n"
        result_text += f"🎰 Результат слотов:\n[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]\n\n"
        result_text += f"📊 Комбинация: {combo}\n"
        result_text += f"🎯 Коэффициент: {coefficient}×\n"
        result_text += f"💰 Ставка: {bet_amount} RUB\n"
        result_text += f"🏆 Выигрыш: {win_amount} RUB\n\n"
        result_text += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, win_amount, "win", f"Выигрыш в слотах - {combo}")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        result_text = f"😔 **К сожалению... Вы проиграли.**\n\n"
        result_text += f"🎰 Результат слотов:\n[ {result[0]} ] [ {result[1]} ] [ {result[2]} ]\n\n"
        result_text += f"📊 Комбинация: {combo}\n"
        result_text += f"🎯 Коэффициент: 0×\n"
        result_text += f"💰 Ставка: {bet_amount} RUB\n\n"
        result_text += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, -bet_amount, "bet", "Проигрыш в слотах")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["slot_amount"] = 0
    
    keyboard = [
        [InlineKeyboardButton("🎰 Ещё раз", callback_data="slot_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== FOOTBALL GAME ========================
async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("10 RUB", callback_data="football_bet_10"),
         InlineKeyboardButton("20 RUB", callback_data="football_bet_20")],
        [InlineKeyboardButton("50 RUB", callback_data="football_bet_50"),
         InlineKeyboardButton("100 RUB", callback_data="football_bet_100")],
        [InlineKeyboardButton("200 RUB", callback_data="football_bet_200")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"⚽ **Футбол**\n\n"
        f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
        f"📊 Коэффициент: **2.5**\n\n"
        f"📌 Выберите сумму ставки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def football_bet_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[2])
    
    if amount > user["balance"]:
        await query.edit_message_text(
            f"❌ Недостаточно средств!\n"
            f"💰 Ваш баланс: {format_russian_number(user['balance'])} RUB\n"
            f"🎯 Сумма ставки: {amount} RUB",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Выбрать сумму", callback_data="football_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    context.user_data["football_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("⚽️ Будет гол (коэф. 2.5)", callback_data="football_predict_goal")],
        [InlineKeyboardButton("❌ Гола не будет (коэф. 2.5)", callback_data="football_predict_miss")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"⚽ **Прогноз на футбол**\n\n"
        f"💰 Сумма ставки: {amount} RUB\n"
        f"📊 Коэффициент: **2.5**\n\n"
        f"Мяч летит к воротам!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def football_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    bet_amount = context.user_data.get("football_amount", 0)
    prediction = query.data.split("_")[2]
    
    if bet_amount == 0:
        await query.edit_message_text(
            "❌ Ошибка! Пожалуйста, начните заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Футбол", callback_data="football_game")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
        return
    
    await query.edit_message_text("⚽ **Удар...**")
    dice_message = await query.message.reply_dice(emoji="⚽")
    dice_value = dice_message.dice.value
    
    is_goal = dice_value >= 4
    result_text = "Гол ✅" if is_goal else "Гола нет ❌"
    is_win = (prediction == "goal" and is_goal) or (prediction == "miss" and not is_goal)
    
    if is_win:
        win_amount = int(bet_amount * 2.5)
        user["balance"] += win_amount
        user["total_wins"] = user.get("total_wins", 0) + 1
        result_msg = f"🎉 **Поздравляем! Вы выиграли!**\n\n"
        result_msg += f"⚽ Результат удара: {result_text}\n"
        result_msg += f"🎯 Прогноз: {'Будет гол' if prediction == 'goal' else 'Гола не будет'} ✅\n"
        result_msg += f"💰 Ставка: {bet_amount} RUB\n"
        result_msg += f"📊 Коэффициент: 2.5×\n"
        result_msg += f"🏆 Выигрыш: {win_amount} RUB\n\n"
        result_msg += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, win_amount, "win", "Выигрыш в футболе")
    else:
        user["balance"] -= bet_amount
        user["total_losses"] = user.get("total_losses", 0) + 1
        result_msg = f"😔 **К сожалению... Вы проиграли.**\n\n"
        result_msg += f"⚽ Результат удара: {result_text}\n"
        result_msg += f"🎯 Прогноз: {'Будет гол' if prediction == 'goal' else 'Гола не будет'}\n"
        result_msg += f"💰 Ставка: {bet_amount} RUB\n\n"
        result_msg += f"💳 Новый баланс: {format_russian_number(user['balance'])} RUB"
        add_transaction(user_id, -bet_amount, "bet", "Проигрыш в футболе")
    
    user["total_bets"] = user.get("total_bets", 0) + 1
    save_user(user_id, user)
    
    context.user_data["football_amount"] = 0
    
    keyboard = [
        [InlineKeyboardButton("⚽ Ещё раз", callback_data="football_game")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.message.reply_text(result_msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== MY ACCOUNT ========================
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    total_bets = user.get("total_bets", 0)
    wins = user.get("total_wins", 0)
    losses = user.get("total_losses", 0)
    win_rate = round((wins / total_bets * 100) if total_bets > 0 else 0, 1)
    
    text = f"👤 **Мой счёт**\n\n"
    text += f"🆔 Номер пользователя: {user_id}\n"
    text += f"👥 Успешных приглашений: {user.get('referral_count', 0)}\n"
    text += f"📊 Всего ставок: {total_bets} | Побед: {wins} | Поражений: {losses}\n"
    text += f"📈 Процент побед: {win_rate}%\n"
    text += f"💰 Баланс: {format_russian_number(user['balance'])} RUB"
    
    keyboard = [
        [InlineKeyboardButton("💳 Пополнить", callback_data="deposit")],
        [InlineKeyboardButton("🏦 Вывести", callback_data="withdraw")],
        [InlineKeyboardButton("📜 История", callback_data="transactions")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================== DEPOSIT ========================
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    trx_wallet = admin_config.get("trx_wallet", TRX_WALLET)
    usdt_wallet = admin_config.get("usdt_wallet", USDT_WALLET)
    support = admin_config.get("support", SUPPORT)
    
    bonus_text = ""
    if not user.get("has_deposited", False):
        bonus_text = f"🎁 **Бонус за первое пополнение: 50% до 2 500 RUB**\n\n"
    
    text = f"""💳 **Пополнение баланса**

💰 Минимальная сумма пополнения: {MIN_DEPOSIT} RUB

{bonus_text}
━━━━━━━━━━━━━━━━━━━━━━
📌 **Банковская карта для пополнения:**
❌ **Временно недоступна.**

━━━━━━━━━━━━━━━━━━━━━━
🟣 **TRX-кошелёк (TRC20):**
`{trx_wallet}`

📋 **Нажмите на адрес, чтобы скопировать**

━━━━━━━━━━━━━━━━━━━━━━
🟢 **USDT-кошелёк (TRC20):**
`{usdt_wallet}`

📋 **Нажмите на адрес, чтобы скопировать**

━━━━━━━━━━━━━━━━━━━━━━
📌 **Важная информация:**
• Минимальная сумма пополнения: {MIN_DEPOSIT} RUB
• Используйте сеть **TRC20**
• После пополнения отправьте скриншот администратору
• Все пополнения проверяются и подтверждаются вручную

━━━━━━━━━━━━━━━━━━━━━━
📌 **Администратор для отправки скриншота:**

🆔 {SUPPORT}

📋 **Нажмите на ID и отправьте скриншот**

🆘 Поддержка: {SUPPORT}"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ======================== WITHDRAW ========================
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user.get("has_deposited", False):
        await query.edit_message_text(
            f"❌ **Вывод средств недоступен!**\n\n"
            f"Вы ещё не пополняли баланс.\n\n"
            f"📌 Вывод доступен только после **первого пополнения**.\n\n"
            f"Пополните баланс через «💳 Пополнить».",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Пополнить", callback_data="deposit")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
            ])
        )
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
        await query.edit_message_text(
            f"🏦 **Вывод средств**\n\n"
            f"💰 Доступный баланс: {format_russian_number(balance)} RUB\n"
            f"📌 Минимальная сумма вывода: {min_withdraw} RUB\n\n"
            f"❌ Недостаточно средств для вывода!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
    
    await query.edit_message_text(
        f"🏦 **Вывод средств**\n\n"
        f"💰 Доступный баланс: {format_russian_number(balance)} RUB\n"
        f"📌 Минимальная сумма вывода: {min_withdraw} RUB\n\n"
        f"📌 Выберите сумму:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw_amount_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    amount = int(query.data.split("_")[1])
    context.user_data["withdraw_amount"] = amount
    
    keyboard = [
        [InlineKeyboardButton("💳 Номер карты", callback_data="withdraw_card")],
        [InlineKeyboardButton("🟣 Адрес кошелька (TRX)", callback_data="withdraw_wallet")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"✅ Сумма {amount} RUB зарегистрирована для вывода.\n\n"
        f"Выберите один из способов:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["withdraw_method"] = "card"
    await query.edit_message_text(
        "💳 **Вывод на карту**\n\n"
        f"Введите номер карты (16 цифр):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]])
    )

async def withdraw_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["withdraw_method"] = "wallet"
    await query.edit_message_text(
        "🟣 **Вывод на TRX-кошелёк**\n\n"
        f"Введите адрес TRX-кошелька:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")]])
    )

async def handle_withdraw_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
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
                f"🏦 **Новый запрос на вывод**\n\n"
                f"👤 Пользователь: @{user['username'] or user_id}\n"
                f"💰 Сумма: {amount} RUB\n"
                f"📌 Способ: {method_name}\n"
                f"📋 Информация: {info}"
            )
        except:
            pass
    
    await update.message.reply_text(
        f"✅ **Запрос на вывод зарегистрирован!**\n\n"
        f"💰 Сумма: {amount} RUB\n"
        f"🕒 Запрос отправлен на обработку.\n"
        f"По вопросам обращайтесь: {SUPPORT}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]])
    )

# ======================== TRANSACTIONS ========================
async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    trans = user.get("transactions", [])[-10:]
    if not trans:
        text = "📜 **История транзакций**\n\nНет транзакций."
    else:
        text = "📜 **История транзакций**\n\n"
        for t in trans[-10:]:
            emoji = "💰" if t["amount"] > 0 else "💸"
            text += f"{t['date']} | {emoji} {format_russian_number(t['amount'])} RUB | Баланс: {format_russian_number(t['balance_after'])} RUB\n"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Мой счёт", callback_data="my_account")]]))

# ======================== GIFT ========================
async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    bot_username = "onewinbot"
    link = f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
    commission_percent = user.get("commission_percent", COMMISSION_PERCENT)
    
    text = f"🎁 **Бонус и комиссия**\n\n"
    text += f"📌 **Ваш процент комиссии:** {commission_percent}%\n\n"
    text += f"👤 За каждого приглашённого — {admin_config.get('gift_amount', GIFT_AMOUNT)} RUB бонус\n"
    text += f"💰 С каждого пополнения реферала — {commission_percent}% комиссия\n\n"
    text += f"🔗 Ваша реферальная ссылка:\n`{link}`\n\n"
    text += f"📋 **Нажмите на ссылку, чтобы скопировать**\n\n"
    text += f"📊 **Ваша статистика:**\n"
    text += f"👥 Успешных приглашений: {user.get('referral_count', 0)}\n"
    text += f"💰 Получено бонусов: {format_russian_number(user.get('referral_gift', 0))} RUB\n"
    text += f"💸 Получено комиссии: {format_russian_number(user.get('referral_commission', 0))} RUB"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ======================== TRUST ========================
async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"❓ **Как доверять?**\n\n"
        f"Мы понимаем, что доверие к онлайн-сервису может быть сложным.\n\n"
        f"Чтобы вы могли начать с уверенностью, мы дарим **{admin_config.get('gift_amount', GIFT_AMOUNT)} RUB бонус** при подписке на наш канал.\n\n"
        f"Мы стремимся предоставить приятный и честный игровой опыт для всех пользователей. ❤️",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]])
    )

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
    await update.message.reply_text("👑 **one win Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total = len(users)
    total_balance = sum(u["balance"] for u in users.values())
    banned = sum(1 for u in users.values() if u.get("banned", False))
    text = f"📊 **Statistics**\n\n"
    text += f"👥 Total users: {total}\n"
    text += f"🚫 Banned users: {banned}\n"
    text += f"💰 Total balance: {format_russian_number(total_balance)} RUB"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]))

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
    await query.edit_message_text("👥 **Users Management**", reply_markup=InlineKeyboardMarkup(keyboard))

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
    await query.edit_message_text("⚙️ **Settings**", reply_markup=InlineKeyboardMarkup(keyboard))

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
        f"🔌 **Bot status changed!**\n\n"
        f"📌 New status: {status_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Toggle", callback_data="admin_toggle_bot")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ])
    )

async def admin_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"📅 **Change Deposit Date**\n\n"
        f"📌 Current date: {admin_config.get('deposit_enable_date', '30 August')}\n\n"
        f"Enter new date:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_set_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🔄 **Change Wallets**\n\n"
        f"🟣 Current TRX wallet:\n`{admin_config.get('trx_wallet', TRX_WALLET)}`\n\n"
        f"🟢 Current USDT wallet:\n`{admin_config.get('usdt_wallet', USDT_WALLET)}`\n\n"
        f"Select wallet to change:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Change TRX", callback_data="admin_edit_trx")],
            [InlineKeyboardButton("✏️ Change USDT", callback_data="admin_edit_usdt")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ])
    )

async def admin_edit_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **Change TRX Wallet**\n\n"
        f"📌 Current address:\n`{admin_config.get('trx_wallet', TRX_WALLET)}`\n\n"
        f"Enter new TRX address:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_edit_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **Change USDT Wallet**\n\n"
        f"📌 Current address:\n`{admin_config.get('usdt_wallet', USDT_WALLET)}`\n\n"
        f"Enter new USDT address:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_change_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🎯 **Change Limits**\n\n"
        f"💰 Minimum bet: {admin_config.get('min_bet', MIN_BET)} RUB\n"
        f"💰 Minimum deposit: {admin_config.get('min_deposit', MIN_DEPOSIT)} RUB\n"
        f"💰 Minimum withdraw: {admin_config.get('min_withdraw', MIN_WITHDRAW)} RUB\n\n"
        f"Select limit to change:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Min Bet", callback_data="admin_edit_min_bet")],
            [InlineKeyboardButton("✏️ Min Deposit", callback_data="admin_edit_min_deposit")],
            [InlineKeyboardButton("✏️ Min Withdraw", callback_data="admin_edit_min_withdraw")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ])
    )

async def admin_edit_min_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **Change Minimum Bet**\n\n"
        f"📌 Current minimum bet: {admin_config.get('min_bet', MIN_BET)} RUB\n\n"
        f"Enter new amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_edit_min_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **Change Minimum Deposit**\n\n"
        f"📌 Current minimum deposit: {admin_config.get('min_deposit', MIN_DEPOSIT)} RUB\n\n"
        f"Enter new amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_edit_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"✏️ **Change Minimum Withdraw**\n\n"
        f"📌 Current minimum withdraw: {admin_config.get('min_withdraw', MIN_WITHDRAW)} RUB\n\n"
        f"Enter new amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_manage_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = admin_config.get("games", {})
    text = "🎲 **Manage Games**\n\nCurrent status:\n"
    for game, status in games.items():
        text += f"✅ {game}: {'Enabled' if status else 'Disabled'}\n"
    
    keyboard = []
    for game in games.keys():
        keyboard.append([InlineKeyboardButton(f"🔄 Toggle {game}", callback_data=f"admin_toggle_game_{game}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_toggle_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data.split("_")[3]
    games = admin_config.get("games", {})
    games[game] = not games.get(game, True)
    admin_config["games"] = games
    save_json(ADMIN_CONFIG_FILE, admin_config)
    
    await query.edit_message_text(
        f"✅ Game {game} toggled successfully.\n"
        f"📌 New status: {'Enabled' if games[game] else 'Disabled'}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Manage Games", callback_data="admin_manage_games")]])
    )

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚫 **Ban User**\n\n"
        f"Enter user ID:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📨 **Broadcast**\n\n"
        f"Enter your message:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_global_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎁 **Global Gift**\n\n"
        f"Enter amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💸 **Balance Management**\n\n"
        f"Enter user ID:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
    )

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 **Search User**\n\n"
        f"Enter user ID:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
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
                await context.bot.send_message(int(uid), f"📨 **Broadcast**\n\n{text}")
                success += 1
            except:
                fail += 1
        await update.message.reply_text(
            f"✅ **Broadcast sent!**\n\n"
            f"👥 Success: {success}\n"
            f"❌ Failed: {fail}"
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
                        f"🎁 **Special Gift from one win!**\n\n"
                        f"💰 {amount} RUB added to your balance.\n\n"
                        f"💳 New balance: {format_russian_number(user['balance'])} RUB",
                        parse_mode="Markdown"
                    )
                    success += 1
                except:
                    fail += 1
            await update.message.reply_text(
                f"✅ **Global gift sent!**\n\n"
                f"💰 Amount: {amount} RUB\n"
                f"👥 Success: {success}\n"
                f"❌ Failed: {fail}"
            )
        except:
            await update.message.reply_text("❌ Enter a valid number.")
    
    elif action == "balance":
        try:
            target = int(text)
            user = get_user(target)
            await update.message.reply_text(
                f"👤 **User Info**\n\n"
                f"🆔 ID: {target}\n"
                f"👤 Username: @{user['username'] or 'User'}\n"
                f"💰 Balance: {format_russian_number(user['balance'])} RUB\n"
                f"📊 Status: {'🚫 Banned' if user.get('banned', False) else '✅ Active'}\n"
                f"💳 Deposited: {'✅ Yes' if user.get('has_deposited', False) else '❌ No'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Balance", callback_data=f"admin_add_{target}")],
                    [InlineKeyboardButton("➖ Remove Balance", callback_data=f"admin_remove_{target}")],
                    [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
                ])
            )
        except:
            await update.message.reply_text("❌ Invalid ID.")
    
    elif action == "search":
        try:
            target = int(text)
            user = get_user(target)
            await update.message.reply_text(
                f"👤 **User Info**\n\n"
                f"🆔 ID: {target}\n"
                f"👤 Username: @{user['username'] or 'User'}\n"
                f"💰 Balance: {format_russian_number(user['balance'])} RUB\n"
                f"📊 Status: {'🚫 Banned' if user.get('banned', False) else '✅ Active'}\n"
                f"💳 Deposited: {'✅ Yes' if user.get('has_deposited', False) else '❌ No'}\n"
                f"📅 Joined: {user.get('created_at', 'Unknown')}"
            )
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
        await update.message.reply_text(f"✅ TRX wallet updated.\n🟣 New address: `{text}`")
    
    elif action == "edit_usdt":
        admin_config["usdt_wallet"] = text
        save_json(ADMIN_CONFIG_FILE, admin_config)
        await update.message.reply_text(f"✅ USDT wallet updated.\n🟢 New address: `{text}`")
    
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
        f"➕ **Add Balance**\n\n"
        f"👤 User: @{get_user(target)['username'] or target}\n"
        f"💰 Current balance: {format_russian_number(get_user(target)['balance'])} RUB\n\n"
        f"Enter amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")]])
    )

async def admin_remove_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = int(query.data.split("_")[2])
    context.user_data["admin_remove_user"] = target
    context.user_data["admin_action"] = "admin_remove"
    
    await query.edit_message_text(
        f"➖ **Remove Balance**\n\n"
        f"👤 User: @{get_user(target)['username'] or target}\n"
        f"💰 Current balance: {format_russian_number(get_user(target)['balance'])} RUB\n\n"
        f"Enter amount:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")]])
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
            f"✅ Balance added.\n"
            f"👤 User: @{user['username'] or target}\n"
            f"💰 Amount: {amount} RUB\n"
            f"💰 New balance: {format_russian_number(user['balance'])} RUB"
        )
        try:
            await context.bot.send_message(
                target,
                f"✅ **Balance increased!**\n\n"
                f"💰 Amount: {amount} RUB\n"
                f"💰 New balance: {format_russian_number(user['balance'])} RUB"
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
            f"✅ Balance removed.\n"
            f"👤 User: @{user['username'] or target}\n"
            f"💰 Amount: {amount} RUB\n"
            f"💰 New balance: {format_russian_number(user['balance'])} RUB"
        )
        try:
            await context.bot.send_message(
                target,
                f"⚠️ **Balance decreased!**\n\n"
                f"💰 Amount: {amount} RUB\n"
                f"💰 New balance: {format_russian_number(user['balance'])} RUB"
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
            "❌ **Usage:**\n"
            "/jayeze amount\n\n"
            "Example: /jayeze 100\n"
            "Sends 100 RUB to all users."
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
    
    msg = await update.message.reply_text(f"📨 **Sending {amount} RUB to all users...**")
    
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
                    f"🎁 **Special Gift from one win!**\n\n"
                    f"💰 {amount} RUB added to your balance.\n"
                    f"💳 New balance: {format_russian_number(user['balance'])} RUB\n\n"
                    f"🎉 Enjoy our games!",
                    parse_mode="Markdown"
                )
            except:
                pass
        except:
            fail += 1
    
    await msg.edit_text(
        f"✅ **Global gift sent successfully!**\n\n"
        f"💰 Amount per user: {amount} RUB\n"
        f"👥 Success: {success}\n"
        f"💰 Total cost: {format_russian_number(total_cost)} RUB\n"
        f"❌ Failed: {fail}"
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
            "❌ **Usage:**\n"
            "/ersal your message\n\n"
            "Example: /ersal Hello everyone!"
        )
        return
    
    success = 0
    fail = 0
    
    msg = await update.message.reply_text("📨 **Sending broadcast...**")
    
    for uid, data in users.items():
        if data.get("banned", False):
            continue
        try:
            await context.bot.send_message(
                int(uid),
                f"{text}",
                parse_mode="Markdown"
            )
            success += 1
        except:
            fail += 1
    
    await msg.edit_text(
        f"✅ **Broadcast sent!**\n\n"
        f"👥 Success: {success}\n"
        f"❌ Failed: {fail}"
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
    
    text = "🏆 **Top 20 Users by Balance:**\n\n"
    for i, user in enumerate(sorted_by_balance, 1):
        username = user["username"] if user["username"] else f"User {user['id'][:8]}"
        text += f"{i}. @{username} — 💰 {format_russian_number(user['balance'])} RUB\n"
    
    sorted_by_referral = sorted(user_list, key=lambda x: x["referral_count"], reverse=True)[:20]
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "👥 **Top 20 Users by Referrals:**\n\n"
    for i, user in enumerate(sorted_by_referral, 1):
        username = user["username"] if user["username"] else f"User {user['id'][:8]}"
        text += f"{i}. @{username} — 👥 {user['referral_count']}\n"
    
    total_users = len(user_list)
    total_balance = sum(u["balance"] for u in user_list)
    total_bets = sum(u["total_bets"] for u in user_list)
    total_wins = sum(u["total_wins"] for u in user_list)
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 **Bot Statistics:**\n"
    text += f"👥 Total users: {total_users:,}\n"
    text += f"💰 Total balance: {format_russian_number(total_balance)} RUB\n"
    text += f"🎯 Total bets: {total_bets:,}\n"
    text += f"🏆 Total wins: {total_wins:,}"
    
    await update.message.reply_text(text, parse_mode="Markdown")

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
    
    # ======================== COMMANDS ========================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("jayeze", jayeze))
    app.add_handler(CommandHandler("ersal", ersal))
    app.add_handler(CommandHandler("amar", amar))
    
    # ======================== MAIN CALLBACKS ========================
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(game_menu, pattern="^game_menu$"))
    app.add_handler(CallbackQueryHandler(check_gift, pattern="^check_gift$"))
    
    # ======================== DICE GAME ========================
    app.add_handler(CallbackQueryHandler(dice_game, pattern="^dice_game$"))
    app.add_handler(CallbackQueryHandler(dice_bet_selected, pattern="^dice_bet_"))
    app.add_handler(CallbackQueryHandler(dice_coef_selected, pattern="^dice_coef_"))
    app.add_handler(CallbackQueryHandler(dice_roll, pattern="^dice_roll$"))
    
    # ======================== COIN GAME ========================
    app.add_handler(CallbackQueryHandler(coin_game, pattern="^coin_game$"))
    app.add_handler(CallbackQueryHandler(coin_bet_selected, pattern="^coin_bet_"))
    app.add_handler(CallbackQueryHandler(coin_predict, pattern="^coin_predict_"))
    
    # ======================== SLOT GAME ========================
    app.add_handler(CallbackQueryHandler(slot_game, pattern="^slot_game$"))
    app.add_handler(CallbackQueryHandler(slot_bet_selected, pattern="^slot_bet_"))
    app.add_handler(CallbackQueryHandler(slot_spin, pattern="^slot_spin$"))
    
    # ======================== FOOTBALL GAME ========================
    app.add_handler(CallbackQueryHandler(football_game, pattern="^football_game$"))
    app.add_handler(CallbackQueryHandler(football_bet_selected, pattern="^football_bet_"))
    app.add_handler(CallbackQueryHandler(football_predict, pattern="^football_predict_"))
    
    # ======================== ACCOUNT ========================
    app.add_handler(CallbackQueryHandler(my_account, pattern="^my_account$"))
    app.add_handler(CallbackQueryHandler(deposit, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(withdraw, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(withdraw_amount_selected, pattern="^withdraw_"))
    app.add_handler(CallbackQueryHandler(withdraw_card, pattern="^withdraw_card$"))
    app.add_handler(CallbackQueryHandler(withdraw_wallet, pattern="^withdraw_wallet$"))
    app.add_handler(CallbackQueryHandler(transactions, pattern="^transactions$"))
    
    # ======================== OTHER ========================
    app.add_handler(CallbackQueryHandler(gift, pattern="^gift$"))
    app.add_handler(CallbackQueryHandler(trust, pattern="^trust$"))
    
    # ======================== ADMIN ========================
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
    
    # ======================== MESSAGE HANDLERS ========================
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_balance_action))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    print("🤖 one win bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
