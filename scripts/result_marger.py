"""
結果合併器 (Result Merger)
功能：
1. 合併多模型辨識結果
2. 對齊 ground_truth（標準答案）
3. 生成統一的評測 CSV
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional
import argparse

from utils.logger import get_logger

logger = get_logger(__name__)


class ResultMerger:
    """結果合併器"""
    
    def __init__(self, evaluation_dir: str):
        """
        初始化結果合併器
        
        Args:
            evaluation_dir: ASR_Evaluation 目錄路徑
        """
        self.eval_dir = Path(evaluation_dir)
        
        if not self.eval_dir.exists():
            raise FileNotFoundError(f"評測目錄不存在: {evaluation_dir}")
        
        self.ground_truth_dir = self.eval_dir / "ground_truth"
        self.stt_output_dir = self.eval_dir / "stt_output"
        self.whisper_output_dir = self.eval_dir / "whisper_output"
        self.gemini_output_dir = self.eval_dir / "gemini_output"
        
        logger.info(f"結果合併器初始化完成")
        logger.info(f"  評測目錄: {self.eval_dir}")
    
    def merge_results(self, output_csv: Optional[str] = None) -> Dict:
        """
        合併所有模型的辨識結果
        
        Args:
            output_csv: 輸出 CSV 檔案路徑（預設為 evaluation_dir/asr_results.csv）
        
        Returns:
            合併結果統計
        """
        if output_csv is None:
            output_csv = self.eval_dir / "asr_results.csv"
        else:
            output_csv = Path(output_csv)
        
        logger.info("開始合併辨識結果...")
        
        # 1. 取得所有 chunk_id（從 ground_truth）
        chunk_ids = self._get_chunk_ids()
        
        if not chunk_ids:
            logger.warning("找不到任何 ground_truth 檔案")
            return {}
        
        logger.info(f"找到 {len(chunk_ids)} 個測試樣本")
        
        # 2. 讀取所有模型的結果
        results = []
        
        for chunk_id in sorted(chunk_ids):
            row = {
                'chunk_id': chunk_id,
                'ground_truth': self._read_text_file(self.ground_truth_dir / f"{chunk_id}.txt"),
                'stt_output': self._read_text_file(self.stt_output_dir / f"{chunk_id}.txt"),
                'whisper_output': self._read_text_file(self.whisper_output_dir / f"{chunk_id}.txt"),
                'gemini_output': self._read_text_file(self.gemini_output_dir / f"{chunk_id}.txt")
            }
            results.append(row)
        
        # 3. 寫入 CSV
        logger.info(f"寫入合併結果至: {output_csv}")
        
        with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = ['chunk_id', 'ground_truth', 'stt_output', 'whisper_output', 'gemini_output']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerows(results)
        
        # 4. 統計
        stats = {
            'total_samples': len(results),
            'ground_truth_available': sum(1 for r in results if r['ground_truth']),
            'stt_available': sum(1 for r in results if r['stt_output']),
            'whisper_available': sum(1 for r in results if r['whisper_output']),
            'gemini_available': sum(1 for r in results if r['gemini_output']),
        }
        
        logger.info("=" * 60)
        logger.info("合併完成！統計資訊：")
        logger.info(f"  總樣本數: {stats['total_samples']}")
        logger.info(f"  Ground Truth: {stats['ground_truth_available']}")
        logger.info(f"  Google STT: {stats['stt_available']}")
        logger.info(f"  Whisper: {stats['whisper_available']}")
        logger.info(f"  Gemini: {stats['gemini_available']}")
        logger.info("=" * 60)
        
        return stats
    
    def create_timestamped_results(
        self,
        model_name: str,
        chunks_timeline_file: str
    ) -> Dict:
        """
        建立含完整時間戳的辨識結果
        
        Args:
            model_name: 模型名稱 ("stt", "whisper", "gemini")
            chunks_timeline_file: chunks_timeline.json 路徑
        
        Returns:
            含時間戳的結果字典
        """
        logger.info(f"建立 {model_name} 的時間戳結果...")
        
        # 讀取時間軸
        from utils.timestamp_manager import TimestampManager
        tm = TimestampManager()
        chunks_timeline = tm.load_chunks_timeline(chunks_timeline_file)
        
        # 讀取辨識結果
        model_output_dir = self.eval_dir / f"{model_name}_output"
        results_json_file = model_output_dir / f"{model_name}_results_full.json"
        
        if results_json_file.exists():
            with open(results_json_file, 'r', encoding='utf-8') as f:
                stt_results = json.load(f)
        else:
            # 如果沒有 JSON，從文字檔建立
            logger.info(f"找不到 {results_json_file}，從文字檔建立結果...")
            stt_results = {}
            
            for txt_file in model_output_dir.glob("chunk_*.txt"):
                chunk_id = txt_file.stem
                with open(txt_file, 'r', encoding='utf-8') as f:
                    transcript = f.read().strip()
                
                stt_results[chunk_id] = {
                    'transcript': transcript,
                    'transcript_raw': transcript
                }
        
        # 對齊時間戳
        aligned_results = tm.align_stt_results_with_timeline(
            stt_results=stt_results,
            chunks_timeline=chunks_timeline,
            model_name=model_name
        )
        
        # 儲存
        output_file = self.eval_dir / f"timestamped_{model_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(aligned_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"時間戳結果已儲存: {output_file}")
        
        return aligned_results
    
    def _get_chunk_ids(self) -> List[str]:
        """取得所有 chunk ID"""
        if not self.ground_truth_dir.exists():
            return []
        
        chunk_ids = []
        for txt_file in self.ground_truth_dir.glob("chunk_*.txt"):
            chunk_id = txt_file.stem
            chunk_ids.append(chunk_id)
        
        return chunk_ids
    
    def _read_text_file(self, file_path: Path) -> str:
        """讀取文字檔，如果檔案不存在則回傳空字串"""
        if not file_path.exists():
            return ""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logger.warning(f"讀取檔案失敗 ({file_path}): {e}")
            return ""


def main():
    """命令列介面"""
    parser = argparse.ArgumentParser(description="結果合併器")
    parser.add_argument(
        "evaluation_dir",
        help="ASR_Evaluation 目錄路徑"
    )
    parser.add_argument(
        "--output-csv",
        help="輸出 CSV 檔案路徑（預設為 evaluation_dir/asr_results.csv）"
    )
    parser.add_argument(
        "--create-timestamped",
        action="store_true",
        help="建立含時間戳的結果檔案"
    )
    parser.add_argument(
        "--chunks-timeline",
        help="chunks_timeline.json 路徑（用於建立時間戳結果）"
    )
    
    args = parser.parse_args()
    
    # 建立合併器
    merger = ResultMerger(args.evaluation_dir)
    
    # 合併結果
    stats = merger.merge_results(output_csv=args.output_csv)
    
    # 建立時間戳結果（如果需要）
    if args.create_timestamped and args.chunks_timeline:
        logger.info("\n建立時間戳結果...")
        
        for model_name in ['stt', 'whisper', 'gemini']:
            try:
                merger.create_timestamped_results(
                    model_name=model_name,
                    chunks_timeline_file=args.chunks_timeline
                )
            except Exception as e:
                logger.warning(f"建立 {model_name} 時間戳結果失敗: {e}")
    
    print("\n合併完成！")


if __name__ == "__main__":
    main()