import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, ConversationHandler, filters
)
import openai
import mercadopago
import psycopg2
from psycopg2.extras import Json

load_dotenv()

# ===================== CONFIG =====================
PUBLIC_TOKEN = os.getenv("BOT_PUBLIC_TOKEN")
ADMIN_TOKEN = os.getenv("BOT_ADMIN_TOKEN")
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

# ===================== BANCO =====================
def get_db_conn():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            data JSONB DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            plan TEXT,
            price NUMERIC,
            status TEXT DEFAULT 'pending',
            payment_id TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# ===================== PLANOS =====================
PLANS = {
    "basico": {"name": "Básico", "price": 2.00, "features": ["4 conteúdos exclusivos"]},
    "premium": {"name": "Premium", "price": 30.00, "features": ["15+ conteúdos + prioridade + bônus"]}
}

# ===================== BOT PÚBLICO =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Ver Planos", callback_data="plans")],
        [InlineKeyboardButton("💬 Suporte IA", callback_data="support")],
        [InlineKeyboardButton("📝 Marcar Análise", callback_data="analysis")]
    ]
    await update.message.reply_text(
        "👋 Bem-vindo ao **Xixa Marketing**!\n\nEscolha uma opção abaixo:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "plans":
        text = "🔥 **Planos**\n\n"
        for k, p in PLANS.items():
            text += f"**{p['name']}** - R${p['price']}\n" + "\n".join(f"• {f}" for f in p['features']) + "\n\n"
        text += "Use /comprar basico ou /comprar premium"
        await query.edit_message_text(text)

    elif data == "support":
        await query.edit_message_text("✍️ Envie sua dúvida que a IA vai responder:")

    elif data == "analysis":
        await query.edit_message_text("Vamos iniciar o formulário de análise.\nQual seu nome?")
        return NAME

# ===================== FORMULÁRIO MULTI-ETAPA =====================
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

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id, username, data) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET data = %s",
                (user.id, user.username, Json(context.user_data), Json(context.user_data)))
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text("✅ Formulário salvo com sucesso! O dono foi notificado.")
    # Aqui você pode enviar para o admin bot
    return ConversationHandler.END

# ===================== PAGAMENTO MERCADO PAGO =====================
async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        plan_name = context.args[0].lower()
        plan = PLANS.get(plan_name)
        if not plan:
            await update.message.reply_text("Plano inválido!")
            return

        preference_data = {
            "items": [{"title": plan["name"], "quantity": 1, "unit_price": float(plan["price"])}],
            "back_urls": {"success": "https://seusite.com/sucesso", "failure": "https://seusite.com/erro"},
            "auto_return": "approved"
        }
        preference_response = sdk.preference().create(preference_data)
        payment_url = preference_response["response"]["init_point"]

        await update.message.reply_text(f"🔗 Link de pagamento para **{plan['name']}**:\n{payment_url}")
    except Exception as e:
        await update.message.reply_text("Erro ao gerar pagamento.")

# ===================== IA SUPORTE =====================
async def ia_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": update.message.text}],
            max_tokens=500
        )
        await update.message.reply_text(resp.choices[0].message.content)
    except:
        await update.message.reply_text("Erro na IA. Tente novamente.")

# ===================== MAIN =====================
def main():
    init_db()
    
    app = Application.builder().token(PUBLIC_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("comprar", comprar))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Formulário
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^analysis$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
            DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, details)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ia_handler))

    logger.info("🚀 Bot iniciado com sucesso!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
