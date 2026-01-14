"""
批次推論引擎 (Batch Inference Engine) - 完全相容版
功能：
1. ✅ 自動設定 Google Cloud 認證（新增）
2. ✅ 呼叫 AI 模型模組（Google STT / Whisper / Gemini）
3. ✅ 支援多模型同時執行比較
4. ✅ 自動載入詞彙表（google_phrases.json）
5. ✅ 後處理修正（text_cleaner.fix_radio_jargon）
6. ✅ 支援 --test-case 自動路徑生成（新增）
7. ✅ 支援 --input-dir / --output-dir 手動指定（保留）
8. ✅ Whisper 雙模式支援（新版/舊版）
9. ✅ Gemini 詞彙表上下文（保留）
"""

import os
import sys
import json
import argparse
from pathlib import Path
from tqdm import tqdm

# ============================================================================
# 內建認證設定（在 import 任何模型之前）
# ============================================================================
def setup_google_credentials():
    """自動設定 Google Cloud 認證"""
    default_key_path = Path(__file__).parent.parent / "utils" / "google-speech-key.json"
    
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        if default_key_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(default_key_path)
            # 靜默設定（避免重複輸出）

# 在 import 之前設定認證
setup_google_credentials()

# 設定路徑：將上層目錄加入 path 才能 import utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.logger import get_logger
from utils.text_cleaner import fix_radio_jargon

logger = get_logger(__name__)


