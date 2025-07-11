# main.py
import requests, time, json
import pandas as pd
import numpy as np
import telebot
from datetime import datetime

# --- Bot Telegram ---
TOKEN = '8132929879:AAHIPZYtQjWG9OFLAlc4nir_fv_0S_lpSWM'
CHAT_ID = '8120795325'
bot = telebot.TeleBot(TOKEN)

# --- Config Trading ---
PAIR = 'BTCUSDT'
INTERVAL = '15m'
URL = f'https://api.binance.com/api/v3/klines?symbol={PAIR}&interval={INTERVAL}&limit=100'
TP_PERCENT = 0.0002
SL_PERCENT = 0.0002

# --- Status Posisi ---
posisi = None
harga_entry = None

def simpan_posisi():
    with open('posisi.json', 'w') as f:
        json.dump({'posisi': posisi, 'harga_entry': harga_entry}, f)

def muat_posisi():
    global posisi, harga_entry
    try:
        with open('posisi.json', 'r') as f:
            data = json.load(f)
            posisi = data.get('posisi')
            harga_entry = data.get('harga_entry')
    except:
        posisi, harga_entry = None, None

def ambil_data():
    res = requests.get(URL)
    data = res.json()
    df = pd.DataFrame(data, columns=['t','o','h','l','c','v','x','n','taker_buy','n2','n3','n4'])
    df['close'] = df['c'].astype(float)
    return df[['close']]

def indikator(df):
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['BB_MID'] = df['close'].rolling(20).mean()
    df['BB_STD'] = df['close'].rolling(20).std()
    df['BB_UPPER'] = df['BB_MID'] + 2 * df['BB_STD']
    df['BB_LOWER'] = df['BB_MID'] - 2 * df['BB_STD']

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    min_rsi = df['RSI'].rolling(window=14).min()
    max_rsi = df['RSI'].rolling(window=14).max()
    df['StochRSI'] = (df['RSI'] - min_rsi) / (max_rsi - min_rsi)

    df.dropna(inplace=True)
    return df

def kirim(pesan):
    bot.send_message(CHAT_ID, pesan)

def cek_tp_sl(harga):
    global posisi, harga_entry
    tp = harga_entry * (1 + TP_PERCENT) if posisi == 'buy' else harga_entry * (1 - TP_PERCENT)
    sl = harga_entry * (1 - SL_PERCENT) if posisi == 'buy' else harga_entry * (1 + SL_PERCENT)

    if posisi == 'buy':
        if harga >= tp:
            kirim(f"🎯 TP BUY Tercapai @ {harga:.2f}")
            posisi, harga_entry = None, None
            simpan_posisi()
        elif harga <= sl:
            kirim(f"🚫 SL BUY Terpukul @ {harga:.2f}")
            posisi, harga_entry = None, None
            simpan_posisi()
    elif posisi == 'sell':
        if harga <= tp:
            kirim(f"🎯 TP SELL Tercapai @ {harga:.2f}")
            posisi, harga_entry = None, None
            simpan_posisi()
        elif harga >= sl:
            kirim(f"🚫 SL SELL Terpukul @ {harga:.2f}")
            posisi, harga_entry = None, None
            simpan_posisi()

def analisa():
    global posisi, harga_entry
    df = ambil_data()
    df = indikator(df)
    last = df.iloc[-1]
    harga = last['close']

    pesan = (
        f"📊 {PAIR} - {datetime.now().strftime('%H:%M:%S')}\n"
        f"Harga: {harga:.2f} USDT\n"
        f"RSI: {last['RSI']:.2f} | StochRSI: {last['StochRSI']:.2f}\n"
        f"MACD: {last['MACD']:.2f} | Signal: {last['MACD_signal']:.2f}\n"
    )

    if posisi is None:
        if (
            harga < last['BB_LOWER'] and
            last['RSI'] < 30 and
            last['MACD'] > last['MACD_signal'] and
            last['StochRSI'] < 0.2
        ):
            posisi = 'buy'
            harga_entry = harga
            pesan += f"✅ ENTRY BUY @ {harga_entry:.2f}"
            kirim(pesan)
            simpan_posisi()
        elif (
            harga > last['BB_UPPER'] and
            last['RSI'] > 70 and
            last['MACD'] < last['MACD_signal'] and
            last['StochRSI'] > 0.8
        ):
            posisi = 'sell'
            harga_entry = harga
            pesan += f"❌ ENTRY SELL @ {harga_entry:.2f}"
            kirim(pesan)
            simpan_posisi()
        else:
            pesan += "⏳ Belum ada sinyal entry"
            kirim(pesan)
    else:
        cek_tp_sl(harga)

    print(pesan)

# --- Run Setiap 15 Menit ---
muat_posisi()
while True:
    try:
        analisa()
    except Exception as e:
        kirim(f"⚠️ Error: {str(e)}")
    time.sleep(900)  # 15 menit