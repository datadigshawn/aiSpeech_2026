#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text V2 動態配置管理系統
版本: 2.0 (2025年1月修正版)

修正重點:
1. ✅ Chirp 3 僅支援 us, eu 多區域 (不支援 global)
2. ✅ Chirp 2 使用 us-central1 區域端點
3. ✅ 所有 V2 API 都需要區域端點 ({REGION}-speech.googleapis.com)
4. ✅ chirp_telephony 專為電話/無線電 8kHz 優化
5. ✅ 正確的 recognizer 路徑格式
6. ✅ 移除 global 區域（V2 API 不支援）
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 修正 import 路徑
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


# ============================================================================
# 內建認證設定（自動設定環境變數）
# ============================================================================
def setup_credentials():
    """自動設定 Google Cloud 認證"""
    # 嘗試多個可能的金鑰路徑
    possible_paths = [
        Path(__file__).parent.parent / "utils" / "google-speech-key.json",
        Path(__file__).parent / "utils" / "google-speech-key.json",
        Path.home() / ".config" / "gcloud" / "application_default_credentials.json",
    ]
    
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        for key_path in possible_paths:
            if key_path.exists():
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_path)
                return str(key_path)
    return os.getenv('GOOGLE_APPLICATION_CREDENTIALS')


# 在 import Google Client 之前設定認證
setup_credentials()

try:
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech
    from google.api_core import exceptions
    from google.api_core.client_options import ClientOptions
    GOOGLE_CLIENT_AVAILABLE = True
except ImportError:
    GOOGLE_CLIENT_AVAILABLE = False
    print("⚠️  Google Cloud Speech-to-Text 客戶端不可用")
    print("   請執行: pip install google-cloud-speech")

try:
    from utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


