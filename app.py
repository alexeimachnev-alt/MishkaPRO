import os
import time
import threading
import requests
import io
import datetime
from flask import Flask, request, render_template, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_НОВОГО_БОТА")
APP_URL = os.environ.get("APP_URL", "https://твой-новый-сервис.onrender.com").rstrip("/")
ADMIN_IDS = [551209811, 447208738, 840231919]

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__, template_folder=".")
NL = chr(10)

def create_kp_pdf(dealer_company, client_name, items, markup_pct, client_total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)

    try:
        pdfmetrics.registerFont(TTFont('Roboto', 'Roboto-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', 'Roboto-Bold.ttf'))
        pdfmetrics.registerFontFamily('Roboto', normal='Roboto', bold='Roboto-Bold')
        font_name = 'Roboto'
        font_bold = 'Roboto-Bold'
    except Exception:
        try:
            pdfmetrics.registerFont(TTFont('Calibri', 'calibri.ttf'))
            pdfmetrics.registerFont(TTFont('Calibri-Bold', 'calibrib.ttf'))
            pdfmetrics.registerFontFamily('Calibri', normal='Calibri', bold='Calibri-Bold')
            font_name = 'Calibri'
            font_bold = 'Calibri-Bold'
        except Exception:
            font_name = 'Helvetica'
            font_bold = 'Helvetica-Bold'

    styles = getSampleStyleSheet()
    TEXT_DARK = colors.HexColor("#0f172a")
    TEXT_MUTED = colors.HexColor("#64748b")
    ACCENT = colors.HexColor("#0284c7")
    ACCENT_LIGHT = colors.HexColor("#38bdf8")
    BG_LIGHT = colors.HexColor("#f8fafc")
    BORDER_COLOR = colors.HexColor("#e2e8f0")

    style_h1 = ParagraphStyle('H1', fontName=font_bold, fontSize=20, textColor=ACCENT, spaceAfter=5)
    style_date = ParagraphStyle('Date', fontName=font_name, fontSize=10, textColor=TEXT_MUTED, spaceAfter=20)
    style_label = ParagraphStyle('Label', fontName=font_bold, fontSize=10, textColor=TEXT_MUTED)
    style_value = ParagraphStyle('Value', fontName=font_name, fontSize=11, textColor=TEXT_DARK, spaceAfter=10)
    style_guarantee = ParagraphStyle('Guarantee', fontName=font_name, fontSize=10, textColor=TEXT_DARK, leading=14)

    elements = []
    
    current_date = datetime.datetime.now().strftime("%d.%m.%Y")
    left_header = [Paragraph("<b>КОММЕРЧЕСКОЕ<br/>ПРЕДЛОЖЕНИЕ</b>", style_h1), Paragraph(f"От {current_date}", style_date)]
    right_header = [
        Paragraph("ДИЛЕР / ПОСТАВЩИК:", style_label), Paragraph(dealer_company, style_value),
        Paragraph("ДЛЯ КЛИЕНТА / ОБЪЕКТА:", style_label), Paragraph(client_name, style_value)
    ]
    
    header_table = Table([[left_header, right_header]], colWidths=[270, 240])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    table_data = [["№", "Наименование оборудования и работ", "Кол-во", "Цена, ₽", "Сумма, ₽"]]
    idx = 1
    for i in items:
        cat = i.get("cat")
        name = i.get("name") # ВНИМАНИЕ: Сюда уже будет приходить русское название из Web App
        qty = int(i.get("qty", 1))
        base_price = float(i.get("base_price", 0))

        client_price = base_price if cat == "works" else round(base_price * (1 + markup_pct / 100.0))
        row_sum = client_price * qty
        prefix = "🚜 " if cat == "works" else ""

        table_data.append([str(idx), prefix + name, f"{qty} шт.", f"{int(client_price):,}".replace(",", " "), f"{int(row_sum):,}".replace(",", " ")])
        idx += 1

    t = Table(table_data, colWidths=[30, 260, 50, 80, 90])
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), font_bold), ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 10), ('TOPPADDING', (0,0), (-1,0), 10),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,0), (1,-1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ])
    
    for row in range(1, len(table_data)):
        bg = colors.white if row % 2 == 1 else BG_LIGHT
        t_style.add('BACKGROUND', (0,row), (-1,row), bg)
        t_style.add('FONTNAME', (0,row), (-1,row), font_name)
        t_style.add('FONTSIZE', (0,row), (-1,row), 10)
        t_style.add('TEXTCOLOR', (0,row), (-1,row), TEXT_DARK)
        t_style.add('BOTTOMPADDING', (0,row), (-1,row), 10)
        t_style.add('TOPPADDING', (0,row), (-1,row), 10)
        t_style.add('LINEBELOW', (0,row), (-1,row), 0.5, BORDER_COLOR)

    t.setStyle(t_style)
    elements.append(t)
    elements.append(Spacer(1, 20))

    total_data = [["ИТОГО ПОД КЛЮЧ:", f"{int(client_total):,} ₽".replace(",", " ")]]
    total_table = Table(total_data, colWidths=[390, 120])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,0), font_name), ('FONTNAME', (1,0), (1,0), font_bold),
        ('FONTSIZE', (0,0), (-1,-1), 14), ('TEXTCOLOR', (0,0), (-1,-1), TEXT_DARK),
        ('ALIGN', (0,0), (0,0), 'RIGHT'), ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LINEABOVE', (0,0), (-1,-1), 2.5, ACCENT_LIGHT)
    ]))
    
    elements.append(KeepTogether([total_table, Spacer(1, 30)]))

    guarantee_block = [
        Paragraph("<b>ГАРАНТИЙНЫЕ ОБЯЗАТЕЛЬСТВА</b>", ParagraphStyle('G_Title', fontName=font_bold, fontSize=11, textColor=ACCENT, spaceAfter=6)),
        Paragraph("Настоящее коммерческое предложение включает использование оригинального оборудования. "
                  "Гарантия на 100% герметичность и целостность полипропиленового корпуса кессона <b>МИШКА</b> "
                  "предоставляется напрямую от завода-изготовителя.", style_guarantee)
    ]
    
    g_table = Table([[guarantee_block]], colWidths=[510])
    g_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT), ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (-1,-1), 15), ('RIGHTPADDING', (0,0), (-1,-1), 15),
    ]))
    elements.append(g_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.route("/")
def index(): return render_template("index.html")

@app.route("/health")
def health(): return "OK", 200

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

        # Текст КП всегда на русском
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
            "<i>👆 Готовое КП для вашего заказчика.</i>"
        ])

        if user_id:
            bot.send_message(user_id, NL.join(kp_lines), parse_mode="HTML")
            try:
                pdf_buffer = create_kp_pdf(dealer_company, client_name, items, markup_pct, client_total)
                file_name = f"KP_{client_name.replace(' ', '_')}.pdf" if client_name != "Не указан" else "KP_MISHKA.pdf"
                bot.send_document(user_id, document=(file_name, pdf_buffer.getvalue()), caption="📄 Стилизованный бланк КП для заказчика.")
            except Exception as e:
                print(f"Ошибка при генерации PDF: {e}")

        # Админская заявка тоже всегда на русском
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
            try: bot.send_message(admin_id, NL.join(admin_lines), parse_mode="HTML")
            except: pass
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bot.message_handler(commands=["start"])
def cmd_start(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="🐻 Открыть Инженерный Конфигуратор МИШКА", web_app=WebAppInfo(url=APP_URL)))
    welcome_lines = [
        "👋 <b>Добро пожаловать в инженерный конфигуратор ПК «МИШКА»!</b>",
        "",
        "Внутри приложения:",
        "🔹 Живая интерактивная схема обустройства скважины в разрезе",
        "🔹 Готовые узлы обвязки в 1 клик (Эконом / Хит / VIP)",
        "🔹 Инженерный контроль забытых деталей (Smart Upsell)",
        "🔹 Режим «Дилер / Клиент» с генерацией чистого КП."
    ]
    bot.send_message(message.chat.id, NL.join(welcome_lines), parse_mode="HTML", reply_markup=kb)

_threads_started = False
def run_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except: pass

def keep_alive():
    while True:
        time.sleep(600)
        if "onrender.com" in APP_URL:
            try: requests.get(f"{APP_URL}/health", timeout=10)
            except: pass

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
