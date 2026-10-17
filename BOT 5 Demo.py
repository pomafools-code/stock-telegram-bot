import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# ตั้งค่าหน้าเว็บ (Page Config)
# ==========================================
st.set_page_config(
    page_title="ByPomSwingtrader Web App", page_icon="🤖", layout="wide"
)

# ==========================================
# ข้อมูล Telegram & JSONBin
# ==========================================
TOKEN = "8716643800:AAFoN_YyOf1hFLUMskEDtfBtQ2NCoEDDe3A"
CHAT_ID = "8735795390"

JSONBIN_BIN_ID = "6a93da60da38895dfe223f00"
JSONBIN_MASTER_KEY = (
    "$2a$10$NjCsm/l7lP0JrFPiwIL4wev2QO.gRIw6eR3PBHEy0Q/BjG9b4Vf8C"
)

headers = {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_MASTER_KEY,
}


def send_msg(text):
  try:
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
    )
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
        if "watchlist" in record and isinstance(record["watchlist"], dict):
          return record["watchlist"]
        return {k: v for k, v in record.items() if not k.startswith("_")}
  except Exception as e:
    st.error(f"Error loading from JSONBin: {e}")
  return {}


def save_watchlist(watchlist):
  try:
    url_get = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
    res_get = requests.get(url_get, headers=headers)
    record = {}
    if res_get.status_code == 200:
      record = res_get.json().get("record", {})

    if "watchlist" in record:
      record["watchlist"] = watchlist
    else:
      record = watchlist

    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    response = requests.put(url, json=record, headers=headers)
    return response.status_code == 200
  except Exception as e:
    st.error(f"Error saving to JSONBin: {e}")
    return False


def generate_kagi_signals(df, reversal_pct=0.03):
  if df.empty or len(df) < 10:
    return "NEUTRAL", 0.0

  prices = df["Close"]
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
    else:  # SELL
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

    current_close = df["Close"].iloc[-1]
    alerts = []

    if entry_price is not None:
      if side.upper() == "LONG" and current_close <= entry_price:
        alerts.append(
            f"🔔 ถึงราคาเข้าซื้อ ENTRY LONG: หุ้น {symbol}\nราคาปัจจุบัน"
            f" (${current_close:.2f}) ลงมาถึงจุดเข้าซื้อ"
            f" (${entry_price:.2f})\n[ByPomSwingtrader]"
        )
      elif side.upper() == "SHORT" and current_close >= entry_price:
        alerts.append(
            f"🔔 ถึงราคาเข้าชอร์ต ENTRY SHORT: หุ้น {symbol}\nราคาปัจจุบัน"
            f" (${current_close:.2f}) ขึ้นมาถึงจุดเข้าชอร์ต"
            f" (${entry_price:.2f})\n[ByPomSwingtrader]"
        )

    if tp_price is not None:
      if side.upper() == "LONG" and current_close >= tp_price:
        alerts.append(
            f"🎯 ถึงเป้า Take Profit (TP) LONG: หุ้น {symbol}\nราคาปัจจุบัน"
            f" (${current_close:.2f}) ชนเป้า TP"
            f" (${tp_price:.2f})\n[ByPomSwingtrader]"
        )
      elif side.upper() == "SHORT" and current_close <= tp_price:
        alerts.append(
            f"🎯 ถึงเป้า Take Profit (TP) SHORT: หุ้น {symbol}\nราคาปัจจุบัน"
            f" (${current_close:.2f}) ชนเป้า TP"
            f" (${tp_price:.2f})\n[ByPomSwingtrader]"
        )

    if sl_price is not None:
      if side.upper() == "LONG" and current_close <= sl_price:
        alerts.append(
            f"🛑 ชนจุด Stop Loss (SL) LONG: หุ้น {symbol}\nราคาปัจจุบัน"
            f" (${current_close:.2f}) หลุด SL"
            f" (${sl_price:.2f})\n[ByPomSwingtrader]"
        )
      elif side.upper() == "SHORT" and current_close >= sl_price:
        alerts.append(
            f"🛑 ชนจุด Stop Loss (SL) SHORT: หุ้น {symbol}\nราคาปัจจุบัน"
            f" (${current_close:.2f}) ทะลุ SL"
            f" (${sl_price:.2f})\n[ByPomSwingtrader]"
        )

    kagi_trend, _ = generate_kagi_signals(df, reversal_pct=0.03)
    if side.upper() == "LONG" and kagi_trend == "BUY":
      alerts.append(
          f"🟢 สัญญาณ Kagi 3% BUY: หุ้น {symbol}\nราคาปัจจุบัน:"
          f" ${current_close:.2f}\n[ByPomSwingtrader]"
      )
    elif side.upper() == "SHORT" and kagi_trend == "SELL":
      alerts.append(
          f"🔴 สัญญาณ Kagi 3% SELL: หุ้น {symbol}\nราคาปัจจุบัน:"
          f" ${current_close:.2f}\n[ByPomSwingtrader]"
      )

    return "\n\n".join(alerts) if alerts else None
  except Exception as e:
    return f"Error processing {symbol}: {e}"


