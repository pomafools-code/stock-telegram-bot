import os
import requests
import pandas as pd
import yfinance as yf

# API Keys & Token ของเจ้านาย
TOKEN = "8716643800:AAFoN_YyOf1hFLUMskEDtfBtQ2NCoEDDe3A"
CHAT_ID = "8735795390"
JSONBIN_BIN_ID = "6a93da60da38895dfe223f00"
JSONBIN_MASTER_KEY = "$2a$10$ABZMwjVjxKfLtpMmhb4uUeL4eqgB1rrZT9UjTpRIUhgQd9.3oUHo2"

headers = {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_MASTER_KEY
}

def send_msg(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print(f"Error sending message: {e}")

def load_watchlist():
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            record = data.get("record", {})
            if isinstance(record, dict):
                return record
    except Exception as e:
        print(f"Error loading from JSONBin: {e}")
    return {}

def generate_kagi_signals(df, reversal_pct=0.03):
    if df.empty or len(df) < 10:
        return "NEUTRAL", 0.0
    
    prices = df['Close']
    current_price = prices.iloc[-1]
    
    trend = "BUY"
    peak = prices.iloc[0]
    trough = prices.iloc[0]
    
    for p in prices:
        if trend == "BUY":
            if p > peak:
                peak = p
            elif p <= peak * (1 - reversal_pct):
                trend = "SELL"
                trough = p
        else: # SELL
            if p < trough:
                trough = p
            elif p >= trough * (1 + reversal_pct):
                trend = "BUY"
                peak = p
                
    return trend, current_price

def check_full_strategy(symbol, data):
    try:
        side = data.get("side", "LONG")
        entry_price = data.get("entry", None)
        tp_price = data.get("tp", None)
        sl_price = data.get("sl", None)

        df = yf.Ticker(symbol).history(period="6mo")
        if df.empty or len(df) < 10:
            return None

        current_close = df['Close'].iloc[-1]
        alerts = []

        # 1. ตรวจสอบเงื่อนไขราคา Entry
        if entry_price is not None:
            if side.upper() == "LONG" and current_close <= entry_price:
                alerts.append(f"🔔 ถึงราคาเข้าซื้อ ENTRY LONG: หุ้น {symbol}\n- ราคาปัจจุบัน (${current_close:.2f}) ลงมาถึงจุดเข้าซื้อ (${entry_price:.2f})\n[ByPomSwingtrader]")
            elif side.upper() == "SHORT" and current_close >= entry_price:
                alerts.append(f"🔔 ถึงราคาเข้าชอร์ต ENTRY SHORT: หุ้น {symbol}\n- ราคาปัจจุบัน (${current_close:.2f}) ขึ้นมาถึงจุดเข้าชอร์ต (${entry_price:.2f})\n[ByPomSwingtrader]")

        # 2. ตรวจสอบเงื่อนไข Take Profit (TP)
        if tp_price is not None:
            if side.upper() == "LONG" and current_close >= tp_price:
                alerts.append(f"🎯 ถึงเป้า Take Profit (TP) LONG: หุ้น {symbol}\n- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n[ByPomSwingtrader]")
            elif side.upper() == "SHORT" and current_close <= tp_price:
                alerts.append(f"🎯 ถึงเป้า Take Profit (TP) SHORT: หุ้น {symbol}\n- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n[ByPomSwingtrader]")

        # 3. ตรวจสอบเงื่อนไข Stop Loss (SL)
        if sl_price is not None:
            if side.upper() == "LONG" and current_close <= sl_price:
                alerts.append(f"🛑 ชนจุด Stop Loss (SL) LONG: หุ้น {symbol}\n- ราคาปัจจุบัน (${current_close:.2f}) หลุด SL (${sl_price:.2f})\n[ByPomSwingtrader]")
            elif side.upper() == "SHORT" and current_close >= sl_price:
                alerts.append(f"🛑 ชนจุด Stop Loss (SL) SHORT: หุ้น {symbol}\n- ราคาปัจจุบัน (${current_close:.2f}) ทะลุ SL (${sl_price:.2f})\n[ByPomSwingtrader]")

        # 4. ตรวจสอบสัญญาณ Kagi Chart 3%
        kagi_trend, _ = generate_kagi_signals(df, reversal_pct=0.03)
        if side.upper() == "LONG" and kagi_trend == "BUY":
            alerts.append(f"🟢 สัญญาณ Kagi 3% BUY: หุ้น {symbol}\n- ราคาปัจจุบัน: ${current_close:.2f}\n[ByPomSwingtrader]")
        elif side.upper() == "SHORT" and kagi_trend == "SELL":
            alerts.append(f"🔴 สัญญาณ Kagi 3% SELL: หุ้น {symbol}\n- ราคาปัจจุบัน: ${current_close:.2f}\n[ByPomSwingtrader]")

        return "\n\n".join(alerts) if alerts else None

    except Exception as e:
        return f"Error processing {symbol}: {e}"

if __name__ == "__main__":
    watchlist = load_watchlist()
    if watchlist:
        print(f"กำลังสแกนหุ้นจำนวน {len(watchlist)} ตัว...")
        for symbol, data in watchlist.items():
            res = check_full_strategy(symbol, data)
            if res:
                send_msg(res)
                print(f"ส่งการแจ้งเตือนหุ้น {symbol} เรียบร้อย")
    else:
        print("ไม่พบรายชื่อหุ้นใน Cloud")
