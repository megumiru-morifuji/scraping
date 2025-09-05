!pip install requests beautifulsoup4

import requests
from bs4 import BeautifulSoup

# User-Agentを設定（多くのサイトで必要）
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# eBayのトップページにリクエスト
url = 'https://www.ebay.com'
r = requests.get(url, headers=headers)

# BeautifulSoupでパース
r_text = BeautifulSoup(r.text, 'html.parser')

# レスポンス情報を表示
print("ステータスコード:", r.status_code)
print("URL:", r.url)
print("=" * 50)

# タイトルタグを取得
title = r_text.find('title')
if title:
    print("ページタイトル:", title.text.strip())

# metaタグから説明を取得
description = r_text.find('meta', attrs={'name': 'description'})
if description:
    print("ページ説明:", description.get('content', 'なし'))

print("=" * 50)
print("HTMLの最初の500文字:")
print(r.text[:500])

# レスポンスオブジェクト自体も表示
print("=" * 50)
print("レスポンスオブジェクト:", r)
