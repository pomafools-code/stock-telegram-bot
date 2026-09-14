import os
import requests
import feedparser

# Token และ Chat ID ของเจ้านาย
TOKEN = "8716643800:AAFoN_YyOf1hFLUMskEDtfBtQ2NCoEDDe3A"
CHAT_ID = "8735795390"

def get_news_summary():
    news_sources = {
        "🇺🇸 **ข่าวเศรษฐกิจ & การลงทุนสหรัฐฯ/โลก (CNBC)**": "https://search.cnbc.com/rs/search/combinedrss.html?partnerId=wrnt&keywords=economy",
        "🇹🇭 **ข่าวหน้า 1 / ประเด็นเด่นประเทศไทย (Thai PBS)**": "https://news.thaipbs.or.th/rss/news/news_popular.xml"
    }
    
    message_lines = ["📰 **สรุปข่าวเศรษฐกิจ การลงทุน & ข่าวหน้า 1 (ประจำเช้า 07:00 น.)**\n"]
    
    for category, url in news_sources.items():
        message_lines.append(f"\n{category}")
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:3]:
                    title = entry.title.strip()
                    link = entry.link
                    message_lines.append(f"• [{title}]({link})")
            else:
                message_lines.append("• ไม่พบข่าวใหม่ในหมวดนี้")
        except Exception as e:
            message_lines.append(f"• เกิดข้อผิดพลาดในการดึงข่าว: {e}")
            
    message_lines.append("\n[ByPomSwingtrader]")
    return "\n".join(message_lines)

def send_telegram():
    message = get_news_summary()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("ส่งข่าวเข้า Telegram สำเร็จ!")
        else:
            print(f"เกิดข้อผิดพลาด: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    send_telegram()
