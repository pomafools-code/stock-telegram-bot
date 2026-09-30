from datetime import datetime
import os
import pandas as pd
import pytz
import requests
import yfinance as yf

# ==========================================
# API Keys & Credentials
# ==========================================
TOKEN = os.getenv("TELEGRAM_TOKEN", "8716643800:AAFoN_YyOf1hFLUMskEDtfBtQ2NCoEDDe3A")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8735795390")
JSONBIN_BIN_ID = os.getenv("JSONBIN_BIN_ID", "6a93da60da38895dfe223f00")
JSONBIN_MASTER_KEY = os.getenv(
    "JSONBIN_MASTER_KEY",
    "$2a$10$ABZMwjVjxKfLtpMmhb4uUeL4eqgB1rrZT9UjTpRIUhgQd9.3oUHo2"
)

headers = {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_MASTER_KEY,
}


def send_msg(text):
    """ฟังก์ชันส่งข้อความไปยัง Telegram"""
    if not text:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if not res_data.get("ok"):
            print(f"❌ Telegram API Error: {res_data.get('description')}")
        else:
            print("✅ ส่งข้อความไปยัง Telegram สำเร็จ")
    except Exception as e:
        print(f"❌ Error sending message: {e}")


def load_watchlist():
    """ดึงรายชื่อหุ้นจาก JSONBin"""
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            record = data.get("record", {})
            # ป้องกันกรณี JSONBin ซ้อน Key ชื่อ 'watchlist'
            if "watchlist" in record:
                return record["watchlist"]
            if isinstance(record, dict):
                return record
        else:
            print(f"❌ JSONBin Error Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error loading from JSONBin: {e}")
    return {}


