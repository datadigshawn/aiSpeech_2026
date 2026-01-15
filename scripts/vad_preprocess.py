#!/usr/bin/env python3
"""
VAD 預處理腳本 - 完整實作
用於處理無線電音訊，去除靜音和噪音，切分音檔
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import json
from datetime import datetime
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 嘗試導入 WebRTC VAD
try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    logger.warning("WebRTC VAD 未安裝，將使用基於能量的 VAD")

# 嘗試導入 Silero VAD
try:
    import torch
    SILERO_AVAILABLE = True
except ImportError:
    SILERO_AVAILABLE = False
    logger.warning("Silero VAD 未安裝 (需要 PyTorch)")


class VADPreprocessor:
    """VAD 預處理器"""
    
    def __init__(
        self,
        vad_method: str = "energy",  # "energy", "webrtc", "silero"
        vad_threshold: float = 0.5,
        min_speech_duration: float = 0.3,  # 最短語音段（秒）
        min_silence_duration: float = 0.5,  # 最短靜音段（秒）
        max_chunk_length: float = 50.0,    # 最大切段長度（秒）
        sample_rate: int = 16000
    ):
        """初始化 VAD 預處理器"""
        self.vad_method = vad_method
        self.vad_threshold = vad_threshold
        self.min_speech_duration = min_speech_duration
        self.min_silence_duration = min_silence_duration
        self.max_chunk_length = max_chunk_length
        self.sample_rate = sample_rate
        
        # 初始化對應的 VAD
        if vad_method == "webrtc":
            if not WEBRTC_AVAILABLE:
                logger.warning("WebRTC VAD 不可用，回退到能量檢測")
                self.vad_method = "energy"
            else:
                # aggressiveness: 0=寬鬆, 3=嚴格
                # vad_threshold 0.6 對應 aggressiveness 2-3
                aggressiveness = min(3, max(0, int(vad_threshold * 4)))
                self.vad = webrtcvad.Vad(aggressiveness)
                logger.info(f"✅ 使用 WebRTC VAD (aggressiveness={aggressiveness})")
        
        elif vad_method == "silero":
            if not SILERO_AVAILABLE:
                logger.warning("Silero VAD 不可用，回退到能量檢測")
                self.vad_method = "energy"
            else:
                self._init_silero()
                logger.info("✅ 使用 Silero VAD")
        
        else:
            logger.info("✅ 使用基於能量的 VAD")
    
    def _init_silero(self):
        """初始化 Silero VAD"""
        try:
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            self.silero_model = model
            self.get_speech_timestamps = utils[0]
            logger.info("Silero VAD 模型載入成功")
        except Exception as e:
            logger.error(f"Silero VAD 載入失敗: {e}")
            logger.warning("回退到能量檢測")
            self.vad_method = "energy"
    
    def detect_speech_segments_energy(
        self, 
        audio: AudioSegment
    ) -> List[Tuple[int, int]]:
        """
        使用能量檢測法檢測語音段
        
        Returns:
            List of (start_ms, end_ms) tuples
        """
        # 計算靜音閾值
        # dBFS 通常在 -60 到 0 之間
        # vad_threshold 0.5 → -40 dBFS
        # vad_threshold 0.6 → -35 dBFS
        silence_thresh = -60 + (self.vad_threshold * 50)
        
        # 使用 pydub 的 detect_nonsilent
        speech_segments = detect_nonsilent(
            audio,
            min_silence_len=int(self.min_silence_duration * 1000),  # 轉為毫秒
            silence_thresh=silence_thresh,
            seek_step=10  # 10ms 步長
        )
        
        # 過濾太短的語音段
        min_speech_ms = int(self.min_speech_duration * 1000)
        filtered_segments = [
            (start, end) for start, end in speech_segments
            if (end - start) >= min_speech_ms
        ]
        
        logger.info(f"   檢測到 {len(filtered_segments)} 個語音段")
        return filtered_segments
    
    def detect_speech_segments_webrtc(
        self, 
        audio: AudioSegment
    ) -> List[Tuple[int, int]]:
        """
        使用 WebRTC VAD 檢測語音段
        
        Returns:
            List of (start_ms, end_ms) tuples
        """
        # WebRTC VAD 需要 16-bit PCM
        # 轉換音訊
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        
        # 準備音訊數據
        raw_data = audio.raw_data
        sample_rate = audio.frame_rate
        
        # WebRTC VAD 使用 10/20/30ms 幀
        frame_duration_ms = 30
        frame_size = int(sample_rate * frame_duration_ms / 1000) * 2  # 2 bytes per sample
        
        # 檢測語音
        speech_frames = []
        for i in range(0, len(raw_data), frame_size):
            frame = raw_data[i:i + frame_size]
            if len(frame) < frame_size:
                break
            
            is_speech = self.vad.is_speech(frame, sample_rate)
            speech_frames.append(is_speech)
        
        # 合併連續的語音幀
        segments = []
        start_frame = None
        
        for i, is_speech in enumerate(speech_frames):
            if is_speech and start_frame is None:
                start_frame = i
            elif not is_speech and start_frame is not None:
                # 語音段結束
                start_ms = start_frame * frame_duration_ms
                end_ms = i * frame_duration_ms
                
                # 檢查長度
                if (end_ms - start_ms) >= (self.min_speech_duration * 1000):
                    segments.append((start_ms, end_ms))
                
                start_frame = None
        
        # 處理最後一段
        if start_frame is not None:
            start_ms = start_frame * frame_duration_ms
            end_ms = len(speech_frames) * frame_duration_ms
            if (end_ms - start_ms) >= (self.min_speech_duration * 1000):
                segments.append((start_ms, end_ms))
        
        logger.info(f"   檢測到 {len(segments)} 個語音段")
        return segments
    
    def detect_speech_segments_silero(
        self, 
        audio: AudioSegment
    ) -> List[Tuple[int, int]]:
        """
        使用 Silero VAD 檢測語音段
        
        Returns:
            List of (start_ms, end_ms) tuples
        """
        # 轉換為 Silero 所需格式
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        # 轉換為 float32 numpy array
        samples = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(samples)
        
        # 檢測語音時間戳
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor,
            self.silero_model,
            threshold=self.vad_threshold,
            min_speech_duration_ms=int(self.min_speech_duration * 1000),
            min_silence_duration_ms=int(self.min_silence_duration * 1000),
            sampling_rate=16000
        )
        
        # 轉換為毫秒格式
        segments = [
            (int(seg['start'] / 16), int(seg['end'] / 16))  # samples to ms
            for seg in speech_timestamps
        ]
        
        logger.info(f"   檢測到 {len(segments)} 個語音段")
        return segments
    
    def split_long_segments(
        self, 
        segments: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """
        切分過長的語音段
        
        Args:
            segments: List of (start_ms, end_ms)
        
        Returns:
            切分後的語音段
        """
        max_length_ms = int(self.max_chunk_length * 1000)
        split_segments = []
        
        for start_ms, end_ms in segments:
            duration = end_ms - start_ms
            
            if duration <= max_length_ms:
                split_segments.append((start_ms, end_ms))
            else:
                # 需要切分
                num_chunks = int(np.ceil(duration / max_length_ms))
                chunk_length = duration / num_chunks
                
                for i in range(num_chunks):
                    chunk_start = start_ms + int(i * chunk_length)
                    chunk_end = start_ms + int((i + 1) * chunk_length)
                    split_segments.append((chunk_start, chunk_end))
                
                logger.info(f"   長音段 ({duration/1000:.1f}s) 切分為 {num_chunks} 段")
        
        return split_segments
    
    def process_audio_file(
        self, 
        input_path: Path,
        output_dir: Path
    ) -> Dict:
        """
        處理單個音訊檔案
        
        Returns:
            處理結果字典
        """
        logger.info(f"處理: {input_path.name}")
        
        try:
            # 載入音訊
            audio = AudioSegment.from_wav(input_path)
            original_duration = len(audio) / 1000.0  # 秒
            
            logger.info(f"   原始長度: {original_duration:.2f}秒")
            logger.info(f"   取樣率: {audio.frame_rate} Hz")
            logger.info(f"   聲道數: {audio.channels}")
            
            # 檢測語音段
            if self.vad_method == "webrtc":
                segments = self.detect_speech_segments_webrtc(audio)
            elif self.vad_method == "silero":
                segments = self.detect_speech_segments_silero(audio)
            else:
                segments = self.detect_speech_segments_energy(audio)
            
            if not segments:
                logger.warning(f"   ⚠️  未檢測到語音段")
                return {
                    "filename": input_path.name,
                    "status": "no_speech",
                    "original_duration": original_duration,
                    "chunks": 0
                }
            
            # 切分長音段
            segments = self.split_long_segments(segments)
            
            # 儲存切分後的音檔
            chunks_info = []
            for i, (start_ms, end_ms) in enumerate(segments):
                chunk = audio[start_ms:end_ms]
                
                # 檔名格式: original_name_chunk_001.wav
                chunk_filename = f"{input_path.stem}_chunk_{i+1:03d}.wav"
                chunk_path = output_dir / chunk_filename
                
                # 匯出
                chunk.export(chunk_path, format="wav")
                
                chunk_duration = (end_ms - start_ms) / 1000.0
                chunks_info.append({
                    "filename": chunk_filename,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "duration": chunk_duration
                })
                
                logger.info(f"   ✅ 切段 {i+1}: {chunk_duration:.2f}秒 ({start_ms}ms - {end_ms}ms)")
            
            # 計算統計
            total_speech_duration = sum(c["duration"] for c in chunks_info)
            speech_ratio = total_speech_duration / original_duration
            
            logger.info(f"   語音總長: {total_speech_duration:.2f}秒 ({speech_ratio*100:.1f}%)")
            
            return {
                "filename": input_path.name,
                "status": "success",
                "original_duration": original_duration,
                "speech_duration": total_speech_duration,
                "speech_ratio": speech_ratio,
                "chunks": len(chunks_info),
                "chunks_info": chunks_info
            }
        
        except Exception as e:
            logger.error(f"   ❌ 處理失敗: {e}")
            return {
                "filename": input_path.name,
                "status": "error",
                "error": str(e)
            }
    
    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path
    ) -> Dict:
        """
        處理整個目錄
        
        Returns:
            處理結果統計
        """
        # 創建輸出目錄
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 找到所有音檔
        audio_files = list(input_dir.glob("*.wav"))
        
        if not audio_files:
            logger.error(f"❌ 在 {input_dir} 中找不到 .wav 檔案")
            return {}
        
        logger.info(f"\n{'='*70}")
        logger.info(f"VAD 預處理開始")
        logger.info(f"{'='*70}")
        logger.info(f"輸入目錄: {input_dir}")
        logger.info(f"輸出目錄: {output_dir}")
        logger.info(f"找到 {len(audio_files)} 個音檔")
        logger.info(f"VAD 方法: {self.vad_method}")
        logger.info(f"VAD 閾值: {self.vad_threshold}")
        logger.info(f"最短語音段: {self.min_speech_duration}秒")
        logger.info(f"最短靜音段: {self.min_silence_duration}秒")
        logger.info(f"最大切段長度: {self.max_chunk_length}秒")
        logger.info(f"{'='*70}\n")
        
        # 處理每個檔案
        results = []
        for audio_file in sorted(audio_files):
            result = self.process_audio_file(audio_file, output_dir)
            results.append(result)
        
        # 統計
        total_files = len(results)
        success_files = sum(1 for r in results if r["status"] == "success")
        total_chunks = sum(r.get("chunks", 0) for r in results)
        total_original_duration = sum(r.get("original_duration", 0) for r in results)
        total_speech_duration = sum(r.get("speech_duration", 0) for r in results)
        
        # 儲存處理報告
        report = {
            "timestamp": datetime.now().isoformat(),
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "vad_config": {
                "method": self.vad_method,
                "threshold": self.vad_threshold,
                "min_speech_duration": self.min_speech_duration,
                "min_silence_duration": self.min_silence_duration,
                "max_chunk_length": self.max_chunk_length
            },
            "statistics": {
                "total_files": total_files,
                "success_files": success_files,
                "total_chunks": total_chunks,
                "original_duration": total_original_duration,
                "speech_duration": total_speech_duration,
                "speech_ratio": total_speech_duration / total_original_duration if total_original_duration > 0 else 0
            },
            "files": results
        }
        
        report_path = output_dir / "vad_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 輸出總結
        logger.info(f"\n{'='*70}")
        logger.info(f"VAD 預處理完成")
        logger.info(f"{'='*70}")
        logger.info(f"處理檔案: {success_files}/{total_files}")
        logger.info(f"生成切段: {total_chunks}")
        logger.info(f"原始總長: {total_original_duration:.2f}秒")
        logger.info(f"語音總長: {total_speech_duration:.2f}秒")
        logger.info(f"語音比例: {(total_speech_duration/total_original_duration)*100:.1f}%")
        logger.info(f"處理報告: {report_path}")
        logger.info(f"{'='*70}\n")
        
        return report


def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description="VAD 預處理 - 語音活動檢測與音訊切分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 基本使用（能量檢測）
  python vad_preprocess.py \\
      --input-dir experiments/Test_02_TMRT/source_audio \\
      --output-dir experiments/Test_02_TMRT/vad_chunks
  
  # 使用 WebRTC VAD（更準確）
  python vad_preprocess.py \\
      --input-dir experiments/Test_02_TMRT/source_audio \\
      --output-dir experiments/Test_02_TMRT/vad_chunks \\
      --vad-method webrtc \\
      --vad-threshold 0.6
  
  # 調整參數
  python vad_preprocess.py \\
      --input-dir experiments/Test_02_TMRT/source_audio \\
      --output-dir experiments/Test_02_TMRT/vad_chunks \\
      --vad-threshold 0.6 \\
      --min-speech-duration 0.3 \\
      --min-silence-duration 0.5 \\
      --max-chunk-length 50
        """
    )
    
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="輸入音訊目錄"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="輸出切分音訊目錄"
    )
    
    parser.add_argument(
        "--vad-method",
        type=str,
        default="energy",
        choices=["energy", "webrtc", "silero"],
        help="VAD 方法 (預設: energy)"
    )
    
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=0.5,
        help="VAD 閾值，0.5-0.7 較合適 (預設: 0.5)"
    )
    
    parser.add_argument(
        "--min-speech-duration",
        type=float,
        default=0.3,
        help="最短語音段長度（秒）(預設: 0.3)"
    )
    
    parser.add_argument(
        "--min-silence-duration",
        type=float,
        default=0.5,
        help="最短靜音段長度（秒）(預設: 0.5)"
    )
    
    parser.add_argument(
        "--max-chunk-length",
        type=float,
        default=50.0,
        help="最大切段長度（秒）(預設: 50)"
    )
    
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="目標取樣率 (預設: 16000)"
    )
    
    args = parser.parse_args()
    
    # 檢查輸入目錄
    if not args.input_dir.exists():
        logger.error(f"❌ 輸入目錄不存在: {args.input_dir}")
        sys.exit(1)
    
    # 創建處理器
    processor = VADPreprocessor(
        vad_method=args.vad_method,
        vad_threshold=args.vad_threshold,
        min_speech_duration=args.min_speech_duration,
        min_silence_duration=args.min_silence_duration,
        max_chunk_length=args.max_chunk_length,
        sample_rate=args.sample_rate
    )
    
    # 處理
    processor.process_directory(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()