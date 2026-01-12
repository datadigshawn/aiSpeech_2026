#!/bin/bash
# Test_02_TMRT Google STT 快速啟動腳本

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║               Test_02_TMRT Google STT 批次辨識 - 快速啟動                    ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 切換到專案根目錄
cd /Users/apple/Projects/aiSpeech

# 啟動虛擬環境
echo "🔧 啟動虛擬環境..."
source ~/miniforge3/etc/profile.d/conda.sh
conda activate aiSpeech_project_nightly

# 檢查環境變數
echo ""
echo "🔍 檢查環境設定..."
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "⚠️  GOOGLE_APPLICATION_CREDENTIALS 未設定"
    echo "正在自動設定..."
    export GOOGLE_APPLICATION_CREDENTIALS=/Users/apple/Projects/aiSpeech/utils/google-speech-key.json
    echo "✅ 已設定為: $GOOGLE_APPLICATION_CREDENTIALS"
else
    echo "✅ GOOGLE_APPLICATION_CREDENTIALS 已設定"
fi

# 檢查金鑰檔案
echo ""
echo "🔑 檢查 Google Cloud 金鑰..."
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "❌ 錯誤: 金鑰檔案不存在: $GOOGLE_APPLICATION_CREDENTIALS"
    echo "請確認檔案路徑是否正確"
    exit 1
else
    echo "✅ 金鑰檔案存在"
fi

# 檢查音檔
echo ""
echo "🎵 檢查音檔..."
AUDIO_COUNT=$(ls experiments/Test_02_TMRT/souce_audio/*.wav 2>/dev/null | wc -l)
if [ $AUDIO_COUNT -eq 0 ]; then
    echo "❌ 錯誤: 未找到音檔"
    echo "請確認路徑: experiments/Test_02_TMRT/souce_audio/"
    exit 1
else
    echo "✅ 找到 $AUDIO_COUNT 個音檔"
fi

# 確認是否執行
echo ""
echo "準備開始批次辨識..."
echo "音檔數量: $AUDIO_COUNT"
echo "預估耗時: 約 $((AUDIO_COUNT * 13 / 60)) 分鐘"
echo ""
read -p "是否繼續？(y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 執行批次辨識
echo ""
echo "🚀 開始執行批次辨識..."
echo "============================================================"
python scripts/batch_google_stt_test02.py

# 檢查執行結果
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "✅ 批次辨識完成！"
    echo ""
    echo "📁 結果位置:"
    echo "   experiments/Test_02_TMRT/ASR_Evaluation/google_stt_output/"
    echo ""
    echo "📊 摘要檔案:"
    echo "   experiments/Test_02_TMRT/ASR_Evaluation/google_stt_summary.txt"
    echo ""
    echo "下一步："
    echo "1. 查看結果: cat experiments/Test_02_TMRT/ASR_Evaluation/google_stt_summary.txt"
    echo "2. 建立 Ground Truth (人工聽打)"
    echo "3. 執行評測"
    echo ""
else
    echo ""
    echo "❌ 執行失敗"
    echo "請檢查日誌: logs/BatchGoogleSTTProcessor_errors.log"
    exit 1
fi
