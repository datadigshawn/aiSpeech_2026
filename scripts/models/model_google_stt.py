#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text V2 模型包裝器
版本: 2.0 (2025年1月修正版)

修正重點:
1. ✅ 正確使用區域端點 ({REGION}-speech.googleapis.com)
2. ✅ 正確的 recognizer 路徑格式
3. ✅ 支援 Chirp 3 / Chirp Telephony / Chirp 2 等模型
4. ✅ 正確實作 PhraseSet 適應功能
5. ✅ 自動區域回退機制
修正_2026.01.12-16:00:
1. ✅ 音訊格式自動轉換（解決 400 Audio encoding 錯誤）
2. ✅ 正確的 recognizer 路徑格式（使用 recognizers/_)
3. ✅ 明確指定音訊編碼參數
4. ✅ 區域端點配置
"""

import os
import sys
import wave
import struct
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

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
from google.api_core.client_options import ClientOptions

try:
    from utils.logger import get_logger
    from utils.google_stt_config_manager import GoogleSTTConfigManager
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from utils.logger import get_logger
    from utils.google_stt_config_manager import GoogleSTTConfigManager


# ============================================================================
# 音訊格式轉換工具
# ============================================================================
class AudioConverter:
    """音訊格式轉換器 - 確保音訊符合 Google STT 要求"""
    
    SUPPORTED_SAMPLE_RATES = [8000, 16000, 32000, 48000]
    TARGET_SAMPLE_RATE = 16000  # Google STT 推薦的取樣率
    
    @staticmethod
    def get_wav_info(audio_path: str) -> Dict:
        """
        讀取 WAV 檔案資訊
        
        Returns:
            dict: {
                'sample_rate': int,
                'channels': int,
                'sample_width': int (bytes),
                'frames': int,
                'duration': float (seconds),
                'encoding': str
            }
        """
        try:
            with wave.open(audio_path, 'rb') as wav:
                return {
                    'sample_rate': wav.getframerate(),
                    'channels': wav.getnchannels(),
                    'sample_width': wav.getsampwidth(),
                    'frames': wav.getnframes(),
                    'duration': wav.getnframes() / wav.getframerate(),
                    'encoding': 'LINEAR16' if wav.getsampwidth() == 2 else f'UNKNOWN_{wav.getsampwidth()*8}bit'
                }
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def convert_to_linear16(
        input_path: str,
        output_path: str = None,
        target_sample_rate: int = 16000
    ) -> str:
        """
        將音訊轉換為 LINEAR16 PCM 格式
        
        Args:
            input_path: 輸入音檔路徑
            output_path: 輸出路徑（None 則使用臨時檔案）
            target_sample_rate: 目標取樣率
        
        Returns:
            str: 轉換後的檔案路徑
        """
        if output_path is None:
            # 建立臨時檔案
            fd, output_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
        
        # 使用 ffmpeg 轉換
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-acodec', 'pcm_s16le',  # LINEAR16 (16-bit signed little-endian)
            '-ar', str(target_sample_rate),  # 取樣率
            '-ac', '1',  # 單聲道
            output_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg 轉換失敗: {result.stderr}")
            
            return output_path
        
        except FileNotFoundError:
            raise RuntimeError("找不到 ffmpeg，請安裝 ffmpeg")
    
    @staticmethod
    def needs_conversion(audio_path: str) -> Tuple[bool, Dict]:
        """
        檢查音訊是否需要轉換
        
        Returns:
            Tuple[bool, Dict]: (需要轉換, 音訊資訊)
        """
        info = AudioConverter.get_wav_info(audio_path)
        
        if 'error' in info:
            # 無法讀取，可能不是標準 WAV，需要轉換
            return True, info
        
        needs_convert = False
        reasons = []
        
        # 檢查編碼
        if info['sample_width'] != 2:  # 不是 16-bit
            needs_convert = True
            reasons.append(f"非 16-bit ({info['sample_width']*8}-bit)")
        
        # 檢查聲道
        if info['channels'] != 1:
            needs_convert = True
            reasons.append(f"非單聲道 ({info['channels']} channels)")
        
        # 檢查取樣率
        if info['sample_rate'] not in AudioConverter.SUPPORTED_SAMPLE_RATES:
            needs_convert = True
            reasons.append(f"取樣率不支援 ({info['sample_rate']} Hz)")
        
        info['needs_conversion'] = needs_convert
        info['conversion_reasons'] = reasons
        
        return needs_convert, info


class GoogleSTTModel:
    """Google Cloud Speech-to-Text V2 API 包裝器（修正版 v2）"""
    
    def __init__(
        self,
        project_id: str = None,
        location: str = None,
        model: str = "chirp_3",
        language_code: str = "cmn-Hant-TW",
        auto_config: bool = True,
        auto_convert_audio: bool = True  # 新增：自動轉換音訊
    ):
        """初始化 Google STT 模型"""
        self.logger = get_logger(self.__class__.__name__)
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406')
        self.language_code = language_code
        self.auto_convert_audio = auto_convert_audio
        self._temp_files = []  # 追蹤臨時檔案
        
        # 確保認證已設定
        setup_credentials()
        
        # 初始化配置管理器
        if auto_config:
            try:
                self.config_manager = GoogleSTTConfigManager(self.project_id)
                # 取得最佳配置（返回三元組：model, region, endpoint）
                config_result = self.config_manager.get_optimal_config(
                    model=model or "chirp_3",
                    preferred_region=location
                )
                
                # 相容新舊版本的配置管理器
                if isinstance(config_result, tuple) and len(config_result) == 3:
                    self.model, self.location, self.api_endpoint = config_result
                else:
                    self.model, self.location = config_result
                    self.api_endpoint = f"{self.location}-speech.googleapis.com"
                
                self.logger.info("✅ 使用動態配置管理")
            except Exception as e:
                self.logger.warning(f"⚠️ 動態配置失敗，使用預設值: {e}")
                self.model = model or "chirp_3"
                self.location = location or "us"
                self.api_endpoint = f"{self.location}-speech.googleapis.com"
                self.config_manager = None
        else:
            self.model = model or "chirp_3"
            self.location = location or "us"
            self.api_endpoint = f"{self.location}-speech.googleapis.com"
            self.config_manager = None
            self.logger.warning("⚠️ 手動配置模式（不建議）")
        
        # 建立客戶端（使用區域端點）
        try:
            client_options = ClientOptions(api_endpoint=self.api_endpoint)
            self.client = SpeechClient(client_options=client_options)
            
            self.logger.info(f"✅ Google STT 初始化成功")
            self.logger.info(f"   專案: {self.project_id}")
            self.logger.info(f"   區域: {self.location}")
            self.logger.info(f"   端點: {self.api_endpoint}")
            self.logger.info(f"   模型: {self.model}")
            self.logger.info(f"   語言: {self.language_code}")
            self.logger.info(f"   自動轉檔: {'✅ 啟用' if auto_convert_audio else '❌ 停用'}")
        except Exception as e:
            self.logger.error(f"❌ Google STT 初始化失敗: {e}")
            raise
    
    def __del__(self):
        """清理臨時檔案"""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
    
    def _prepare_audio(self, audio_file: str) -> Tuple[bytes, int]:
        """
        準備音訊資料（必要時進行轉換）
        
        Returns:
            Tuple[bytes, int]: (音訊資料, 取樣率)
        """
        audio_path = Path(audio_file)
        
        if self.auto_convert_audio:
            # 檢查是否需要轉換
            needs_convert, info = AudioConverter.needs_conversion(str(audio_path))
            
            if needs_convert:
                reasons = info.get('conversion_reasons', ['格式不相容'])
                self.logger.info(f"🔄 音訊需要轉換: {', '.join(reasons)}")
                
                # 轉換音訊
                converted_path = AudioConverter.convert_to_linear16(
                    str(audio_path),
                    target_sample_rate=16000
                )
                self._temp_files.append(converted_path)
                
                self.logger.debug(f"✅ 音訊已轉換: {converted_path}")
                
                # 讀取轉換後的音訊
                with open(converted_path, 'rb') as f:
                    audio_content = f.read()
                
                return audio_content, 16000
            else:
                # 不需要轉換，直接讀取
                sample_rate = info.get('sample_rate', 16000)
                with open(audio_file, 'rb') as f:
                    audio_content = f.read()
                
                return audio_content, sample_rate
        else:
            # 不自動轉換，直接讀取
            with open(audio_file, 'rb') as f:
                audio_content = f.read()
            
            # 嘗試取得取樣率
            info = AudioConverter.get_wav_info(str(audio_path))
            sample_rate = info.get('sample_rate', 16000)
            
            return audio_content, sample_rate
    
    def transcribe_file(
        self,
        audio_file: str,
        phrases: List[Dict] = None,
        enable_word_time_offsets: bool = True, # 支援標點符號 
        **kwargs # 接收並忽略不支援的參數 (例如 diarization)
        # 17:10增加參數
    ) -> Dict:
        """
        辨識音檔（修正版 v2）
        
        Args:
            audio_file: 音檔路徑
            phrases: 詞彙表列表 [{"value": "詞彙", "boost": 10}, ...]
            enable_word_time_offsets: 是否啟用字詞時間戳
        
        Returns:
            辨識結果字典
        """
        try:
            # 準備音訊（必要時自動轉換）
            audio_content, sample_rate = self._prepare_audio(audio_file)
            
            # ====================================================================
            # 修正：正確的 recognizer 路徑格式
            # V2 API 使用 recognizers/_ 而不是 recognizers/{model_name}
            # ====================================================================
            recognizer_path = (
                f"projects/{self.project_id}/locations/{self.location}/recognizers/_"
            )
            
            self.logger.debug(f"Recognizer 路徑: {recognizer_path}")
            
            # ====================================================================
            # 修正：明確指定音訊編碼（不使用 auto_decoding_config）
            # ====================================================================
            explicit_decoding = cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                audio_channel_count=1
            )
            
            config = cloud_speech.RecognitionConfig(
                explicit_decoding_config=explicit_decoding,
                language_codes=[self.language_code],
                model=self.model,
                features=cloud_speech.RecognitionFeatures(
                    enable_word_time_offsets=enable_word_time_offsets,
                    enable_automatic_punctuation=False
                )
            )
            
            # 如果有詞彙表，使用 inline phrase_hints
            if phrases and len(phrases) > 0:
                phrase_hints = []
                for phrase_dict in phrases:
                    if isinstance(phrase_dict, dict) and 'value' in phrase_dict:
                        phrase_hints.append(phrase_dict['value'])
                    elif isinstance(phrase_dict, str):
                        phrase_hints.append(phrase_dict)
                
                if phrase_hints:
                    # 限制數量（Chirp 3 支援 1000，其他模型 500）
                    max_phrases = 1000 if 'chirp_3' in self.model else 500
                    phrase_hints = phrase_hints[:max_phrases]
                    
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
            self.logger.debug(f"發送辨識請求: {Path(audio_file).name}")
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
            error_msg = str(e)
            self.logger.error(f"❌ 辨識失敗 ({Path(audio_file).name}): {error_msg}")
            
            # 如果啟用了自動配置，嘗試回退到備選區域
            if self.config_manager and "does not exist in the location" in error_msg:
                return self._try_fallback_regions(audio_file, phrases, enable_word_time_offsets, e)
            
            # 回傳錯誤資訊
            return {
                'transcript': '',
                'transcript_raw': '',
                'confidence': 0.0,
                'error': error_msg
            }
    
    def _try_fallback_regions(self, audio_file, phrases, enable_word_time_offsets, original_error):
        """嘗試使用回退區域"""
        self.logger.warning(f"⚠️ 當前區域 '{self.location}' 失敗，嘗試回退區域...")
        
        if not self.config_manager:
            raise original_error
        
        model_config = self.config_manager.config['models'].get(self.model, {})
        fallback_regions = model_config.get('fallback_regions', [])
        
        for fallback_region in fallback_regions:
            if fallback_region == self.location:
                continue
            
            try:
                self.logger.info(f"嘗試回退區域: {fallback_region}")
                
                # 臨時切換區域和端點
                original_location = self.location
                original_endpoint = self.api_endpoint
                
                self.location = fallback_region
                self.api_endpoint = f"{fallback_region}-speech.googleapis.com"
                
                # 重建客戶端
                client_options = ClientOptions(api_endpoint=self.api_endpoint)
                self.client = SpeechClient(client_options=client_options)
                
                # 重新嘗試辨識
                result = self.transcribe_file(audio_file, phrases, enable_word_time_offsets)
                
                if 'error' not in result:
                    self.logger.info(f"✅ 回退成功！使用區域: {fallback_region}")
                    return result
                
            except Exception as e:
                self.logger.warning(f"回退區域 {fallback_region} 也失敗: {e}")
                self.location = original_location
                self.api_endpoint = original_endpoint
                continue
        
        # 所有回退都失敗
        self.logger.error("❌ 所有回退區域都失敗")
        return {
            'transcript': '',
            'transcript_raw': '',
            'confidence': 0.0,
            'error': str(original_error)
        }
    
    def get_current_config(self) -> Dict:
        """獲取當前配置資訊"""
        return {
            'project_id': self.project_id,
            'location': self.location,
            'api_endpoint': self.api_endpoint,
            'model': self.model,
            'language_code': self.language_code,
            'auto_config_enabled': self.config_manager is not None,
            'auto_convert_audio': self.auto_convert_audio,
            'credentials_set': bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
        }
    
    def print_config_info(self):
        """列印配置資訊"""
        config = self.get_current_config()
        print("\n當前 Google STT 配置:")
        print(f"  專案ID: {config['project_id']}")
        print(f"  區域: {config['location']}")
        print(f"  端點: {config['api_endpoint']}")
        print(f"  模型: {config['model']}")
        print(f"  語言: {config['language_code']}")
        print(f"  動態配置: {'✅ 啟用' if config['auto_config_enabled'] else '❌ 停用'}")
        print(f"  自動轉檔: {'✅ 啟用' if config['auto_convert_audio'] else '❌ 停用'}")
        print(f"  認證設定: {'✅ 已設定' if config['credentials_set'] else '❌ 未設定'}")
        
        if config['credentials_set']:
            print(f"  金鑰路徑: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")


def test_audio_conversion():
    """測試音訊轉換功能"""
    print("\n測試音訊轉換功能")
    print("=" * 80)
    
    # 測試用的音訊檔案路徑（需要存在）
    test_files = [
        "/path/to/test.wav",
        # 新增您的測試檔案路徑
    ]
    
    for audio_file in test_files:
        if not os.path.exists(audio_file):
            print(f"⚠️ 測試檔案不存在: {audio_file}")
            continue
        
        print(f"\n檔案: {audio_file}")
        
        # 取得音訊資訊
        info = AudioConverter.get_wav_info(audio_file)
        print(f"  資訊: {info}")
        
        # 檢查是否需要轉換
        needs_convert, detailed_info = AudioConverter.needs_conversion(audio_file)
        print(f"  需要轉換: {needs_convert}")
        if needs_convert:
            print(f"  原因: {detailed_info.get('conversion_reasons', [])}")


def test_google_stt():
    """測試 Google STT 功能"""
    print("\n測試 Google STT（修正版 v2）")
    print("=" * 80)
    
    # 初始化模型
    try:
        model = GoogleSTTModel(
            model="chirp_3",
            location="us",
            auto_convert_audio=True
        )
        model.print_config_info()
        print("✅ 模型初始化成功")
    except Exception as e:
        print(f"❌ 模型初始化失敗: {e}")


if __name__ == "__main__":
    test_google_stt()
