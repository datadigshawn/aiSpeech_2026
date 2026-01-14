#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text 動態配置管理系統
功能：
1. 自動偵測可用的模型和區域
2. 維護模型-區域相容性表
3. 自動回退到穩定配置
4. 定期更新配置檔案
5. 內建認證設定
修正 global 區域版_2026.01.12-11:00
修正: Expected resource location to be global 錯誤
增加 chirp_telephony模組來優化無線電語音辨識效果
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
    default_key_path = Path(__file__).parent.parent / "utils" / "google-speech-key.json"
    
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        if default_key_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(default_key_path)

# 在 import Google Client 之前設定認證
setup_credentials()

try:
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech
    from google.api_core import exceptions
    GOOGLE_CLIENT_AVAILABLE = True
except ImportError:
    GOOGLE_CLIENT_AVAILABLE = False
    print("⚠️  Google Cloud Speech-to-Text 客戶端不可用")

try:
    from utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    print("⚠️  使用標準 logging，未找到 utils.logger")


class GoogleSTTConfigManager:
    """Google STT 動態配置管理器（修正 global 區域版）"""
    
    CONFIG_FILE = Path(__file__).parent.parent / "config" / "google_stt_config.json"
    
    # ========================================================================
    # 修正：預設使用 global 區域（而不是 us）
    # ========================================================================
    DEFAULT_CONFIG = {
        "last_updated": None,
        "models": {
            "chirp_3": {
                "display_name": "Chirp 3.0",
                "supported_regions": ["us", "eu"],
                "preferred_region": "us",  # ✅ 當下僅支援us, eu兩區域
                "fallback_regions": ["eu"],
                "status": "stable",
                "description": "Chirp 3.0 版本，最新通用多國語言模型"
            },
            "chirp_telephony": {
                "display_name": "Chirp Telephony",
                "supported_regions": ["asia-southeast1", "asia-southeast1"],
                "preferred_region": "asia-southeast1",  
                "fallback_regions": ["asia-southeast1"],
                "status": "stable",
                "description": "優化無線電和電話語音辨識效果的模型"
            },
            "chirp": {
                "display_name": "Chirp (Universal)",
                "supported_regions": ["global", "us", "eu", "asia"],
                "preferred_region": "global",  # ✅ 改為 global
                "fallback_regions": ["us", "eu", "asia"],
                "status": "stable",
                "description": "第一代chirp模型"
            },
            "chirp_2": {
                "display_name": "Chirp 2.0",
                "supported_regions": ["global", "us", "eu"],
                "preferred_region": "global",  # ✅ 改為 global
                "fallback_regions": ["us", "eu"],
                "status": "stable",
                "description": "Chirp 2.0 版本"
            },
            
            "latest_long": {
                "display_name": "Latest Long",
                "supported_regions": ["global", "us", "eu", "asia"],
                "preferred_region": "global",  # ✅ 改為 global
                "fallback_regions": ["us", "eu", "asia"],
                "status": "stable",
                "description": "長音訊優化模型"
            },
            "latest_short": {
                "display_name": "Latest Short",
                "supported_regions": ["global", "us", "eu", "asia"],
                "preferred_region": "global",  # ✅ 改為 global
                "fallback_regions": ["us", "eu", "asia"],
                "status": "stable",
                "description": "短音訊優化模型"
            }
        },
        "region_aliases": {
            "us": "global",           # ✅ us 對應到 global
            "us-central1": "global",  # ✅ us-central1 對應到 global
            "asia-east1": "global",   # ✅ asia-east1 對應到 global
            "europe-west1": "global", # ✅ europe-west1 對應到 global
            "taiwan": "global",       # ✅ taiwan 對應到 global
            "united-states": "global" # ✅ united-states 對應到 global
        },
        "model_aliases": {
            "chirp3": "chirp_3",
            "radio": "chirp_telephony",    # 指向無線電專用模型
            "telephony": "chirp_telephony",
            "universal": "chirp_3",        # 預設通用也改用 V3
            "default": "chirp_3"
        }
    }
    
    def __init__(self, project_id: str = None):
        """初始化配置管理器"""
        self.logger = logger
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT', 'dazzling-seat-315406')
        self.config = self._load_config()
        
        if GOOGLE_CLIENT_AVAILABLE:
            try:
                self.client = SpeechClient()
            except Exception as e:
                self.logger.warning(f"無法建立 Speech 客戶端: {e}")
                self.client = None
        else:
            self.client = None
    
    def _load_config(self) -> Dict:
        """載入配置檔案"""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info(f"載入配置檔案 (更新於: {config.get('last_updated')})")
                return config
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
            self.logger.info(f"配置已儲存: {self.CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"儲存配置失敗: {e}")
    
    def get_optimal_config(self, model: str, preferred_region: str = None) -> Tuple[str, str]:
        """獲取最佳配置"""
        normalized_model = self._normalize_model_name(model)
        normalized_region = self._normalize_region_name(preferred_region)
        
        model_config = self.config['models'].get(normalized_model)
        if not model_config:
            self.logger.warning(f"未知模型 '{model}'，使用預設 'chirp'")
            normalized_model = "chirp"
            model_config = self.config['models']['chirp']
        
        optimal_region = self._select_optimal_region(model_config, normalized_region)
        
        self.logger.info(f"✅ 配置: {model} -> {normalized_model} @ {optimal_region}")
        return normalized_model, optimal_region
    
    def _normalize_model_name(self, model: str) -> str:
        """正規化模型名稱"""
        if not model:
            return "chirp"
        model = model.lower().strip()
        return self.config['model_aliases'].get(model, model if model in self.config['models'] else "chirp")
    
    def _normalize_region_name(self, region: str) -> Optional[str]:
        """正規化區域名稱"""
        if not region:
            return None
        region = region.lower().strip()
        # ✅ 修正：所有區域都對應到 global
        return self.config['region_aliases'].get(region, region if region in ['global', 'us', 'eu', 'asia'] else None)
    
    def _select_optimal_region(self, model_config: Dict, preferred_region: Optional[str]) -> str:
        """選擇最佳區域"""
        supported_regions = model_config.get('supported_regions', ['global'])
        
        if preferred_region and preferred_region in supported_regions:
            return preferred_region
        
        preferred = model_config.get('preferred_region', 'global')  # ✅ 預設改為 global
        if preferred in supported_regions:
            return preferred
        
        for region in model_config.get('fallback_regions', []):
            if region in supported_regions:
                return region
        
        return supported_regions[0] if supported_regions else 'global'  # ✅ 回退改為 global
    
    def print_config_summary(self):
        """列印配置摘要"""
        print("\n" + "=" * 80)
        print("Google STT 配置摘要（Global 區域版）")
        print("=" * 80)
        print(f"最後更新: {self.config.get('last_updated', '未知')}\n")
        print("可用模型:")
        for name, cfg in self.config['models'].items():
            status_emoji = {'stable': '✅', 'beta': '🧪', 'deprecated': '⚠️'}.get(cfg.get('status'), '❓')
            print(f"\n  {status_emoji} {name} ({cfg.get('display_name')})")
            print(f"     狀態: {cfg.get('status')}")
            print(f"     區域: {', '.join(cfg.get('supported_regions', []))}")
            print(f"     偏好: {cfg.get('preferred_region')}")
            print(f"     說明: {cfg.get('description', 'N/A')}")
        print("\n" + "=" * 80)
    
    def test_configurations(self):
        """測試各種配置組合"""
        print("\n" + "=" * 80)
        print("測試配置轉換")
        print("=" * 80)
        
        test_cases = [
            ("chirp", "global"),
            ("chirp", "us"),
            ("chirp_3", "taiwan"),
            ("latest_long", "asia"),
            ("unknown_model", "eu"),
        ]
        
        for model, region in test_cases:
            print(f"\n測試: model={model}, region={region}")
            normalized_model, optimal_region = self.get_optimal_config(model, region)
            print(f"  結果: {normalized_model} @ {optimal_region}")
        
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
    print("║" + " " * 15 + "Google STT 配置管理器（Global 區域版）" + " " * 23 + "║")
    print("╚" + "=" * 78 + "╝")
    
    manager = create_default_config()
    manager.print_config_summary()
    manager.test_configurations()
    
    print("\n✅ 配置管理器測試完成！\n")
    print("配置檔案位置:", manager.CONFIG_FILE)
    print("\n下一步:")
    print("  python scripts/batch_inference.py --test-case Test_02_TMRT --model google_stt")
    print("")


if __name__ == "__main__":
    main()