# ==========================================
# ระบบ Login ง่ายๆ ด้วย Password
# ==========================================
if "authenticated" not in st.session_state:
  st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
  st.markdown("## 🔐 เข้าสู่ระบบ - ByPomSwingtrader")
  password = st.text_input("กรุณาใส่รหัสผ่านเพื่อเข้าใช้งาน", type="password")
  if st.button("เข้าสู่ระบบ"):
    if password == "112233":
      st.session_state["authenticated"] = True
      st.rerun()
    else:
      st.error("รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง")
  st.stop()

# ==========================================
# หน้าจอหลักหลัง Login สำเร็จ
# ==========================================
st.title("🤖 บอทหุ้นสหรัฐ & วิเคราะห์สัญญาณ (ByPomSwingtrader)")
st.caption("Created by ByPomSwingtrader | Cloud-Synced Web Application")

# Sidebar สำหรับเพิ่มหุ้น
with st.sidebar:
  st.header("➕ เพิ่มหุ้น / กำหนดแผน")
  with st.form("add_stock_form"):
    sym_input = st.text_input("ชื่อหุ้น (เช่น AAPL, TSLA)").strip().upper()
    side_input = st.radio("โหมด", ["LONG", "SHORT"])
    entry_input = st.text_input("Entry Price (เว้นว่างได้)")
    tp_input = st.text_input("Take Profit (TP) (เว้นว่างได้)")
    sl_input = st.text_input("Stop Loss (SL) (เว้นว่างได้)")

    submitted = st.form_submit_button("บันทึกขึ้น Cloud")
    if submitted:
      if not sym_input:
        st.warning("กรุณากรอกชื่อหุ้นครับ")
      else:
        try:
          entry_val = float(entry_input) if entry_input else None
          tp_val = float(tp_input) if tp_input else None
          sl_val = float(sl_input) if sl_input else None

          watchlist = load_watchlist()
          if not isinstance(watchlist, dict):
            watchlist = {}

          watchlist[sym_input] = {
              "side": side_input,
              "entry": entry_val,
              "tp": tp_val,
              "sl": sl_val,
          }

          if save_watchlist(watchlist):
            st.success(f"บันทึกแผนหุ้น {sym_input} สำเร็จ!")
            st.rerun()
          else:
            st.error("บันทึกไม่สำเร็จ")
        except ValueError:
          st.error("กรุณากรอกราคาเป็นตัวเลขเท่านั้น")

# Tabs แบ่งหน้าการทำงานหลัก
tab1, tab2 = st.tabs(["📊 จัดการหุ้น & ตรวจสอบแผน", "📉 Kagi Chart Scan (3%)"])