class GoogleSTTConfigManager:
    """
    Google STT V2 API 動態配置管理器
    
    重要修正說明:
    - V2 API 不使用 'global' 區域，必須使用具體的多區域 (us, eu) 或單一區域
    - API 端點格式: {REGION}-speech.googleapis.com
    - Recognizer 路徑: projects/{PROJECT}/locations/{REGION}/recognizers/_
    """
    
    CONFIG_FILE = Path(__file__).parent.parent / "config" / "google_stt_config.json"
    
    # ========================================================================
    # 最新模型配置 (基於 2025年12月 Google Cloud 官方文件)
    # ========================================================================
    DEFAULT_CONFIG = {
        "last_updated": None,
        "api_version": "V2",
        "models": {
            # ----------------------------------------------------------------
            # Chirp 3 - 最新一代，僅支援 us/eu 多區域
            # ----------------------------------------------------------------
            "chirp_3": {
                "display_name": "Chirp 3.0 (最新)",
                "model_id": "chirp_3",
                "supported_regions": ["us", "eu"],  # ⚠️ 不支援 global
                "preferred_region": "us",
                "fallback_regions": ["eu"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": True,
                    "sync": True,
                    "batch": True,
                    "diarization": True,
                    "adaptation": True,
                    "auto_language_detect": True,
                    "denoiser": True,
                    "max_phrases": 1000
                },
                "description": "最新一代多語言 ASR 模型，支援說話者辨識和自動語言偵測",
                "supported_languages": ["cmn-Hant-TW", "cmn-Hans-CN", "en-US", "ja-JP", "ko-KR"]
            },
            
            # ----------------------------------------------------------------
            # Chirp Telephony - 電話/無線電專用 (8kHz 優化)
            # ----------------------------------------------------------------
            "chirp_telephony": {
                "display_name": "Chirp Telephony (電話/無線電專用)",
                "model_id": "chirp_telephony",
                "supported_regions": ["us-central1", "asia-southeast1", "europe-west1"],
                "preferred_region": "us-central1",
                "fallback_regions": ["asia-southeast1", "europe-west1"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": True,
                    "sync": True,
                    "batch": True,
                    "diarization": False,
                    "adaptation": True,
                    "optimized_for": "8kHz telephony audio"
                },
                "description": "針對電話和無線電音訊優化 (8kHz 取樣率)",
                "notes": "適合捷運無線電通訊辨識"
            },
            
            # ----------------------------------------------------------------
            # Chirp 2 - 穩定版本
            # ----------------------------------------------------------------
            "chirp_2": {
                "display_name": "Chirp 2.0",
                "model_id": "chirp_2",
                "supported_regions": ["us-central1", "asia-southeast1", "europe-west4"],
                "preferred_region": "us-central1",
                "fallback_regions": ["asia-southeast1", "europe-west4"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": True,
                    "sync": True,
                    "batch": True,
                    "translation": True
                },
                "description": "Chirp 2.0 版本，支援語音翻譯"
            },
            
            # ----------------------------------------------------------------
            # Chirp (Original) - 第一代
            # ----------------------------------------------------------------
            "chirp": {
                "display_name": "Chirp (Universal)",
                "model_id": "chirp",
                "supported_regions": ["us-central1", "europe-west4", "asia-southeast1"],
                "preferred_region": "us-central1",
                "fallback_regions": ["europe-west4", "asia-southeast1"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": False,  # Chirp 1 不適合即時串流
                    "sync": True,
                    "batch": True
                },
                "description": "第一代 Chirp 模型 (Universal Speech Model)",
                "limitations": ["不支援真正的即時串流", "不支援說話者辨識"]
            },
            
            # ----------------------------------------------------------------
            # Latest Long - 長音訊優化
            # ----------------------------------------------------------------
            "latest_long": {
                "display_name": "Latest Long",
                "model_id": "latest_long",
                "supported_regions": ["us-central1", "europe-west4", "asia-southeast1"],
                "preferred_region": "us-central1",
                "fallback_regions": ["europe-west4", "asia-southeast1"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": True,
                    "sync": True,
                    "batch": True,
                    "adaptation": True
                },
                "description": "長音訊優化模型"
            },
            
            # ----------------------------------------------------------------
            # Latest Short - 短音訊優化
            # ----------------------------------------------------------------
            "latest_short": {
                "display_name": "Latest Short",
                "model_id": "latest_short",
                "supported_regions": ["us-central1", "europe-west4", "asia-southeast1"],
                "preferred_region": "us-central1",
                "fallback_regions": ["europe-west4", "asia-southeast1"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": True,
                    "sync": True,
                    "batch": True,
                    "adaptation": True
                },
                "description": "短音訊優化模型"
            },
            
            # ----------------------------------------------------------------
            # Telephony (傳統電話模型)
            # ----------------------------------------------------------------
            "telephony": {
                "display_name": "Telephony",
                "model_id": "telephony",
                "supported_regions": ["us-central1", "europe-west4", "asia-southeast1"],
                "preferred_region": "us-central1",
                "fallback_regions": ["europe-west4"],
                "api_endpoint_format": "{region}-speech.googleapis.com",
                "status": "GA",
                "features": {
                    "streaming": True,
                    "sync": True,
                    "batch": True
                },
                "description": "傳統電話音訊模型 (8kHz)"
            }
        },
        
        # ====================================================================
        # 區域別名映射（用於相容性）
        # ====================================================================
        "region_aliases": {
            # 多區域
            "united-states": "us",
            "america": "us",
            "europe": "eu",
            
            # 單一區域映射
            "taiwan": "us",          # 台灣用戶建議使用 us 多區域
            "asia-east1": "us",      # 東亞映射到 us
            "asia": "asia-southeast1",
            
            # ⚠️ 重要：global 不再支援，映射到 us
            "global": "us"
        },
        
        # ====================================================================
        # 模型別名映射
        # ====================================================================
        "model_aliases": {
            # Chirp 3 別名
            "chirp3": "chirp_3",
            "chirp-3": "chirp_3",
            "v3": "chirp_3",
            "latest": "chirp_3",
            
            # Chirp Telephony 別名
            "radio": "chirp_telephony",
            "telephony_chirp": "chirp_telephony",
            "phone": "chirp_telephony",
            "8khz": "chirp_telephony",
            
            # Chirp 2 別名
            "chirp2": "chirp_2",
            "chirp-2": "chirp_2",
            "v2": "chirp_2",
            
            # 其他
            "universal": "chirp",
            "default": "chirp_3",
            "long": "latest_long",
            "short": "latest_short"
        },
        
        # ====================================================================
        # 無線電專案推薦配置
        # ====================================================================
        "recommended_for_radio": {
            "primary_model": "chirp_3",
            "fallback_model": "chirp_telephony",
            "reason": "chirp_3 具有內建降噪功能和最佳準確度；chirp_telephony 針對 8kHz 電話音質優化",
            "configuration": {
                "region": "us",
                "language_code": "cmn-Hant-TW",
                "enable_denoiser": True,
                "snr_threshold": 20.0
            }
        }
    }
    
    def __init__(self, project_id: str = None):
        """初始化配置管理器"""
        self.logger = logger
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406')
        self.config = self._load_config()
        self._clients = {}  # 快取不同區域的客戶端
        
        self.logger.info(f"Google STT 配置管理器初始化")
        self.logger.info(f"  專案 ID: {self.project_id}")
    
    def _load_config(self) -> Dict:
        """載入配置檔案"""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # 驗證配置版本
                if config.get('api_version') == self.DEFAULT_CONFIG.get('api_version'):
                    self.logger.info(f"載入配置檔案 (更新於: {config.get('last_updated')})")
                    return config
                else:
                    self.logger.warning("配置檔案版本不符，使用預設配置")
            except Exception as e:
                self.logger.warning(f"載入配置失敗: {e}，使用預設配置")
        
        self.logger.info("使用預設配置")
        return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """儲存配置檔案"""
        try:
            self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.config['last_updated'] = datetime.now().isoformat()
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ 配置已儲存: {self.CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"❌ 儲存配置失敗: {e}")
    
    def get_optimal_config(self, model: str, preferred_region: str = None) -> Tuple[str, str, str]:
        """
        獲取最佳配置
        
        Args:
            model: 模型名稱或別名
            preferred_region: 偏好區域
        
        Returns:
            Tuple[model_id, region, api_endpoint]
        """
        # 1. 正規化模型名稱
        normalized_model = self._normalize_model_name(model)
        
        # 2. 獲取模型配置
        model_config = self.config['models'].get(normalized_model)
        if not model_config:
            self.logger.warning(f"未知模型 '{model}'，使用預設 'chirp_3'")
            normalized_model = "chirp_3"
            model_config = self.config['models']['chirp_3']
        
        # 3. 選擇最佳區域
        normalized_region = self._normalize_region_name(preferred_region)
        optimal_region = self._select_optimal_region(model_config, normalized_region)
        
        # 4. 生成 API 端點
        api_endpoint = self._get_api_endpoint(model_config, optimal_region)
        
        self.logger.info(f"✅ 配置完成:")
        self.logger.info(f"   模型: {model} -> {normalized_model}")
        self.logger.info(f"   區域: {preferred_region} -> {optimal_region}")
        self.logger.info(f"   端點: {api_endpoint}")
        
        return normalized_model, optimal_region, api_endpoint
    
    def _normalize_model_name(self, model: str) -> str:
        """正規化模型名稱"""
        if not model:
            return "chirp_3"
        
        model = model.lower().strip().replace('-', '_')
        
        # 檢查別名
        if model in self.config.get('model_aliases', {}):
            return self.config['model_aliases'][model]
        
        # 檢查是否為有效模型
        if model in self.config['models']:
            return model
        
        self.logger.warning(f"未知模型 '{model}'，使用預設 'chirp_3'")
        return "chirp_3"
    
    def _normalize_region_name(self, region: str) -> Optional[str]:
        """正規化區域名稱"""
        if not region:
            return None
        
        region = region.lower().strip()
        
        # 檢查別名
        if region in self.config.get('region_aliases', {}):
            return self.config['region_aliases'][region]
        
        return region
    
    def _select_optimal_region(self, model_config: Dict, preferred_region: Optional[str]) -> str:
        """選擇最佳區域"""
        supported_regions = model_config.get('supported_regions', ['us-central1'])
        
        # 如果指定的區域受支援，直接使用
        if preferred_region and preferred_region in supported_regions:
            return preferred_region
        
        # 使用模型的偏好區域
        preferred = model_config.get('preferred_region')
        if preferred and preferred in supported_regions:
            return preferred
        
        # 使用回退區域
        for region in model_config.get('fallback_regions', []):
            if region in supported_regions:
                return region
        
        # 使用第一個支援的區域
        return supported_regions[0] if supported_regions else 'us-central1'
    
    def _get_api_endpoint(self, model_config: Dict, region: str) -> str:
        """生成 API 端點"""
        endpoint_format = model_config.get('api_endpoint_format', '{region}-speech.googleapis.com')
        return endpoint_format.format(region=region)
    
    def get_recognizer_path(self, region: str) -> str:
        """
        獲取 Recognizer 路徑
        
        格式: projects/{PROJECT}/locations/{REGION}/recognizers/_
        """
        return f"projects/{self.project_id}/locations/{region}/recognizers/_"
    
    def create_client(self, region: str) -> 'SpeechClient':
        """
        建立指定區域的客戶端（帶快取）
        
        Args:
            region: 區域名稱
        
        Returns:
            SpeechClient 實例
        """
        if not GOOGLE_CLIENT_AVAILABLE:
            raise ImportError("Google Cloud Speech-to-Text 客戶端不可用")
        
        if region not in self._clients:
            api_endpoint = f"{region}-speech.googleapis.com"
            self.logger.debug(f"建立新客戶端: {api_endpoint}")
            
            self._clients[region] = SpeechClient(
                client_options=ClientOptions(
                    api_endpoint=api_endpoint
                )
            )
        
        return self._clients[region]
    
    def get_model_info(self, model: str) -> Dict:
        """獲取模型詳細資訊"""
        normalized = self._normalize_model_name(model)
        return self.config['models'].get(normalized, {})
    
    def list_available_models(self) -> List[str]:
        """列出所有可用模型"""
        return list(self.config['models'].keys())
    
    def print_config_summary(self):
        """列印配置摘要"""
        print("\n" + "=" * 80)
        print("Google STT V2 API 配置摘要")
        print("=" * 80)
        print(f"專案 ID: {self.project_id}")
        print(f"最後更新: {self.config.get('last_updated', '未知')}")
        print(f"API 版本: {self.config.get('api_version', 'V2')}")
        
        print("\n可用模型:")
        print("-" * 80)
        
        for name, cfg in self.config['models'].items():
            status_emoji = {
                'GA': '✅',
                'Preview': '🧪',
                'Beta': '🧪',
                'Deprecated': '⚠️'
            }.get(cfg.get('status'), '❓')
            
            print(f"\n{status_emoji} {name}")
            print(f"   顯示名稱: {cfg.get('display_name')}")
            print(f"   狀態: {cfg.get('status')}")
            print(f"   支援區域: {', '.join(cfg.get('supported_regions', []))}")
            print(f"   偏好區域: {cfg.get('preferred_region')}")
            print(f"   說明: {cfg.get('description', 'N/A')}")
            
            features = cfg.get('features', {})
            if features:
                feature_list = [k for k, v in features.items() if v is True]
                print(f"   功能: {', '.join(feature_list)}")
        
        print("\n" + "=" * 80)
        
        # 無線電專案推薦
        radio_rec = self.config.get('recommended_for_radio', {})
        if radio_rec:
            print("\n📻 無線電專案推薦配置:")
            print(f"   主要模型: {radio_rec.get('primary_model')}")
            print(f"   備用模型: {radio_rec.get('fallback_model')}")
            print(f"   原因: {radio_rec.get('reason')}")
        
        print("\n" + "=" * 80)
    
    def test_configurations(self):
        """測試各種配置組合"""
        print("\n" + "=" * 80)
        print("測試配置轉換")
        print("=" * 80)
        
        test_cases = [
            # (model, region, expected_description)
            ("chirp_3", "us", "Chirp 3 + US 多區域"),
            ("chirp_3", "eu", "Chirp 3 + EU 多區域"),
            ("chirp_3", "global", "Chirp 3 + global (應自動轉為 us)"),
            ("chirp_telephony", "us-central1", "電話模型 + 美國中部"),
            ("radio", None, "無線電別名 (應解析為 chirp_telephony)"),
            ("chirp_2", "asia-southeast1", "Chirp 2 + 東南亞"),
            ("latest_long", None, "長音訊模型 (使用預設區域)"),
            ("unknown_model", "eu", "未知模型 (應回退到 chirp_3)"),
        ]
        
        for model, region, description in test_cases:
            print(f"\n測試: {description}")
            print(f"  輸入: model={model}, region={region}")
            
            try:
                norm_model, opt_region, endpoint = self.get_optimal_config(model, region)
                print(f"  輸出: model={norm_model}, region={opt_region}")
                print(f"  端點: {endpoint}")
                print(f"  Recognizer: {self.get_recognizer_path(opt_region)}")
            except Exception as e:
                print(f"  錯誤: {e}")
        
        print("\n" + "=" * 80)


