#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text V2 模型包裝器 - 修正 PhraseSet 版本
修正: Parameter to MergeFrom() must be instance of same class 錯誤
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

# 修正 import 路徑
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

# ============================================================================
# 內建認證設定（在 import Google Client 之前）
# ============================================================================
def setup_credentials():
    """自動設定 Google Cloud 認證"""
    default_key_path = Path(__file__).parent.parent.parent / "utils" / "google-speech-key.json"
    
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        if default_key_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(default_key_path)

# 設定認證
setup_credentials()

from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

try:
    from utils.logger import get_logger
    from aiSpeech.utils.google_stt_config_manager_odd import GoogleSTTConfigManager
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from utils.logger import get_logger
    from aiSpeech.utils.google_stt_config_manager_odd import GoogleSTTConfigManager


class GoogleSTTModel:
    """Google Cloud Speech-to-Text V2 API 包裝器（修正 PhraseSet 版）"""
    
    def __init__(
        self,
        project_id: str = None,
        location: str = None,
        model: str = "chirp_3",
        language_code: str = "cmn-Hant-TW",
        auto_config: bool = True
    ):
        """初始化 Google STT 模型"""
        self.logger = get_logger(self.__class__.__name__)
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406')
        self.language_code = language_code
        
        # 確保認證已設定
        setup_credentials()
        
        # 初始化配置管理器
        if auto_config:
            self.config_manager = GoogleSTTConfigManager(self.project_id)
            self.model, self.location = self.config_manager.get_optimal_config(
                model=model or "chirp",
                preferred_region=location
            )
            self.logger.info("✅ 使用動態配置管理")
        else:
            self.model = model or "chirp_3"
            self.location = location or "us"
            self.config_manager = None
            self.logger.warning("⚠️  手動配置模式（不建議）")
        
        # 建立客戶端
        try:
            self.client = SpeechClient()
            self.logger.info(f"✅ Google STT 初始化成功")
            self.logger.info(f"   專案: {self.project_id}")
            self.logger.info(f"   區域: {self.location}")
            self.logger.info(f"   模型: {self.model}")
            self.logger.info(f"   語言: {self.language_code}")
        except Exception as e:
            self.logger.error(f"❌ Google STT 初始化失敗: {e}")
            raise
    
    def transcribe_file(
        self,
        audio_file: str,
        phrases: List[Dict] = None,
        enable_word_time_offsets: bool = False
    ) -> Dict:
        """
        辨識音檔（修正版 - 使用 inline phrase hints）
        
        Args:
            audio_file: 音檔路徑
            phrases: 詞彙表列表 [{"value": "詞彙", "boost": 10}, ...]
            enable_word_time_offsets: 是否啟用字詞時間戳
        
        Returns:
            辨識結果字典
        """
        try:
            # 讀取音檔
            with open(audio_file, 'rb') as f:
                audio_content = f.read()
            
            # 建立辨識器路徑
            recognizer_path = (
                f"projects/{self.project_id}/locations/{self.location}/"
                f"recognizers/{self.model}"
            )
            
            # ====================================================================
            # 修正：使用 inline phrase_hints 而不是 adaptation
            # ====================================================================
            config = cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                language_codes=[self.language_code],
                model=self.model,
                features=cloud_speech.RecognitionFeatures(
                    enable_word_time_offsets=enable_word_time_offsets,
                    enable_automatic_punctuation=True
                )
            )
            
            # 如果有詞彙表，使用 inline phrase_hints（正確方式）
            if phrases and len(phrases) > 0:
                phrase_hints = []
                for phrase_dict in phrases:
                    if isinstance(phrase_dict, dict) and 'value' in phrase_dict:
                        phrase_hints.append(phrase_dict['value'])
                
                if phrase_hints:
                    # 限制數量（API 限制通常是 500）
                    phrase_hints = phrase_hints[:500]
                    
                    # 使用 inline adaptation（正確的 V2 API 方式）
                    config.adaptation = cloud_speech.SpeechAdaptation(
                        phrase_sets=[
                            cloud_speech.SpeechAdaptation.AdaptationPhraseSet(
                                inline_phrase_set=cloud_speech.PhraseSet(
                                    phrases=[
                                        cloud_speech.PhraseSet.Phrase(value=hint, boost=10)
                                        for hint in phrase_hints
                                    ]
                                )
                            )
                        ]
                    )
                    self.logger.debug(f"✅ 載入 {len(phrase_hints)} 個詞彙提示")
            
            # 建立請求
            request = cloud_speech.RecognizeRequest(
                recognizer=recognizer_path,
                config=config,
                content=audio_content
            )
            
            # 執行辨識
            response = self.client.recognize(request=request)
            
            # 處理結果
            if not response.results:
                self.logger.warning(f"辨識結果為空: {audio_file}")
                return {
                    'transcript': '',
                    'transcript_raw': '',
                    'confidence': 0.0
                }
            
            # 提取文字
            transcript = ''
            confidence_sum = 0.0
            word_count = 0
            
            for result in response.results:
                if result.alternatives:
                    alternative = result.alternatives[0]
                    transcript += alternative.transcript
                    confidence_sum += alternative.confidence
                    word_count += 1
            
            avg_confidence = confidence_sum / word_count if word_count > 0 else 0.0
            
            self.logger.debug(f"✅ 辨識成功: {Path(audio_file).name} (信心度: {avg_confidence:.2%})")
            
            return {
                'transcript': transcript,
                'transcript_raw': transcript,
                'confidence': avg_confidence,
                'results': response.results
            }
        
        except Exception as e:
            self.logger.error(f"❌ 辨識失敗 ({Path(audio_file).name}): {e}")
            
            # 如果啟用了自動配置，嘗試回退到備選區域
            if self.config_manager and "does not exist in the location" in str(e):
                return self._try_fallback_regions(audio_file, phrases, enable_word_time_offsets, e)
            
            raise
    
    def _try_fallback_regions(self, audio_file, phrases, enable_word_time_offsets, original_error):
        """嘗試使用回退區域"""
        self.logger.warning(f"⚠️  當前區域 '{self.location}' 失敗，嘗試回退區域...")
        
        model_config = self.config_manager.config['models'].get(self.model, {})
        fallback_regions = model_config.get('fallback_regions', [])
        
        for fallback_region in fallback_regions:
            if fallback_region == self.location:
                continue
            
            try:
                self.logger.info(f"嘗試回退區域: {fallback_region}")
                
                # 臨時切換區域
                original_location = self.location
                self.location = fallback_region
                
                # 重新嘗試辨識
                result = self.transcribe_file(audio_file, phrases, enable_word_time_offsets)
                
                self.logger.info(f"✅ 回退成功！使用區域: {fallback_region}")
                
                # 更新配置檔案
                if self.config_manager:
                    self.config_manager.config['models'][self.model]['preferred_region'] = fallback_region
                    self.config_manager._save_config()
                
                return result
            
            except Exception as e:
                self.logger.warning(f"回退區域 {fallback_region} 也失敗: {e}")
                self.location = original_location
                continue
        
        # 所有回退都失敗，拋出原始錯誤
        self.logger.error("❌ 所有回退區域都失敗")
        raise original_error
    
    def get_current_config(self) -> Dict:
        """獲取當前配置資訊"""
        return {
            'project_id': self.project_id,
            'location': self.location,
            'model': self.model,
            'language_code': self.language_code,
            'auto_config_enabled': self.config_manager is not None,
            'credentials_set': bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
        }
    
    def print_config_info(self):
        """列印配置資訊"""
        config = self.get_current_config()
        print("\n當前 Google STT 配置:")
        print(f"  專案ID: {config['project_id']}")
        print(f"  區域: {config['location']}")
        print(f"  模型: {config['model']}")
        print(f"  語言: {config['language_code']}")
        print(f"  動態配置: {'✅ 啟用' if config['auto_config_enabled'] else '❌ 停用'}")
        print(f"  認證設定: {'✅ 已設定' if config['credentials_set'] else '❌ 未設定'}")
        
        if config['credentials_set']:
            print(f"  金鑰路徑: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        
        if self.config_manager:
            model_info = self.config_manager.config['models'].get(self.model, {})
            print(f"\n模型資訊:")
            print(f"  名稱: {model_info.get('display_name', 'N/A')}")
            print(f"  狀態: {model_info.get('status', 'unknown')}")
            print(f"  支援區域: {', '.join(model_info.get('supported_regions', []))}")
            print(f"  說明: {model_info.get('description', 'N/A')}")


def test_dynamic_config():
    """測試動態配置"""
    print("\n測試 Google STT 動態配置（修正 PhraseSet 版本）")
    print("=" * 80)
    
    test_cases = [
        {"model": "chirp", "location": "global"},
        {"model": "chirp_3", "location": "us"},
        {"model": "latest_long", "location": None},
        {"model": "unknown", "location": "asia"},
    ]
    
    for i, config in enumerate(test_cases, 1):
        print(f"\n測試 {i}: {config}")
        try:
            model = GoogleSTTModel(**config)
            model.print_config_info()
            print("✅ 初始化成功")
        except Exception as e:
            print(f"❌ 初始化失敗: {e}")
        print("-" * 80)


if __name__ == "__main__":
    test_dynamic_config()