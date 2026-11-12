import os
import time
import threading
import requests
import io
from flask import Flask, request, render_template, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_НОВОГО_БОТА")
APP_URL = os.environ.get("APP_URL", "https://твой-новый-сервис.onrender.com").rstrip("/")
ADMIN_IDS = [551209811, 447208738, 840231919]

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__, template_folder=".")
NL = chr(10)

def create_kp_pdf(dealer_company, client_name, items, markup_pct, client_total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Подключаем кириллицу (шрифты нужно закинуть в папку проекта)
    try:
        pdfmetrics.registerFont(TTFont('Calibri', 'calibri.ttf'))
        try:
            pdfmetrics.registerFont(TTFont('Calibri-Bold', 'calibrib.ttf'))
            pdfmetrics.registerFontFamily('Calibri', normal='Calibri', bold='Calibri-Bold')
        except:
            pass
        font_name = 'Calibri'
    except Exception:
        font_name = 'Helvetica' # Резервный

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle('Title', fontName=font_name, fontSize=16, alignment=1, spaceAfter=20)
    style_norm = ParagraphStyle('Norm', fontName=font_name, fontSize=12, spaceAfter=8)

    elements = []
    
    elements.append(Paragraph("<b>КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ</b>", style_title))
    elements.append(Paragraph(f"<b>Поставщик:</b> {dealer_company}", style_norm))
    elements.append(Paragraph(f"<b>Заказчик / Объект:</b> {client_name}", style_norm))
    elements.append(Spacer(1, 15))

    table_data = [["№", "Наименование", "Кол-во", "Цена, ₽", "Сумма, ₽"]]
    idx = 1
    for i in items:
        cat = i.get("cat")
        name = i.get("name")
        qty = int(i.get("qty", 1))
        base_price = float(i.get("base_price", 0))

        client_price = base_price if cat == "works" else round(base_price * (1 + markup_pct / 100.0))
        row_sum = client_price * qty

        table_data.append([
            str(idx),
            name,
            f"{qty} шт.",
            f"{int(client_price):,}".replace(",", " "),
            f"{int(row_sum):,}".replace(",", " ")
        ])
        idx += 1

    t = Table(table_data, colWidths=[30, 250, 50, 80, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#38bdf8")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), font_name),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))

    elements.append(t)
    elements.append(Spacer(1, 20))

    style_total = ParagraphStyle('Total', fontName=font_name, fontSize=14, alignment=2, spaceAfter=20)
    elements.append(Paragraph(f"<b>ИТОГО ПОД КЛЮЧ: {int(client_total):,} ₽</b>".replace(",", " "), style_total))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- РОУТЫ FLASK ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return "OK", 200

@app.route("/api/test_order", methods=["POST"])
def handle_test_order():
    try:
        data = request.json or {}
        user = data.get("user", {})
        user_id = user.get("id")
        username = user.get("username", "Без_ника")
        first_name = user.get("first_name", "Клиент")
        client_name = data.get("client_name", "Не указан")
        client_phone = data.get("client_phone", "Не указан")
        dealer_company = data.get("dealer_company", "Официальный дилер ПК МИШКА")
        markup_pct = int(data.get("markup_pct", 0))
        items = data.get("items", [])

        goods_base = sum(i["base_price"] * i["qty"] for i in items if i["cat"] != "works")
        works_base = sum(i["base_price"] * i["qty"] for i in items if i["cat"] == "works")
        markup_rub = round(goods_base * (markup_pct / 100.0))
        base_total = goods_base + works_base
        client_total = base_total + markup_rub

        # 1. ЧИСТОЕ КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ ДЛЯ КЛИЕНТА
        kp_lines = [
            "🐻 <b>ПК «МИШКА» — КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ</b>",
            f"📍 Заказчик / Объект: <b>{client_name}</b>",
            "──────────────────────────",
            "<b>📦 Оборудование и материалы:</b>"
        ]
        for i in items:
            if i["cat"] != "works":
                client_unit_price = round(i["base_price"] * (1 + markup_pct / 100.0))
                row_sum = client_unit_price * i["qty"]
                kp_lines.append(f"• {i['name']} ({i['qty']} шт.) — <b>{row_sum:,} ₽</b>".replace(",", " "))

        work_items = [i for i in items if i["cat"] == "works"]
        if work_items:
            kp_lines.append("")
            kp_lines.append("<b>🚜 Монтажные работы под ключ:</b>")
            for i in work_items:
                row_sum = i["base_price"] * i["qty"]
                kp_lines.append(f"• {i['name']} — <b>{row_sum:,} ₽</b>".replace(",", " "))

        kp_lines.extend([
            "──────────────────────────",
            f"✅ <b>ИТОГО ПОД КЛЮЧ: {client_total:,} ₽</b>".replace(",", " "),
            "🛡 <i>Гарантия на корпус кессона МИШКА и герметичность!</i>",
            "",
            "<i>👆 Готовое КП для вашего заказчика (внутренние цены склада скрыты).</i>"
        ])

        if user_id:
            bot.send_message(user_id, NL.join(kp_lines), parse_mode="HTML")
            
            try:
                pdf_buffer = create_kp_pdf(dealer_company, client_name, items, markup_pct, client_total)
                file_name = f"KP_{client_name.replace(' ', '_')}.pdf" if client_name != "Не указан" else "KP_MISHKA.pdf"
                
                bot.send_document(
                    user_id,
                    document=(file_name, pdf_buffer.getvalue()),
                    caption="📄 Готовый бланк КП для вашего заказчика."
                )
            except Exception as e:
                print(f"Ошибка при генерации PDF: {e}")

        # 2. ВНУТРЕННЯЯ ЗАЯВКА ДЛЯ СКЛАДА И АДМИНОВ
        admin_lines = [
            "🔥 <b>НОВАЯ ЗАЯВКА (МИШКА: КОНФИГУРАТОР + КП)</b>",
            f"👷 Отправитель: {first_name} (@{username})",
            f"🏠 Клиент / Объект: <b>{client_name}</b> | 📞 <b>{client_phone}</b>",
            f"💼 Дилер: <b>{dealer_company}</b>",
            "──────────────────────────"
        ]
        for i in items:
            tag = " [РАБОТА]" if i["cat"] == "works" else ""
            row_sum = i["base_price"] * i["qty"]
            admin_lines.append(f"▫️ {i['name']}{tag} x{i['qty']} = {row_sum:,} ₽".replace(",", " "))

        admin_lines.extend([
            "──────────────────────────",
            f"📦 База оборудования (Склад): <b>{goods_base:,} ₽</b>".replace(",", " "),
            f"🚜 Сумма работ: <b>{works_base:,} ₽</b>".replace(",", " "),
            f"📈 Наценка дилера ({markup_pct}%): <b>+{markup_rub:,} ₽</b>".replace(",", " "),
            f"💵 <b>Итоговая цена для клиента: {client_total:,} ₽</b>".replace(",", " ")
        ])

        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, NL.join(admin_lines), parse_mode="HTML")
            except Exception:
                pass

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# --- КОМАНДЫ БОТА ---
@bot.message_handler(commands=["start"])
def cmd_start(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        text="🐻 Открыть Инженерный Конфигуратор МИШКА",
        web_app=WebAppInfo(url=APP_URL)
    ))
    welcome_lines = [
        "👋 <b>Добро пожаловать в инженерный конфигуратор ПК «МИШКА»!</b>",
        "",
        "Внутри приложения:",
        "🔹 Живая интерактивная схема обустройства скважины в разрезе",
        "🔹 Готовые узлы обвязки в 1 клик (Эконом / Хит / VIP)",
        "🔹 Инженерный контроль забытых деталей (Smart Upsell)",
        "🔹 Режим «Дилер / Клиент» с генерацией чистого КП."
    ]
    bot.send_message(
        message.chat.id,
        NL.join(welcome_lines),
        parse_mode="HTML",
        reply_markup=kb
    )

# --- ФОНОВЫЙ ПОЛЛИНГ И АВТОПИНГ RENDER ---
_threads_started = False

def run_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"Polling error: {e}")

def keep_alive():
    while True:
        time.sleep(600)
        if "onrender.com" in APP_URL:
            try:
                requests.get(f"{APP_URL}/health", timeout=10)
            except Exception:
                pass

def start_background_workers():
    global _threads_started
    if not _threads_started:
        _threads_started = True
        threading.Thread(target=run_bot, daemon=True).start()
        threading.Thread(target=keep_alive, daemon=True).start()

start_background_workers()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
