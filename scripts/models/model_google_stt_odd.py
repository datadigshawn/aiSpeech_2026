"""
Google Cloud Speech-to-Text 模組
支援功能:
- Chirp 3 / Long / Latest Short / Phone Call 模型
- V2 API (Recognizers)
- PhraseSet (詞彙表提示)
- 字級時間戳
- 同步與批次辨識
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Union
import os

from google.cloud import speech_v2
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

from utils.logger import get_model_logger

logger = get_model_logger('google_stt')


class GoogleSTTModel:
    """Google Speech-to-Text V2 模型封裝"""
    
    # 支援的模型類型
    MODELS = {
        'chirp_3': 'chirp',
        'chirp_2': 'chirp_2',
        'long': 'long',
        'short': 'short',
        'phone_call': 'phone_call',
        'medical_dictation': 'medical_dictation',
        'medical_conversation': 'medical_conversation'
    }
    
    def __init__(
        self,
        project_id: str,
        location: str = "global",
        model: str = "chirp_3",
        language_code: str = "cmn-Hant-TW",
        sample_rate: int = 16000,
        recognizer_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        """
        初始化 Google STT 模型
        
        Args:
            project_id: Google Cloud 專案 ID
            location: 區域 (global, us-central1, asia-east1 等)
            model: 模型類型 (chirp_3, long, short, phone_call)
            language_code: 語言代碼 (cmn-Hant-TW 為繁體中文)
            sample_rate: 音訊採樣率 (Hz)
            recognizer_id: 預先建立的 Recognizer ID (可選)
            credentials_path: 服務帳號 JSON 金鑰路徑 (可選)
        """
        self.project_id = project_id
        self.location = location
        self.model_type = model
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.recognizer_id = recognizer_id
        
        # 設定憑證
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        # 初始化客戶端
        try:
            self.client = SpeechClient()
            logger.info(f"Google STT 客戶端初始化成功")
            logger.info(f"  專案: {project_id}")
            logger.info(f"  區域: {location}")
            logger.info(f"  模型: {model}")
            logger.info(f"  語言: {language_code}")
        except Exception as e:
            logger.error(f"初始化 Google STT 客戶端失敗: {e}")
            raise
        
        # 建立或載入 Recognizer
        if recognizer_id:
            self.recognizer_name = f"projects/{project_id}/locations/{location}/recognizers/{recognizer_id}"
            logger.info(f"使用現有 Recognizer: {self.recognizer_name}")
        else:
            self.recognizer_name = None
            logger.info("將使用臨時 RecognitionConfig")
    
    def create_recognizer(
        self,
        recognizer_id: str,
        display_name: str = "Radio Transcription Recognizer",
        phrase_set_ids: Optional[List[str]] = None
    ) -> str:
        """
        建立 Recognizer (V2 API 的推薦做法)
        
        Args:
            recognizer_id: Recognizer ID
            display_name: 顯示名稱
            phrase_set_ids: PhraseSet ID 列表
        
        Returns:
            Recognizer 資源名稱
        """
        parent = f"projects/{self.project_id}/locations/{self.location}"
        
        # 建立 RecognitionConfig
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[self.language_code],
            model=self.MODELS.get(self.model_type, 'chirp'),
            features=cloud_speech.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_word_confidence=True,
                enable_automatic_punctuation=True
            )
        )
        
        # 如果有 PhraseSet，加入適應配置
        if phrase_set_ids:
            adaptation = cloud_speech.SpeechAdaptation()
            for phrase_set_id in phrase_set_ids:
                phrase_set_name = f"{parent}/phraseSets/{phrase_set_id}"
                adaptation.phrase_sets.append(
                    cloud_speech.SpeechAdaptation.AdaptationPhraseSet(
                        phrase_set=phrase_set_name
                    )
                )
            config.adaptation = adaptation
        
        # 建立 Recognizer
        recognizer = cloud_speech.Recognizer(
            display_name=display_name,
            model=self.MODELS.get(self.model_type, 'chirp'),
            language_codes=[self.language_code],
            default_recognition_config=config
        )
        
        request = cloud_speech.CreateRecognizerRequest(
            parent=parent,
            recognizer_id=recognizer_id,
            recognizer=recognizer
        )
        
        try:
            operation = self.client.create_recognizer(request=request)
            response = operation.result(timeout=300)  # 等待最多 5 分鐘
            
            recognizer_name = response.name
            logger.info(f"Recognizer 建立成功: {recognizer_name}")
            
            self.recognizer_name = recognizer_name
            self.recognizer_id = recognizer_id
            
            return recognizer_name
            
        except Exception as e:
            logger.error(f"建立 Recognizer 失敗: {e}")
            raise
    
    def create_phrase_set(
        self,
        phrase_set_id: str,
        phrases: List[Dict[str, Union[str, int]]],
        display_name: str = "Radio Terminology PhraseSet"
    ) -> str:
        """
        建立 PhraseSet (詞彙表)
        
        Args:
            phrase_set_id: PhraseSet ID
            phrases: 詞彙列表，格式:
                [
                    {"value": "OCC", "boost": 20},
                    {"value": "R13", "boost": 15}
                ]
            display_name: 顯示名稱
        
        Returns:
            PhraseSet 資源名稱
        """
        parent = f"projects/{self.project_id}/locations/{self.location}"
        
        # 建立 Phrase 物件
        phrase_objects = []
        for phrase_dict in phrases:
            phrase = cloud_speech.PhraseSet.Phrase(
                value=phrase_dict["value"],
                boost=phrase_dict.get("boost", 10)
            )
            phrase_objects.append(phrase)
        
        # 建立 PhraseSet
        phrase_set = cloud_speech.PhraseSet(
            phrases=phrase_objects,
            display_name=display_name
        )
        
        request = cloud_speech.CreatePhraseSetRequest(
            parent=parent,
            phrase_set_id=phrase_set_id,
            phrase_set=phrase_set
        )
        
        try:
            operation = self.client.create_phrase_set(request=request)
            response = operation.result(timeout=60)
            
            phrase_set_name = response.name
            logger.info(f"PhraseSet 建立成功: {phrase_set_name}")
            logger.info(f"  包含 {len(phrases)} 個詞彙")
            
            return phrase_set_name
            
        except Exception as e:
            logger.error(f"建立 PhraseSet 失敗: {e}")
            raise
    
    def transcribe_file(
        self,
        audio_file: str,
        phrases: Optional[List[Dict]] = None,
        enable_word_time_offsets: bool = True
    ) -> Dict:
        """
        同步辨識音檔 (適用於短音檔 < 1 分鐘)
        
        Args:
            audio_file: 音檔路徑
            phrases: 詞彙提示列表 (臨時使用，不建立 PhraseSet)
            enable_word_time_offsets: 是否啟用字級時間戳
        
        Returns:
            辨識結果字典:
            {
                'transcript': '完整逐字稿',
                'transcript_raw': '未經修正的原始逐字稿',
                'words': [字級時間戳列表],
                'confidence': 信心分數
            }
        """
        # 讀取音檔
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"音檔不存在: {audio_file}")
        
        with open(audio_path, 'rb') as f:
            audio_content = f.read()
        
        # 建立 RecognitionConfig
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[self.language_code],
            model=self.MODELS.get(self.model_type, 'chirp'),
            features=cloud_speech.RecognitionFeatures(
                enable_word_time_offsets=enable_word_time_offsets,
                enable_word_confidence=True,
                enable_automatic_punctuation=True
            )
        )
        
        # 如果有臨時詞彙提示
        if phrases:
            inline_phrase_set = cloud_speech.PhraseSet()
            for phrase_dict in phrases:
                inline_phrase_set.phrases.append(
                    cloud_speech.PhraseSet.Phrase(
                        value=phrase_dict["value"],
                        boost=phrase_dict.get("boost", 10)
                    )
                )
            
            adaptation = cloud_speech.SpeechAdaptation(
                phrase_sets=[
                    cloud_speech.SpeechAdaptation.AdaptationPhraseSet(
                        inline_phrase_set=inline_phrase_set
                    )
                ]
            )
            config.adaptation = adaptation
        
        # 建立辨識請求
        if self.recognizer_name:
            # 使用預先建立的 Recognizer
            request = cloud_speech.RecognizeRequest(
                recognizer=self.recognizer_name,
                config=config,
                content=audio_content
            )
        else:
            # 使用臨時配置
            parent = f"projects/{self.project_id}/locations/{self.location}"
            request = cloud_speech.RecognizeRequest(
                recognizer=f"{parent}/recognizers/_",
                config=config,
                content=audio_content
            )
        
        # 執行辨識
        try:
            response = self.client.recognize(request=request)
            
            # 解析結果
            result = self._parse_response(response)
            
            logger.info(f"辨識完成: {audio_path.name}")
            logger.info(f"  逐字稿: {result['transcript'][:50]}...")
            logger.info(f"  信心分數: {result.get('confidence', 0):.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"辨識失敗 ({audio_file}): {e}")
            raise
    
    def _parse_response(self, response) -> Dict:
        """解析 Google STT 回應"""
        if not response.results:
            logger.warning("辨識結果為空")
            return {
                'transcript': '',
                'transcript_raw': '',
                'words': [],
                'confidence': 0.0
            }
        
        # 取得第一個結果（通常是最佳結果）
        result = response.results[0]
        
        if not result.alternatives:
            return {
                'transcript': '',
                'transcript_raw': '',
                'words': [],
                'confidence': 0.0
            }
        
        alternative = result.alternatives[0]
        
        # 提取逐字稿
        transcript = alternative.transcript
        
        # 提取字級時間戳
        words = []
        if hasattr(alternative, 'words'):
            for word_info in alternative.words:
                word_entry = {
                    'word': word_info.word,
                    'start_ms': int(word_info.start_offset.total_seconds() * 1000),
                    'end_ms': int(word_info.end_offset.total_seconds() * 1000),
                    'confidence': word_info.confidence if hasattr(word_info, 'confidence') else None
                }
                words.append(word_entry)
        
        # 提取信心分數
        confidence = alternative.confidence if hasattr(alternative, 'confidence') else None
        
        return {
            'transcript': transcript,
            'transcript_raw': transcript,  # 後續由 text_cleaner 處理
            'words': words,
            'confidence': confidence
        }
    
    def batch_transcribe_files(
        self,
        audio_files: List[str],
        output_dir: str,
        phrases: Optional[List[Dict]] = None
    ) -> Dict[str, Dict]:
        """
        批次辨識多個音檔
        
        Args:
            audio_files: 音檔路徑列表
            output_dir: 輸出目錄
            phrases: 詞彙提示列表
        
        Returns:
            辨識結果字典，key 為 chunk_id
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        for i, audio_file in enumerate(audio_files, 1):
            logger.info(f"正在處理 [{i}/{len(audio_files)}]: {Path(audio_file).name}")
            
            try:
                result = self.transcribe_file(audio_file, phrases=phrases)
                
                # 取得 chunk_id (從檔名)
                chunk_id = Path(audio_file).stem
                results[chunk_id] = result
                
                # 儲存文字檔
                txt_file = output_path / f"{chunk_id}.txt"
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(result['transcript'])
                
            except Exception as e:
                logger.error(f"處理失敗 ({audio_file}): {e}")
                results[chunk_id] = {
                    'transcript': '',
                    'transcript_raw': '',
                    'words': [],
                    'confidence': 0.0,
                    'error': str(e)
                }
        
        # 儲存完整結果 JSON
        json_file = output_path / "stt_results_full.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"批次辨識完成，結果已儲存至: {output_dir}")
        logger.info(f"  成功: {sum(1 for r in results.values() if 'error' not in r)}/{len(results)}")
        
        return results


if __name__ == "__main__":
    # 測試 Google STT 模型
    import sys
    
    # 檢查環境變數
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        print("請設定 GOOGLE_APPLICATION_CREDENTIALS 環境變數")
        print("或在初始化時提供 credentials_path 參數")
        sys.exit(1)
    
    # 初始化模型
    model = GoogleSTTModel(
        project_id="dazzling-seat-315406",  # 替換為您的專案 ID
        location="global",
        model="chirp_3",
        language_code="cmn-Hant-TW",
        sample_rate=16000
    )
    
    # 測試辨識
    test_audio = "experiments/Test_01_TMRT/batch_processing/dataset_chunks/chunk_001.wav"
    
    if Path(test_audio).exists():
        result = model.transcribe_file(test_audio)
        
        print(f"\n辨識結果:")
        print(f"逐字稿: {result['transcript']}")
        print(f"信心分數: {result.get('confidence', 0):.2f}")
        print(f"\n字級時間戳 (前5個字):")
        for word in result['words'][:5]:
            print(f"  {word['word']}: {word['start_ms']}ms - {word['end_ms']}ms")
    else:
        print(f"測試檔案不存在: {test_audio}")