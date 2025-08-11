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
import signal
import sys

# ログ設定（Render用に調整）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Renderのログに出力
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Gemini API設定
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# プロセス状態管理（Render用にメモリ効率化）
process_status = {}
results_cache = {}
MAX_CONCURRENT_PROCESSES = 2  # Renderの制限を考慮
MAX_CACHE_SIZE = 50  # メモリ制限対策

class RenderOptimizedScraper:
    def __init__(self):
        # セッション数を削減（Renderのメモリ制限対策）
        self.sessions = []
        for i in range(2):  # 3→2に削減
            session = requests.Session()
            # Renderのタイムアウト対策
            session.timeout = 30
            self.sessions.append(session)
        self.current_session_index = 0
        
        # 最新のUser-Agentリスト
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0'
        ]
        
        # Renderの外向きIPアドレスをログ出力
        self.log_render_ip()
    
    def log_render_ip(self):
        """RenderのIPアドレスを確認"""
        try:
            response = requests.get('https://httpbin.org/ip', timeout=10)
            ip_info = response.json()
            logger.info(f"Render Instance IP: {ip_info.get('origin', 'Unknown')}")
        except Exception as e:
            logger.warning(f"IP確認失敗: {e}")
    
    def get_current_session(self):
        """セッションをローテーションで取得"""
        session = self.sessions[self.current_session_index]
        self.current_session_index = (self.current_session_index + 1) % len(self.sessions)
        return session
    
    def get_human_like_headers(self):
        """人間らしいヘッダーを生成（Render最適化）"""
        user_agent = random.choice(self.user_agents)
        
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': random.choice([
                'en-US,en;q=0.9',
                'en-US,en;q=0.9,ja;q=0.8'
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',  # 直接アクセスを装う
            'Cache-Control': 'max-age=0',
        }
        
        # Renderの場合はRefererを控えめに
        if random.random() < 0.2:  # 20%に削減
            headers['Referer'] = 'https://www.google.com/'
        
        return headers
    
    def render_safe_delay(self, min_delay=10, max_delay=30):
        """Render環境での安全な遅延"""
        # Renderのタイムアウト（30秒）を考慮して調整
        base_delay = random.uniform(min_delay, max_delay)
        
        # 長時間休憩の頻度と時間を調整
        if random.random() < 0.15:  # 15%に削減
            extra_delay = random.uniform(20, 60)  # 最大60秒に削減
            base_delay += extra_delay
            logger.info(f"[RENDER] 長時間休憩: +{extra_delay:.1f}秒")
        
        # Renderのリソース制限を考慮して分割待機
        logger.info(f"[RENDER] 待機開始: {base_delay:.1f}秒")
        
        # 30秒以上の場合は分割して待機
        while base_delay > 25:
            time.sleep(25)
            base_delay -= 25
            logger.info(f"[RENDER] 継続待機中... 残り{base_delay:.1f}秒")
        
        if base_delay > 0:
            time.sleep(base_delay)
        
        logger.info(f"[RENDER] 待機完了")
    
    def cleanup_memory(self):
        """メモリクリーンアップ（Render対策）"""
        import gc
        
        # 古いキャッシュを削除
        if len(results_cache) > MAX_CACHE_SIZE:
            oldest_keys = list(results_cache.keys())[:-MAX_CACHE_SIZE//2]
            for key in oldest_keys:
                results_cache.pop(key, None)
            logger.info(f"[RENDER] メモリクリーンアップ: {len(oldest_keys)} キャッシュ削除")
        
        # ガベージコレクション実行
        gc.collect()
    
    def search_japanese_products_render(self, process_id, keywords_limit=5):
        """Render最適化版の検索メソッド"""
        
        # 同時実行プロセス数制限
        active_processes = len([p for p in process_status.values() if p.get('status') == 'running'])
        if active_processes >= MAX_CONCURRENT_PROCESSES:
            logger.warning(f"[RENDER] 同時実行制限: {active_processes}/{MAX_CONCURRENT_PROCESSES}")
            process_status[process_id] = {
                'status': 'error',
                'error': 'Too many concurrent processes. Please wait.',
                'start_time': datetime.now()
            }
            return
        
        japanese_keywords = [
            'japanese traditional',
            'japanese vintage', 
            'japanese kimono',
            'japanese ceramics',
            'japanese art',
            'japanese antique',
            'japanese pottery',
            'japanese woodblock',
            'japanese tea ceremony',
            'japanese lacquer'
        ]
        
        # Render環境では少ないキーワード数に制限
        keywords_limit = min(keywords_limit, 5)  # 最大5個
        random.shuffle(japanese_keywords)
        keywords_to_search = japanese_keywords[:keywords_limit]
        
        all_products = {}
        
        try:
            # プロセス状態初期化
            process_status[process_id] = {
                'status': 'running',
                'progress': 0,
                'current_keyword': '',
                'total_keywords': len(keywords_to_search),
                'completed_keywords': 0,
                'start_time': datetime.now(),
                'error': None,
                'render_optimized': True
            }
            
            logger.info(f"[RENDER] プロセス開始: {process_id} - {keywords_limit}キーワード")
            
            # 初期待機（Render用に調整）
            initial_wait = random.uniform(5, 15)  # 短縮
            logger.info(f"[RENDER] 初期待機: {initial_wait:.1f}秒")
            time.sleep(initial_wait)
            
            for i, keyword in enumerate(keywords_to_search):
                try:
                    # メモリクリーンアップ
                    if i > 0:
                        self.cleanup_memory()
                    
                    process_status[process_id]['current_keyword'] = keyword
                    process_status[process_id]['progress'] = int((i / len(keywords_to_search)) * 100)
                    
                    logger.info(f"[RENDER] 検索 ({i+1}/{len(keywords_to_search)}): {keyword}")
                    
                    # 検索実行
                    products = self.scrape_ebay_render_safe(keyword)
                    
                    if products:
                        all_products[keyword] = products
                        logger.info(f"[RENDER] {keyword}: {len(products)} 件取得")
                    else:
                        logger.warning(f"[RENDER] {keyword}: 取得失敗")
                    
                    process_status[process_id]['completed_keywords'] = i + 1
                    
                    # 次のキーワード前の待機（Render用に調整）
                    if i < len(keywords_to_search) - 1:
                        wait_time = random.uniform(20, 45)  # 短縮
                        logger.info(f"[RENDER] 次のキーワード前待機: {wait_time:.1f}秒")
                        
                        # 分割して待機（Renderのタイムアウト対策）
                        while wait_time > 20:
                            time.sleep(20)
                            wait_time -= 20
                            logger.info(f"[RENDER] 待機継続中...")
                        if wait_time > 0:
                            time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"[RENDER] キーワード {keyword} エラー: {e}")
                    # エラー時の待機時間も短縮
                    error_wait = random.uniform(30, 60)
                    logger.info(f"[RENDER] エラー回復待機: {error_wait:.1f}秒")
                    time.sleep(error_wait)
                    continue
            
            # 分析フェーズ
            process_status[process_id]['status'] = 'analyzing'
            process_status[process_id]['progress'] = 90
            
            logger.info(f"[RENDER] 分析開始: 取得カテゴリ数 {len(all_products)}")
            
            # 分析実行
            result = self.analyze_with_gemini_render(all_products)
            
            # 結果保存
            results_cache[process_id] = result
            
            # 完了
            process_status[process_id]['status'] = 'completed'
            process_status[process_id]['progress'] = 100
            process_status[process_id]['end_time'] = datetime.now()
            
            logger.info(f"[RENDER] プロセス完了: {process_id}")
            
        except Exception as e:
            logger.error(f"[RENDER] プロセス全体エラー: {e}")
            process_status[process_id]['status'] = 'error'
            process_status[process_id]['error'] = str(e)
    
    def scrape_ebay_render_safe(self, keyword):
        """Render環境でのeBay検索（安全版）"""
        products = []
        
        try:
            # Render用の控えめな遅延
            self.render_safe_delay(10, 25)
            
            session = self.get_current_session()
            headers = self.get_human_like_headers()
            session.headers.update(headers)
            
            # URL構築（Render用に簡素化）
            url = (f"https://www.ebay.com/sch/i.html"
                  f"?_nkw={quote_plus(keyword)}"
                  f"&LH_Sold=1"
                  f"&_pgn=1"
                  f"&_ipg=50")  # 固定化
            
            logger.info(f"[RENDER] アクセス: {keyword}")
            
            # Renderのタイムアウトを考慮
            response = session.get(url, timeout=25)
            logger.info(f"[RENDER] レスポンス: {response.status_code}")
            
            # ボット検出チェック（簡素化）
            response_text = response.text.lower()
            if any(word in response_text for word in ['bot', 'captcha', 'blocked']):
                logger.warning(f"[RENDER] ボット検出の可能性: {keyword}")
                # Render環境では短めの待機
                time.sleep(random.uniform(60, 120))
                return products
            
            response.raise_for_status()
            
            # HTML解析
            soup = BeautifulSoup(response.content, 'html.parser')
            items = soup.select('div.s-item__wrapper, div.s-item')
            
            logger.info(f"[RENDER] 商品要素数: {len(items)}")
            
            # 商品処理（Render用に制限）
            processed_count = 0
            for item in items[:15]:  # 20→15に削減
                if processed_count >= 10:  # さらに制限
                    break
                    
                try:
                    product_data = self.extract_product_info_render(item)
                    if product_data and self.validate_product_render(product_data):
                        products.append(product_data)
                        processed_count += 1
                        
                        # 処理間隔を短縮
                        time.sleep(random.uniform(0.2, 0.5))
                except Exception as e:
                    logger.debug(f"[RENDER] 商品抽出エラー: {e}")
                    continue
            
            logger.info(f"[RENDER] 取得商品数: {len(products)}")
            
        except requests.exceptions.Timeout:
            logger.error(f"[RENDER] タイムアウト: {keyword}")
        except Exception as e:
            logger.error(f"[RENDER] 検索エラー: {e}")
        
        return products
    
    def extract_product_info_render(self, item):
        """Render最適化版商品抽出"""
        try:
            # タイトル（簡素化）
            title_elem = (item.select_one('h3.s-item__title') or 
                         item.select_one('.s-item__title'))
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 10 or 'Shop on eBay' in title:
                return None
            
            # 価格（簡素化）
            price_elem = (item.select_one('span.s-item__price') or
                         item.select_one('.s-item__price'))
            
            if not price_elem:
                return None
            
            price_text = price_elem.get_text(strip=True)
            price = self.parse_price_simple(price_text)
            
            if not price or price <= 0:
                return None
            
            return {
                'title': title[:200],  # 長さ制限
                'price': price
            }
            
        except Exception as e:
            logger.debug(f"[RENDER] 抽出エラー: {e}")
            return None
    
    def parse_price_simple(self, price_text):
        """簡素化された価格解析"""
        import re
        try:
            match = re.search(r'[\$]?([\d,]+\.?\d*)', price_text.replace(',', ''))
            if match:
                price = float(match.group(1))
                return price if 0.1 <= price <= 10000 else None
            return None
        except:
            return None
    
    def validate_product_render(self, product):
        """Render用商品検証"""
        if not product or not product.get('title') or not product.get('price'):
            return False
        
        title = product['title']
        price = product['price']
        
        return (10 <= len(title) <= 200 and 
                0.1 <= price <= 10000 and
                'test' not in title.lower())
    
    def analyze_with_gemini_render(self, products_data):
        """Render用Gemini分析"""
        try:
            ranking_data = []
            
            for keyword, products in products_data.items():
                if not products:
                    continue
                    
                prices = [p['price'] for p in products]
                if prices:
                    ranking_data.append({
                        'keyword': keyword,
                        'count': len(products),
                        'mean': round(sum(prices) / len(prices), 2),
                        'max': max(prices),
                        'min': min(prices)
                    })
            
            ranking_data.sort(key=lambda x: x['count'], reverse=True)
            
            # Gemini分析（簡素化）
            if GEMINI_API_KEY:
                try:
                    analysis_text = "eBay和風商品データ:\n"
                    for data in ranking_data[:3]:
                        analysis_text += f"{data['keyword']}: {data['count']}件\n"
                    
                    analysis_comment = self.call_gemini_simple(analysis_text)
                except Exception as e:
                    logger.error(f"[RENDER] Gemini分析エラー: {e}")
                    analysis_comment = "分析エラー"
            else:
                analysis_comment = "Gemini APIキーが設定されていません"
            
            return {
                'ranking': ranking_data,
                'analysis': analysis_comment,
                'total_products': sum(len(products) for products in products_data.values()),
                'render_optimized': True
            }
            
        except Exception as e:
            logger.error(f"[RENDER] 分析全体エラー: {e}")
            return {
                'ranking': [],
                'analysis': f"分析エラー: {str(e)}",
                'total_products': 0
            }
    
    def call_gemini_simple(self, text):
        """簡素化されたGemini API呼び出し"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "contents": [{"parts": [{"text": text + "\n50文字以内で要約してください。"}]}]
            }
            
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
            
        except Exception as e:
            logger.error(f"[RENDER] Gemini呼び出しエラー: {e}")
            return "Gemini分析失敗"

# グローバルスクレイパーインスタンス
scraper = RenderOptimizedScraper()

@app.route('/')
def home():
    return jsonify({
        "message": "eBay Japanese Products Scraper - Render Optimized",
        "version": "render-v1.0",
        "status": "ready",
        "limits": {
            "max_concurrent_processes": MAX_CONCURRENT_PROCESSES,
            "max_keywords": 5,
            "recommended_keywords": 3
        }
    })

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Render最適化版スクレイピング開始"""
    try:
        data = request.get_json() or {}
        keywords_limit = min(data.get('keywords_limit', 3), 5)  # Render用に制限
        
        # 同時実行チェック
        active_processes = len([p for p in process_status.values() if p.get('status') == 'running'])
        if active_processes >= MAX_CONCURRENT_PROCESSES:
            return jsonify({
                'error': f'同時実行制限に達しています ({active_processes}/{MAX_CONCURRENT_PROCESSES})',
                'message': '少し待ってから再試行してください'
            }), 429
        
        process_id = str(uuid.uuid4())
        
        # バックグラウンド実行
        thread = threading.Thread(
            target=scraper.search_japanese_products_render,
            args=(process_id, keywords_limit)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'process_id': process_id,
            'status': 'started',
            'message': f'Render環境で{keywords_limit}キーワード検索開始',
            'estimated_time': f'{keywords_limit * 45}-{keywords_limit * 90}秒',
            'render_optimized': True
        })
        
    except Exception as e:
        logger.error(f"[RENDER] 開始エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/check_progress/<process_id>', methods=['GET'])
def check_progress(process_id):
    """進行状況チェック"""
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
    """結果取得"""
    if process_id not in results_cache:
        return jsonify({'error': '結果が見つかりません'}), 404
    
    return jsonify(results_cache[process_id])

@app.route('/health', methods=['GET'])
def health_check():
    """Render用ヘルスチェック"""
    return jsonify({
        'status': 'healthy',
        'platform': 'Render',
        'version': 'render-optimized-v1.0',
        'active_processes': len([p for p in process_status.values() if p.get('status') == 'running']),
        'cached_results': len(results_cache),
        'limits': {
            'max_concurrent': MAX_CONCURRENT_PROCESSES,
            'max_cache_size': MAX_CACHE_SIZE,
            'max_keywords': 5
        },
        'gemini_api': 'configured' if GEMINI_API_KEY else 'not configured'
    })

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """キャッシュクリア（Render用）"""
    global results_cache, process_status
    
    old_cache_size = len(results_cache)
    old_status_size = len(process_status)
    
    # 実行中以外のプロセスをクリア
    active_processes = {k: v for k, v in process_status.items() 
                       if v.get('status') == 'running'}
    
    results_cache.clear()
    process_status = active_processes
    
    return jsonify({
        'message': 'キャッシュクリア完了',
        'cleared_cache': old_cache_size,
        'cleared_status': old_status_size - len(active_processes),
        'remaining_active': len(active_processes)
    })

# クリーンアップ関数（Render用）
def render_cleanup():
    """Render用定期クリーンアップ"""
    current_time = datetime.now()
    old_processes = []
    
    for process_id, status in list(process_status.items()):
        start_time = status.get('start_time')
        if start_time:
            elapsed = (current_time - start_time).total_seconds()
            # 1時間で自動クリーンアップ
            if elapsed > 3600:
                old_processes.append(process_id)
    
    for process_id in old_processes:
        process_status.pop(process_id, None)
        results_cache.pop(process_id, None)
    
    if old_processes:
        logger.info(f"[RENDER] 自動クリーンアップ: {len(old_processes)} プロセス削除")
    
    # 30分後に再実行
    timer = threading.Timer(1800, render_cleanup)
    timer.daemon = True
    timer.start()

# Renderのシグナルハンドリング
def signal_handler(signum, frame):
    logger.info(f"[RENDER] シャットダウンシグナル受信: {signum}")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# 初期化
render_cleanup()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"[RENDER] サーバー起動 - ポート: {port}")
    logger.info("[RENDER] 最適化: メモリ効率化、タイムアウト対策、同時実行制限")
    
    # Renderの本番環境設定
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
