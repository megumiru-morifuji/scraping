from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import quote_plus
import google.generativeai as genai
import json
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Google Apps ScriptからのCORS対応

# Gemini API設定
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

class EbayScraper:
    def __init__(self):
        self.session = requests.Session()
        # User-Agentの設定（ブロック回避）
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def search_japanese_products(self, max_pages=3):
        """和風商品を検索する"""
        # 和風関連のキーワード
        japanese_keywords = [
            'japanese traditional',
            'japanese vintage',
            'japanese kimono',
            'japanese ceramics',
            'japanese art',
            'japanese antique',
            'japanese pottery',
            'japanese woodblock',
            'japanese sword',
            'japanese tea ceremony'
        ]
        
        all_products = {}
        
        for keyword in japanese_keywords[:5]:  # 最初の5つのキーワードに制限
            try:
                logger.info(f"検索中: {keyword}")
                products = self.scrape_ebay_search(keyword, max_pages=2)
                if products:
                    all_products[keyword] = products
                time.sleep(random.uniform(2, 4))  # リクエスト間隔
            except Exception as e:
                logger.error(f"キーワード {keyword} の検索でエラー: {e}")
                continue
        
        return all_products
    
    def scrape_ebay_search(self, keyword, max_pages=2):
        """eBayで特定のキーワードを検索し、商品情報を取得"""
        products = []
        
        for page in range(1, max_pages + 1):
            try:
                # eBayの検索URL（売れた商品のみ、LH_Soldを使用）
                url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(keyword)}&LH_Sold=1&_pgn={page}"
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 商品要素を取得
                items = soup.find_all('div', class_='s-item__wrapper')
                
                for item in items:
                    try:
                        product_data = self.extract_product_info(item)
                        if product_data:
                            products.append(product_data)
                    except Exception as e:
                        logger.warning(f"商品データ抽出エラー: {e}")
                        continue
                
                logger.info(f"{keyword} - ページ {page}: {len(items)} 件取得")
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"ページ {page} の取得でエラー: {e}")
                break
        
        return products
    
    def extract_product_info(self, item):
        """商品情報を抽出"""
        try:
            # タイトル
            title_elem = item.find('h3', class_='s-item__title')
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            
            # 価格
            price_elem = item.find('span', class_='s-item__price')
            if not price_elem:
                return None
            
            price_text = price_elem.get_text(strip=True)
            
            # 価格をパース（$記号と,を除去）
            try:
                price_clean = price_text.replace('$', '').replace(',', '').replace(' ', '')
                # 範囲価格の場合は最初の価格を使用
                if 'to' in price_clean.lower():
                    price_clean = price_clean.split('to')[0]
                price = float(price_clean)
            except:
                price = 0
            
            # 販売終了日
            date_elem = item.find('span', class_='s-item__ended-date')
            sold_date = date_elem.get_text(strip=True) if date_elem else ''
            
            return {
                'title': title,
                'price': price,
                'sold_date': sold_date,
                'url': item.find('a', class_='s-item__link').get('href') if item.find('a', class_='s-item__link') else ''
            }
        except Exception as e:
            logger.warning(f"商品情報抽出エラー: {e}")
            return None

def analyze_with_gemini(products_data):
    """Gemini APIで商品データを分析"""
    try:
        # データの統計を計算
        ranking_data = []
        
        for keyword, products in products_data.items():
            if not products:
                continue
                
            prices = [p['price'] for p in products if p['price'] > 0]
            if not prices:
                continue
            
            ranking_data.append({
                'keyword': keyword,
                'count': len(products),
                'mean': round(sum(prices) / len(prices), 2),
                'max': max(prices),
                'min': min(prices)
            })
        
        # 人気順にソート
        ranking_data.sort(key=lambda x: x['count'], reverse=True)
        
        # Gemini用のプロンプト作成
        analysis_text = "以下は和風商品のeBay販売データです:\n\n"
        for data in ranking_data:
            analysis_text += f"キーワード: {data['keyword']}\n"
            analysis_text += f"販売件数: {data['count']}件\n"
            analysis_text += f"平均価格: ${data['mean']}\n"
            analysis_text += f"最高価格: ${data['max']}\n\n"
        
        analysis_text += """
この販売データから以下の点について200文字以内で分析してください：
1. どのカテゴリの和風商品が人気か
2. 価格帯の傾向
3. 販売機会についてのアドバイス
"""
        
        # Gemini APIで分析
        response = model.generate_content(analysis_text)
        analysis_comment = response.text
        
        return {
            'ranking': ranking_data[:10],  # トップ10
            'analysis': analysis_comment
        }
        
    except Exception as e:
        logger.error(f"Gemini分析エラー: {e}")
        return {
            'ranking': ranking_data if 'ranking_data' in locals() else [],
            'analysis': f"分析中にエラーが発生しました: {str(e)}"
        }

@app.route('/')
def home():
    return "eBay Japanese Products Scraper API"

@app.route('/fetch_ebay_data', methods=['POST'])
def fetch_ebay_data():
    try:
        logger.info("eBayデータ取得開始")
        
        # スクレイピング実行
        scraper = EbayScraper()
        products_data = scraper.search_japanese_products(max_pages=2)
        
        if not products_data:
            return jsonify({
                'ranking': [],
                'analysis': 'データが取得できませんでした。eBayの仕様変更の可能性があります。'
            })
        
        logger.info(f"取得したキーワード数: {len(products_data)}")
        
        # Gemini APIで分析
        result = analyze_with_gemini(products_data)
        
        logger.info("分析完了")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"エラー: {e}")
        return jsonify({
            'ranking': [],
            'analysis': f'エラーが発生しました: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
