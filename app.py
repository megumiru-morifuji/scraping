from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import quote_plus
import json
import logging
import threading
from datetime import datetime
import uuid

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Gemini API設定
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# プロセス状態管理
process_status = {}
results_cache = {}

class EbayScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def search_japanese_products_async(self, process_id, keywords_limit=10):
        """非同期で和風商品を検索する"""
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
            'japanese tea ceremony',
            'japanese lacquer',
            'japanese calligraphy',
            'japanese fabric',
            'japanese doll',
            'japanese screen'
        ]
        
        # 指定されたキーワード数に制限
        keywords_to_search = japanese_keywords[:keywords_limit]
        total_keywords = len(keywords_to_search)
        
        all_products = {}
        completed_keywords = 0
        
        try:
            # プロセス状態を初期化
            process_status[process_id] = {
                'status': 'running',
                'progress': 0,
                'current_keyword': '',
                'total_keywords': total_keywords,
                'completed_keywords': 0,
                'start_time': datetime.now(),
                'error': None
            }
            
            for i, keyword in enumerate(keywords_to_search):
                try:
                    # プロセス状態を更新
                    process_status[process_id]['current_keyword'] = keyword
                    process_status[process_id]['progress'] = int((i / total_keywords) * 100)
                    
                    logger.info(f"[{process_id}] 検索中 ({i+1}/{total_keywords}): {keyword}")
                    
                    # キーワード検索（ページ数を少なく）
                    products = self.scrape_ebay_search(keyword, max_pages=1)
                    
                    if products:
                        all_products[keyword] = products
                        logger.info(f"[{process_id}] {keyword}: {len(products)} 件取得")
                    
                    completed_keywords += 1
                    process_status[process_id]['completed_keywords'] = completed_keywords
                    
                    # リクエスト間隔（短縮）
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    logger.error(f"[{process_id}] キーワード {keyword} の検索でエラー: {e}")
                    # エラーでも続行
                    continue
            
            # 完了処理
            process_status[process_id]['status'] = 'analyzing'
            process_status[process_id]['progress'] = 90
            
            # 分析実行
            result = analyze_with_gemini(all_products)
            
            # 結果をキャッシュに保存
            results_cache[process_id] = result
            
            # プロセス完了
            process_status[process_id]['status'] = 'completed'
            process_status[process_id]['progress'] = 100
            process_status[process_id]['end_time'] = datetime.now()
            
            logger.info(f"[{process_id}] 処理完了")
            
        except Exception as e:
            logger.error(f"[{process_id}] 処理エラー: {e}")
            process_status[process_id]['status'] = 'error'
            process_status[process_id]['error'] = str(e)
    
    def scrape_ebay_search(self, keyword, max_pages=1):
        """eBayで特定のキーワードを検索（軽量化版）"""
        products = []
        
        try:
            # 人間らしい検索前の遅延
            time.sleep(random.uniform(0.8, 2.0))
            
            # eBayの検索URL（売れた商品のみ）
            url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(keyword)}&LH_Sold=1&_pgn=1"
            
            logger.info(f"アクセスURL: {url}")
            
            # リクエストヘッダーにランダム性を追加
            headers = self.session.headers.copy()
            headers['Cache-Control'] = 'no-cache'
            headers['Pragma'] = 'no-cache'
            
            response = self.session.get(url, headers=headers, timeout=10)
            logger.info(f"レスポンスコード: {response.status_code}")
            
            # レスポンス内容の一部をログ出力（デバッグ用）
            if "bot" in response.text.lower() or "captcha" in response.text.lower():
                logger.warning(f"ボット検出の可能性: {keyword}")
                logger.warning(f"レスポンス断片: {response.text[:500]}")
            
            response.raise_for_status()
            
            # レスポンス後の人間らしい遅延
            time.sleep(random.uniform(0.5, 1.2))
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 商品要素を取得（複数のセレクターを試す）
            items = soup.find_all('div', class_='s-item__wrapper')
            if not items:
                # 別のセレクターも試す
                items = soup.find_all('div', class_='s-item')
                logger.info(f"代替セレクター使用: {len(items)} 件")
            
            logger.info(f"取得した商品要素数: {len(items)}")
            
            # 最大20件に制限
            items = items[:20]
            
            for i, item in enumerate(items):
                try:
                    product_data = self.extract_product_info(item)
                    if product_data:
                        products.append(product_data)
                        logger.info(f"商品 {i+1}: {product_data['title'][:50]}... - ${product_data['price']}")
                        # アイテム処理間の微小な遅延
                        time.sleep(random.uniform(0.1, 0.3))
                except Exception as e:
                    logger.warning(f"商品 {i+1} 抽出エラー: {e}")
                    continue
            
            logger.info(f"最終取得商品数: {len(products)}")
            
        except Exception as e:
            logger.error(f"検索エラー ({keyword}): {e}")
        
        return products
    
    def extract_product_info(self, item):
        """商品情報を抽出（改良版）"""
        try:
            # タイトル（複数のセレクターを試す）
            title_elem = item.find('h3', class_='s-item__title') or \
                        item.find('a', class_='s-item__link') or \
                        item.find('span', role='heading')
            
            if not title_elem:
                logger.debug("タイトル要素が見つからない")
                return None
            
            title = title_elem.get_text(strip=True)
            if not title or title == 'New Listing':
                logger.debug("有効なタイトルなし")
                return None
            
            # 価格（複数のセレクターを試す）
            price_elem = item.find('span', class_='s-item__price') or \
                        item.find('span', class_='notranslate')
            
            if not price_elem:
                logger.debug("価格要素が見つからない")
                return None
            
            price_text = price_elem.get_text(strip=True)
            logger.debug(f"価格テキスト: {price_text}")
            
            # 価格をパース（より柔軟に）
            try:
                # $記号と数字以外を除去
                import re
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_text)
                if price_match:
                    price_clean = price_match.group(1).replace(',', '')
                    price = float(price_clean)
                    if price <= 0:
                        return None
                else:
                    logger.debug(f"価格パース失敗: {price_text}")
                    return None
            except Exception as e:
                logger.debug(f"価格変換エラー: {e}")
                return None
            
            product = {
                'title': title,
                'price': price
            }
            
            logger.debug(f"商品抽出成功: {title[:30]}... - ${price}")
            return product
            
        except Exception as e:
            logger.debug(f"商品情報抽出エラー: {e}")
            return None

