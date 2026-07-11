import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, ConversationHandler, filters
)
import openai
import mercadopago
import psycopg2
from psycopg2.extras import Json

load_dotenv()

# Configurações
PUBLIC_TOKEN = os.getenv("BOT_PUBLIC_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MP_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
DB_URL = os.getenv("DB_URL")

openai.api_key = OPENAI_API_KEY
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Estados do formulário
NAME, PHONE, DETAILS = range(3)

PLANS = {
    "basico": {"name": "Básico", "price": 2.00, "features": ["4 conteúdos exclusivos"]},
    "premium": {"name": "Premium", "price": 30.00, "features": ["15+ conteúdos + prioridade + bônus"]}
}

def init_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            data JSONB DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            plan TEXT,
            price NUMERIC,
            status TEXT DEFAULT 'pending',
            payment_id TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Ver Planos", callback_data="plans")],
        [InlineKeyboardButton("💬 Suporte IA", callback_data="support")],
        [InlineKeyboardButton("📝 Marcar Análise", callback_data="analysis")]
    ]
    await update.message.reply_text("👋 Bem-vindo ao Xixa Marketing Bot!", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "plans":
        text = "🔥 Planos:\n\n"
        for k, p in PLANS.items():
            text += f"**{p['name']}** - R${p['price']}\n" + "\n".join([f"• {f}" for f in p["features"]]) + "\n\n"
        await query.edit_message_text(text + "Use: /comprar basico ou /comprar premium")
    elif query.data == "support":
        await query.edit_message_text("Envie sua dúvida:")
    elif query.data == "analysis":
        await query.edit_message_text("Qual é o seu nome?")
        return NAME

# Formulário
async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Qual seu telefone?")
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Descreva o que precisa na análise:")
    return DETAILS

async def details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data['details'] = update.message.text

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id, username, data) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET data = %s",
                (user.id, user.username, Json(context.user_data), Json(context.user_data)))
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text("✅ Dados salvos com sucesso! O administrador foi notificado.")
    return ConversationHandler.END

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        plan_key = context.args[0].lower()
        plan = PLANS.get(plan_key)
        if not plan:
            return await update.message.reply_text("Plano inválido! Use basico ou premium.")

        preference = {
            "items": [{"title": plan["name"], "quantity": 1, "unit_price": float(plan["price"])}],
            "back_urls": {"success": "https://t.me/Marketingxixapubli_bot", "failure": "https://t.me/Marketingxixapubli_bot"}
        }
        response = sdk.preference().create(preference)
        await update.message.reply_text(f"🔗 Pague aqui:\n{response['response']['init_point']}")
    except Exception as e:
        await update.message.reply_text("Erro ao gerar link de pagamento.")

async def ia_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": update.message.text}])
        await update.message.reply_text(resp.choices[0].message.content)
    except:
        await update.message.reply_text("Erro na IA. Tente novamente.")

def main():
    init_db()
    app = Application.builder().token(PUBLIC_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("comprar", comprar))
    app.add_handler(CallbackQueryHandler(button_handler))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^analysis$")],
        states={NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
                DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, details)]},
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ia_handler))

    logger.info("Bot iniciado com sucesso!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
