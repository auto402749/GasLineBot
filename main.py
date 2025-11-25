from flask import Flask
app = Flask(__name__)

from flask import request, abort
from linebot import  LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage,StickerSendMessage

import requests
from bs4 import BeautifulSoup
import threading
import schedule
import time
import json
import os

#Line Bot設定
line_bot_api = LineBotApi('f6lHgzwcRpAxrzWVTgAkUwgyaPWWbNPhUUAtgQPx+6wRNtBgKhUuDAIVguDZoqHY7ewzETvzxUPUNErqVbj1M1qLFUCjhp7Aq2moakTecLOdmPhzoicvHM4IW13J5XDFQZVMeWlammiB/eJj9BJgvAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('07b58db5ec7eff2c9f5af2d9460e3a21')

# 訂閱用戶管理（存檔）
SUBSCRIBERS_FILE = 'subscribers.json'

# 初始化訂閱者列表
if os.path.exists(SUBSCRIBERS_FILE):
    with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
        subscribers = json.load(f)  #把 JSON 轉成 Python 資料結構(list)
else:
    subscribers = []   #若不存在，用空list([])當初始訂閱者清單(代表目前沒人訂閱)

#儲存函式：把記憶體中的subscribers寫回檔案
#json.dump():Python物件轉換為JSON格式的函式
#ensure_ascii=False：讓json.dump在遇到非ASCII(例如中文)時不把字元轉成"\uXXXX"，而是直接輸出原始字
#indent=2：輸出的 JSON 會有縮排(漂亮列印），便於人工檢視與除錯
def save_subscribers():   
    with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(subscribers, f, ensure_ascii=False, indent=2)


#定義爬取油價並推播的函式
def push_gas_info():
    gas_url = 'https://gas.goodlife.tw/'
    gas_web = requests.get(gas_url)   #爬取網頁資料
    gas_web.encoding = 'utf-8'
    soup = BeautifulSoup(gas_web.text, "html.parser")
    msg=""

    #找到價格區間
    updown = soup.find(id='gas-price')
    datas = soup.find(id='cpc')
    #print(updown)
    #print(datas)

    #調漲期間
    title = updown.find('p')
    title2 = datas.find('h2')
    msg += '\n'
    msg += title.text
    #print(title.text,end="")

    #漲跌狀況
    price = updown.find('h2')
    msg += price.text + '\n'
    #print(price.text)

    msg += "--------------------------------------------"+'\n'

    msg += title2.text + ":"+"\n"
    msg += '\n'
    #print(title2.text + ":")
    #print()

    items = datas.find_all('li')

    for i in range(len(items)):

        #print(items[i].text,end="")
        h3_item = items[i].find("h3")
        msg += h3_item.text.strip()
        #print(h3_item.text.strip(),end="")      #strip():移除字串頭尾指定的字符(默認為空格)
        h3_item.extract()                        #extract():把不要的標籤淬出或是移除
        msg += items[i].text.strip()+" 元/升"+"\n"
        msg += "\n"
        #print(items[i].text.strip()+" 元/升")
        #print()
    print(msg)

    # 自動推播給所有訂閱者 LINE 訊息與貼圖
    for user_id in subscribers:
        line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        line_bot_api.push_message(user_id, StickerSendMessage(package_id='6325', sticker_id='10979917'))

    print(f"已推播給 {len(subscribers)} 位使用者：{time.strftime('%Y-%m-%d %H:%M:%S')}")

#排程在固定時間執行
def schedule_thread():
    #每個星期日的13:30分執行任務(線上編譯器為GMT時間，台灣為GMT+8，故設定上要-8)
    #schedule.every(1).minute.do(push_gas_info)  # 每分鐘執行一次
    #schedule.every().sunday.at("05:30").do(push_gas_info)
    schedule.every().tuesday.at("09:18").do(push_gas_info)

    # 讓排程持續運作
    while True:
        schedule.run_pending()   #持續檢查和執行排程任務
        time.sleep(1)       #避免無限迴圈跑太快吃CPU → 每次檢查完排程後休息1秒

# 啟動背景 Thread 執行排程，讓排程“在Flask旁邊同時執行”，目的:
# Flask 主程式：接收 LINE webhook
# 背景Thread：排程自動抓油價 + 推播
threading.Thread(target=schedule_thread, daemon=True).start()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    mtext = event.message.text.strip()
    user_id = event.source.user_id

    if mtext == "綁定":
        if user_id not in subscribers:
            subscribers.append(user_id)
            save_subscribers()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已成功綁定，每周日13:30將自動接收油價資訊！"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你已經綁定過了!"))
    elif mtext == "解除綁定":
        if user_id in subscribers:
            subscribers.remove(user_id)
            save_subscribers()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已解除綁定，不再接收油價推播!"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你尚未綁定!"))
    elif mtext == "下週油價":
        push_gas_info()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已推播油價資訊"))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="輸入「綁定」即可訂閱油價自動推播\n輸入「解除綁定」取消"))


#啟動 Flask
if __name__ == '__main__':

    app.run()
