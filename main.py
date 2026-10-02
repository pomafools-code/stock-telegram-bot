from datetime import datetime
import json
import os
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
    "$2a$10$NjCsm/l7lP0JrFPiwIL4wev2QO.gRIw6eR3PBHEy0Q/BjG9b4Vf8C",
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
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if not res_data.get("ok"):
            print(f"❌ Telegram API Error: {res_data.get('description')}")
        else:
            print("✅ ส่งข้อความไปยัง Telegram สำเร็จ")
    except Exception as e:
        print(f"❌ Error sending message: {e}")


def load_jsonbin_data():
    """ดึงข้อมูลทั้งหมดจาก JSONBin (รวมทั้ง Watchlist, State และ Summary Tracker)"""
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("record", {})
        else:
            print(f"❌ JSONBin Read Error Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error loading from JSONBin: {e}")
    return {}


def save_jsonbin_data(data):
    """บันทึกข้อมูลทั้งหมดกลับไปยัง JSONBin เพื่อแก้ปัญหา State หายบน GitHub Actions"""
    try:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        response = requests.put(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            print("✅ บันทึก State กลับขึ้น JSONBin สำเร็จ")
        else:
            print(f"❌ JSONBin Save Error Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error saving to JSONBin: {e}")


def safe_float(val):
    if val in [None, "-", "", "None", "null"]:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def check_full_strategy(symbol, data, state):
    try:
        side = str(data.get("side", "LONG")).upper()
        entry_price = safe_float(data.get("entry"))
        tp_price = safe_float(data.get("tp"))
        sl_price = safe_float(data.get("sl"))

        # ดึงราคา 7 วันป้องกันช่วงวันหยุด
        df = yf.Ticker(symbol).history(period="7d")
        if df.empty or len(df) < 2:
            print(f"⚠️ หุ้น {symbol}: ไม่พบข้อมูลราคาจาก yfinance")
            return None

        current_close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])

        if prev_close == 0:
            return None

        change_pct = ((current_close - prev_close) / prev_close) * 100
        current_color = "GREEN" if change_pct >= 0 else "RED"

        symbol_state = state.get(symbol, {})
        last_color = symbol_state.get("color")
        alerts = []

        # 1. เช็กหุ้นเปลี่ยนสี (เขียว <-> แดง)
        if last_color and last_color != current_color:
            if current_color == "RED":
                alerts.append(
                    f"🚨 **เตือนหุ้นเปลี่ยนสี (เขียว 🟢 ➔ แดง 🔴)**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน: ${current_close:.2f} ({change_pct:+.2f}%)\n"
                    f"- ราคาปิดวันก่อน: ${prev_close:.2f}\n"
                    f"[ByPomSwingtrader]"
                )
            elif current_color == "GREEN":
                alerts.append(
                    f"✳️ **เตือนหุ้นเปลี่ยนสี (แดง 🔴 ➔ เขียว 🟢)**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน: ${current_close:.2f} ({change_pct:+.2f}%)\n"
                    f"- ราคาปิดวันก่อน: ${prev_close:.2f}\n"
                    f"[ByPomSwingtrader]"
                )

        # 2. เช็กราคา Entry (แจ้งเตือนแค่ครั้งเดียวจนกว่าจะแก้ค่า)
        if entry_price is not None:
            is_entry = (side == "LONG" and current_close <= entry_price) or (
                side == "SHORT" and current_close >= entry_price
            )
            if is_entry and not symbol_state.get("alert_entry"):
                alerts.append(
                    f"🔔 **ถึงราคาเข้า ({side})**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ถึงจุดเข้าซื้อ (${entry_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
                symbol_state["alert_entry"] = True

        # 3. เช็กราคา Take Profit (TP)
        if tp_price is not None:
            is_tp = (side == "LONG" and current_close >= tp_price) or (
                side == "SHORT" and current_close <= tp_price
            )
            if is_tp and not symbol_state.get("alert_tp"):
                alerts.append(
                    f"🎯 **ถึงเป้า Take Profit (TP)**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) ชนเป้า TP (${tp_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
                symbol_state["alert_tp"] = True

        # 4. เช็กราคา Stop Loss (SL)
        if sl_price is not None:
            is_sl = (side == "LONG" and current_close <= sl_price) or (
                side == "SHORT" and current_close >= sl_price
            )
            if is_sl and not symbol_state.get("alert_sl"):
                alerts.append(
                    f"🛑 **ชนจุด Stop Loss (SL)**: หุ้น {symbol}\n"
                    f"- ราคาปัจจุบัน (${current_close:.2f}) หลุด SL (${sl_price:.2f})\n"
                    f"[ByPomSwingtrader]"
                )
                symbol_state["alert_sl"] = True

        # อัปเดตสถานะล่าสุด
        symbol_state["color"] = current_color
        state[symbol] = symbol_state

        return "\n\n".join(alerts) if alerts else None

    except Exception as e:
        print(f"❌ Error processing {symbol}: {e}")
        return None


def get_daily_summary(watchlist):
    summary_msgs = []
    tz = pytz.timezone("Asia/Bangkok")
    now_str = datetime.now(tz).strftime("%d/%m/%Y %H:%M")

    summary_msgs.append(
        f"📊 **รายงานสรุปราคาหุ้นประจำรอบ ({now_str} น.)**\n[ByPomSwingtrader]\n"
    )

    for symbol, data in watchlist.items():
        if symbol.startswith("_"):
            continue
        try:
            side = str(data.get("side", "LONG")).upper()
            entry_price = data.get("entry", "-")
            tp_price = data.get("tp", "-")
            sl_price = data.get("sl", "-")

            df = yf.Ticker(symbol).history(period="7d")
            if len(df) >= 2:
                current_close = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2])
                change_pct = ((current_close - prev_close) / prev_close) * 100
                status_icon = "🟢" if change_pct >= 0 else "🔴"

                msg = (
                    f"🔹 หุ้น **{symbol}** ({side})\n"
                    f"- ราคาปัจจุบัน: ${current_close:.2f} ({status_icon} {change_pct:+.2f}%)\n"
                    f"- Entry: ${entry_price} | TP: ${tp_price} | SL: ${sl_price}"
                )
                summary_msgs.append(msg)
        except Exception as e:
            summary_msgs.append(f"❌ หุ้น {symbol}: ดึงข้อมูลไม่ได้ ({e})")

    return "\n\n".join(summary_msgs)


