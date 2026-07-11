import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_PUBLIC_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Ver Planos", callback_data="plans")],
        [InlineKeyboardButton("💬 Suporte", callback_data="support")]
    ]
    await update.message.reply_text("✅ Bot Xixa Marketing Online!\nEscolha uma opção abaixo:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "plans":
        await query.edit_message_text("📊 *Nossos Planos:*\n\nBásico R$97/mês\nPremium R$297/mês\n\nChama no Whats pra fechar!", parse_mode="Markdown")
    elif query.data == "support":
        await query.edit_message_text("💬 Suporte em desenvolvimento...\nEm breve você fala direto com um atendente.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    logger.info("✅ Bot iniciado com sucesso")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
