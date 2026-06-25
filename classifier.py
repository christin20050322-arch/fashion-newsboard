"""
classifier.py
--------------
核心分類邏輯：依「標題 + 摘要」自動歸類到 5 大分類（可多選）。

設計兩層策略：
1. classify_with_llm()  -> 呼叫真實 LLM API（此處用 Anthropic Claude 範例，亦可換成 OpenAI）。
2. classify_with_rules() -> 沒有 API Key 時的離線備援，用關鍵字規則模擬分類，
   確保整個系統在沒有金鑰的狀態下依然可以跑完整流程做測試。

對外統一呼叫 classify_article(title, summary)，會自動判斷使用哪一種策略。
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
2. 抽取 2-3 個最能代表這篇文章核心內容的「中文關鍵詞」，每個關鍵詞需為完整、語意正確的詞組（例如「永續纖維」「聯名合作」「秀場趨勢」），不要切出不完整或無意義的片段，也不要使用單一個中文字。若文章本身是英文，也請將關鍵詞翻譯/轉換成簡潔的中文詞組。

務必只回傳 JSON，格式如下，不要有任何其他文字：
{{
  "categories": ["Trends & Aesthetics", "Marketing & Collaborations"],
  "summary": "一句話精簡摘要...",
  "keywords": ["聯名合作", "快閃店", "秀場趨勢"]
}}
"""


def classify_with_llm(title: str, raw_summary: str = "") -> dict:
    """
    呼叫 Anthropic API 進行分類 + 摘要生成。
    需要環境變數 ANTHROPIC_API_KEY。
    若你想用 OpenAI，把這個函式換成 openai.ChatCompletion 呼叫即可，介面保持一致（回傳同樣的 dict 結構）。
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_content = f"標題：{title}\n原始摘要/內容：{raw_summary}"

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = resp.content[0].text.strip()
    # 防止模型誤加 ```json 包裹
    text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
    data = json.loads(text)

    # 防呆：過濾掉不在白名單內的分類
    data["categories"] = [c for c in data.get("categories", []) if c in CATEGORIES]
    if not data["categories"]:
        data["categories"] = ["Corporate & Market"]  # 預設保底分類

    # 防呆：keywords 確保是 list[str]，且過濾掉空字串/過長異常值
    raw_keywords = data.get("keywords", [])
    if not isinstance(raw_keywords, list):
        raw_keywords = []
    data["keywords"] = [str(k).strip() for k in raw_keywords if str(k).strip() and len(str(k)) <= 12][:3]

    return data


# ---------------------------------------------------------------------------
# 離線規則式備援（沒有 API Key 時使用，方便先跑通整套系統做 Demo / 測試）
# ---------------------------------------------------------------------------
KEYWORD_RULES = {
    "Corporate & Market": ["財報", "earnings", "revenue", "CEO", "收購", "acquisition", "IPO",
                            "股價", "stock", "人事", "appoint", "layoff", "裁員", "業績"],
    "Trends & Aesthetics": ["trend", "趨勢", "走秀", "runway", "fashion week", "風格", "style",
                             "corpcore", "minimalism", "siren", "look", "爆款", "預測"],
    "Supply Chain & Textile Tech": ["布料", "fabric", "textile", "原物料", "raw material",
                                     "supply chain", "供應鏈", "smart textile", "智慧紡織", "打版", "pattern"],
    "Sustainability & ESG": ["sustainab", "永續", "esg", "碳足跡", "carbon", "recycl", "回收",
                              "gots", "grs", "green", "環保"],
    "Marketing & Collaborations": ["collab", "聯名", "campaign", "代言", "ambassador", "快閃",
                                    "pop-up", "capsule", "膠囊系列", "marketing"],
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
    matched = list(dict.fromkeys(matched))  # 去重但保留順序
    if not matched:
        matched = ["Corporate & Market"]

    # 簡單摘要：取前 60 字當作摘要（純離線情境下沒有 LLM 可生成）
    base_text = raw_summary or title
    summary = base_text[:80] + ("..." if len(base_text) > 80 else "")

    # 離線關鍵詞：用實際匹配到的規則關鍵字當作關鍵詞（去重，最多3個）
    keywords = list(dict.fromkeys(matched_terms))[:3]

    return {"categories": matched, "summary": summary, "keywords": keywords}


def classify_article(title: str, raw_summary: str = "") -> dict:
    """統一入口：有 API Key 用 LLM，沒有就用規則式備援"""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return classify_with_llm(title, raw_summary)
        except Exception as e:
            print(f"[WARN] LLM 分類失敗，改用規則式備援：{e}")
            return classify_with_rules(title, raw_summary)
    return classify_with_rules(title, raw_summary)


if __name__ == "__main__":
    # 簡單自我測試
    sample_title = "H&M 與知名插畫家推出聯名膠囊系列，主打永續回收布料"
    sample_summary = "本次合作採用 GRS 認證回收聚酯纖維，並於三大城市開設快閃店。"
    print(json.dumps(classify_article(sample_title, sample_summary), ensure_ascii=False, indent=2))