def check_full_strategy(symbol, data):
    """สแกนเงื่อนไขราคา Entry, TP, SL"""
    try:
        side = str(data.get("side", "LONG")).upper()

        entry_price = float(data["entry"]) if data.get("entry") not in [None, "-", ""] else None
        tp_price = float(data["tp"]) if data.get("tp") not in [None, "-", ""] else None
        sl_price = float(data["sl"]) if data.get("sl") not in [None, "-", ""] else None

        df = yf.Ticker(symbol).history(period="6mo")
        if df.empty or len(df) < 10:
            print(f"⚠️ หุ้น {symbol}: ไม่พบข้อมูลราคา")
            return None

        current_close = df["Close"].iloc[-1]
        alerts = []

        # 1. ตรวจสอบเงื่อนไข Entry
        if entry_price is not None:
            if side == "LONG" and current_close <= entry_price:
                alerts.append(
                    f"🔔 ถึงราคาเข้าซื้อ ENTRY LONG: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ลงมาถึงจุดเข้าซื้อ (${entry_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
            elif side == "SHORT" and current_close >= entry_price:
                alerts.append(
                    f"🔔 ถึงราคาเข้าชอร์ต ENTRY SHORT: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ขึ้นมาถึงจุดเข้าชอร์ต (${entry_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )

        # 2. ตรวจสอบเงื่อนไข Take Profit (TP)
        if tp_price is not None:
            if side == "LONG" and current_close >= tp_price:
                alerts.append(
                    f"🎯 ถึงเป้า Take Profit (TP) LONG: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
            elif side == "SHORT" and current_close <= tp_price:
                alerts.append(
                    f"🎯 ถึงเป้า Take Profit (TP) SHORT: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )

        # 3. ตรวจสอบเงื่อนไข Stop Loss (SL)
        if sl_price is not None:
            if side == "LONG" and current_close <= sl_price:
                alerts.append(
                    f"🛑 ชนจุด Stop Loss (SL) LONG: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) หลุด SL (${sl_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
            elif side == "SHORT" and current_close >= sl_price:
                alerts.append(
                    f"🛑 ชนจุด Stop Loss (SL) SHORT: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ทะลุ SL (${sl_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )

        return "\n\n".join(alerts) if alerts else None

    except Exception as e:
        print(f"❌ Error processing {symbol}: {e}")
        return None


def get_daily_summary(watchlist):
    """สร้างข้อความรายงานสรุปราคาหุ้น"""
    summary_msgs = []
    tz = pytz.timezone("Asia/Bangkok")
    now_str = datetime.now(tz).strftime("%d/%m/%Y %H:%M")

    summary_msgs.append(f"📊 รายงานสรุปราคาหุ้นประจำรอบ ({now_str} น.)\n[ByPomSwingtrader]\n")

    for symbol, data in watchlist.items():
        try:
            side = str(data.get("side", "LONG")).upper()
            entry_price = data.get("entry", "-")
            tp_price = data.get("tp", "-")
            sl_price = data.get("sl", "-")

            df = yf.Ticker(symbol).history(period="5d")
            if len(df) >= 2:
                current_close = df["Close"].iloc[-1]
                prev_close = df["Close"].iloc[-2]
                change_pct = ((current_close - prev_close) / prev_close) * 100
                status_icon = "🟢" if change_pct >= 0 else "🔴"

                msg = (
                    f"🔹 หุ้น {symbol} ({side})\n"
                    f"- ราคาปัจจุบัน: ${current_close:.2f} ({status_icon} {change_pct:+.2f}%)\n"
                    f"- Entry: ${entry_price} | TP: ${tp_price} | SL: ${sl_price}"
                )
                summary_msgs.append(msg)
            elif len(df) == 1:
                current_close = df["Close"].iloc[-1]
                msg = (
                    f"🔹 หุ้น {symbol} ({side})\n"
                    f"- ราคาปัจจุบัน: ${current_close:.2f}\n"
                    f"- Entry: ${entry_price} | TP: ${tp_price} | SL: ${sl_price}"
                )
                summary_msgs.append(msg)
        except Exception as e:
            summary_msgs.append(f"❌ หุ้น {symbol}: ดึงข้อมูลไม่ได้ ({e})")

    return "\n\n".join(summary_msgs)


def should_send_summary(current_hour, today_str):
    """ตรวจสอบช่วงเวลา 06.00-08.59 และ 17.00-19.59 พร้อมป้องกันการส่งซ้ำ"""
    flag_file = f"summary_sent_{today_str}.txt"

    period = None
    if 6 <= current_hour < 9:
        period = "MORNING"
    elif 17 <= current_hour < 20:
        period = "EVENING"

    # ถ้านอกช่วงเวลาส่งสรุป ให้ข้าม
    if not period:
        return False, None

    # ตรวจสอบประวัติการส่งของวันนี้
    sent_periods = []
    if os.path.exists(flag_file):
        with open(flag_file, "r") as f:
            sent_periods = f.read().splitlines()

    # หากยังไม่เคยส่งในรอบนี้ ให้ผ่านและลงบันทึก
    if period not in sent_periods:
        with open(flag_file, "a") as f:
            f.write(f"{period}\n")
        return True, period

    return False, period


if __name__ == "__main__":
    watchlist = load_watchlist()
    print(f"📌 ดึง Watchlist ได้ทั้งหมด: {len(watchlist)} รายการ")

    if watchlist:
        tz = pytz.timezone("Asia/Bangkok")
        now = datetime.now(tz)
        current_hour = now.hour
        today_str = now.strftime("%Y-%m-%d")

        print(f"⏰ เวลาปัจจุบัน (Bangkok): {now.strftime('%H:%M:%S')}")

        # 1. ตรวจสอบการส่งรายงานสรุป (ช่วงเช้า 06-08 น. / ช่วงเย็น 17-19 น.)
        send_flag, period_name = should_send_summary(current_hour, today_str)
        if send_flag:
            print(f"📢 กำลังส่งรายงานสรุปหุ้นประจำรอบช่วงเวลา ({period_name})...")
            summary_text = get_daily_summary(watchlist)
            send_msg(summary_text)
        else:
            if period_name:
                print(f"ℹ️️ รอบ {period_name} ของวันนี้ ได้ทำการส่งสรุปไปเรียบร้อยแล้ว")
            else:
                print("ℹ️ นอกช่วงเวลาการส่งรายงานสรุปประจำรอบ (06.00-08.59 น. / 17.00-19.59 น.)")

        # 2. สแกนเงื่อนไขราคาเข้า/ออก หุ้นแต่ละตัว
        print(f"🔍 กำลังสแกนเงื่อนไขหุ้นจำนวน {len(watchlist)} ตัว...")
        for symbol, data in watchlist.items():
            res = check_full_strategy(symbol, data)
            if res:
                send_msg(res)
                print(f"✅ ส่งการแจ้งเตือนเงื่อนไขหุ้น {symbol} เรียบร้อย")
            else:
                print(f"ℹ️ หุ้น {symbol}: ยังไม่เข้าเงื่อนไขแจ้งเตือน")
    else:
        print("❌ ไม่พบรายชื่อหุ้นใน Cloud หรือดึงข้อมูล JSONBin ไม่สำเร็จ")