def create_default_config():
    """建立預設配置檔案"""
    print("\n建立預設配置檔案...")
    manager = GoogleSTTConfigManager()
    manager._save_config()
    print(f"✅ 配置檔案已建立: {manager.CONFIG_FILE}\n")
    return manager


def main():
    """主函數"""
    print("\n" + "╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "Google STT V2 配置管理器 (2025.01 修正版)" + " " * 15 + "║")
    print("╚" + "=" * 78 + "╝")
    
    manager = create_default_config()
    manager.print_config_summary()
    manager.test_configurations()
    
    print("\n✅ 配置管理器測試完成！")
    print(f"\n配置檔案位置: {manager.CONFIG_FILE}")
    
    print("\n" + "=" * 80)
    print("使用範例:")
    print("=" * 80)
    print("""
# 初始化
from utils.google_stt_config_manager import GoogleSTTConfigManager
manager = GoogleSTTConfigManager()

# 獲取 Chirp 3 配置
model, region, endpoint = manager.get_optimal_config("chirp_3", "us")

# 獲取無線電專用配置
model, region, endpoint = manager.get_optimal_config("radio")  # -> chirp_telephony

# 建立客戶端
client = manager.create_client(region)

# 獲取 Recognizer 路徑
recognizer = manager.get_recognizer_path(region)
""")
    
    print("\n下一步:")
    print("  python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt")
    print("")


if __name__ == "__main__":
    main()
