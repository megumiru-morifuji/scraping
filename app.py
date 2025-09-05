from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/')
def hello():
    return "eBay Scraper API is running!"

@app.route('/scrape-ebay')
def scrape_ebay():
    """
    このエンドポイントにアクセスされた時だけeBayにリクエストが送信される
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        url = 'https://www.ebay.com'
        r = requests.get(url, headers=headers)
        
        r_text = BeautifulSoup(r.text, 'html.parser')
        
        # タイトルを取得
        title = r_text.find('title')
        title_text = title.text.strip() if title else "タイトルなし"
        
        return jsonify({
            "status": "success",
            "status_code": r.status_code,
            "url": r.url,
            "title": title_text,
            "html_preview": r.text[:300]
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

if __name__ == '__main__':
    # Renderでは環境変数PORTが設定される
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
