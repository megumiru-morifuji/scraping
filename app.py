!pip install requests beautifulsoup4 fake-useragent lxml pandas

import requests
from bs4 import BeautifulSoup
import time
import random
from fake_useragent import UserAgent
import json
from urllib.parse import urlencode, urlparse
import re
import pandas as pd
from datetime import datetime

def get_stealth_headers():
    """
    Bot検出を回避するためのリアルなヘッダー
    """
    ua = UserAgent()
    
    return {
        'User-Agent': ua.chrome,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Referer': 'https://www.ebay.com/',
    }

def get_ebay_session():
    """
    セッションとクッキーを取得
    """
    session = requests.Session()
    session.headers.update(get_stealth_headers())
    
    # トップページにアクセスしてクッキーを取得
    try:
        response = session.get('https://www.ebay.com', timeout=10)
        print(f"🍪 セッション開始: {response.status_code}")
        time.sleep(random.uniform(1, 3))
        return session
    except Exception as e:
        print(f"❌ セッション取得エラー: {e}")
        return None

def extract_price_from_text(text):
    """
    テキストから価格を抽出する改良版関数
    """
    if not text:
        return "価格不明"
    
    # 複数の価格パターンを試す
    price_patterns = [
        r'Sold for\s*\$?([\d,]+\.?\d*)',  # "Sold for $25.00"
        r'Price:\s*\$?([\d,]+\.?\d*)',    # "Price: $25.00"
        r'\$\s*([\d,]+\.?\d*)',           # "$25.00"
        r'USD\s*([\d,]+\.?\d*)',          # "USD 25.00"
        r'([\d,]+\.?\d*)\s*USD',          # "25.00 USD"
        r'sold\s+for\s+\$?([\d,]+\.?\d*)', # 大文字小文字区別なし
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                # 最初にマッチした価格を返す
                price_str = matches[0].replace(',', '')
                price_float = float(price_str)
                if price_float > 0:
                    return f"${price_float:.2f}"
            except (ValueError, IndexError):
                continue
    
    return "価格不明"

def extract_item_data(item_element):
    """
    商品要素から詳細情報を抽出（価格抽出大幅改良版）
    """
    try:
        # タイトル抽出（改良版）
        title = "タイトル不明"
        
        # 方法1: 様々なセレクタを試す
        title_selectors = [
            'h3.s-item__title',
            '.s-item__title',
            'h3',
            '.s-item__title-label',
            'a[href*="/itm/"]'
        ]
        
        for selector in title_selectors:
            title_elem = item_element.select_one(selector)
            if title_elem:
                title_text = title_elem.get_text().strip()
                # 不要な文字列を除外
                if title_text and len(title_text) > 10 and not any(x in title_text.lower() for x in ['shop on ebay', 'new listing', 'opens in']):
                    title = title_text
                    break
        
        # 方法2: 全てのaタグからリンクテキストを探す
        if title == "タイトル不明":
            links = item_element.find_all('a', href=lambda x: x and '/itm/' in x)
            for link in links:
                link_text = link.get_text().strip()
                if len(link_text) > 15 and not any(x in link_text.lower() for x in ['shop on ebay', 'new listing', 'opens in']):
                    title = link_text
                    break
        
        # 価格抽出（大幅改良版）
        price = "価格不明"
        
        # 方法1: 売り切れ商品特有のセレクタを試す
        price_selectors = [
            '.s-item__price',
            '.s-item__detail--primary',
            '.s-item__details',
            '.s-item__soldPrice',
            '.sold-price',
            '.s-item__price-soldValue',
            '.notranslate'
        ]
        
        for selector in price_selectors:
            price_elem = item_element.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text().strip()
                extracted_price = extract_price_from_text(price_text)
                if extracted_price != "価格不明":
                    price = extracted_price
                    break
        
        # 方法2: より広い範囲でテキスト検索
        if price == "価格不明":
            # 商品要素全体のテキストから価格を抽出
            all_text = item_element.get_text()
            price = extract_price_from_text(all_text)
        
        # 方法3: span要素から価格を探す
        if price == "価格不明":
            spans = item_element.find_all('span')
            for span in spans:
                span_text = span.get_text().strip()
                if any(keyword in span_text.lower() for keyword in ['sold', 'price', '$', 'usd']):
                    extracted_price = extract_price_from_text(span_text)
                    if extracted_price != "価格不明":
                        price = extracted_price
                        break
        
        # 商品URL抽出
        link_elem = item_element.select_one('a[href*="/itm/"]')
        url = link_elem.get('href') if link_elem else ""
        
        # 画像URL抽出
        img_elem = item_element.select_one('img')
        image_url = ""
        if img_elem:
            image_url = img_elem.get('src') or img_elem.get('data-src') or ""
        
        # 送料情報
        shipping_elem = item_element.select_one('.s-item__shipping, .s-item__freeXDays')
        shipping = shipping_elem.get_text().strip() if shipping_elem else ""
        
        # 販売者情報
        seller_elem = item_element.select_one('.s-item__seller-info, .s-item__seller-info-text')
        seller = seller_elem.get_text().strip() if seller_elem else ""
        
        # 販売日時（売り切れ商品の場合）
        sold_elem = item_element.select_one('.s-item__sold-date, .s-item__endedDate, .s-item__detail--primary')
        sold_date = sold_elem.get_text().strip() if sold_elem else ""
        
        # デバッグ出力（最初の数件のみ）
        if not hasattr(extract_item_data, 'debug_count'):
            extract_item_data.debug_count = 0
        
        if extract_item_data.debug_count < 5:
            print(f"    🔍 商品 {extract_item_data.debug_count + 1}:")
            print(f"      タイトル: {title}")
            print(f"      価格: {price}")
            print(f"      URL: {url[:50]}..." if url else "URL不明")
            
            # デバッグ用：商品要素の一部テキストを表示
            debug_text = item_element.get_text()[:200]
            print(f"      要素テキスト: {debug_text}...")
            
            extract_item_data.debug_count += 1
        
        return {
            'title': title,
            'price': price,
            'url': url,
            'image_url': image_url,
            'shipping': shipping,
            'seller': seller,
            'sold_date': sold_date,
            'scraped_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"⚠️ 商品データ抽出エラー: {e}")
        return None

def search_japanese_items(session, keywords, pages=3):
    """
    和風商品を検索して取得
    """
    all_items = []
    
    japanese_keywords = [
        "japan vintage", "japanese antique", "kimono", "sake", "sushi", "manga", 
        "anime", "katana", "bonsai", "origami", "zen", "samurai", "geisha",
        "tokyo", "kyoto", "osaka", "nintendo", "sony", "toyota", "honda"
    ]
    
    # キーワードをランダムに選択
    if not keywords:
        keywords = random.sample(japanese_keywords, min(3, len(japanese_keywords)))
    
    for keyword in keywords:
        print(f"\n🔍 検索中: '{keyword}'")
        
        for page in range(1, pages + 1):
            print(f"  📄 ページ {page}/{pages}")
            
            # 検索パラメータ
            params = {
                '_nkw': keyword,
                'LH_Sold': '1',  # 売れた商品のみ
                'LH_Complete': '1',  # 完了した取引のみ
                '_sop': '13',  # 最近売れた順
                '_ipg': '60',  # ページあたり60件
                '_pgn': page
            }
            
            url = f"https://www.ebay.com/sch/i.html?{urlencode(params)}"
            
            try:
                response = session.get(url, timeout=15)
                
                if response.status_code != 200:
                    print(f"    ❌ エラー: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 商品要素を取得
                items = soup.select('li[data-view]')
                
                # 広告や無関係な要素を除外
                items = [item for item in items if item.find('a', href=lambda x: x and '/itm/' in x)]
                
                print(f"    ✅ {len(items)}件の商品を発見")
                
                for item in items:
                    item_data = extract_item_data(item)
                    if item_data and item_data['title'] != "タイトル不明":
                        all_items.append({**item_data, 'keyword': keyword})
                
                # Bot検出回避のための待機
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"    ❌ 検索エラー: {e}")
                continue
    
    return all_items

def filter_japanese_items(items, min_price=1.0):
    """
    和風商品をフィルタリング（改良版）
    """
    japanese_indicators = [
        'japan', 'japanese', 'kimono', 'sake', 'sushi', 'manga', 'anime',
        'katana', 'bonsai', 'origami', 'zen', 'samurai', 'geisha', 'tokyo',
        'kyoto', 'osaka', 'vintage', 'antique', 'authentic', 'traditional',
        'nintendo', 'sony', 'toyota', 'honda', 'mitsubishi', 'panasonic'
    ]
    
    filtered_items = []
    debug_count = 0
    
    print(f"🔍 フィルタリング開始: {len(items)}件の商品を確認")
    
    # まず最初の10件の内容を確認
    print("\n📋 最初の10件のタイトルと価格確認:")
    for i, item in enumerate(items[:10], 1):
        if item:
            print(f"  {i}. {item.get('title', '不明')[:60]}... | {item.get('price', '不明')}")
    
    for i, item in enumerate(items):
        if not item:
            continue
            
        title = item.get('title', '').lower()
        price_str = item.get('price', '')
        keyword = item.get('keyword', '').lower()
        
        # タイトルが空でないことを確認
        if not title or title == "タイトル不明" or len(title) < 5:
            continue
        
        # 日本関連キーワードが含まれているか確認
        is_japanese = (
            any(indicator in title for indicator in japanese_indicators) or
            any(indicator in keyword for indicator in japanese_indicators)
        )
        
        # 価格フィルタ（改良版）
        has_valid_price = True
        if price_str and price_str != "価格不明":
            # $20.00 のような価格から数値を抽出
            price_match = re.search(r'[\d,]+\.?\d*', str(price_str))
            if price_match:
                try:
                    price_value = float(price_match.group().replace(',', ''))
                    has_valid_price = price_value >= min_price
                except:
                    has_valid_price = True
        
        # デバッグ出力（最初の5件）
        if debug_count < 5:
            print(f"\n  📋 商品 {debug_count + 1} 詳細:")
            print(f"     タイトル: {item.get('title', '')[:80]}...")
            print(f"     価格: {price_str}")
            print(f"     検索キーワード: {keyword}")
            matching_title_keywords = [kw for kw in japanese_indicators if kw in title]
            matching_search_keywords = [kw for kw in japanese_indicators if kw in keyword]
            print(f"     タイトル内キーワード: {matching_title_keywords}")
            print(f"     検索キーワード内: {matching_search_keywords}")
            print(f"     日本関連判定: {is_japanese}")
            print(f"     価格判定: {has_valid_price}")
            print(f"     → 追加: {is_japanese and has_valid_price}")
            debug_count += 1
        
        if is_japanese and has_valid_price:
            filtered_items.append(item)
    
    print(f"\n✅ フィルタリング完了: {len(filtered_items)}件が条件に合致")
    return filtered_items

def analyze_items(items):
    """
    取得した商品を分析
    """
    if not items:
        print("📊 分析する商品がありません")
        return
    
    print(f"\n📊 取得商品分析 (総数: {len(items)}件)")
    print("=" * 50)
    
    # 価格帯分析
    prices = []
    price_unknown_count = 0
    
    for item in items:
        price_str = item.get('price', '価格不明')
        if price_str == "価格不明":
            price_unknown_count += 1
            continue
            
        price_match = re.search(r'[\d,]+\.?\d*', price_str)
        if price_match:
            try:
                price = float(price_match.group().replace(',', ''))
                prices.append(price)
            except:
                price_unknown_count += 1
    
    print(f"💰 価格情報:")
    print(f"  価格取得済み: {len(prices)}件")
    print(f"  価格不明: {price_unknown_count}件")
    
    if prices:
        print(f"  平均価格: ${sum(prices)/len(prices):.2f}")
        print(f"  最高価格: ${max(prices):.2f}")
        print(f"  最低価格: ${min(prices):.2f}")
    
    # 人気キーワード分析
    keyword_counts = {}
    for item in items:
        keyword = item.get('keyword', 'unknown')
        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
    
    print(f"\n🔥 人気検索キーワード:")
    for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {keyword}: {count}件")
    
    # 高額商品トップ5
    if prices:
        items_with_prices = [(item, price) for item, price in zip([item for item in items if item.get('price') != '価格不明'], prices) if price > 0]
        items_with_prices.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\n💎 高額商品トップ5:")
        for i, (item, price) in enumerate(items_with_prices[:5], 1):
            title = item['title'][:50] + "..." if len(item['title']) > 50 else item['title']
            print(f"  {i}. ${price:.2f} - {title}")

def save_to_csv(items, filename="ebay_japanese_items.csv"):
    """
    CSVファイルに保存
    """
    if not items:
        print("💾 保存する商品がありません")
        return
    
    df = pd.DataFrame(items)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"💾 {len(items)}件の商品を '{filename}' に保存しました")
    
    # 価格情報の統計も表示
    price_with_value = df[df['price'] != '価格不明']
    print(f"  価格取得率: {len(price_with_value)}/{len(items)} ({len(price_with_value)/len(items)*100:.1f}%)")

def main():
    """
    メイン実行
    """
    print("🚀 eBay和風商品スクレイピング開始")
    print("=" * 50)
    
    # セッション開始
    session = get_ebay_session()
    if not session:
        print("❌ セッション取得失敗")
        return
    
    # 検索キーワード（空の場合は自動選択）
    custom_keywords = ["japan vintage", "japanese antique"]  # ここを変更可能
    
    # 商品検索
    print("🔍 商品検索中...")
    items = search_japanese_items(session, custom_keywords, pages=2)
    
    if not items:
        print("❌ 商品が見つかりませんでした")
        return
    
    # 和風商品フィルタリング
    print("🎌 和風商品フィルタリング中...")
    filtered_items = filter_japanese_items(items, min_price=5.0)
    
    print(f"✅ フィルタリング後: {len(filtered_items)}件")
    
    # 分析実行
    analyze_items(filtered_items)
    
    # CSV保存
    save_to_csv(filtered_items)
    
    print("\n🎉 スクレイピング完了！")
    
    return filtered_items

# 実行
if __name__ == "__main__":
    result = main()
