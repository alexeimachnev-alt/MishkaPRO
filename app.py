
from flask import Flask, render_template, request, send_file
import pdfkit
import os

app = Flask(__name__)

# Пример базы кессонов (в реальном проекте берется из БД)
CAISSONS = {
    'caisson_1': {'name': 'Кессон Корсар 1', 'price': 45000},
    'caisson_2': {'name': 'Кессон Корсар 2', 'price': 55000},
    'caisson_3': {'name': 'Кессон Корсар 3', 'price': 65000},
    'caisson_4': {'name': 'Кессон Аква', 'price': 35000}
}

@app.route('/')
def index():
    return render_template('index.html', caissons=CAISSONS)

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    # Получаем данные от дилера
    dealer_name = request.form.get('dealer_name', 'ООО Дилер')
    dealer_phone = request.form.get('dealer_phone', '+7 (999) 000-00-00')
    markup = float(request.form.get('markup', 0))
    caisson_id = request.form.get('caisson_id', 'caisson_1')
    
    # Расчеты
    caisson = CAISSONS.get(caisson_id, CAISSONS['caisson_1'])
    base_price = caisson['price']
    final_price = base_price + markup

    # Данные для PDF шаблона
    data = {
        'dealer_name': dealer_name,
        'dealer_phone': dealer_phone,
        'item_name': caisson['name'],
        'base_price': base_price,
        'final_price': final_price,
        'markup': markup
    }

    # Рендерим HTML для PDF
    rendered = render_template('pdf_template.html', **data)
    
    # Настройки для pdfkit 
    # ВАЖНО: на сервере должен быть установлен wkhtmltopdf
    options = {
        'page-size': 'A4',
        'encoding': "UTF-8",
        'margin-top': '20mm',
        'margin-bottom': '20mm',
        'margin-left': '20mm',
        'margin-right': '20mm',
    }
    
    pdf = pdfkit.from_string(rendered, False, options=options)
    
    pdf_path = 'commercial_offer.pdf'
    with open(pdf_path, 'wb') as f:
        f.write(pdf)
        
    # === ИНТЕГРАЦИЯ С ТЕЛЕГРАМ-БОТОМ (Пример) ===
    # Если вы используете Aiogram или telebot:
    # 
    # text_message = f"✅ КП сформировано!\nКессон: {caisson['name']}\nЗакупочная цена: {base_price} руб.\nНаценка: {markup} руб.\nИтого для клиента: {final_price} руб."
    # bot.send_message(chat_id, text_message)
    # bot.send_document(chat_id, open(pdf_path, 'rb'))
    # ===========================================
        
    return send_file(pdf_path, as_attachment=True, download_name='Смета_для_клиента.pdf')

if __name__ == '__main__':
    app.run(debug=True)
