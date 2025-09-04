from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
import logging
import time
import json

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def test_ebay_access():
    """eBayに1回だけアクセスしてブロック状況をテスト"""
    try:
        # 最もシンプルな検索（1件のみ取得）
        url = "https://www.ebay.com/sch/i.html?_nkw=test&_pgn=1"
        
        # 標準的なブラウザヘッダー
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        logger.info(f"テストURL: {url}")
        
        # リクエスト実行
        response = requests.get(url, headers=headers, timeout=15)
        
        logger.info(f"ステータスコード: {response.status_code}")
        logger.info(f"レスポンスサイズ: {len(response.text)} 文字")
        
        # レスポンス分析
        analysis = analyze_response(response)
        
        # HTMLをパース
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 商品要素を探す
        items = soup.find_all('div', class_='s-item__wrapper')
        if not items:
            items = soup.find_all('div', class_='s-item')
        
        logger.info(f"取得した商品要素数: {len(items)}")
        
        # 最初の商品情報を取得
        first_product = None
        if items and len(items) > 1:  # 最初の要素は広告の場合があるので2番目以降を確認
            for item in items[:3]:  # 最初の3つを試す
                product = extract_single_product(item)
                if product:
                    first_product = product
                    break
        
        # ページタイトルを取得
        title_elem = soup.find('title')
        page_title = title_elem.get_text() if title_elem else "タイトルなし"
        
        return {
            'status': 'success',
            'response_code': response.status_code,
            'response_size': len(response.text),
            'page_title': page_title,
            'items_found': len(items),
            'first_product': first_product,
            'analysis': analysis,
            'server_ip': get_server_info()
        }
        
    except Exception as e:
        logger.error(f"テストエラー: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'server_ip': get_server_info()
        }

def analyze_response(response):
    """レスポンスを分析してブロック状況を判定"""
    analysis = {
        'likely_blocked': False,
        'block_indicators': [],
        'content_type': response.headers.get('content-type', 'unknown'),
        'server': response.headers.get('server', 'unknown'),
        'response_headers': dict(response.headers)
    }
    
    text_lower = response.text.lower()
    
    # ブロック指標をチェック
    block_indicators = [
        ('captcha', 'CAPTCHA検出'),
        ('robot', 'ロボット検出'),
        ('blocked', 'ブロック検出'),
        ('access denied', 'アクセス拒否'),
        ('security check', 'セキュリティチェック'),
        ('unusual traffic', '異常なトラフィック'),
        ('try again later', '後で試すメッセージ'),
        ('automated requests', '自動リクエスト検出'),
        ('suspicious activity', '疑わしいアクティビティ')
    ]
    
    for indicator, description in block_indicators:
        if indicator in text_lower:
            analysis['block_indicators'].append(description)
            analysis['likely_blocked'] = True
    
    # 異常に短いレスポンス
    if len(response.text) < 5000:
        analysis['block_indicators'].append('異常に短いレスポンス')
        analysis['likely_blocked'] = True
    
    # リダイレクトチェック
    if len(response.history) > 0:
        analysis['redirects'] = [r.url for r in response.history]
    
    return analysis

def extract_single_product(item):
    """単一商品の情報を抽出"""
    try:
        # タイトル抽出
        title_elem = item.find('h3', class_='s-item__title') or \
                    item.find('a', class_='s-item__link')
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        if not title or title in ['New Listing', '']:
            return None
        
        # 価格抽出
        price_elem = item.find('span', class_='s-item__price') or \
                    item.find('span', class_='notranslate')
        
        price_text = price_elem.get_text(strip=True) if price_elem else "価格なし"
        
        return {
            'title': title[:100],  # 最初の100文字のみ
            'price_text': price_text
        }
        
    except Exception as e:
        logger.debug(f"商品抽出エラー: {e}")
        return None

def get_server_info():
    """サーバー情報を取得"""
    try:
        # 外部IPを取得
        ip_response = requests.get('https://api.ipify.org', timeout=5)
        external_ip = ip_response.text if ip_response.status_code == 200 else "取得失敗"
        
        return {
            'external_ip': external_ip,
            'render_service': os.environ.get('RENDER_SERVICE_NAME', 'unknown'),
            'render_instance': os.environ.get('RENDER_INSTANCE_ID', 'unknown')
        }
    except:
        return {'external_ip': '取得エラー'}

@app.route('/')
def home():
    return """
    <h1>eBay Access Test for Render</h1>
    <p><a href="/test_single">単発テスト実行</a></p>
    <p><a href="/health">ヘルスチェック</a></p>
    """

@app.route('/test_single')
def test_single():
    """単発テスト実行"""
    logger.info("eBayアクセステスト開始")
    result = test_ebay_access()
    
    # 結果をログ出力
    logger.info(f"テスト結果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
    return jsonify(result)

@app.route('/test_multiple')
def test_multiple():
    """複数回テスト（3回実行して比較）"""
    results = []
    
    for i in range(3):
        logger.info(f"テスト {i+1}/3 実行中")
        result = test_ebay_access()
        result['test_number'] = i + 1
        results.append(result)
        
        # 2秒待機
        if i < 2:
            time.sleep(2)
    
    # 結果比較
    comparison = {
        'all_success': all(r['status'] == 'success' for r in results),
        'block_detected': any(r.get('analysis', {}).get('likely_blocked', False) for r in results),
        'consistent_ip': len(set(r.get('server_ip', {}).get('external_ip', '') for r in results)) == 1,
        'results': results
    }
    
    return jsonify(comparison)

@app.route('/health')
def health():
    """ヘルスチェック"""
    return jsonify({
        'status': 'ok',
        'timestamp': time.time(),
        'server_info': get_server_info()
    })

@app.route('/debug_headers')
def debug_headers():
    """リクエストヘッダーデバッグ"""
    try:
        # HTTPBinを使ってヘッダー情報を確認
        response = requests.get('https://httpbin.org/headers', timeout=10)
        return jsonify({
            'our_request_appears_as': response.json(),
            'our_server_info': get_server_info()
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"アプリケーション起動 - ポート: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
