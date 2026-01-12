#!/usr/bin/env python3
"""
批次推論引擎 (Batch Inference Engine)
版本: 2.0 (2025年1月修正版)

功能:
1. ✅ 支援 Google STT V2 API (Chirp 3/Telephony/2)
2. ✅ 支援 Whisper (large-v3, turbo, medium)
3. ✅ 支援 Gemini (2.0-flash-exp)
4. ✅ 自動載入詞彙表 (google_phrases.json)
5. ✅ 後處理修正 (text_cleaner.fix_radio_jargon)
6. ✅ 支援 --test-case 自動路徑生成
7. ✅ 支援 --stt-model 指定 STT 子模型

使用範例:
    # 使用 Chirp 3
    python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt --stt-model chirp_3
    
    # 使用電話/無線電專用模型
    python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt --stt-model chirp_telephony
    
    # 使用 Whisper
    python scripts/batch_inference.py --test-case Test_02_TMRT --model whisper
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# ============================================================================
# 設定路徑
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# 內建認證設定
# ============================================================================
def setup_google_credentials():
    """自動設定 Google Cloud 認證"""
    possible_paths = [
        PROJECT_ROOT / "utils" / "google-speech-key.json",
        PROJECT_ROOT / "config" / "google-speech-key.json",
    ]
    
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        for key_path in possible_paths:
            if key_path.exists():
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_path)
                return True
    return bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))


# 在 import 之前設定認證
setup_google_credentials()


# ============================================================================
# 導入模組
# ============================================================================
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("⚠️  tqdm 不可用，將使用簡單進度顯示")

try:
    from utils.logger import get_logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    def get_logger(name):
        return logging.getLogger(name)

try:
    from utils.text_cleaner import fix_radio_jargon
except ImportError:
    def fix_radio_jargon(text):
        """Fallback: 不做任何處理"""
        return text


logger = get_logger(__name__)


class BatchInference:
    """
    批次推論引擎
    
    支援的模型:
    - whisper: OpenAI Whisper (large-v3, turbo, medium)
    - google_stt: Google Cloud Speech-to-Text V2 (chirp_3, chirp_telephony, chirp_2)
    - gemini: Google Gemini (2.0-flash-exp)
    """
    
    # 支援的音檔格式
    SUPPORTED_EXTENSIONS = ('.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac')
    
    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        model_type: str = "google_stt",
        vocabulary_file: str = None,
        stt_model: str = "chirp_3",
        stt_region: str = None,
        language_code: str = "cmn-Hant-TW"
    ):
        """
        初始化批次推論引擎
        
        Args:
            input_dir: 輸入音檔目錄
            output_dir: 輸出結果目錄
            model_type: 模型類型 (whisper, google_stt, gemini)
            vocabulary_file: 詞彙表檔案路徑
            stt_model: Google STT 子模型 (chirp_3, chirp_telephony, chirp_2)
            stt_region: Google STT 區域 (us, eu, us-central1)
            language_code: 語言代碼
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model_type = model_type.lower()
        self.vocabulary_file = vocabulary_file
        self.stt_model = stt_model
        self.stt_region = stt_region
        self.language_code = language_code
        
        # 建立輸出目錄
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 載入詞彙表
        self.phrases = self._load_vocabulary() if vocabulary_file else None
        
        # 初始化模型
        self.model = self._init_model()
        
        # 記錄配置
        logger.info("=" * 60)
        logger.info("批次推論引擎初始化完成")
        logger.info("=" * 60)
        logger.info(f"模型類型: {model_type}")
        if model_type == "google_stt":
            logger.info(f"STT 模型: {stt_model}")
            logger.info(f"STT 區域: {stt_region or '自動'}")
        logger.info(f"輸入目錄: {self.input_dir}")
        logger.info(f"輸出目錄: {self.output_dir}")
        if self.phrases:
            logger.info(f"詞彙表: {self.phrases.get('total_terms', len(self.phrases.get('phrases', [])))} 個詞彙")
        logger.info("=" * 60)
    
    def _load_vocabulary(self) -> dict:
        """載入詞彙表"""
        if not self.vocabulary_file:
            return None
        
        vocab_path = Path(self.vocabulary_file)
        if not vocab_path.exists():
            logger.warning(f"找不到詞彙表檔案: {self.vocabulary_file}")
            return None
        
        try:
            with open(vocab_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total = data.get('total_terms', len(data.get('phrases', [])))
            logger.info(f"✅ 載入詞彙表: {total} 個詞彙")
            return data
        
        except Exception as e:
            logger.error(f"❌ 載入詞彙表失敗: {e}")
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
        """初始化 Whisper 模型"""
        try:
            # 嘗試使用新版模組
            from scripts.models.model_whisper import WhisperModel
            logger.info("使用新版 Whisper 模組")
            return WhisperModel(model_size="large-v3")
        except ImportError:
            try:
                # 嘗試直接使用 whisper
                import whisper
                logger.info("使用原生 whisper 模組")
                model = whisper.load_model("large-v3")
                return {"model": model, "type": "native"}
            except ImportError:
                raise ImportError("找不到 Whisper 模組，請安裝: pip install openai-whisper")
    
    def _init_google_stt(self):
        """初始化 Google STT 模型"""
        # 確保認證已設定
        if not setup_google_credentials():
            logger.warning("⚠️  未設定 Google Cloud 認證")
        
        try:
            # 嘗試使用新版模組
            from scripts.models.model_google_stt import GoogleSTTModel
            
            logger.info(f"初始化 Google STT: {self.stt_model}")
            
            return GoogleSTTModel(
                project_id=os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406'),
                location=self.stt_region,
                model=self.stt_model,
                language_code=self.language_code,
                auto_config=True
            )
        
        except ImportError as e:
            logger.error(f"找不到 Google STT 模組: {e}")
            raise
    
    def _init_gemini(self):
        """初始化 Gemini 模型"""
        try:
            from scripts.models.model_gemini import GeminiModel
            
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')
            logger.info(f"初始化 Gemini: {model_name}")
            
            return GeminiModel(
                model=model_name,
                temperature=0.0
            )
        
        except ImportError as e:
            logger.error(f"找不到 Gemini 模組: {e}")
            raise
    
    def transcribe_file(self, audio_file: Path) -> dict:
        """
        辨識單一音檔
        
        Args:
            audio_file: 音檔路徑
        
        Returns:
            辨識結果字典
        """
        if self.model_type == "whisper":
            return self._transcribe_whisper(audio_file)
        elif self.model_type == "google_stt":
            return self._transcribe_google_stt(audio_file)
        elif self.model_type == "gemini":
            return self._transcribe_gemini(audio_file)
        else:
            raise ValueError(f"不支援的模型類型: {self.model_type}")
    
    def _transcribe_whisper(self, audio_file: Path) -> dict:
        """使用 Whisper 辨識"""
        if hasattr(self.model, 'transcribe_file'):
            # 新版模組
            result = self.model.transcribe_file(str(audio_file))
        elif isinstance(self.model, dict) and self.model.get('type') == 'native':
            # 原生 whisper
            raw_result = self.model['model'].transcribe(
                str(audio_file),
                language="zh",
                initial_prompt="這是台灣捷運無線電通訊錄音。"
            )
            result = {
                'transcript': raw_result.get('text', ''),
                'transcript_raw': raw_result.get('text', '')
            }
        else:
            raise RuntimeError("Whisper 模型初始化異常")
        
        return result
    
    def _transcribe_google_stt(self, audio_file: Path) -> dict:
        """使用 Google STT 辨識"""
        phrases_list = None
        if self.phrases:
            phrases_list = self.phrases.get('phrases', [])
        
        return self.model.transcribe_file(
            str(audio_file),
            phrases=phrases_list,
            enable_word_time_offsets=True,         # 講者識別通常需要時間戳
            enable_automatic_punctuation=True,     # 啟用自動斷句
            enable_speaker_diarization=True,       # 新增：啟用講者識別
            min_speaker_count=1,                   # 新增：最少講者
            max_speaker_count=3                    # 新增：最多講者

        )
    
    def _transcribe_gemini(self, audio_file: Path) -> dict:
        """使用 Gemini 辨識"""
        context = "這是台灣捷運無線電通訊錄音。"
        
        if self.phrases:
            top_terms = [p.get('value', p) if isinstance(p, dict) else p 
                        for p in self.phrases.get('phrases', [])[:30]]
            if top_terms:
                context += f"\n常見術語: {', '.join(top_terms)}"
        
        return self.model.transcribe_file(
            str(audio_file),
            context=context
        )
    
    def run(self) -> dict:
        """
        執行批次推論
        
        Returns:
            所有檔案的辨識結果
        """
        # 掃描音檔
        audio_files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            audio_files.extend(self.input_dir.glob(f"*{ext}"))
            audio_files.extend(self.input_dir.glob(f"*{ext.upper()}"))
        
        audio_files = sorted(set(audio_files))
        
        if not audio_files:
            logger.warning(f"❌ 找不到任何音檔在: {self.input_dir}")
            return {}
        
        logger.info(f"找到 {len(audio_files)} 個音檔，開始處理...")
        
        results = {}
        success_count = 0
        error_count = 0
        
        # 建立進度迭代器
        if TQDM_AVAILABLE:
            iterator = tqdm(audio_files, desc=f"處理 {self.model_type}")
        else:
            iterator = audio_files
        
        # 處理每個檔案
        for audio_file in iterator:
            chunk_id = audio_file.stem
            
            if not TQDM_AVAILABLE:
                logger.info(f"處理: {audio_file.name}")
            
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
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ 處理失敗 ({audio_file.name}): {e}")
                results[chunk_id] = {
                    'transcript': '',
                    'transcript_raw': '',
                    'error': str(e)
                }
                error_count += 1
        
        # 儲存完整結果 JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = self.output_dir / f"{self.model_type}_results_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'model_type': self.model_type,
                    'stt_model': self.stt_model if self.model_type == 'google_stt' else None,
                    'timestamp': timestamp,
                    'total_files': len(results),
                    'success_count': success_count,
                    'error_count': error_count
                },
                'results': results
            }, f, ensure_ascii=False, indent=2)
        
        # 輸出摘要
        logger.info("=" * 60)
        logger.info("批次推論完成")
        logger.info("=" * 60)
        logger.info(f"成功: {success_count}/{len(results)}")
        logger.info(f"失敗: {error_count}/{len(results)}")
        logger.info(f"結果已儲存: {self.output_dir}")
        logger.info(f"詳細 JSON: {json_file}")
        logger.info("=" * 60)
        
        return results


