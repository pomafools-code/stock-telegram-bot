from datetime import datetime
import json
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
            if "watchlist" in record:
                return record["watchlist"]
            if isinstance(record, dict):
                return record
        else:
            print(f"❌ JSONBin Error Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error loading from JSONBin: {e}")
    return {}


def load_color_state():
    """โหลดสถานะสีล่าสุดของหุ้น"""
    state_file = "stock_colors_state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_color_state(state):
    """บันทึกสถานะสีล่าสุดลงไฟล์"""
    state_file = "stock_colors_state.json"
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"❌ บันทึก Color State ไม่สำเร็จ: {e}")


def check_color_change(symbol, current_close, prev_close):
    """ตรวจจับการเปลี่ยนสีของหุ้น (เขียว <-> แดง)"""
    if prev_close == 0:
        return None

    change_pct = ((current_close - prev_close) / prev_close) * 100
    current_color = "GREEN" if change_pct >= 0 else "RED"

    color_state = load_color_state()
    last_color = color_state.get(symbol)

    alert_msg = None

    if last_color and last_color != current_color:
        if current_color == "RED":
            alert_msg = (
                f"🚨 **เตือนหุ้นเปลี่ยนสี (เขียว 🟢 ➔ แดง 🔴)**: หุ้น {symbol}\n"
                f"- ราคาปัจจุบัน: ${current_close:.2f} ({change_pct:+.2f}%)\n"
                f"- ราคาปิดวันก่อน: ${prev_close:.2f}\n"
                f"[ByPomSwingtrader]"
            )
        elif current_color == "GREEN":
            alert_msg = (
                f"✳️ **เตือนหุ้นเปลี่ยนสี (แดง 🔴 ➔ เขียว 🟢)**: หุ้น {symbol}\n"
                f"- ราคาปัจจุบัน: ${current_close:.2f} ({change_pct:+.2f}%)\n"
                f"- ราคาปิดวันก่อน: ${prev_close:.2f}\n"
                f"[ByPomSwingtrader]"
            )

    color_state[symbol] = current_color
    save_color_state(color_state)
    return alert_msg


def safe_float(val):
    """แปลงค่าตัวเลขให้ปลอดภัย ป้องกันการเปรียบเทียบราคาผิดพลาด"""
    if val in [None, "-", "", "None", "null"]:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def check_full_strategy(symbol, data):
    """สแกนเงื่อนไขราคา Entry, TP, SL และการเปลี่ยนสีอย่างละเอียด"""
    try:
        side = str(data.get("side", "LONG")).upper()

        entry_price = safe_float(data.get("entry"))
        tp_price = safe_float(data.get("tp"))
        sl_price = safe_float(data.get("sl"))

        df = yf.Ticker(symbol).history(period="5d")
        if df.empty or len(df) < 2:
            print(f"⚠️ หุ้น {symbol}: ไม่พบข้อมูลราคา")
            return None

        current_close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        alerts = []

        # 1. เช็กหุ้นเปลี่ยนสี (เขียว <-> แดง)
        color_alert = check_color_change(symbol, current_close, prev_close)
        if color_alert:
            alerts.append(color_alert)

        # 2. เช็กราคา ENTRY (เช่น ตั้งไว้ 5 แล้วราคาลงมาถึงหรือต่ำกว่า 5)
        if entry_price is not None:
            if side == "LONG" and current_close <= entry_price:
                alerts.append(
                    f"🔔 **ถึงราคาเข้าซื้อ ENTRY LONG**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ถึงจุดเข้าซื้อ (${entry_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
            elif side == "SHORT" and current_close >= entry_price:
                alerts.append(
                    f"🔔 **ถึงราคาเข้าชอร์ต ENTRY SHORT**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ถึงจุดเข้าชอร์ต (${entry_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )

        # 3. เช็กราคา TAKE PROFIT (TP)
        if tp_price is not None:
            if side == "LONG" and current_close >= tp_price:
                alerts.append(
                    f"🎯 **ถึงเป้า Take Profit (TP) LONG**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
            elif side == "SHORT" and current_close <= tp_price:
                alerts.append(
                    f"🎯 **ถึงเป้า Take Profit (TP) SHORT**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )

        # 4. เช็กราคา STOP LOSS (SL)
        if sl_price is not None:
            if side == "LONG" and current_close <= sl_price:
                alerts.append(
                    f"🛑 **ชนจุด Stop Loss (SL) LONG**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) หลุด SL (${sl_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
            elif side == "SHORT" and current_close >= sl_price:
                alerts.append(
                    f"🛑 **ชนจุด Stop Loss (SL) SHORT**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ทะลุ SL (${sl_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )

        return "\n\n".join(alerts) if alerts else None

    except Exception as e:
        print(f"❌ Error processing {symbol}: {e}")
        return None


def get_daily_summary(watchlist):
    """สร้างข้อความรายงานสรุปราคาหุ้นประจำรอบ"""
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
                current_close = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2])
                change_pct = ((current_close - prev_close) / prev_close) * 100
                status_icon = "🟢" if change_pct >= 0 else "🔴"

                msg = (
                    f"🔹 หุ้น {symbol} ({side})\n"
                    f"- ราคาปัจจุบัน: ${current_close:.2f} ({status_icon} {change_pct:+.2f}%)\n"
                    f"- Entry: ${entry_price} | TP: ${tp_price} | SL: ${sl_price}"
                )
                summary_msgs.append(msg)
            elif len(df) == 1:
                current_close = float(df["Close"].iloc[-1])
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
    """ตรวจสอบช่วงเวลา 06.00-08.59 น. และ 17.00-19.59 น."""
    flag_file = f"summary_sent_{today_str}.txt"

    period = None
    if 6 <= current_hour < 9:
        period = "MORNING"
    elif 17 <= current_hour < 20:
        period = "EVENING"

    if not period:
        return False, None

    sent_periods = []
    if os.path.exists(flag_file):
        with open(flag_file, "r") as f:
            sent_periods = f.read().splitlines()

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

        # 1. รายงานสรุปประจำรอบ (เช้า 06.00-08.59 น. / เย็น 17.00-19.59 น.)
        send_flag, period_name = should_send_summary(current_hour, today_str)
        if send_flag:
            print(f"📢 กำลังส่งรายงานสรุปหุ้นประจำรอบช่วงเวลา ({period_name})...")
            summary_text = get_daily_summary(watchlist)
            send_msg(summary_text)

        # 2. สแกนราคาทุกตัว (Entry, TP, SL, สีเปลี่ยน)
        print(f"🔍 กำลังสแกนราคาหุ้นจำนวน {len(watchlist)} ตัว...")
        for symbol, data in watchlist.items():
            res = check_full_strategy(symbol, data)
            if res:
                send_msg(res)
                print(f"✅ ส่งการแจ้งเตือนระดับราคา/สีเปลี่ยนของหุ้น {symbol} เรียบร้อย")
            else:
                print(f"ℹ️ หุ้น {symbol}: ราคายังไม่แตะระดับ Entry/TP/SL และไม่มีการเปลี่ยนสี")
    else:
        print("❌ ไม่พบรายชื่อหุ้นใน Cloud หรือดึงข้อมูล JSONBin ไม่สำเร็จ")