def analyze_with_gemini(products_data):
    """Gemini APIで商品データを分析（REST API版）"""
    try:
        ranking_data = []
        
        for keyword, products in products_data.items():
            if not products:
                continue
                
            prices = [p['price'] for p in products if p.get('price', 0) > 0]
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
        
        # Gemini用のプロンプト（短縮版）
        analysis_text = "和風商品のeBay販売データ:\n\n"
        for data in ranking_data[:5]:  # 上位5つのみ
            analysis_text += f"{data['keyword']}: {data['count']}件, 平均${data['mean']}\n"
        
        analysis_text += "\n150文字以内で人気カテゴリと価格傾向を分析してください。"
        
        # Gemini REST API呼び出し
        gemini_url = (
            "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
            f"?key={GEMINI_API_KEY}"
        )
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": analysis_text
                        }
                    ]
                }
            ]
        }
        
        # 人間らしいヘッダーを設定
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site'
        }
        
        # 人間らしい遅延を追加
        time.sleep(random.uniform(0.5, 1.5))
        
        response = requests.post(gemini_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        analysis_comment = result['candidates'][0]['content']['parts'][0]['text']
        
        return {
            'ranking': ranking_data,
            'analysis': analysis_comment,
            'total_products': sum(len(products) for products in products_data.values())
        }
        
    except Exception as e:
        logger.error(f"Gemini分析エラー: {e}")
        return {
            'ranking': ranking_data if 'ranking_data' in locals() else [],
            'analysis': f"分析エラー: {str(e)}",
            'total_products': 0
        }

@app.route('/')
def home():
    return "eBay Japanese Products Scraper API - Async Version"

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """スクレイピング開始（非同期）"""
    try:
        # リクエストパラメータ
        data = request.get_json() or {}
        keywords_limit = min(data.get('keywords_limit', 5), 10)  # 最大10個に制限
        
        # プロセスIDを生成
        process_id = str(uuid.uuid4())
        
        # バックグラウンドでスクレイピング開始
        scraper = EbayScraper()
        thread = threading.Thread(
            target=scraper.search_japanese_products_async,
            args=(process_id, keywords_limit)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'process_id': process_id,
            'status': 'started',
            'message': f'{keywords_limit}個のキーワードで検索を開始しました'
        })
        
    except Exception as e:
        logger.error(f"開始エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/check_progress/<process_id>', methods=['GET'])
def check_progress(process_id):
    """プロセス進行状況をチェック"""
    if process_id not in process_status:
        return jsonify({'error': 'プロセスが見つかりません'}), 404
    
    status = process_status[process_id].copy()
    
    # 時間情報を文字列に変換
    if 'start_time' in status:
        status['start_time'] = status['start_time'].isoformat()
    if 'end_time' in status:
        status['end_time'] = status['end_time'].isoformat()
    
    return jsonify(status)

@app.route('/get_results/<process_id>', methods=['GET'])
def get_results(process_id):
    """結果を取得"""
    if process_id not in results_cache:
        return jsonify({'error': '結果が見つかりません'}), 404
    
    result = results_cache[process_id]
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'active_processes': len([p for p in process_status.values() if p['status'] == 'running']),
        'cached_results': len(results_cache)
    })

# 定期的にキャッシュをクリーンアップ
def cleanup_old_data():
    """古いデータをクリーンアップ"""
    current_time = datetime.now()
    old_processes = []
    
    for process_id, status in process_status.items():
        start_time = status.get('start_time')
        if start_time and (current_time - start_time).total_seconds() > 3600:  # 1時間後
            old_processes.append(process_id)
    
    for process_id in old_processes:
        process_status.pop(process_id, None)
        results_cache.pop(process_id, None)
    
    # 60分後に再実行
    timer = threading.Timer(3600, cleanup_old_data)
    timer.daemon = True
    timer.start()

# クリーンアップを開始
cleanup_old_data()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
