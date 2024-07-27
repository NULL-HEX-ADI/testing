import logging
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import numpy as np
from sklearn.linear_model import LinearRegression

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Initialize Firebase
cred = credentials.Certificate('credentials/firebase-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define command handlers
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update.message.reply_text(f'Hi {user.mention_markdown_v2()}! Use /analyze <crypto> to get analysis.', parse_mode='MarkdownV2')

def analyze(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    args = context.args
    if not args:
        update.message.reply_text('Please specify a cryptocurrency (e.g., /analyze bitcoin).')
        return

    crypto = args[0].lower()
    update.message.reply_text(f'Analyzing {crypto}, please wait...')

    # Fetch crypto data
    data = fetch_crypto_data(crypto)
    if not data:
        update.message.reply_text('Failed to fetch data. Please check the cryptocurrency name or try again later.')
        return

    # Store data in Firebase
    store_crypto_data(crypto, data)

    # Get historical data from Firebase
    historical_data = get_historical_data(crypto)
    if not historical_data:
        update.message.reply_text(f'No historical data available for {crypto}.')
        return

    # Predict price
    predicted_price = predict_price(historical_data)
    update.message.reply_text(f'Predicted price of {crypto} after 10 minutes: ${predicted_price:.2f}')

def fetch_crypto_data(crypto):
    url = f"https://api.coingecko.com/api/v3/coins/{crypto}/market_chart?vs_currency=usd&days=30"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException: {e}")
        return None

def store_crypto_data(crypto, data):
    prices = data['prices']
    for price in prices:
        timestamp, price_value = price
        db.collection('crypto_data').add({
            'crypto_name': crypto,
            'timestamp': timestamp,
            'price': price_value
        })

def get_historical_data(crypto):
    docs = db.collection('crypto_data').where('crypto_name', '==', crypto).order_by('timestamp').stream()
    data = [{'timestamp': doc.to_dict()['timestamp'], 'price': doc.to_dict()['price']} for doc in docs]
    return data

def predict_price(historical_data):
    timestamps = np.array([data['timestamp'] for data in historical_data]).reshape(-1, 1)
    prices = np.array([data['price'] for data in historical_data])

    model = LinearRegression()
    model.fit(timestamps, prices)

    future_timestamp = np.array([[timestamps[-1][0] + 600000]])
    predicted_price = model.predict(future_timestamp)
    return predicted_price[0]

def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater("7494284416:AAFiAy_aSAyY0oMnV0wXc8z97rADndRaQQk")

    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("analyze", analyze))

    # Start the Bot
    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()
