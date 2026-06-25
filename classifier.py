"""
classifier.py
--------------
核心分類邏輯：依「標題 + 摘要」自動歸類到 5 大分類（可多選）。
更新：加入了關鍵詞提取保底機制，確保資料庫永遠有 keywords 資料。
"""
import os
import json
import re

CATEGORIES = [
    "Corporate & Market",
    "Trends & Aesthetics",
    "Supply Chain & Textile Tech",
    "Sustainability & ESG",
    "Marketing & Collaborations",
]

CATEGORY_DESCRIPTIONS = {
    "Corporate & Market": "財報、人事異動、收購、零售數據等核心產業與商業動態",
    "Trends & Aesthetics": "秀場直擊、爆款預測、風格發酵（如 Office Siren, Corpcore, Minimalism）",
    "Supply Chain & Textile Tech": "布料創新、原物料、智慧紡織、數位打版等供應鏈與紡織技術",
    "Sustainability & ESG": "綠色法規、碳足跡、衣物回收、GOTS/GRS 認證等永續發展議題",
    "Marketing & Collaborations": "聯名、代言人、快閃店、膠囊系列等行銷創意與跨界合作",
}

SYSTEM_PROMPT = f"""你是一位時尚與紡織產業的新聞分析師。
請依據使用者提供的「文章標題」與「摘要」，判斷該文章屬於以下哪些分類（可同時屬於多個分類）：

{json.dumps(CATEGORY_DESCRIPTIONS, ensure_ascii=False, indent=2)}

請同時完成兩件事：
1. 產生一句精簡的中文摘要（2-3句話，重點濃縮）。
2. 抽取 2-3 個最能代表這篇文章核心內容的「中文關鍵詞」，每個關鍵詞需為完整、語意正確的詞組。

務必只回傳 JSON，格式如下，不要有任何其他文字：
{{
  "categories": ["Trends & Aesthetics", "Marketing & Collaborations"],
  "summary": "一句話精簡摘要...",
  "keywords": ["聯名合作", "快閃店", "秀場趨勢"]
}}
"""

def classify_with_llm(title: str, raw_summary: str = "") -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    user_content = f"標題：{title}\n原始摘要/內容：{raw_summary}"

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = resp.content[0].text.strip()
    text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
    data = json.loads(text)

    # 過濾分類
    data["categories"] = [c for c in data.get("categories", []) if c in CATEGORIES]
    if not data["categories"]:
        data["categories"] = ["Corporate & Market"]

    # 確保 keywords 有資料，沒有就用保底詞
    raw_keywords = data.get("keywords", [])
    if not isinstance(raw_keywords, list) or not raw_keywords:
        raw_keywords = ["產業動態", "市場觀察", "時尚趨勢"]
    
    data["keywords"] = [str(k).strip() for k in raw_keywords if str(k).strip() and len(str(k)) <= 12][:3]

    return data

# 離線規則式備援
KEYWORD_RULES = {
    "Corporate & Market": ["財報", "earnings", "revenue", "CEO", "收購", "acquisition", "股價", "業績"],
    "Trends & Aesthetics": ["trend", "趨勢", "走秀", "runway", "風格", "style", "corpcore", "爆款"],
    "Supply Chain & Textile Tech": ["布料", "fabric", "textile", "供應鏈", "smart textile", "智慧紡織"],
    "Sustainability & ESG": ["sustainab", "永續", "esg", "碳足跡", "carbon", "回收", "環保"],
    "Marketing & Collaborations": ["collab", "聯名", "campaign", "代言", "快閃", "pop-up", "膠囊系列"],
}

def classify_with_rules(title: str, raw_summary: str = "") -> dict:
    text = f"{title} {raw_summary}".lower()
    matched = []
    matched_terms = []
    
    for cat, keywords in KEYWORD_RULES.items():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(cat)
                matched_terms.append(kw)
                break
    
    matched = list(dict.fromkeys(matched))
    if not matched:
        matched = ["Corporate & Market"]

    # 關鍵字保底機制
    keywords = list(dict.fromkeys(matched_terms))[:3]
    if not keywords:
        keywords = ["產業動態", "市場觀察", "時尚趨勢"]

    base_text = raw_summary or title
    summary = base_text[:80] + ("..." if len(base_text) > 80 else "")

    return {"categories": matched, "summary": summary, "keywords": keywords}

def classify_article(title: str, raw_summary: str = "") -> dict:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return classify_with_llm(title, raw_summary)
        except Exception as e:
            print(f"[WARN] LLM 分類失敗，改用規則式備援：{e}")
            return classify_with_rules(title, raw_summary)
    return classify_with_rules(title, raw_summary)
