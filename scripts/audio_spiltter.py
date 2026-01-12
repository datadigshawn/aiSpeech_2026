"""
音檔切分器 (Audio Splitter)
功能：
1. 使用 VAD 智慧切分音檔
2. 建立全局時間基準 (session_metadata.json)
3. 建立切片時間戳索引 (chunks_timeline.json)
4. 只儲存語音段（節省 80% 空間和成本）
"""

import wave
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import argparse

from utils.vad_processor import VADProcessor
from utils.timestamp_manager import TimestampManager
from utils.logger import get_logger

logger = get_logger(__name__)


class AudioSplitter:
    """音檔切分器"""
    
    def __init__(
        self,
        vad_engine: str = "silero",
        vad_threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
        max_chunk_duration_s: float = 30.0
    ):
        """
        初始化音檔切分器
        
        Args:
            vad_engine: VAD 引擎 ("silero" 或 "webrtc")
            vad_threshold: VAD 閾值
            min_speech_duration_ms: 最小語音段長度
            min_silence_duration_ms: 最小靜音段長度
            max_chunk_duration_s: 單一切片最大長度（秒）
        """
        self.vad_engine = vad_engine
        self.max_chunk_duration_ms = int(max_chunk_duration_s * 1000)
        
        # 初始化 VAD 處理器
        self.vad = VADProcessor(
            engine=vad_engine,
            threshold=vad_threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms
        )
        
        # 初始化時間戳管理器
        self.timestamp_manager = TimestampManager()
        
        logger.info(f"音檔切分器初始化完成")
        logger.info(f"  VAD 引擎: {vad_engine}")
        logger.info(f"  最大切片長度: {max_chunk_duration_s}s")
    
    def split_audio(
        self,
        audio_file: str,
        output_dir: str,
        test_case: str,
        create_timeline: bool = True
    ) -> Dict:
        """
        切分音檔
        
        Args:
            audio_file: 原始音檔路徑
            output_dir: 輸出目錄
            test_case: 測試案名稱
            create_timeline: 是否建立時間軸索引
        
        Returns:
            切分結果統計
        """
        audio_path = Path(audio_file)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"開始切分音檔: {audio_path.name}")
        
        # 1. 建立 Session Metadata (全局時間基準)
        logger.info("步驟 1/4: 建立 Session 時間基準...")
        session_metadata = self.timestamp_manager.create_session_metadata(
            audio_file=str(audio_path),
            test_case=test_case,
            mode="batch",
            output_dir=audio_path.parent
        )
        
        # 2. 使用 VAD 檢測語音段
        logger.info("步驟 2/4: 執行 VAD 語音檢測...")
        speech_segments = self.vad.detect_speech_segments(
            str(audio_path),
            return_seconds=False  # 使用毫秒
        )
        
        logger.info(f"檢測到 {len(speech_segments)} 個語音段")
        
        # 3. 分割過長的語音段
        logger.info("步驟 3/4: 分割語音段...")
        split_segments = self._split_long_segments(speech_segments)
        
        logger.info(f"分割後共 {len(split_segments)} 個切片")
        
        # 4. 儲存音訊切片
        logger.info("步驟 4/4: 儲存音訊切片...")
        chunks_info = self._save_chunks(
            audio_file=str(audio_path),
            segments=split_segments,
            output_dir=output_path
        )
        
        # 5. 建立時間軸索引
        if create_timeline:
            logger.info("建立切片時間軸索引...")
            timeline = self.timestamp_manager.create_chunks_timeline(
                chunks_info=chunks_info,
                session_metadata=session_metadata,
                output_dir=output_path
            )
        
        # 統計結果
        total_duration_ms = session_metadata["audio_properties"]["duration_seconds"] * 1000
        speech_duration_ms = sum(chunk["duration_ms"] for chunk in chunks_info if chunk["is_speech"])
        silence_duration_ms = total_duration_ms - speech_duration_ms
        
        stats = {
            "total_chunks": len(chunks_info),
            "speech_chunks": sum(1 for chunk in chunks_info if chunk["is_speech"]),
            "silence_chunks": sum(1 for chunk in chunks_info if not chunk["is_speech"]),
            "total_duration_s": round(total_duration_ms / 1000, 2),
            "speech_duration_s": round(speech_duration_ms / 1000, 2),
            "silence_duration_s": round(silence_duration_ms / 1000, 2),
            "speech_ratio": round(speech_duration_ms / total_duration_ms, 4) if total_duration_ms > 0 else 0,
            "storage_savings": round(silence_duration_ms / total_duration_ms, 4) if total_duration_ms > 0 else 0
        }
        
        logger.info("=" * 60)
        logger.info("切分完成！統計資訊：")
        logger.info(f"  總切片數: {stats['total_chunks']}")
        logger.info(f"  語音段數: {stats['speech_chunks']}")
        logger.info(f"  靜音段數: {stats['silence_chunks']}")
        logger.info(f"  總時長: {stats['total_duration_s']:.2f}s")
        logger.info(f"  語音時長: {stats['speech_duration_s']:.2f}s ({stats['speech_ratio']:.1%})")
        logger.info(f"  靜音時長: {stats['silence_duration_s']:.2f}s")
        logger.info(f"  儲存空間節省: {stats['storage_savings']:.1%}")
        logger.info("=" * 60)
        
        return stats
    
    def _split_long_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        分割過長的語音段
        
        Args:
            segments: VAD 檢測到的語音段
        
        Returns:
            分割後的語音段列表
        """
        split_segments = []
        
        for seg in segments:
            start_ms = seg['start']
            end_ms = seg['end']
            duration_ms = end_ms - start_ms
            
            if duration_ms <= self.max_chunk_duration_ms:
                # 不需要分割
                split_segments.append(seg)
            else:
                # 需要分割成多個片段
                num_chunks = int(np.ceil(duration_ms / self.max_chunk_duration_ms))
                chunk_size = duration_ms / num_chunks
                
                for i in range(num_chunks):
                    chunk_start = start_ms + int(i * chunk_size)
                    chunk_end = start_ms + int((i + 1) * chunk_size)
                    
                    split_segments.append({
                        'start': chunk_start,
                        'end': chunk_end
                    })
                
                logger.debug(f"語音段 {start_ms}-{end_ms} 被分割為 {num_chunks} 個切片")
        
        return split_segments
    
    def _save_chunks(
        self,
        audio_file: str,
        segments: List[Dict],
        output_dir: Path
    ) -> List[Dict]:
        """
        儲存音訊切片
        
        Args:
            audio_file: 原始音檔
            segments: 語音段列表
            output_dir: 輸出目錄
        
        Returns:
            切片資訊列表
        """
        # 讀取原始音檔
        with wave.open(audio_file, 'rb') as wf:
            sample_rate = wf.getframerate()
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            
            # 讀取所有音訊資料
            audio_data = wf.readframes(wf.getnframes())
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            if num_channels > 1:
                # 轉換為單聲道（取平均）
                audio_array = audio_array.reshape(-1, num_channels).mean(axis=1).astype(np.int16)
                num_channels = 1
                logger.info("已將多聲道音訊轉換為單聲道")
        
        chunks_info = []
        current_offset_ms = 0
        
        for i, seg in enumerate(segments, 1):
            chunk_id = f"{i:03d}"
            
            start_ms = seg['start']
            end_ms = seg['end']
            duration_ms = end_ms - start_ms
            
            # 計算樣本位置
            start_sample = int(start_ms * sample_rate / 1000)
            end_sample = int(end_ms * sample_rate / 1000)
            
            # 提取音訊片段
            chunk_audio = audio_array[start_sample:end_sample]
            
            # 儲存為 WAV 檔案
            chunk_filename = f"chunk_{chunk_id}.wav"
            chunk_path = output_dir / chunk_filename
            
            with wave.open(str(chunk_path), 'wb') as chunk_wf:
                chunk_wf.setnchannels(num_channels)
                chunk_wf.setsampwidth(sample_width)
                chunk_wf.setframerate(sample_rate)
                chunk_wf.writeframes(chunk_audio.tobytes())
            
            # 記錄切片資訊
            chunk_info = {
                "chunk_id": chunk_id,
                "offset_ms": start_ms,
                "duration_ms": duration_ms,
                "is_speech": True,
                "audio_file": chunk_filename
            }
            chunks_info.append(chunk_info)
            
            logger.debug(f"已儲存切片 {chunk_id}: {start_ms}ms - {end_ms}ms ({duration_ms}ms)")
        
        return chunks_info


def main():
    """命令列介面"""
    parser = argparse.ArgumentParser(description="音檔切分器")
    parser.add_argument(
        "audio_file",
        help="原始音檔路徑"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="輸出目錄"
    )
    parser.add_argument(
        "--test-case",
        default="Test_01_TMRT",
        help="測試案名稱 (預設: Test_01_TMRT)"
    )
    parser.add_argument(
        "--vad-engine",
        choices=["silero", "webrtc"],
        default="silero",
        help="VAD 引擎 (預設: silero)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="VAD 閾值 (預設: 0.5)"
    )
    parser.add_argument(
        "--max-chunk-duration",
        type=float,
        default=30.0,
        help="單一切片最大長度（秒）(預設: 30.0)"
    )
    
    args = parser.parse_args()
    
    # 建立切分器
    splitter = AudioSplitter(
        vad_engine=args.vad_engine,
        vad_threshold=args.threshold,
        max_chunk_duration_s=args.max_chunk_duration
    )
    
    # 執行切分
    stats = splitter.split_audio(
        audio_file=args.audio_file,
        output_dir=args.output_dir,
        test_case=args.test_case
    )
    
    print("\n切分完成！")


if __name__ == "__main__":
    main()