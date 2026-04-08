#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
英语学习闪卡生成器 - 微信小程序风格
支持日期化配置文件和输出文件
"""

import os
import re
import json
import glob
from datetime import datetime
import sys

def extract_date_from_filename(filename):
    """
    从文件名中提取日期信息
    支持格式: config_YYYYMMDD.txt 或 config.txt
    """
    # 尝试从文件名中提取日期
    # 兼容:
    # - config_YYYYMMDD.txt
    # - <anything>_YYYYMMDD.txt
    match = re.search(r'(\d{8})\.txt$', os.path.basename(filename))
    if match:
        return match.group(1)
    
    # 如果没有日期信息，使用当前日期
    return datetime.now().strftime("%Y%m%d")

def parse_config_file(config_path):
    """
    解析配置文件，提取中英文对照内容和元数据
    配置文件格式：每行"英文|中文"
    元数据格式: # KEY: VALUE
    """
    flashcards = []
    metadata = {
        "grade": "通用",
        "date": extract_date_from_filename(config_path)
    }
    
    if not os.path.exists(config_path):
        print(f"错误: 配置文件 {config_path} 不存在")
        return metadata, flashcards
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 解析元数据（非注释形式）：grade: xxx / date: yyyymmdd
            match_plain_meta = re.match(r'(\w+)\s*:\s*(.+)', line)
            if match_plain_meta:
                key = match_plain_meta.group(1).lower()
                value = match_plain_meta.group(2).strip()
                if key in ("grade", "date"):
                    metadata[key] = value
                    continue

            # 解析元数据
            if line.startswith('#'):
                # 检查是否是元数据格式: # KEY: VALUE
                match = re.match(r'#\s*(\w+)\s*:\s*(.+)', line)
                if match:
                    key = match.group(1).lower()
                    value = match.group(2).strip()
                    metadata[key] = value
                continue
            
            # 使用正则表达式匹配英文和中文部分
            match = re.match(r'(.+?)\|(.+)', line)
            if match:
                english = match.group(1).strip()
                chinese = match.group(2).strip()
                flashcards.append({"english": english, "chinese": chinese})
            else:
                print(f"警告: 跳过无法解析的行: {line}")
    
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
    
    return metadata, flashcards

def parse_config_text(config_text, default_date=None):
    """
    Parse config from a multi-line string (same rules as parse_config_file).
    default_date: used for metadata['date'] if not set in text (YYYYMMDD string).
    """
    flashcards = []
    metadata = {
        "grade": "通用",
        "date": default_date or datetime.now().strftime("%Y%m%d"),
    }
    if not config_text:
        return metadata, flashcards
    try:
        for raw in config_text.splitlines():
            line = raw.strip()
            if not line:
                continue
            match_plain_meta = re.match(r"(\w+)\s*:\s*(.+)", line)
            if match_plain_meta:
                key = match_plain_meta.group(1).lower()
                value = match_plain_meta.group(2).strip()
                if key in ("grade", "date"):
                    metadata[key] = value
                    continue
            if line.startswith("#"):
                match = re.match(r"#\s*(\w+)\s*:\s*(.+)", line)
                if match:
                    key = match.group(1).lower()
                    value = match.group(2).strip()
                    metadata[key] = value
                continue  # skip comments and non-card # lines
            match = re.match(r"(.+?)\|(.+)", line)
            if match:
                flashcards.append(
                    {"english": match.group(1).strip(), "chinese": match.group(2).strip()}
                )
            else:
                print(f"警告: 跳过无法解析的行: {line}")
    except Exception as e:
        print(f"解析配置文本时出错: {e}")
    return metadata, flashcards

def generate_html_string(metadata, flashcards):
    """
    Build complete HTML document as a string (for upload / embedding).
    """
    if not flashcards:
        raise ValueError("没有可用的闪卡数据")

    # 构建标题
    title = f"英语学习闪卡-{metadata['grade']}-{metadata['date']}"
    
    # 微信小程序风格的HTML模板
    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>TITLE_PLACEHOLDER</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background-color: #f7f7f7;
            color: #333;
            line-height: 1.6;
            max-width: 500px;
            margin: 0 auto;
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }
        
        /* 微信小程序样式 */
        .weui-tab {
            position: relative;
            height: 100vh;
            overflow: hidden;
        }
        
        .weui-tab__panel {
            box-sizing: border-box;
            padding-bottom: 55px;
            overflow: auto;
            -webkit-overflow-scrolling: touch;
            height: calc(100vh - 55px);
        }
        
        .weui-tabbar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            height: 55px;
            background-color: #f7f7f7;
            z-index: 500;
            border-top: 1px solid #e5e5e5;
            max-width: 500px;
            margin: 0 auto;
        }
        
        .weui-tabbar__item {
            flex: 1;
            text-align: center;
            padding: 5px 0 0;
            font-size: 0;
            color: #999;
        }
        
        .weui-tabbar__icon {
            display: inline-block;
            width: 27px;
            height: 27px;
        }
        
        .weui-tabbar__label {
            font-size: 10px;
            line-height: 1.8;
            color: #999;
        }
        
        .weui-tabbar__item.weui-bar__item_on {
            color: #07C160;
        }
        
        .weui-tabbar__item.weui-bar__item_on .weui-tabbar__label {
            color: #07C160;
        }
        
        /* 页面内容 */
        .page {
            padding: 15px;
            background: #fff;
            border-radius: 12px;
            margin: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }
        
        .page-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            padding-left: 5px;
            border-left: 3px solid #07C160;
        }
        
        /* 卡片样式 */
        .card-container {
            perspective: 1000px;
            height: 280px;
            margin-bottom: 20px;
        }
        
        .card {
            position: relative;
            width: 100%;
            height: 100%;
            transition: transform 0.3s;
            transform-style: preserve-3d;
            cursor: pointer;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        .card.flipped {
            transform: rotateY(180deg);
        }
        
        .card-face {
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .card-front {
            background: linear-gradient(135deg, #07C160, #05a75a);
            color: white;
        }
        
        .card-back {
            background: linear-gradient(135deg, #10aeff, #0f93e0);
            color: white;
            transform: rotateY(180deg);
        }
        
        .card-content {
            font-size: 22px;
            text-align: center;
            line-height: 1.4;
            font-weight: bold;
        }
        
        .card-note {
            margin-top: 15px;
            font-size: 14px;
            opacity: 0.9;
        }
        
        /* 进度条 */
        .progress-container {
            background-color: #f1f1f1;
            border-radius: 10px;
            margin: 20px 0;
            padding: 12px 15px;
        }
        
        .progress-text {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 14px;
            color: #666;
        }
        
        .progress-bar {
            background-color: #e0e0e0;
            border-radius: 5px;
            height: 10px;
            overflow: hidden;
        }
        
        .progress {
            background: linear-gradient(90deg, #07C160, #10aeff);
            height: 100%;
            width: 12.5%;
            border-radius: 5px;
            transition: width 0.3s ease;
        }
        
        /* 按钮样式 */
        .btn-group {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
        }
        
        .btn {
            padding: 12px 20px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            transition: all 0.3s;
            flex: 1;
            margin: 0 5px;
        }
        
        .btn-primary {
            background-color: #07C160;
            color: white;
        }
        
        .btn-default {
            background-color: #f1f1f1;
            color: #333;
        }
        
        .btn-success {
            background-color: #07C160;
            color: white;
        }
        
        .btn-danger {
            background-color: #ff6b6b;
            color: white;
        }
        
        .btn-warning {
            background-color: #ffa726;
            color: white;
        }
        
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        
        .btn:active {
            transform: scale(0.98);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        /* 提示信息 */
        .hint {
            text-align: center;
            margin: 15px 0;
            font-size: 14px;
            color: #666;
        }
        
        /* 微信顶部导航 */
        .weui-navbar {
            display: flex;
            position: relative;
            z-index: 500;
            background-color: #07C160;
            color: white;
            padding: 10px 15px;
            align-items: center;
        }
        
        .weui-navbar__title {
            text-align: center;
            font-size: 17px;
            font-weight: bold;
            flex: 1;
        }
        
        /* 隐藏非活动页面 */
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* 学习统计 */
        .stats-container {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #07C160;
        }
        
        .stat-label {
            font-size: 14px;
            color: #666;
        }
        
        /* 元数据信息 */
        .metadata-info {
            text-align: center;
            margin: 10px 0;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <!-- 微信顶部导航 -->
    <div class="weui-navbar">
        <div class="weui-navbar__title">TITLE_PLACEHOLDER</div>
    </div>

    <!-- 主内容区域 -->
    <div class="weui-tab">
        <div class="weui-tab__panel">
            <!-- 学习页面 -->
            <div id="study-tab" class="tab-content active">
                <div class="page">
                    <div class="metadata-info">
                        年级: GRADE_PLACEHOLDER | 日期: DATE_PLACEHOLDER
                    </div>
                    
                    <div class="page-title">学习模式</div>
                    
                    <div class="progress-container">
                        <div class="progress-text">
                            <span>学习进度</span>
                            <span id="progress-percent">0%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress" id="progress"></div>
                        </div>
                    </div>
                    
                    <div class="card-container">
                        <div class="card" id="card">
                            <div class="card-face card-front">
                                <div class="card-content" id="chinese-text">加载中...</div>
                                <div class="card-note">点击卡片查看英文</div>
                            </div>
                            <div class="card-face card-back">
                                <div class="card-content" id="english-text">Loading...</div>
                                <div class="card-note">点击卡片返回中文</div>
                            </div>
                        </div>
                    </div>
                    
                    
                    <!-- 熟悉/不熟悉按钮 - 放在卡片下方显著位置 -->
                    <div class="btn-group" style="margin: 25px 0; justify-content: center;">
                        <button class="btn btn-success" id="familiar-btn" style="font-size: 20px; padding: 18px 30px; margin: 0 10px; min-width: 120px;">✓ 熟悉</button>
                        <button class="btn btn-danger" id="unfamiliar-btn" style="font-size: 20px; padding: 18px 30px; margin: 0 10px; min-width: 120px;">✗ 不熟悉</button>
                    </div>
                    
                    <div class="hint" style="margin-top: 15px; font-size: 16px; color: #07C160; font-weight: bold;">请选择熟悉程度以继续学习</div>
                    
                    <!-- 导航按钮 -->
                    <div class="btn-group" style="margin-top: 20px; justify-content: center;">
                        <button class="btn btn-secondary" id="prev-btn" style="font-size: 16px; padding: 12px 20px; margin: 0 5px;">← 上一条</button>
                        <button class="btn btn-secondary" id="next-btn" style="font-size: 16px; padding: 12px 20px; margin: 0 5px;">下一条 →</button>
                    </div>
                    
                    <!-- 控制按钮 -->
                    <div class="btn-group" style="margin-top: 20px;">
                        <button class="btn btn-primary" id="reset-btn" disabled>重新开始</button>
                        <button class="btn btn-warning" id="mode-toggle-btn">切换到错题本模式</button>
                    </div>
                </div>
                
                <div class="page" style="margin-top: 15px;">
                    <div class="page-title">学习统计</div>
                    <div class="stats-container">
                        <div class="stat-item">
                            <div class="stat-value" id="total-cards">0</div>
                            <div class="stat-label">总卡片数</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="current-card">0</div>
                            <div class="stat-label">当前卡片</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="learned-cards">0</div>
                            <div class="stat-label">已学习</div>
                        </div>
                    </div>
                    
                    <div class="stats-container">
                        <div class="stat-item">
                            <div class="stat-value" id="familiar-cards" style="color: #07C160;">0</div>
                            <div class="stat-label">已熟悉</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="unfamiliar-cards" style="color: #ff6b6b;">0</div>
                            <div class="stat-label">需复习</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="mode-indicator">全部</div>
                            <div class="stat-label">当前模式</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 底部标签栏 -->
        <div class="weui-tabbar">
            <div class="weui-tabbar__item weui-bar__item_on">
                <div class="weui-tabbar__icon">
                    <i class="fas fa-book" style="font-size: 24px;"></i>
                </div>
                <div class="weui-tabbar__label">学习</div>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const card = document.getElementById('card');
            const englishText = document.getElementById('english-text');
            const chineseText = document.getElementById('chinese-text');
            // 移除上一张/下一张按钮的引用
            const resetBtn = document.getElementById('reset-btn');
            const familiarBtn = document.getElementById('familiar-btn');
            const unfamiliarBtn = document.getElementById('unfamiliar-btn');
            const modeToggleBtn = document.getElementById('mode-toggle-btn');
            const prevBtn = document.getElementById('prev-btn');
            const nextBtn = document.getElementById('next-btn');
            const progressBar = document.getElementById('progress');
            const progressPercent = document.getElementById('progress-percent');
            const totalCardsSpan = document.getElementById('total-cards');
            const currentCardSpan = document.getElementById('current-card');
            const learnedCardsSpan = document.getElementById('learned-cards');
            const familiarCardsSpan = document.getElementById('familiar-cards');
            const unfamiliarCardsSpan = document.getElementById('unfamiliar-cards');
            const modeIndicatorSpan = document.getElementById('mode-indicator');
            
            // 闪卡数据 - 由Python脚本动态生成
            const flashcards = [FLASHCARDS_DATA];
            
            let currentCardIndex = 0;
            let learnedCards = new Set();
            let familiarCards = new Set();
            let unfamiliarCards = new Set();
            let isMistakeMode = false;
            let currentFlashcards = [...flashcards]; // 当前显示的卡片列表
            
            // 更新卡片内容
            function updateCard() {
                if (currentFlashcards.length === 0) {
                    return;
                }
                
                englishText.textContent = currentFlashcards[currentCardIndex].english;
                chineseText.textContent = currentFlashcards[currentCardIndex].chinese;
                currentCardSpan.textContent = currentCardIndex + 1;
                // 总卡片数始终显示全部卡片的数量，而不是当前模式的卡片数
                totalCardsSpan.textContent = flashcards.length;
                learnedCardsSpan.textContent = learnedCards.size;
                
                // 更新熟悉度统计 - 确保总数正确
                const totalCards = flashcards.length;
                const familiarCount = familiarCards.size;
                const unfamiliarCount = unfamiliarCards.size;
                const unmarkedCount = totalCards - familiarCount - unfamiliarCount;
                
                // 显示熟悉和需复习的数量（需复习 = 不熟悉 + 未标记）
                familiarCardsSpan.textContent = familiarCount;
                unfamiliarCardsSpan.textContent = unfamiliarCount + unmarkedCount;
                
                // 更新模式指示器
                modeIndicatorSpan.textContent = isMistakeMode ? '错题本' : '全部';
                
                // 更新按钮状态
                resetBtn.disabled = currentFlashcards.length === 0;
                // 熟悉/不熟悉按钮始终可用
                familiarBtn.disabled = false;
                unfamiliarBtn.disabled = false;
                // 模式切换按钮始终可用
                modeToggleBtn.disabled = false;
                // 导航按钮状态管理
                prevBtn.disabled = currentCardIndex === 0;
                nextBtn.disabled = currentCardIndex === currentFlashcards.length - 1;
                
                // 更新进度条
                const progress = ((currentCardIndex + 1) / currentFlashcards.length) * 100;
                progressBar.style.width = `${progress}%`;
                progressPercent.textContent = `${progress.toFixed(1)}%`;
                
                // 标记为已学习
                learnedCards.add(currentCardIndex);
                learnedCardsSpan.textContent = learnedCards.size;
            }
            
            // 切换学习模式
            function toggleMode() {
                if (isMistakeMode) {
                    // 从错题本模式切换到全部模式
                    isMistakeMode = false;
                    currentFlashcards = [...flashcards];
                    modeToggleBtn.textContent = '切换到错题本模式';
                    modeToggleBtn.className = 'btn btn-warning';
                } else {
                    // 从全部模式切换到错题本模式
                    isMistakeMode = true;
                    currentFlashcards = flashcards.filter((card, index) => unfamiliarCards.has(index));
                    modeToggleBtn.textContent = '切换到全部模式';
                    modeToggleBtn.className = 'btn btn-primary';
                }
                currentCardIndex = 0;
                learnedCards.clear(); // 清空已学习记录，因为索引会改变
                card.classList.remove('flipped');
                updateCard();
            }
            
            // 进入上一页
            function goToPrevCard() {
                if (currentCardIndex > 0) {
                    card.classList.remove('flipped');
                    // 等待翻转过半（150ms = 0.3s动画的一半）后再更新，避免看到新卡片答案
                    setTimeout(function() {
                        currentCardIndex--;
                        updateCard();
                    }, 150);
                }
            }

            // 进入下一页
            function goToNextCard() {
                if (currentCardIndex < currentFlashcards.length - 1) {
                    card.classList.remove('flipped');
                    // 等待翻转过半（150ms = 0.3s动画的一半）后再更新，避免看到新卡片答案
                    setTimeout(function() {
                        currentCardIndex++;
                        updateCard();
                    }, 150);
                } else {
                    // 学习完成，检查是否需要继续学习
                    checkAndHandleCompletion();
                }
            }
            
            // 检查并处理学习完成
            function checkAndHandleCompletion() {
                if (isMistakeMode) {
                    // 错题本模式：检查是否还有需复习的卡片
                    const totalCards = flashcards.length;
                    const familiarCount = familiarCards.size;
                    const unfamiliarCount = unfamiliarCards.size;
                    const unmarkedCount = totalCards - familiarCount - unfamiliarCount;
                    const needReviewCount = unfamiliarCount + unmarkedCount;
                    
                    if (needReviewCount > 0) {
                        // 还有需复习的卡片，重新开始错题本学习
                        const remainingUnfamiliar = flashcards.filter((card, index) => unfamiliarCards.has(index));
                        currentFlashcards = remainingUnfamiliar;
                        currentCardIndex = 0;
                        learnedCards.clear();
                        card.classList.remove('flipped');
                        updateCard();
                        return;
                    }
                }
                // 全部模式或错题本模式中所有卡片都已熟悉，显示完成消息
                showCompletionMessage();
            }
            
            // 显示学习完成消息
            function showCompletionMessage() {
                const totalCards = flashcards.length;
                const familiarCount = familiarCards.size;
                const unfamiliarCount = unfamiliarCards.size;
                const unmarkedCount = totalCards - familiarCount - unfamiliarCount;
                const needReviewCount = unfamiliarCount + unmarkedCount;
                
                if (isMistakeMode) {
                    alert(`🎉 错题本学习完成！\n\n所有不熟悉的卡片都已掌握！\n已熟悉: ${familiarCount} 张\n需复习: ${needReviewCount} 张\n总计: ${totalCards} 张\n\n点击"全部模式"查看所有卡片，或点击"重新开始"重新学习。`);
                } else {
                    alert(`全部卡片学习完成！\n已熟悉: ${familiarCount} 张\n需复习: ${needReviewCount} 张\n总计: ${totalCards} 张\n\n点击"错题本模式"专注复习不熟悉的卡片，或点击"重新开始"重新学习。`);
                }
            }
            
            // 标记为熟悉
            function markAsFamiliar() {
                if (currentFlashcards.length === 0) return;
                const originalIndex = flashcards.findIndex(card => 
                    card.english === currentFlashcards[currentCardIndex].english && 
                    card.chinese === currentFlashcards[currentCardIndex].chinese
                );
                if (originalIndex !== -1) {
                    familiarCards.add(originalIndex);
                    unfamiliarCards.delete(originalIndex);
                    updateCard();
                    // 自动进入下一页
                    setTimeout(goToNextCard, 500); // 延迟500ms让用户看到反馈
                }
            }
            
            // 标记为不熟悉
            function markAsUnfamiliar() {
                if (currentFlashcards.length === 0) return;
                const originalIndex = flashcards.findIndex(card => 
                    card.english === currentFlashcards[currentCardIndex].english && 
                    card.chinese === currentFlashcards[currentCardIndex].chinese
                );
                if (originalIndex !== -1) {
                    unfamiliarCards.add(originalIndex);
                    familiarCards.delete(originalIndex);
                    updateCard();
                    // 自动进入下一页
                    setTimeout(goToNextCard, 500); // 延迟500ms让用户看到反馈
                }
            }
            
            // 初始更新
            if (flashcards.length > 0) {
                updateCard();
            }
            
            // 卡片点击事件 - 翻转
            card.addEventListener('click', function() {
                if (currentFlashcards.length === 0) return;
                card.classList.toggle('flipped');
            });
            
            // 移除上一张/下一张按钮的事件监听器
            
            // 重新开始按钮
            resetBtn.addEventListener('click', function() {
                currentCardIndex = 0;
                learnedCards.clear();
                familiarCards.clear();
                unfamiliarCards.clear();
                card.classList.remove('flipped');
                // 重置为全部模式
                isMistakeMode = false;
                currentFlashcards = [...flashcards];
                modeToggleBtn.textContent = '切换到错题本模式';
                modeToggleBtn.className = 'btn btn-warning';
                updateCard();
            });
            
            // 移除随机排序按钮的事件监听器
            
            // 熟悉按钮
            familiarBtn.addEventListener('click', function() {
                markAsFamiliar();
            });
            
            // 不熟悉按钮
            unfamiliarBtn.addEventListener('click', function() {
                markAsUnfamiliar();
            });
            
            // 模式切换按钮
            modeToggleBtn.addEventListener('click', function() {
                toggleMode();
            });
            
            // 导航按钮事件监听器
            prevBtn.addEventListener('click', function() {
                goToPrevCard();
            });
            
            nextBtn.addEventListener('click', function() {
                goToNextCard();
            });
            
            // 移除触摸滑动支持，因为现在使用自动进入下一页模式
        });
    </script>
</body>
</html>"""
    
    # 将闪卡数据转换为JSON格式
    flashcards_json = "[\n"
    for i, card in enumerate(flashcards):
        # 转义特殊字符
        english = card['english'].replace('"', '\\"')
        chinese = card['chinese'].replace('"', '\\"')
        
        flashcards_json += f"        {{ english: \"{english}\", chinese: \"{chinese}\" }}"
        if i < len(flashcards) - 1:
            flashcards_json += ",\n"
        else:
            flashcards_json += "\n    "
    flashcards_json += "]"
    
    # 替换模板中的占位符
    html_content = html_template.replace("TITLE_PLACEHOLDER", title)
    html_content = html_content.replace("GRADE_PLACEHOLDER", metadata['grade'])
    html_content = html_content.replace("DATE_PLACEHOLDER", metadata['date'])
    html_content = html_content.replace("[FLASHCARDS_DATA]", flashcards_json)
    return html_content

