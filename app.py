from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

# 環境変数からAPIキーを取得
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EBAY_APP_ID = os.environ.get("EBAY_APP_ID")  # 必要に応じて追加

@app.route("/")
def index():
    return "Flask app is running!"

@app.route("/fetch_ebay_data", methods=["POST"])
def fetch_ebay_data():
    try:
        # 1. eBay APIでデータ取得（例）
        ebay_url = "https://svcs.ebay.com/services/search/FindingService/v1"
        params = {
            "OPERATION-NAME": "findItemsByKeywords",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": EBAY_APP_ID,
            "RESPONSE-DATA-FORMAT": "JSON",
            "keywords": "和風",
            "paginationInput.entriesPerPage": "10"
        }
        ebay_res = requests.get(ebay_url, params=params)
        ebay_data = ebay_res.json()

        # データ加工例
        items = ebay_data.get("findItemsByKeywordsResponse", [])[0].get("searchResult", [{}])[0].get("item", [])
        ranking = []
        prices = []
        for item in items:
            title = item.get("title", [None])[0]
            price = float(item.get("sellingStatus", [{}])[0].get("currentPrice", [{}])[0].get("__value__", 0))
            prices.append(price)
            ranking.append({"keyword": title, "count": 1, "mean": price, "max": price})

        # 2. Gemini APIで分析コメント生成（例）
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        gemini_payload = {
            "contents": [{"parts": [{"text": f"次のeBayの価格データを分析してコメントを作成: {prices}"}]}]
        }
        gemini_res = requests.post(gemini_url, json=gemini_payload)
        gemini_text = gemini_res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        return jsonify({
            "ranking": ranking,
            "analysis": gemini_text
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