def main():
    """命令列介面"""
    parser = argparse.ArgumentParser(
        description="批次推論引擎 - 支援 Whisper / Google STT / Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 使用 Chirp 3 (推薦)
  python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt --stt-model chirp_3

  # 使用電話/無線電專用模型
  python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt --stt-model chirp_telephony

  # 使用 Whisper
  python scripts/batch_inference.py --test-case Test_02_TMRT --model whisper

  # 手動指定路徑
  python scripts/batch_inference.py --input-dir audio/ --output-dir results/ --model google_stt
        """
    )
    
    # 模型選擇
    parser.add_argument(
        "--model",
        choices=["whisper", "google_stt", "gemini"],
        default="google_stt",
        help="主要模型類型"
    )
    
    # Google STT 專用參數
    parser.add_argument(
        "--stt-model",
        choices=["chirp_3", "chirp_telephony", "chirp_2", "chirp", "latest_long", "latest_short"],
        default="chirp_3",
        help="Google STT 子模型 (預設: chirp_3)"
    )
    
    parser.add_argument(
        "--stt-region",
        choices=["us", "eu", "us-central1", "asia-southeast1", "europe-west4"],
        default=None,
        help="Google STT 區域 (預設: 自動選擇)"
    )
    
    # 路徑設定
    parser.add_argument(
        "--test-case",
        help="測試案名稱 (用於自動設定路徑，如 Test_02_TMRT)"
    )
    
    parser.add_argument(
        "--input-dir",
        help="輸入音檔目錄 (與 --test-case 二擇一)"
    )
    
    parser.add_argument(
        "--output-dir",
        help="輸出結果目錄 (與 --test-case 二擇一)"
    )
    
    # 其他參數
    parser.add_argument(
        "--vocabulary",
        help="詞彙表檔案 (google_phrases.json)"
    )
    
    parser.add_argument(
        "--language",
        default="cmn-Hant-TW",
        help="語言代碼 (預設: cmn-Hant-TW 繁體中文)"
    )
    
    args = parser.parse_args()
    
    # ========================================================================
    # 路徑決定邏輯
    # ========================================================================
    if args.test_case:
        # 模式 1: 使用 --test-case 自動生成路徑
        input_dir = PROJECT_ROOT / "experiments" / args.test_case / "source_audio"
        output_dir = PROJECT_ROOT / "experiments" / args.test_case / "ASR_Evaluation" / f"{args.model}_output"
        
        logger.info(f"使用測試案例模式: {args.test_case}")
        
    elif args.input_dir and args.output_dir:
        # 模式 2: 手動指定路徑
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        
        logger.info("使用手動路徑模式")
        
    else:
        print("❌ 錯誤: 請提供以下其中一組參數：")
        print("  模式 1: --test-case TEST_NAME")
        print("  模式 2: --input-dir INPUT_PATH --output-dir OUTPUT_PATH")
        print("\n執行 --help 查看完整說明")
        return
    
    # 檢查輸入目錄
    if not input_dir.exists():
        print(f"❌ 錯誤: 輸入目錄不存在: {input_dir}")
        return
    
    # 自動尋找詞彙表
    if not args.vocabulary:
        possible_vocab_paths = [
            PROJECT_ROOT / "vocabulary" / "google_phrases.json",
            PROJECT_ROOT / "config" / "google_phrases.json",
        ]
        for vocab_path in possible_vocab_paths:
            if vocab_path.exists():
                args.vocabulary = str(vocab_path)
                logger.info(f"自動載入詞彙表: {vocab_path}")
                break
    
    # ========================================================================
    # 建立並執行推論引擎
    # ========================================================================
    engine = BatchInference(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        model_type=args.model,
        vocabulary_file=args.vocabulary,
        stt_model=args.stt_model,
        stt_region=args.stt_region,
        language_code=args.language
    )
    
    results = engine.run()
    
    print(f"\n✨ 處理完成！共 {len(results)} 個檔案")


if __name__ == "__main__":
    main()