def generate_html(metadata, flashcards, output_path):
    """
    生成微信小程序风格的HTML文件
    """
    if not flashcards:
        print("错误: 没有可用的闪卡数据")
        return False
    try:
        html_content = generate_html_string(metadata, flashcards)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        title = f"英语学习闪卡-{metadata['grade']}-{metadata['date']}"
        print(f"成功生成HTML文件: {output_path}")
        print(f"标题: {title}")
        print(f"共生成 {len(flashcards)} 张闪卡")
        return True
    except Exception as e:
        print(f"生成HTML文件时出错: {e}")
        return False

def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        # 如果没有指定配置文件，查找所有config_*.txt文件
        config_files = glob.glob("config_*.txt")
        if config_files:
            # 按日期排序，选择最新的文件
            config_files.sort(reverse=True)
            config_file = config_files[0]
            print(f"自动选择最新配置文件: {config_file}")
        else:
            # 如果没有找到带日期的配置文件，使用默认配置文件
            config_file = "config.txt"
            if not os.path.exists(config_file):
                print("错误: 未找到配置文件")
                print("请创建config.txt或config_YYYYMMDD.txt文件")
                return
    
    # 从文件名中提取日期
    date_str = extract_date_from_filename(config_file)
    output_file = f"flashcards_{date_str}.html"
    
    print("英语学习闪卡生成器 - 微信小程序风格")
    print("=" * 40)
    
    # 解析配置文件
    metadata, flashcards = parse_config_file(config_file)
    if not flashcards:
        print("没有找到有效的闪卡数据，请检查配置文件格式")
        return
    
    print(f"成功读取 {len(flashcards)} 张闪卡")
    print(f"年级: {metadata['grade']}")
    print(f"日期: {metadata['date']}")
    
    # 生成HTML文件
    if generate_html(metadata, flashcards, output_file):
        print("生成完成！")
        print(f"请打开 {output_file} 文件使用闪卡")
    else:
        print("生成失败")

if __name__ == "__main__":
    main()