if __name__ == "__main__":
    print("🚀 เริ่มต้นการทำงานบน GitHub Actions...")
    record = load_jsonbin_data()

    # แยก Watchlist และส่วนเก็บ State ออกจากกัน
    if "watchlist" in record and isinstance(record["watchlist"], dict):
        watchlist = record["watchlist"]
    else:
        watchlist = {k: v for k, v in record.items() if not k.startswith("_")}

    state = record.get("_state", {})
    summary_tracker = record.get("_summary_tracker", {})

    print(f"📌 ดึง Watchlist ได้ทั้งหมด: {len(watchlist)} รายการ")

    if watchlist:
        tz = pytz.timezone("Asia/Bangkok")
        now = datetime.now(tz)
        current_hour = now.hour
        today_str = now.strftime("%Y-%m-%d")

        print(f"⏰ เวลาปัจจุบัน (Bangkok): {now.strftime('%H:%M:%S (%d/%m/%Y)')}")

        # 1. เช็กการส่งรายงานสรุปประจำรอบ (เช้า 06.00-08.59 น. / เย็น 17.00-19.59 น.)
        period = None
        if 6 <= current_hour < 9:
            period = "MORNING"
        elif 17 <= current_hour < 20:
            period = "EVENING"

        if period:
            last_sent_date = summary_tracker.get(period)
            if last_sent_date != today_str:
                print(f"📢 กำลังส่งรายงานสรุปหุ้นประจำรอบช่วงเวลา ({period})...")
                summary_text = get_daily_summary(watchlist)
                send_msg(summary_text)
                summary_tracker[period] = today_str
                record["_summary_tracker"] = summary_tracker

        # 2. สแกนราคาหุ้นทุกตัว
        print(f"🔍 กำลังสแกนราคาหุ้นจำนวน {len(watchlist)} ตัว...")
        for symbol, data in watchlist.items():
            if symbol.startswith("_"):
                continue
            res = check_full_strategy(symbol, data, state)
            if res:
                send_msg(res)
                print(f"✅ ส่งการแจ้งเตือนของหุ้น {symbol} เรียบร้อย")
            else:
                print(f"ℹ️ หุ้น {symbol}: ไม่มีเงื่อนไขแจ้งเตือนใหม่")

        # บันทึก State กลับขึ้น JSONBin เพื่อใช้ต่อในรอบหน้า
        record["_state"] = state
        save_jsonbin_data(record)
        print("🎉 สแกนเรียบร้อย จบการทำงาน!")
    else:
        print(
            "❌ ไม่พบรายชื่อหุ้นใน Cloud หรือดึงข้อมูล JSONBin ไม่สำเร็จ (ตรวจสอบ Key หรือ Bin ID)"
        )
