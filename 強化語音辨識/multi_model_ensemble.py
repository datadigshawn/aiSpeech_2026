#!/usr/bin/env python3
"""
多模型融合引擎 (Multi-Model Ensemble Engine)
==============================================================================
策略：結合 Google STT (Chirp 3) + Gemini 2.0 + Whisper 的辨識結果

設計理念：
---------
從您的測試結果觀察到：
- Google STT (Chirp 3): 專業術語較差，但結構完整
- Gemini 2.0: 整體最佳，但某些術語仍有誤
- Whisper: 本地運行，可作為輔助驗證

融合策略：
---------
1. **關鍵術語投票機制**：
   - 對於 OCC, EDRH, 車站代碼等關鍵術語
   - 三模型投票，多數決定
   - 特殊情況：Gemini 信心度 > 0.9 直接採用

2. **片段級融合**：
   - 按 VAD 切分的時間軸對齊
   - 每個 chunk 獨立融合
   - 保留時間戳記完整性

3. **加權信心度**：
   - Gemini 2.0: 權重 0.5（測試結果最佳）
   - Google STT: 權重 0.35（速度快、穩定）
   - Whisper: 權重 0.15（輔助驗證）

應用場景：
---------
- 離線批次處理：準確率優先
- 生產環境：可根據成本選擇單一模型
- 研究開發：用於評估不同模型的優劣
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
from difflib import SequenceMatcher
import logging

# 設定 logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiModelEnsemble:
    """多模型融合引擎"""
    
    # 關鍵術語列表（需要投票的高重要性術語）
    CRITICAL_KEYWORDS = [
        # 設備代碼
        'OCC', 'MCP', 'EDRH', 'MTC', 'MCS', 
        'ATP', 'ATO', 'VVVF', 'Bypass',
        
        # 車站代碼（正則表達式）
        r'G\d{2}', r'R\d{2}',
        
        # 緊急術語
        '電力異常', '三軌復電', '停準', '未停準',
        '月台門', '軌旁胸牆', '旅客', '障礙物',
        
        # 指令
        '立即回報', '通告全線', '協助確認'
    ]
    
    # 模型權重（根據測試結果調整）
    MODEL_WEIGHTS = {
        'gemini': 0.50,      # 測試結果最佳
        'google_stt': 0.35,  # 穩定性好
        'whisper': 0.15      # 輔助驗證
    }
    
    def __init__(self):
        """初始化融合引擎"""
        self.results_cache = {}
        
    def load_model_results(
        self,
        gemini_json: Optional[str] = None,
        google_stt_json: Optional[str] = None,
        whisper_json: Optional[str] = None
    ) -> Dict:
        """
        載入各模型的辨識結果
        
        Args:
            gemini_json: Gemini 結果 JSON 路徑
            google_stt_json: Google STT 結果 JSON 路徑
            whisper_json: Whisper 結果 JSON 路徑
        
        Returns:
            統一格式的結果字典
        """
        results = {}
        
        # 載入 Gemini 結果
        if gemini_json and Path(gemini_json).exists():
            with open(gemini_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results['gemini'] = data.get('results', {})
                logger.info(f"✅ 載入 Gemini 結果: {len(results['gemini'])} 個檔案")
        
        # 載入 Google STT 結果
        if google_stt_json and Path(google_stt_json).exists():
            with open(google_stt_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results['google_stt'] = data.get('results', {})
                logger.info(f"✅ 載入 Google STT 結果: {len(results['google_stt'])} 個檔案")
        
        # 載入 Whisper 結果
        if whisper_json and Path(whisper_json).exists():
            with open(whisper_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results['whisper'] = data.get('results', {})
                logger.info(f"✅ 載入 Whisper 結果: {len(results['whisper'])} 個檔案")
        
        self.results_cache = results
        return results
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        從文字中提取關鍵術語
        
        Args:
            text: 辨識文字
        
        Returns:
            關鍵術語列表
        """
        found_keywords = []
        
        for keyword in self.CRITICAL_KEYWORDS:
            # 如果是正則表達式
            if keyword.startswith('r'):
                pattern = keyword[1:]  # 移除 'r' 前綴
                matches = re.findall(pattern, text)
                found_keywords.extend(matches)
            # 普通字串匹配
            elif keyword in text:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def vote_on_keyword(
        self,
        keyword: str,
        model_results: Dict[str, str]
    ) -> Tuple[str, float]:
        """
        對單一關鍵術語進行投票
        
        Args:
            keyword: 關鍵術語（例如 "OCC"）
            model_results: {"gemini": "text...", "google_stt": "text...", ...}
        
        Returns:
            (最佳選擇, 信心度)
        """
        # 統計各模型對該術語的識別
        votes = []
        
        for model_name, text in model_results.items():
            if not text:
                continue
            
            # 提取該模型識別的術語
            found_keywords = self.extract_keywords(text)
            
            # 檢查是否包含目標術語
            if keyword in found_keywords:
                weight = self.MODEL_WEIGHTS.get(model_name, 0.0)
                votes.append((keyword, weight))
            else:
                # 檢查是否有相似術語（編輯距離）
                for found in found_keywords:
                    similarity = SequenceMatcher(None, keyword, found).ratio()
                    if similarity > 0.7:  # 70% 相似度
                        weight = self.MODEL_WEIGHTS.get(model_name, 0.0) * similarity
                        votes.append((found, weight))
        
        if not votes:
            return keyword, 0.0
        
        # 加權投票
        vote_counts = Counter()
        for term, weight in votes:
            vote_counts[term] += weight
        
        # 返回得票最高的術語
        winner, confidence = vote_counts.most_common(1)[0]
        return winner, confidence
    
    def ensemble_chunk(
        self,
        chunk_id: str,
        model_results: Dict[str, Dict]
    ) -> Dict:
        """
        融合單一 chunk 的結果
        
        Args:
            chunk_id: Chunk 標識（例如 "chunk_001"）
            model_results: {
                "gemini": {"transcript": "...", "confidence": 0.9},
                "google_stt": {"transcript": "...", "confidence": 0.85},
                ...
            }
        
        Returns:
            融合後的結果
        """
        # 提取各模型的文字
        texts = {
            model: result.get('transcript', '') 
            for model, result in model_results.items()
        }
        
        # 策略 1: 如果 Gemini 信心度 > 0.9，直接採用
        if 'gemini' in model_results:
            gemini_conf = model_results['gemini'].get('confidence', 0.0)
            if gemini_conf > 0.9:
                logger.debug(f"{chunk_id}: 直接採用 Gemini（信心度 {gemini_conf:.2%}）")
                return {
                    'transcript': texts['gemini'],
                    'method': 'direct_gemini',
                    'confidence': gemini_conf,
                    'sources': {'gemini': 1.0}
                }
        
        # 策略 2: 關鍵術語投票
        all_keywords = set()
        for text in texts.values():
            all_keywords.update(self.extract_keywords(text))
        
        voted_keywords = {}
        for keyword in all_keywords:
            winner, confidence = self.vote_on_keyword(keyword, texts)
            voted_keywords[keyword] = (winner, confidence)
        
        # 策略 3: 選擇主文字（基於加權相似度）
        # 使用 Gemini 作為基準
        base_text = texts.get('gemini', '')
        if not base_text:
            # Gemini 不可用，使用 Google STT
            base_text = texts.get('google_stt', '')
        
        # 替換關鍵術語
        final_text = base_text
        for keyword, (winner, conf) in voted_keywords.items():
            if conf > 0.5 and keyword != winner:
                final_text = final_text.replace(keyword, winner)
        
        # 計算總信心度
        total_confidence = sum(
            model_results.get(model, {}).get('confidence', 0.0) * weight
            for model, weight in self.MODEL_WEIGHTS.items()
            if model in model_results
        )
        
        return {
            'transcript': final_text,
            'method': 'keyword_voting',
            'confidence': total_confidence,
            'voted_keywords': voted_keywords,
            'sources': {
                model: self.MODEL_WEIGHTS[model]
                for model in texts.keys()
                if model in self.MODEL_WEIGHTS
            }
        }
    
    def ensemble_all(
        self,
        output_path: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        融合所有 chunks 的結果
        
        Args:
            output_path: 輸出 JSON 路徑（可選）
        
        Returns:
            完整的融合結果字典
        """
        if not self.results_cache:
            logger.error("❌ 請先使用 load_model_results() 載入結果")
            return {}
        
        # 找到所有共同的 chunk_id
        all_chunk_ids = set()
        for model_results in self.results_cache.values():
            all_chunk_ids.update(model_results.keys())
        
        logger.info(f"開始融合 {len(all_chunk_ids)} 個 chunks...")
        
        # 融合每個 chunk
        ensemble_results = {}
        for chunk_id in sorted(all_chunk_ids):
            # 收集該 chunk 的所有模型結果
            chunk_model_results = {}
            for model_name, model_data in self.results_cache.items():
                if chunk_id in model_data:
                    chunk_model_results[model_name] = model_data[chunk_id]
            
            # 融合
            if chunk_model_results:
                ensemble_results[chunk_id] = self.ensemble_chunk(
                    chunk_id, chunk_model_results
                )
        
        logger.info(f"✅ 融合完成: {len(ensemble_results)} 個 chunks")
        
        # 儲存結果
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'total_chunks': len(ensemble_results),
                        'model_weights': self.MODEL_WEIGHTS,
                        'method': 'keyword_voting_with_confidence'
                    },
                    'results': ensemble_results
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"結果已儲存: {output_file}")
        
        return ensemble_results
    
    def compare_models(self) -> Dict:
        """
        比較各模型的表現
        
        Returns:
            統計字典
        """
        if not self.results_cache:
            return {}
        
        stats = {}
        
        for model_name, model_results in self.results_cache.items():
            # 統計該模型的關鍵術語識別率
            keyword_counts = Counter()
            total_chunks = len(model_results)
            
            for chunk_id, result in model_results.items():
                text = result.get('transcript', '')
                keywords = self.extract_keywords(text)
                keyword_counts.update(keywords)
            
            stats[model_name] = {
                'total_chunks': total_chunks,
                'unique_keywords': len(keyword_counts),
                'top_keywords': keyword_counts.most_common(10),
                'avg_confidence': sum(
                    r.get('confidence', 0.0) for r in model_results.values()
                ) / total_chunks if total_chunks > 0 else 0.0
            }
        
        return stats


# ============================================================================
# 便利函數
# ============================================================================

def ensemble_from_directory(
    asr_eval_dir: str,
    output_filename: str = "ensemble_results.json"
) -> Dict:
    """
    從 ASR_Evaluation 目錄自動融合結果
    
    Args:
        asr_eval_dir: ASR_Evaluation 目錄路徑
        output_filename: 輸出檔名
    
    Returns:
        融合結果字典
    """
    asr_path = Path(asr_eval_dir)
    
    # 自動尋找各模型的結果 JSON
    gemini_json = None
    google_stt_json = None
    whisper_json = None
    
    for json_file in asr_path.rglob("*.json"):
        if 'gemini' in json_file.name:
            gemini_json = str(json_file)
        elif 'google_stt' in json_file.name or 'chirp' in json_file.name:
            google_stt_json = str(json_file)
        elif 'whisper' in json_file.name:
            whisper_json = str(json_file)
    
    # 初始化引擎
    engine = MultiModelEnsemble()
    
    # 載入結果
    engine.load_model_results(
        gemini_json=gemini_json,
        google_stt_json=google_stt_json,
        whisper_json=whisper_json
    )
    
    # 融合
    output_path = asr_path / output_filename
    results = engine.ensemble_all(str(output_path))
    
    # 輸出比較統計
    stats = engine.compare_models()
    print("\n" + "="*80)
    print("模型比較統計")
    print("="*80)
    for model_name, model_stats in stats.items():
        print(f"\n{model_name}:")
        print(f"  Chunks: {model_stats['total_chunks']}")
        print(f"  關鍵術語種類: {model_stats['unique_keywords']}")
        print(f"  平均信心度: {model_stats['avg_confidence']:.2%}")
        print(f"  Top 5 關鍵術語:")
        for keyword, count in model_stats['top_keywords'][:5]:
            print(f"    - {keyword}: {count} 次")
    
    return results


# ============================================================================
# 主程式
# ============================================================================

def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="多模型融合引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--asr-eval-dir",
        required=True,
        help="ASR_Evaluation 目錄路徑"
    )
    
    parser.add_argument(
        "--output",
        default="ensemble_results.json",
        help="輸出檔名（預設: ensemble_results.json）"
    )
    
    args = parser.parse_args()
    
    # 執行融合
    results = ensemble_from_directory(args.asr_eval_dir, args.output)
    
    print(f"\n✅ 融合完成！共處理 {len(results)} 個 chunks")
    print(f"結果已儲存至: {Path(args.asr_eval_dir) / args.output}")


if __name__ == "__main__":
    main()
