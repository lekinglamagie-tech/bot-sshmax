import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "COLLE_TON_TOKEN_ICI"
ADMIN_ID = 123456789

db = sqlite3.connect("sshmax.db", check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS clients
(pseudo TEXT PRIMARY KEY, lien TEXT, serveur TEXT, date_creation TEXT, date_fin TEXT, bloque INTEGER, alerte_3j INTEGER, alerte_1j INTEGER, alerte_expire INTEGER)""")
db.commit()

async def new_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Utilise : /new @pseudo + lien")
        return
    pseudo = context.args[0]; lien = context.args[1]
    debut = datetime.now(); fin = debut + timedelta(days=30)
    db.execute("INSERT OR REPLACE INTO clients VALUES (?,?,?,?,?,0,0,0,0)", (pseudo, lien, "VMess France", debut.strftime("%d/%m/%Y"), fin.strftime("%d/%m/%Y")))
    db.commit()
    await update.message.reply_text(f"✅ {pseudo} enregistré\nFin : {fin.strftime('%d/%m/%Y')}")

async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.execute("SELECT pseudo, date_fin, bloque FROM clients").fetchall()
    texte = "📋 TES CLIENTS :\n\n"
    for pseudo, date_fin, bloque in rows:
        statut = "⛔ BLOQUÉ" if bloque == 1 else "🟢 ACTIF"
        texte += f"{pseudo} - expire {date_fin} - {statut}\n"
    await update.message.reply_text(texte if rows else "Aucun client")

async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pseudo = context.args[0]
    db.execute("UPDATE clients SET bloque=1 WHERE pseudo=?", (pseudo,)); db.commit()
    await update.message.reply_text(f"⛔ {pseudo} bloqué")

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pseudo = context.args[0]
    db.execute("UPDATE clients SET bloque=0 WHERE pseudo=?", (pseudo,)); db.commit()
    await update.message.reply_text(f"✅ {pseudo} débloqué")

async def conso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pseudo = context.args[0]
    row = db.execute("SELECT date_creation, date_fin FROM clients WHERE pseudo=?", (pseudo,)).fetchone()
    fin_dt = datetime.strptime(row[1], "%d/%m/%Y")
    restants = (fin_dt - datetime.now()).days
    await update.message.reply_text(f"📊 {pseudo}\nExpire : {row[1]}\nReste : {restants} jours")

async def monfichier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pseudo = "@" + (update.effective_user.username or "")
    row = db.execute("SELECT lien, date_fin FROM clients WHERE pseudo=?", (pseudo,)).fetchone()
    if row:
        await update.message.reply_text(f"Ton fichier (expire {row[1]}) :\n`{row[0]}`")
    else:
        await update.message.reply_text("Pas de fichier, contacte l'admin")

async def renouveler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pseudo = context.args[0]; lien = context.args[1]
    debut = datetime.now(); fin = debut + timedelta(days=30)
    db.execute("UPDATE clients SET lien=?, date_creation=?, date_fin=?, bloque=0, alerte_3j=0, alerte_1j=0, alerte_expire=0 WHERE pseudo=?", (lien, debut.strftime("%d/%m/%Y"), fin.strftime("%d/%m/%Y"), pseudo))
    db.commit()
    await update.message.reply_text(f"✅ {pseudo} renouvelé jusqu'au {fin.strftime('%d/%m/%Y')}")

async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    rows = db.execute("SELECT pseudo, date_fin, bloque, alerte_3j, alerte_1j, alerte_expire FROM clients").fetchall()
    aujourdhui = datetime.now().date()
    for pseudo, date_fin, bloque, a3, a1, a0 in rows:
        if bloque == 1: continue
        fin_dt = datetime.strptime(date_fin, "%d/%m/%Y").date()
        jours = (fin_dt - aujourdhui).days
        if jours == 3 and a3 == 0:
            await context.bot.send_message(ADMIN_ID, f"⚠️ {pseudo} expire dans 3 jours ({date_fin})")
            db.execute("UPDATE clients SET alerte_3j=1 WHERE pseudo=?", (pseudo,))
        elif jours == 1 and a1 == 0:
            await context.bot.send_message(ADMIN_ID, f"🔔 {pseudo} expire DEMAIN ({date_fin})")
            db.execute("UPDATE clients SET alerte_1j=1 WHERE pseudo=?", (pseudo,))
        elif jours <= 0 and a0 == 0:
            await context.bot.send_message(ADMIN_ID, f"⛔ {pseudo} EXPIRÉ ({date_fin})")
            db.execute("UPDATE clients SET alerte_expire=1 WHERE pseudo=?", (pseudo,))
        db.commit()

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("new", new_client))
app.add_handler(CommandHandler("list", liste))
app.add_handler(CommandHandler("block", block))
app.add_handler(CommandHandler("unblock", unblock))
app.add_handler(CommandHandler("conso", conso))
app.add_handler(CommandHandler("monfichier", monfichier))
app.add_handler(CommandHandler("renouveler", renouveler))
app.job_queue.run_repeating(check_expirations, interval=3600, first=10)
app.run_polling()
