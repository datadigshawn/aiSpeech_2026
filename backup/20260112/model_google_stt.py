#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text V2 模型包裝器 - 修復版
解決 Chirp 模型區域和命名問題
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

from utils.logger import get_logger


class GoogleSTTModel:
    """Google Cloud Speech-to-Text V2 API 包裝器"""
    
    # 支援的模型列表（V2 API）
    SUPPORTED_MODELS = {
        'chirp': 'chirp',                    # 最新的通用模型
        'chirp_2': 'chirp_2',                # Chirp 2.0
        'latest_long': 'latest_long',        # 長音訊模型
        'latest_short': 'latest_short',      # 短音訊模型
        'long': 'long',                      # 傳統長音訊
        'short': 'short'                     # 傳統短音訊
    }
    
    # 區域對應表
    REGION_MAPPING = {
        'global': 'us',           # global 不支援 Chirp，改用 us
        'asia-east1': 'asia',     # 台灣
        'us-central1': 'us',      # 美國中部
        'europe-west1': 'eu'      # 歐洲
    }
    
    def __init__(
        self,
        project_id: str = None,
        location: str = 'us',     # ⚠️ 改為 'us' 而非 'global'
        model: str = 'chirp',     # ⚠️ 使用 'chirp' 而非 'chirp_3'
        language_code: str = 'cmn-Hant-TW'
    ):
        """
        初始化 Google STT 模型
        
        Args:
            project_id: Google Cloud 專案 ID
            location: 區域 ('us', 'eu', 'asia')
            model: 模型名稱 ('chirp', 'chirp_2', 'latest_long', 'latest_short')
            language_code: 語言代碼
        """
        self.logger = get_logger(self.__class__.__name__)
        
        # 專案設定
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406')
        
        # 區域修正：如果是 'global' 自動改為 'us'
        if location == 'global':
            self.logger.warning(f"'global' 區域不支援 Chirp 模型，自動改為 'us'")
            location = 'us'
        
        self.location = self._validate_location(location)
        
        # 模型驗證
        self.model = self._validate_model(model)
        self.language_code = language_code
        
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
    
    def _validate_location(self, location: str) -> str:
        """驗證並修正區域設定"""
        # 如果是舊式區域名稱，轉換為新式
        if location in self.REGION_MAPPING:
            new_location = self.REGION_MAPPING[location]
            if new_location != location:
                self.logger.info(f"區域轉換: {location} -> {new_location}")
            return new_location
        
        # 驗證是否為有效區域
        valid_locations = ['us', 'eu', 'asia']
        if location not in valid_locations:
            self.logger.warning(f"未知區域 '{location}'，使用預設 'us'")
            return 'us'
        
        return location
    
    def _validate_model(self, model: str) -> str:
        """驗證模型名稱"""
        # 處理舊版模型名稱（如 chirp_3）
        if model == 'chirp_3':
            self.logger.info(f"模型名稱轉換: chirp_3 -> chirp")
            return 'chirp'
        
        if model not in self.SUPPORTED_MODELS:
            self.logger.warning(f"未知模型 '{model}'，使用預設 'chirp'")
            return 'chirp'
        
        return model
    
    def transcribe_file(
        self,
        audio_file: str,
        phrases: List[Dict] = None,
        enable_word_time_offsets: bool = False
    ) -> Dict:
        """
        辨識音檔
        
        Args:
            audio_file: 音檔路徑
            phrases: 詞彙表 (PhraseSet)
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
            
            # 配置辨識參數
            config = cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                language_codes=[self.language_code],
                model=self.model,
                features=cloud_speech.RecognitionFeatures(
                    enable_word_time_offsets=enable_word_time_offsets,
                    enable_automatic_punctuation=True
                )
            )
            
            # 添加詞彙提示
            if phrases:
                phrase_set = self._create_phrase_set(phrases)
                if phrase_set:
                    config.adaptation = cloud_speech.SpeechAdaptation(
                        phrase_sets=[phrase_set]
                    )
            
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
            
            self.logger.info(f"✅ 辨識成功: {Path(audio_file).name}")
            self.logger.debug(f"   信心度: {avg_confidence:.2%}")
            self.logger.debug(f"   內容: {transcript[:50]}...")
            
            return {
                'transcript': transcript,
                'transcript_raw': transcript,
                'confidence': avg_confidence,
                'results': response.results
            }
        
        except Exception as e:
            self.logger.error(f"❌ 辨識失敗 ({Path(audio_file).name}): {e}")
            raise
    
    def _create_phrase_set(self, phrases: List[Dict]) -> Optional[cloud_speech.PhraseSet]:
        """
        建立詞彙集
        
        Args:
            phrases: 詞彙列表，格式為 [{'value': '詞彙', 'boost': 20}, ...]
        
        Returns:
            PhraseSet 物件
        """
        if not phrases:
            return None
        
        try:
            phrase_list = []
            for phrase_dict in phrases:
                if isinstance(phrase_dict, dict) and 'value' in phrase_dict:
                    phrase_obj = cloud_speech.PhraseSet.Phrase(
                        value=phrase_dict['value'],
                        boost=phrase_dict.get('boost', 10)
                    )
                    phrase_list.append(phrase_obj)
            
            if phrase_list:
                self.logger.info(f"載入 {len(phrase_list)} 個詞彙提示")
                return cloud_speech.PhraseSet(phrases=phrase_list)
            
            return None
        
        except Exception as e:
            self.logger.error(f"建立詞彙集失敗: {e}")
            return None
    
    def list_available_models(self):
        """列出可用的模型"""
        self.logger.info("可用的模型:")
        for model_name in self.SUPPORTED_MODELS:
            self.logger.info(f"  - {model_name}")


def test_google_stt():
    """測試 Google STT 配置"""
    print("\n測試 Google STT 配置...")
    print("=" * 80)
    
    # 測試不同配置
    configs = [
        {'location': 'us', 'model': 'chirp'},
        {'location': 'global', 'model': 'chirp'},  # 應自動轉換為 us
        {'location': 'us', 'model': 'chirp_3'},    # 應自動轉換為 chirp
        {'location': 'us', 'model': 'latest_long'},
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\n測試 {i}: location={config['location']}, model={config['model']}")
        try:
            model = GoogleSTTModel(**config)
            print(f"✅ 初始化成功")
            print(f"   實際區域: {model.location}")
            print(f"   實際模型: {model.model}")
        except Exception as e:
            print(f"❌ 初始化失敗: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_google_stt()