# --- TAB 1: จัดการ Watchlist & ตรวจสอบสัญญาณราคา ---
with tab1:
  st.subheader("📋 รายชื่อหุ้นและแผนราคาใน Cloud")
  watchlist = load_watchlist()

  if watchlist:
    data_list = []
    for sym, details in watchlist.items():
      if sym.startswith("_"):
        continue
      data_list.append({
          "Symbol": sym,
          "Side": details.get("side", "LONG"),
          "Entry": details.get("entry", "-"),
          "TP": details.get("tp", "-"),
          "SL": details.get("sl", "-"),
      })

    df_watch = pd.DataFrame(data_list)
    st.dataframe(df_watch, use_container_width=True)

    # ส่วนลบหุ้น
    col_del1, col_del2 = st.columns([3, 1])
    with col_del1:
      del_sym = st.selectbox(
          "เลือกหุ้นที่ต้องการลบออกจากระบบ",
          options=[d["Symbol"] for d in data_list],
      )
    with col_del2:
      st.write("")  # เว้นช่องไฟ
      st.write("")
      if st.button("🗑️ ลบหุ้นนี้"):
        if del_sym in watchlist:
          del watchlist[del_sym]
          if save_watchlist(watchlist):
            st.success(f"ลบหุ้น {del_sym} เรียบร้อย!")
            st.rerun()

    st.markdown("---")
    if st.button(
        "🔍 ตรวจสอบสัญญาณและราคาตอนนี้ (ส่งเข้า Telegram)",
        type="primary",
        use_container_width=True,
    ):
      with st.spinner("กำลังตรวจสอบข้อมูลตลาดและส่งแจ้งเตือน..."):
        results = []
        for symbol, data in watchlist.items():
          if symbol.startswith("_"):
            continue
          res = check_full_strategy(symbol, data)
          if res:
            results.append(res)
            send_msg(res)

        if results:
          st.success("ตรวจสอบเรียบร้อย! พบสัญญาณเตือนและส่งเข้า Telegram แล้ว:")
          for r in results:
            st.info(r)
        else:
          st.info(
              "ตรวจสอบครบทุกตัวแล้ว ยังไม่มีหุ้นตัวไหนถึงเงื่อนไขราคาครับ"
          )
  else:
    st.warning("ยังไม่มีข้อมูลหุ้นในระบบ Cloud กรุณาเพิ่มหุ้นจากเมนูด้านซ้าย")

# --- TAB 2: Kagi Chart Scan ---
with tab2:
  st.subheader("📉 วิเคราะห์แนวโน้ม Kagi Chart 3% ทั้งหมดใน Watchlist")
  if st.button("🚀 เริ่มสแกนสัญญาณ Kagi 3%", use_container_width=True):
    with st.spinner("กำลังประมวลผลกราฟ Kagi..."):
      watchlist = load_watchlist()
      if not watchlist:
        st.warning("ไม่พบข้อมูลหุ้นใน Watchlist")
      else:
        report = []
        for symbol in watchlist.keys():
          if symbol.startswith("_"):
            continue
          try:
            df = yf.Ticker(symbol).history(period="6mo")
            if df.empty or len(df) < 10:
              continue
            trend, price = generate_kagi_signals(df, reversal_pct=0.03)
            signal_text = (
                "🟢 สัญญาณซื้อ (BUY - Yang)"
                if trend == "BUY"
                else "🔴 สัญญาณขาย (SELL - Yin)"
            )
            report.append({
                "Symbol": symbol,
                "Price ($)": round(price, 2),
                "Kagi 3% Signal": signal_text,
            })
          except Exception as e:
            report.append({"Symbol": symbol, "Error": str(e)})

        if report:
          df_kagi = pd.DataFrame(report)
          st.dataframe(df_kagi, use_container_width=True)
        else:
          st.warning("ไม่สามารถประมวลผลข้อมูล Kagi ได้")