class BatchInference:
    """批次推論引擎（完全相容版）"""
    
    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        model_type: str = "whisper",
        vocabulary_file: str = None
    ):
        """
        初始化批次推論引擎
        
        Args:
            input_dir: 輸入音檔目錄
            output_dir: 輸出結果目錄
            model_type: 模型類型 (whisper, google_stt, gemini)
            vocabulary_file: 詞彙表檔案（google_phrases.json）
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_type = model_type.lower()
        self.vocabulary_file = vocabulary_file
        
        # 建立輸出目錄
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 支援的檔案格式
        self.supported_ext = ('.wav', '.mp3', '.m4a')
        
        # 載入詞彙表
        self.phrases = self._load_vocabulary() if vocabulary_file else None
        
        # 初始化模型
        self.model = self._init_model()
        
        logger.info(f"批次推論引擎初始化完成")
        logger.info(f"  模型類型: {model_type}")
        logger.info(f"  輸入目錄: {self.input_dir}")
        logger.info(f"  輸出目錄: {self.output_dir}")
        if self.phrases:
            logger.info(f"  詞彙表: {len(self.phrases['phrases'])} 個詞彙")
    
    def _load_vocabulary(self):
        """載入詞彙表"""
        if not self.vocabulary_file or not Path(self.vocabulary_file).exists():
            logger.warning(f"找不到詞彙表檔案: {self.vocabulary_file}")
            return None
        
        try:
            with open(self.vocabulary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"載入詞彙表: {data.get('total_terms', 0)} 個詞彙")
            return data
        except Exception as e:
            logger.error(f"載入詞彙表失敗: {e}")
            return None
    
    def _init_model(self):
        """初始化模型"""
        if self.model_type == "whisper":
            return self._init_whisper()
        elif self.model_type == "google_stt":
            return self._init_google_stt()
        elif self.model_type == "gemini":
            return self._init_gemini()
        else:
            raise ValueError(f"不支援的模型類型: {self.model_type}")
    
    def _init_whisper(self):
        """初始化 Whisper 模型（保留雙模式支援）"""
        try:
            # 嘗試使用新版 model_whisper.py
            from scripts.models.model_whisper import WhisperModel
            logger.info("使用新版 Whisper 模組")
            return WhisperModel(model_size="large-v3")
        except ImportError:
            # 回退到舊版
            logger.warning("找不到新版 Whisper 模組，使用舊版")
            try:
                from scripts.model_whisper_old import transcribe_with_whisper
                return {"transcribe": transcribe_with_whisper}
            except ImportError:
                # 再回退到新版的函數式介面
                from scripts.models.model_whisper import transcribe_with_whisper
                return {"transcribe": transcribe_with_whisper}
    
    def _init_google_stt(self):
        """初始化 Google STT 模型（內建認證版）"""
        # 確保認證已設定
        setup_google_credentials()
        
        from aiSpeech.scripts.models.model_google_stt_odd2 import GoogleSTTModel
        
        # 從環境變數讀取設定（動態配置會自動修正）
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406')
        location = os.getenv('GOOGLE_STT_LOCATION', 'us')      # 預設 us（不用 global）
        model = os.getenv('GOOGLE_STT_MODEL', 'chirp_3')        # 預設 chirp（不用 chirp_3）
        
        logger.info(f"初始化 Google STT: {project_id} / {location} / {model}")
        
        return GoogleSTTModel(
            project_id=project_id,
            location=location,
            model=model,
            language_code="cmn-Hant-TW"
        )
    
    def _init_gemini(self):
        """初始化 Gemini 模型"""
        from scripts.models.model_gemini import GeminiModel
        
        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')
        
        logger.info(f"初始化 Gemini: {model_name}")
        
        return GeminiModel(
            model=model_name,
            temperature=0.0
        )
    
    def transcribe_file(self, audio_file: Path):
        """
        辨識單一音檔（保留原版邏輯）
        
        Args:
            audio_file: 音檔路徑
        
        Returns:
            辨識結果字典
        """
        if self.model_type == "whisper":
            # Whisper（支援兩種介面）
            if hasattr(self.model, 'transcribe_file'):
                # 新版模組（物件導向）
                result = self.model.transcribe_file(str(audio_file))
            else:
                # 舊版模組（函數式）
                raw_text = self.model["transcribe"](str(audio_file), model_size="large-v3")
                result = {
                    'transcript': raw_text,
                    'transcript_raw': raw_text
                }
        
        elif self.model_type == "google_stt":
            # Google STT
            phrases_list = self.phrases['phrases'] if self.phrases else None
            result = self.model.transcribe_file(
                str(audio_file),
                phrases=phrases_list
            )
        
        elif self.model_type == "gemini":
            # Gemini（保留詞彙表上下文）
            context = "這是台灣捷運無線電通訊錄音。"
            if self.phrases:
                # 將詞彙表轉為上下文
                top_terms = [p['value'] for p in self.phrases['phrases'][:30]]
                context += f"\n常見術語: {', '.join(top_terms)}"
            
            result = self.model.transcribe_file(
                str(audio_file),
                context=context
            )
        
        return result
    
    def run(self):
        """執行批次推論（保留原版邏輯）"""
        # 掃描輸入檔案
        audio_files = []
        for ext in self.supported_ext:
            audio_files.extend(self.input_dir.glob(f"*{ext}"))
        
        audio_files = sorted(audio_files)
        
        if not audio_files:
            logger.warning(f"找不到任何音檔在: {self.input_dir}")
            return {}
        
        logger.info(f"找到 {len(audio_files)} 個音檔，開始處理...")
        
        results = {}
        
        # 處理每個檔案
        for audio_file in tqdm(audio_files, desc=f"處理 {self.model_type}"):
            chunk_id = audio_file.stem
            
            try:
                # A. 辨識
                result = self.transcribe_file(audio_file)
                
                # B. 後處理修正
                if 'transcript' in result:
                    result['transcript'] = fix_radio_jargon(result['transcript'])
                
                # C. 儲存文字檔
                txt_file = self.output_dir / f"{chunk_id}.txt"
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(result.get('transcript', ''))
                
                # D. 記錄結果
                results[chunk_id] = result
                
            except Exception as e:
                logger.error(f"處理失敗 ({audio_file.name}): {e}")
                results[chunk_id] = {
                    'transcript': '',
                    'transcript_raw': '',
                    'error': str(e)
                }
        
        # 儲存完整結果 JSON
        json_file = self.output_dir / f"{self.model_type}_results_full.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"批次推論完成")
        logger.info(f"  成功: {sum(1 for r in results.values() if 'error' not in r)}/{len(results)}")
        logger.info(f"  結果已儲存: {self.output_dir}")
        
        return results


def main():
    """命令列介面（完全相容版）"""
    parser = argparse.ArgumentParser(description="批次推論引擎")
    parser.add_argument(
        "--model",
        choices=["whisper", "google_stt", "gemini"],
        default="google_stt",
        help="模型類型"
    )
    parser.add_argument(
        "--stt-model", 
        default="chirp_3", 
        help="指定 STT 模型 (chirp_3, radio, chirp_telephony)"    
    )
    parser.add_argument(
        "--input-dir",
        help="輸入音檔目錄（可選，與 --test-case 二擇一）"
    )
    parser.add_argument(
        "--output-dir",
        help="輸出結果目錄（可選，與 --test-case 二擇一）"
    )
    parser.add_argument(
        "--vocabulary",
        help="詞彙表檔案 (google_phrases.json)"
    )
    parser.add_argument(
        "--test-case",
        help="測試案名稱（用於自動設定路徑，如 Test_02_TMRT）"
    )
    
    args = parser.parse_args()
    
    # ========================================================================
    # 路徑決定邏輯（支援兩種模式）
    # ========================================================================
    
    if args.test_case:
        # 模式 1: 使用 --test-case 自動生成路徑
        project_root = Path(__file__).parent.parent
        input_dir = project_root / "experiments" / args.test_case / "source_audio"
        output_dir = project_root / "experiments" / args.test_case / "ASR_Evaluation" / f"{args.model}_output"
        
        logger.info(f"使用測試案例模式: {args.test_case}")
        logger.info(f"  自動生成輸入路徑: {input_dir}")
        logger.info(f"  自動生成輸出路徑: {output_dir}")
        
    elif args.input_dir and args.output_dir:
        # 模式 2: 手動指定路徑
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        
        logger.info(f"使用手動路徑模式")
        
    else:
        # 錯誤：兩種模式都沒有提供
        print("❌ 錯誤: 請提供以下其中一組參數：")
        print("  模式 1: --test-case TEST_NAME")
        print("  模式 2: --input-dir INPUT_PATH --output-dir OUTPUT_PATH")
        print("\n範例:")
        print("  python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt")
        print("  python scripts/batch_inference.py --input-dir data/audio --output-dir results --model whisper")
        return
    
    # 如果沒有指定詞彙表，嘗試使用預設位置
    if not args.vocabulary:
        default_vocab = Path(__file__).parent.parent / "vocabulary" / "google_phrases.json"
        if default_vocab.exists():
            args.vocabulary = str(default_vocab)
            logger.info(f"使用預設詞彙表: {args.vocabulary}")
    
    # 建立推論引擎
    engine = BatchInference(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        model_type=args.model,
        vocabulary_file=args.vocabulary
    )
    
    # 執行推論
    results = engine.run()
    
    print(f"\n✨ 處理完成！共 {len(results)} 個檔案")


if __name__ == "__main__":
    main()