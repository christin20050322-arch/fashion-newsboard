import datetime
from database import insert_article, init_db
from classifier import classify_article

# 範例資料 (維持原樣)
today = datetime.date.today().isoformat()
SAMPLES = [
    dict(source="Business of Fashion", title="LVMH 第二季營收優於預期，皮革製品部門強勁回升",
         url="https://example.com/lvmh-q2-earnings",
         raw_summary="LVMH 公布第二季財報，整體營收超出分析師預期，主要受惠於皮革製品部門的需求回升及亞洲市場復甦。"),
    dict(source="WWD", title="2026 秋冬秀場關鍵詞：Corpcore 風格持續發酵",
         url="https://example.com/corpcore-trend-2026",
         raw_summary="從米蘭到巴黎，多個品牌秀場呈現西裝剪裁與辦公室元素混搭的 Corpcore 風格，預計將成為下一季主要趨勢。"),
    dict(source="Textile World", title="新型生物基聚酯纖維問世，碳排放降低 40%",
         url="https://example.com/bio-polyester-breakthrough",
         raw_summary="一家瑞典紡織科技公司開發出生物基聚酯纖維，相較傳統石化原料製程可降低約 40% 碳排放，已獲得多家品牌測試合作。"),
    dict(source="Fashion United", title="歐盟新規要求 2027 年起服飾標籤須註明回收纖維比例",
         url="https://example.com/eu-recycled-content-label",
         raw_summary="歐盟執委會通過新法規，要求自 2027 年起所有上市服飾須在標籤上清楚標示回收纖維含量比例，以強化消費者透明度。"),
    dict(source="Vogue Business", title="運動品牌與插畫家推出聯名膠囊系列，限定快閃店同步登場",
         url="https://example.com/sportsbrand-illustrator-capsule",
         raw_summary="該運動品牌與知名插畫家合作推出聯名膠囊系列，並於三大城市開設限時快閃店，主打年輕消費族群。"),
    dict(source="Drapers", title="智慧紡織新突破：可監測心率的導電纖維量產在即",
         url="https://example.com/smart-textile-heartrate-fiber",
         raw_summary="一項導電纖維技術可直接編織入衣物用於監測心率，該技術已進入量產前測試階段，預計明年導入運動服飾品牌供應鏈。"),
]

def run_seed():
    print("正在將範例資料寫入資料庫...")
    # 確保資料庫初始化
    init_db()
    
    for item in SAMPLES:
        # 1. 呼叫 AI 分類器處理摘要與關鍵詞
        result = classify_article(item["title"], item["raw_summary"])
        
        # 2. 直接呼叫資料庫函式寫入
        inserted = insert_article(
            date=today,
            source=item["source"],
            title=item["title"],
            url=item["url"],
            summary=result["summary"],
            categories=result["categories"],
            keywords=result.get("keywords", []),
        )
        print(f"成功處理: {item['title'][:20]}... -> 結果: {inserted}")

if __name__ == "__main__":
    run_seed()
