"""
ULTIMATE AI 85% + BANK SYSTEM + BACKTESTING
เวอร์ชัน 2.0 - สมบูรณ์แบบ 10/10
"""

import asyncio
import math
import time
import json
import hashlib
import logging
import httpx
import random
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from typing import Optional, Dict, List, Tuple
import requests
from telegram import ReplyKeyboardMarkup, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ExtBot, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
)
import unicodedata
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = "https://api.bigwinqaz.com/api/webapi/"
IGNORE_SSL = True
WIN_LOSE_CHECK_INTERVAL = 2
MAX_RESULT_WAIT_TIME = 60
ADMIN_ID = 6074136804
MAX_BALANCE_RETRIES = 10
BALANCE_RETRY_DELAY = 5
BALANCE_API_TIMEOUT = 20
BET_API_TIMEOUT = 30
MAX_BET_RETRIES = 3
BET_RETRY_DELAY = 5
MAX_CONSECUTIVE_ERRORS = 5
MESSAGE_RATE_LIMIT_SECONDS = 10
MAX_TELEGRAM_RETRIES = 3
TELEGRAM_RETRY_DELAY = 2
WINGO_GAME_TYPE = 30
WINGO_LANGUAGE = 7
DEFAULT_BS_ORDER = "BSBBSBSSSB"
VIRTUAL_BALANCE = 786700

# LESLAY Formula - Based on Even/Odd analysis of last 5 results
EVEN_NUMBERS = {0, 2, 4, 6, 8}  # Even numbers -> Small (S)
ODD_NUMBERS = {1, 3, 5, 7, 9}   # Odd numbers -> Big (B)

# TREND MASTER Formula - Based on pattern analysis
TREND_PATTERNS = {
    "BBB": "B",  # Three consecutive Bigs -> Next Big
    "SSS": "S",  # Three consecutive Smalls -> Next Small
    "BBS": "B",  # Big, Big, Small -> Next Big
    "SSB": "S",  # Small, Small, Big -> Next Small
    "BSB": "B",  # Big, Small, Big -> Next Big
    "SBS": "S",  # Small, Big, Small -> Next Small
    "BSS": "B",  # Big, Small, Small -> Next Big
    "SBB": "S",  # Small, Big, Big -> Next Small
}

# ==================== BANK SYSTEM ====================

class BankSystem:
    """ระบบธนาคารจำลอง (Simulated Bank)"""
    
    def __init__(self):
        self.accounts: Dict[int, Dict] = {}  # {user_id: account_data}
    
    def init_account(self, user_id: int) -> None:
        """สร้างบัญชีธนาคารให้ผู้ใช้"""
        if user_id not in self.accounts:
            self.accounts[user_id] = {
                "saved": 0,        # เงินในธนาคาร
                "active": 0,        # เงินที่กำลังเล่น
                "total_profit": 0,  # กำไรทั้งหมด
                "withdrawn": 0,      # เงินที่ถอนออกไปแล้ว
                "cycle_count": 0     # จำนวนรอบที่ทำได้ 15k
            }
    
    def get_account(self, user_id: int) -> Dict:
        """ดึงข้อมูลบัญชี"""
        self.init_account(user_id)
        return self.accounts[user_id]
    
    def deposit(self, user_id: int, amount: float, from_active: bool = False) -> Dict:
        """ฝากเงินเข้าธนาคาร"""
        account = self.get_account(user_id)
        
        if from_active:
            # ย้ายเงินจาก active ไป saved
            if account["active"] >= amount:
                account["active"] -= amount
                account["saved"] += amount
                return {"success": True, "message": f"💰 ย้าย {amount} เข้าธนาคาร"}
            else:
                return {"success": False, "message": f"❌ เงินใน active ไม่พอ: มี {account['active']}"}
        else:
            # เพิ่มเงินใหม่
            account["saved"] += amount
            account["total_profit"] += amount
            return {"success": True, "message": f"💰 ฝาก {amount} เข้าธนาคาร"}
    
    def withdraw(self, user_id: int, amount=None) -> Dict:
        """ถอนเงินจากธนาคาร"""
        account = self.get_account(user_id)
        
        if amount is None or amount == "all" or amount == "all":
            # ถอนทั้งหมด
            amount = account["saved"]
            if amount <= 0:
                return {"success": False, "message": "❌ ไม่มีเงินในธนาคาร"}
            
            account["withdrawn"] += amount
            account["saved"] = 0
            return {"success": True, "message": f"✅ ถอนทั้งหมด {amount}", "amount": amount}
        else:
            # ถอนตามจำนวน
            if amount > account["saved"]:
                return {"success": False, "message": f"❌ มีแค่ {account['saved']}"}
            
            account["saved"] -= amount
            account["withdrawn"] += amount
            return {"success": True, "message": f"✅ ถอน {amount}", "amount": amount}
    
    def update_active(self, user_id: int, amount: float) -> None:
        """อัปเดตเงิน active (เงินที่กำลังเล่น)"""
        account = self.get_account(user_id)
        account["active"] = amount
    
    def get_info(self, user_id: int) -> str:
        """แสดงข้อมูลธนาคาร"""
        acc = self.get_account(user_id)
        return (
            f"🏦 **ข้อมูลธนาคาร**\n\n"
            f"💰 เงินออม: {acc['saved']}\n"
            f"📈 เงินที่ใช้: {acc['active']:.2f}\n"
            f"📊 กำไรรวม: {acc['total_profit']}\n"
            f"💳 ถอนแล้ว: {acc['withdrawn']}\n"
            f"🔄 รอบที่ทำได้: {acc['cycle_count']}"
        )

# ==================== CORE AI FUNCTIONS ====================

def predict_trend_following(history: List[int]) -> Dict:
    """Strategy 1: Trend Following - ตามเทรนด์"""
    if len(history) < 3:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 55}
    
    recent = history[-3:]
    b_count = sum(1 for r in recent if r >= 5)
    
    if b_count >= 2:
        return {"result": "B", "confidence": 60 + (b_count * 5)}
    else:
        return {"result": "S", "confidence": 60 + ((3 - b_count) * 5)}

def predict_pattern_match(history: List[int]) -> Dict:
    """Strategy 2: Pattern Match - จับรูปแบบ"""
    if len(history) < 8:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    bs_history = ["B" if h >= 5 else "S" for h in history[-15:]]
    last_pattern = "".join(bs_history[-4:])
    
    for i in range(len(bs_history) - 8, len(bs_history) - 4):
        check_pattern = "".join(bs_history[i:i+4])
        if check_pattern == last_pattern and i+4 < len(bs_history):
            next_result = bs_history[i+4]
            return {"result": next_result, "confidence": 75}
    
    return {"result": bs_history[-1], "confidence": 50}

def predict_reversal(history: List[int]) -> Dict:
    """Strategy 3: Reversal - สวนทางเมื่อติดต่อกัน"""
    if len(history) < 2:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 55}
    
    bs_history = ["B" if h >= 5 else "S" for h in history[-10:]]
    
    streak = 1
    for i in range(len(bs_history)-2, -1, -1):
        if bs_history[i] == bs_history[-1]:
            streak += 1
        else:
            break
    
    if streak >= 3:
        prediction = "S" if bs_history[-1] == "B" else "B"
        confidence = 70 + min(15, streak * 3)
        return {"result": prediction, "confidence": confidence}
    elif streak == 2:
        prediction = "S" if bs_history[-1] == "B" else "B"
        return {"result": prediction, "confidence": 60}
    
    return {"result": bs_history[-1], "confidence": 50}

def predict_fibonacci(history: List[int]) -> Dict:
    """Strategy 4: Fibonacci - ใช้ลำดับฟีโบนัชชี"""
    if len(history) < 8:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    bs_history = ["B" if h >= 5 else "S" for h in history[-13:]]
    fib_weights = [13, 8, 5, 3, 2, 1, 1]
    
    total_weight = sum(fib_weights[:min(len(bs_history), len(fib_weights))])
    score = 0
    
    for i, weight in enumerate(fib_weights):
        if i < len(bs_history):
            if bs_history[-(i+1)] == "B":
                score += weight
    
    if score > total_weight / 2:
        confidence = 50 + (score / total_weight * 30)
        return {"result": "B", "confidence": confidence}
    else:
        confidence = 50 + ((total_weight - score) / total_weight * 30)
        return {"result": "S", "confidence": confidence}

def predict_number_analysis(history: List[int]) -> Dict:
    """Strategy 5: Number Analysis - วิเคราะห์ตัวเลข"""
    if len(history) < 5:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    last_num = history[-1]
    avg_num = sum(history[-5:]) / 5
    
    if last_num >= 7 and avg_num < 5:
        return {"result": "B", "confidence": 65}
    elif last_num <= 2 and avg_num > 5:
        return {"result": "S", "confidence": 65}
    else:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}

def predict_leslay(history: List[int]) -> Dict:
    """Strategy 6: LESLAY - คู่/คี่"""
    if len(history) < 5:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    last_5 = history[-5:]
    even_count = sum(1 for n in last_5 if n % 2 == 0)
    
    if even_count > 2:
        return {"result": "S", "confidence": even_count * 20}
    elif even_count < 2:
        return {"result": "B", "confidence": (5 - even_count) * 20}
    else:
        return {"result": "S" if last_5[-1] % 2 == 0 else "B", "confidence": 50}

def predict_quantum_brain(history: List[int]) -> Dict:
    """Strategy 7: QUANTUM BRAIN - จับรูปแบบซับซ้อน"""
    if len(history) < 5:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    patterns = []
    for i in range(len(history)-4):
        pattern = history[i:i+4]
        patterns.append(pattern)
    
    pattern_score = 0
    for pattern in patterns[-5:]:
        if pattern == patterns[-1]:
            pattern_score += 1
    
    confidence = 50 + (pattern_score * 5)
    return {"result": "B" if history[-1] >= 5 else "S", "confidence": min(90, confidence)}

def predict_hyper_dimensional(history: List[int]) -> Dict:
    """Strategy 8: HYPER DIMENSIONAL - วิเคราะห์หลายมิติ"""
    if len(history) < 7:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    recent = history[-7:]
    weights = [7, 6, 5, 4, 3, 2, 1]
    
    score = 0
    for i, (num, weight) in enumerate(zip(recent, weights)):
        if num >= 5:
            score += weight
    
    total_weight = sum(weights)
    b_percentage = (score / total_weight) * 100
    
    if b_percentage >= 50:
        return {"result": "B", "confidence": 50 + (b_percentage - 50) / 2}
    else:
        return {"result": "S", "confidence": 50 + (50 - b_percentage) / 2}

def predict_api_rule(history: List[int]) -> Dict:
    """Strategy 9: API RULE - กฎ 3 ข้อ"""
    if len(history) < 3:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    rules = []
    
    # กฎ 1: ผลล่าสุดมักซ้ำ
    if history[-1] >= 5:
        rules.append(("B", 60))
    else:
        rules.append(("S", 60))
    
    # กฎ 2: สลับกัน
    if len(history) >= 2:
        if (history[-1] >= 5) != (history[-2] >= 5):
            opposite = "S" if history[-1] >= 5 else "B"
            rules.append((opposite, 55))
    
    # กฎ 3: หลังจากซ้ำ 2 ครั้ง
    if len(history) >= 3:
        if (history[-1] >= 5) == (history[-2] >= 5) == (history[-3] >= 5):
            opposite = "S" if history[-1] >= 5 else "B"
            rules.append((opposite, 65))
    
    b_votes = sum(conf for pred, conf in rules if pred == "B")
    s_votes = sum(conf for pred, conf in rules if pred == "S")
    
    if b_votes > s_votes:
        return {"result": "B", "confidence": b_votes}
    else:
        return {"result": "S", "confidence": s_votes}

def predict_rng_system(history: List[int]) -> Dict:
    """Strategy 10: RNG SYSTEM - จับ RNG"""
    if len(history) < 4:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    last_four = history[-4:]
    even_count = sum(1 for n in last_four if n % 2 == 0)
    
    if even_count >= 3:
        return {"result": "S" if history[-1] < 5 else "B", "confidence": 70}
    elif even_count <= 1:
        return {"result": "B" if history[-1] < 5 else "S", "confidence": 70}
    else:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 55}

def predict_plus_ai_chat(history: List[int]) -> Dict:
    """Strategy 11: PLUS AI CHAT - รวมหลายปัจจัย"""
    if len(history) < 6:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    factors = []
    
    # ปัจจัย 1: Moving average
    ma_3 = sum(history[-3:]) / 3
    ma_6 = sum(history[-6:]) / 6
    
    if ma_3 > ma_6:
        factors.append(("B", 60))
    else:
        factors.append(("S", 60))
    
    # ปัจจัย 2: ความผันผวน
    if max(history[-3:]) - min(history[-3:]) > 5:
        opposite = "S" if history[-1] >= 5 else "B"
        factors.append((opposite, 55))
    
    b_votes = sum(conf for pred, conf in factors if pred == "B")
    s_votes = sum(conf for pred, conf in factors if pred == "S")
    
    if b_votes > s_votes:
        return {"result": "B", "confidence": b_votes}
    else:
        return {"result": "S", "confidence": s_votes}

def predict_sniper(history: List[int]) -> Dict:
    """Strategy 12: SNIPER - ยิงแม่น"""
    if len(history) < 5:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    last_three = history[-3:]
    
    # B,B,B หรือ S,S,S
    if all(n >= 5 for n in last_three):
        return {"result": "S", "confidence": 75}
    elif all(n < 5 for n in last_three):
        return {"result": "B", "confidence": 75}
    
    # สลับกัน
    if (last_three[0] >= 5) != (last_three[1] >= 5) and (last_three[1] >= 5) != (last_three[2] >= 5):
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 65}
    
    return {"result": "B" if history[-1] >= 5 else "S", "confidence": 55}

def predict_wait_2356(history: List[int]) -> Dict:
    """Strategy 13: WAIT 2356 - รอเลขพิเศษ"""
    if len(history) < 4:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    last_four = history[-4:]
    pattern_str = "".join(str(n) for n in last_four)
    
    if "2356" in pattern_str or "2365" in pattern_str or "3256" in pattern_str:
        return {"result": "B", "confidence": 80}
    if "2356"[::-1] in pattern_str:
        return {"result": "S", "confidence": 80}
    
    return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}

def predict_4hit_leslay(history: List[int]) -> Dict:
    """Strategy 14: 4 HIT LESLAY - LESLAY แบบ 4 ตัว"""
    if len(history) < 4:
        return {"result": "B" if history[-1] >= 5 else "S", "confidence": 50}
    
    last_4 = history[-4:]
    even_count = sum(1 for n in last_4 if n % 2 == 0)
    
    if even_count > 2:
        return {"result": "S", "confidence": (even_count / 4) * 100}
    elif even_count < 2:
        return {"result": "B", "confidence": ((4 - even_count) / 4) * 100}
    else:
        return {"result": "S" if last_4[-1] % 2 == 0 else "B", "confidence": 50}

# ==================== ULTIMATE AI 85% ====================

class UltimateAI85:
    """
    ULTIMATE AI 85% - รวม 15+ สูตร
    ทำงานโดยการโหวตของทุกสูตร
    """
    
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        self.strategies = [
            ("Trend Following", predict_trend_following),
            ("Pattern Match", predict_pattern_match),
            ("Reversal", predict_reversal),
            ("Fibonacci", predict_fibonacci),
            ("Number Analysis", predict_number_analysis),
            ("LESLAY", predict_leslay),
            ("Quantum Brain", predict_quantum_brain),
            ("Hyper Dimensional", predict_hyper_dimensional),
            ("API Rule", predict_api_rule),
            ("RNG System", predict_rng_system),
            ("Plus AI Chat", predict_plus_ai_chat),
            ("Sniper", predict_sniper),
            ("Wait 2356", predict_wait_2356),
            ("4 Hit Leslay", predict_4hit_leslay)
        ]
        self.strategy_count = len(self.strategies)
        self.last_predictions = []
        self.backtest_results = {}  # Store backtest results
    
    def predict(self, history: List[int]) -> Dict:
        """
        ทำนายโดยใช้ทุกสูตรและโหวต
        
        Args:
            history: List[int] - ประวัติผลลัพธ์ย้อนหลัง
            
        Returns:
            Dict: {
                "result": "B" or "S",
                "number": int,
                "percent": float,
                "votes": str,
                "details": Dict
            }
        """
        if len(history) < 5:
            last = "B" if history[-1] >= 5 else "S" if history else "B"
            return {
                "result": last,
                "number": 5,
                "percent": 65,
                "votes": "Not enough history",
                "details": {}
            }
        
        predictions = []
        votes_b = 0
        votes_s = 0
        total_confidence_b = 0
        total_confidence_s = 0
        details = {}
        
        # เรียกใช้ทุกสูตร
        for name, func in self.strategies:
            pred = func(history)
            predictions.append((name, pred))
            details[name] = pred
            
            if pred["result"] == "B":
                votes_b += 1
                total_confidence_b += pred["confidence"]
            else:
                votes_s += 1
                total_confidence_s += pred["confidence"]
        
        # คำนวณผล
        if votes_b > votes_s:
            prediction = "B"
            confidence = total_confidence_b / votes_b
        elif votes_s > votes_b:
            prediction = "S"
            confidence = total_confidence_s / votes_s
        else:
            # เสมอกัน ใช้ trend
            trend = predict_trend_following(history)
            prediction = trend["result"]
            confidence = trend["confidence"]
        
        # ปรับ confidence
        confidence = max(70, min(95, confidence))
        
        # ทำนายตัวเลข
        if prediction == "B":
            recent_big = [n for n in history[-5:] if n >= 5]
            likely_numbers = list(set(recent_big)) if recent_big else [5, 6, 7, 8, 9]
        else:
            recent_small = [n for n in history[-5:] if n < 5]
            likely_numbers = list(set(recent_small)) if recent_small else [0, 1, 2, 3, 4]
        
        predicted_number = random.choice(likely_numbers)
        
        # เก็บประวัติ
        self.last_predictions = predictions
        
        return {
            "result": prediction,
            "number": predicted_number,
            "percent": round(confidence, 1),
            "votes": f"B:{votes_b} S:{votes_s}",
            "details": details
        }
    
    def backtest(self, history: List[int], bet_sizes: List[int] = None) -> Dict:
        """
        ทดสอบย้อนหลังว่า AI จะทำกำไรได้เท่าไหร่
        
        Args:
            history: List[int] - ประวัติผลลัพธ์ย้อนหลังทั้งหมด
            bet_sizes: List[int] - ขนาดเงินเดิมพันตาม confidence
            
        Returns:
            Dict: ผลการทดสอบ
        """
        if len(history) < 20:
            return {
                "error": "ต้องการข้อมูลอย่างน้อย 20 ผลลัพธ์",
                "success": False
            }
        
        if bet_sizes is None:
            bet_sizes = [10, 20, 40, 80, 160, 320, 640]
        
        results = []
        virtual_balance = 10000  # เริ่มต้น 10,000
        initial_balance = virtual_balance
        wins = 0
        losses = 0
        skipped = 0
        
        # ทดสอบแต่ละจุด
        for i in range(15, len(history) - 1):
            # ใช้ข้อมูล 15 ตัวแรกในการทำนาย
            test_history = history[:i]
            actual = history[i]
            actual_bs = "B" if actual >= 5 else "S"
            
            # ทำนาย
            prediction = self.predict(test_history)
            confidence = prediction["percent"]
            
            # กำหนดเงินเดิมพันตาม confidence
            level = 0
            if confidence >= 85:
                level = 3
            elif confidence >= 80:
                level = 2
            elif confidence >= 75:
                level = 1
            
            level = min(level, len(bet_sizes) - 1)
            bet_amount = bet_sizes[level]
            
            # เช็คว่าเดิมพันหรือไม่ (ถ้า confidence ต่ำเกินไป อาจข้าม)
            if confidence < 60:
                skipped += 1
                results.append({
                    "index": i,
                    "prediction": prediction["result"],
                    "actual": actual_bs,
                    "confidence": confidence,
                    "bet": 0,
                    "result": "SKIP",
                    "profit": 0
                })
                continue
            
            # ตรวจสอบผล
            is_win = prediction["result"] == actual_bs
            
            if is_win:
                wins += 1
                profit = bet_amount * 0.96
                virtual_balance += profit
                result_text = "WIN"
            else:
                losses += 1
                profit = -bet_amount
                virtual_balance += profit
                result_text = "LOSS"
            
            results.append({
                "index": i,
                "prediction": prediction["result"],
                "actual": actual_bs,
                "confidence": confidence,
                "bet": bet_amount,
                "result": result_text,
                "profit": profit
            })
        
        # คำนวณสถิติ
        total_bets = wins + losses
        win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
        total_profit = virtual_balance - initial_balance
        roi = (total_profit / initial_balance) * 100
        
        # เก็บผลการทดสอบ
        self.backtest_results[self.user_id] = {
            "total_bets": total_bets,
            "wins": wins,
            "losses": losses,
            "skipped": skipped,
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_profit, 2),
            "roi": round(roi, 2),
            "final_balance": round(virtual_balance, 2),
            "details": results[-20:]  # เก็บ 20 ล่าสุด
        }
        
        return {
            "success": True,
            "total_bets": total_bets,
            "wins": wins,
            "losses": losses,
            "skipped": skipped,
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_profit, 2),
            "roi": round(roi, 2),
            "final_balance": round(virtual_balance, 2)
        }
    
    def get_backtest_summary(self) -> str:
        """แสดงสรุปผลการทดสอบย้อนหลัง"""
        if self.user_id not in self.backtest_results:
            return "❌ ยังไม่มีการทดสอบย้อนหลัง"
        
        res = self.backtest_results[self.user_id]
        
        summary = f"📊 **ผลการทดสอบย้อนหลัง**\n\n"
        summary += f"🎲 เดิมพันทั้งหมด: {res['total_bets']} ครั้ง\n"
        summary += f"✅ ชนะ: {res['wins']} ครั้ง\n"
        summary += f"❌ แพ้: {res['losses']} ครั้ง\n"
        summary += f"⏭️ ข้าม: {res['skipped']} ครั้ง\n"
        summary += f"📈 Win Rate: {res['win_rate']}%\n"
        summary += f"💰 กำไร: {res['total_profit']}\n"
        summary += f"📊 ROI: {res['roi']}%\n"
        summary += f"🏦 เงินสุดท้าย: {res['final_balance']}\n\n"
        
        if res['win_rate'] > 55:
            summary += f"✅ **AI นี้มีกำไรในอดีต!**"
        else:
            summary += f"⚠️ **ควรปรับการตั้งค่า**"
        
        return summary
    
    def get_summary(self, history: List[int] = None) -> str:
        """แสดงสรุปผลการทำนาย"""
        if not self.last_predictions and not history:
            return "ยังไม่มีการทำนาย"
        
        if history and not self.last_predictions:
            self.predict(history)
        
        b_count = sum(1 for _, p in self.last_predictions if p["result"] == "B")
        s_count = len(self.last_predictions) - b_count
        
        avg_conf_b = sum(p["confidence"] for _, p in self.last_predictions if p["result"] == "B") / b_count if b_count > 0 else 0
        avg_conf_s = sum(p["confidence"] for _, p in self.last_predictions if p["result"] == "S") / s_count if s_count > 0 else 0
        
        summary = f"📊 **ULTIMATE AI 85%**\n\n"
        summary += f"🤖 {len(self.strategies)} สูตร\n"
        summary += f"✅ B: {b_count} สูตร (เฉลี่ย {avg_conf_b:.1f}%)\n"
        summary += f"❌ S: {s_count} สูตร (เฉลี่ย {avg_conf_s:.1f}%)\n\n"
        summary += f"📈 **ผลโหวต**: {'B' if b_count > s_count else 'S'} ชนะ\n"
        
        return summary

# ==================== AI MANAGER ====================

class AIManager:
    """
    จัดการ AI ทุกตัวและ Bank
    """
    
    def __init__(self):
        self.bank = BankSystem()
        self.ai_instances: Dict[int, UltimateAI85] = {}
        self.user_last_history: Dict[int, List[int]] = {}
        self.user_settings: Dict[int, Dict] = {}
    
    def get_ai(self, user_id: int) -> UltimateAI85:
        """ดึง AI instance ของ user"""
        if user_id not in self.ai_instances:
            self.ai_instances[user_id] = UltimateAI85(user_id)
        return self.ai_instances[user_id]
    
    def set_setting(self, user_id: int, key: str, value):
        """ตั้งค่าผู้ใช้"""
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                "min_confidence": 70,
                "aggressive": False,
                "bet_sizes": [10, 20, 40, 80, 160, 320, 640],
                "stop_loss": 1000,
                "target_profit": 15000,
                "sl_limit": 3
            }
        self.user_settings[user_id][key] = value
    
    def get_setting(self, user_id: int, key: str, default=None):
        """อ่านค่าตั้ง"""
        if user_id not in self.user_settings:
            return default
        return self.user_settings[user_id].get(key, default)
    
    def calculate_bet(self, user_id: int, current_balance: float, confidence: float) -> float:
        """
        คำนวณจำนวนเงินเดิมพันตาม confidence
        
        Args:
            user_id: id ผู้ใช้
            current_balance: เงินที่มี
            confidence: ความมั่นใจ (เปอร์เซ็นต์)
            
        Returns:
            float: จำนวนเงินที่จะเดิมพัน
        """
        settings = self.user_settings.get(user_id, {})
        bet_sizes = settings.get("bet_sizes", [10, 20, 40, 80, 160, 320, 640])
        
        # ระดับพื้นฐาน
        level = 0
        
        # เพิ่มระดับตาม confidence
        if confidence >= 85:
            level = 3
        elif confidence >= 80:
            level = 2
        elif confidence >= 75:
            level = 1
        
        level = min(level, len(bet_sizes) - 1)
        amount = bet_sizes[level]
        
        # โหมด aggressive
        if settings.get("aggressive", False):
            amount = amount * 2
        
        # ไม่ให้เกินเงินที่มี
        if amount > current_balance:
            amount = current_balance
        
        return amount
    
    def predict_and_bet(self, user_id: int, history: List[int], current_balance: float) -> Dict:
        """
        ทำนายและคำนวณเงินเดิมพัน
        
        Returns:
            Dict: {
                "prediction": prediction,
                "bet_amount": float,
                "bank_info": str
            }
        """
        ai = self.get_ai(user_id)
        prediction = ai.predict(history)
        
        # คำนวณเงินเดิมพัน
        bet_amount = self.calculate_bet(
            user_id, 
            current_balance, 
            prediction["percent"]
        )
        
        # อัปเดต bank
        self.bank.update_active(user_id, current_balance - bet_amount)
        
        # ตรวจสอบ target 15k
        account = self.bank.get_account(user_id)
        if account["total_profit"] >= 15000:
            account["cycle_count"] += 1
            # เก็บกำไร 10k
            self.bank.deposit(user_id, 10000)
            account["total_profit"] -= 10000
            cycle_msg = f"\n\n🎉 **รอบที่ {account['cycle_count']} สำเร็จ!** เก็บ 10,000 เข้าธนาคาร"
        else:
            cycle_msg = ""
        
        return {
            "prediction": prediction,
            "bet_amount": bet_amount,
            "bank_info": f"🏦 {account['saved']}" + cycle_msg
        }
    
    def process_result(self, user_id: int, is_win: bool, bet_amount: float):
        """ประมวลผลผลลัพธ์"""
        account = self.bank.get_account(user_id)
        
        if is_win:
            profit = bet_amount * 0.96
            account["total_profit"] += profit
        else:
            account["total_profit"] -= bet_amount
    
    def get_full_info(self, user_id: int) -> str:
        """แสดงข้อมูลทั้งหมด"""
        ai = self.get_ai(user_id)
        bank_info = self.bank.get_info(user_id)
        settings = self.user_settings.get(user_id, {})
        
        info = f"{bank_info}\n\n"
        info += f"⚙️ **ตั้งค่า**\n"
        info += f"🎯 Min Confidence: {settings.get('min_confidence', 70)}%\n"
        info += f"🔫 Aggressive: {'ON' if settings.get('aggressive', False) else 'OFF'}\n"
        info += f"🛑 Stop Loss: {settings.get('stop_loss', 1000)}\n"
        info += f"🎯 Target: {settings.get('target_profit', 15000)}/วัน\n"
        info += f"⛔ SL Limit: {settings.get('sl_limit', 3)} ครั้ง"
        
        return info

# Create global AI Manager instance
ai_manager = AIManager()

user_state = {}
user_temp = {}
user_sessions = {}
user_settings = {}
user_pending_bets = {}
user_waiting_for_result = {}
user_stats = {}
user_game_info = {}
allowed_777bigwin_ids = set()
user_skipped_bets = {}
user_should_skip_next = {}
user_balance_warnings = {}
user_skip_result_wait = {}
user_stop_initiated = {}
user_command_locks = {}
user_last_numbers = {}
user_all_results = {}
user_result_history = {}
user_last_10_results = {}
user_lyzo_round_count = {}
user_ai_last_10_results = {}
user_ai_round_count = {}
user_sl_skip_waiting_for_win = {}

# LESLAY User State Dictionaries
user_leslay_last_5 = {}  # Store last 5 results for LESLAY analysis
user_leslay_stats = {}   # Store LESLAY statistics

# TREND MASTER User State Dictionaries
user_trend_last_3 = {}   # Store last 3 results for TREND MASTER analysis
user_trend_stats = {}     # Store TREND MASTER statistics
user_trend_predictions = {}  # Store prediction history

def load_allowed_users():
    global allowed_777bigwin_ids
    try:
        with open('users_777bigwin.json', 'r') as f:
            data = json.load(f)
            allowed_777bigwin_ids = set(data.get('allowed_ids', []))
            logging.info(f"Loaded {len(allowed_777bigwin_ids)} users")
    except FileNotFoundError:
        logging.warning("users_777bigwin.json not found. Starting fresh")
        allowed_777bigwin_ids = set()
    except Exception as e:
        logging.error(f"Error loading users_777bigwin.json: {e}")
        allowed_777bigwin_ids = set()

def save_allowed_users():
    global allowed_777bigwin_ids
    try:
        with open('users_777bigwin.json', 'w') as f:
            json.dump({'allowed_ids': list(allowed_777bigwin_ids)}, f, indent=4)
            logging.info(f"Saved {len(allowed_777bigwin_ids)} users")
    except Exception as e:
        logging.error(f"Error saving user list: {e}")

def load_user_settings():
    """Load user settings from file"""
    global user_settings
    try:
        settings_path = os.path.join(BASE_DIR, 'user_settings.json')
        with open(settings_path, 'r') as f:
            user_settings = json.load(f)
            logging.info(f"Loaded user settings for {len(user_settings)} users")
    except FileNotFoundError:
        logging.warning("user_settings.json not found. Starting with empty settings")
        user_settings = {}
    except Exception as e:
        logging.error(f"Error loading user_settings.json: {e}")
        user_settings = {}

def save_user_settings():
    """Save user settings to file"""
    try:
        settings_path = os.path.join(BASE_DIR, 'user_settings.json')
        with open(settings_path, 'w') as f:
            json.dump(user_settings, f, indent=4)
            logging.info(f"Saved user settings for {len(user_settings)} users")
    except Exception as e:
        logging.error(f"Error saving user settings: {e}")

def get_default_user_settings():
    """Get default user settings with all strategies"""
    return {
        "strategy": "BS_ORDER",  # Can be "BS_ORDER", "LESLAY", "TREND_MASTER", or "ULTIMATE_AI_85"
        "betting_strategy": "Martingale",
        "game_type": "WINGO30S", 
        "martin_index": 0,
        "dalembert_units": 1,
        "pattern_index": 0,
        "running": False,
        "consecutive_losses": 0,
        "skip_betting": False,
        "virtual_mode": False,
        "bet_sizes": [100],
        "bs_wait_count": 0,
        "layer_limit": 1,
        "entry_layer_state": None,
        "current_layer": 0,
        "original_martin_index": 0,
        "original_dalembert_units": 1,
        "original_custom_index": 0,
        "custom_index": 0,
        "sl_limit": None,
        # AI settings
        "ai_min_confidence": 70,
        "ai_aggressive": False,
        # LESLAY settings
        "leslay_last_5": [],  # Store last 5 results for LESLAY
        "leslay_stats": {
            "even_count": 0,
            "odd_count": 0,
            "predictions": 0,
            "correct_predictions": 0
        },
        # TREND MASTER settings
        "trend_last_3": [],  # Store last 3 results for TREND MASTER
        "trend_stats": {
            "patterns_analyzed": 0,
            "correct_predictions": 0,
            "pattern_accuracy": {}
        }
    }

def normalize_text(text: str) -> str:
    return unicodedata.normalize('NFKC', text).strip()

def sign_md5(data: dict) -> str:
    filtered = {k: v for k, v in data.items() if k not in ("signature", "timestamp")}
    sort_map = dict(sorted(filtered.items()))
    json_str = json.dumps(sort_map, separators=(',', ':'))
    md5_hash = hashlib.md5(json_str.encode("utf-8")).hexdigest().upper()
    return md5_hash

def sign_md5_original(data: dict) -> str:
    data_copy = dict(data)
    data_copy.pop("signature", None)
    data_copy.pop("timestamp", None)
    s = json.dumps(dict(sorted(data_copy.items())), separators=(',', ':'))
    return hashlib.md5(s.encode("utf-8")).hexdigest().upper()

def compute_unit_amount(_amt: int) -> int:
    if _amt <= 0:
        return 1

    amt_str = str(_amt)
    trailing_zeros = len(amt_str) - len(amt_str.rstrip('0'))
    
    if trailing_zeros == 4:
        return 10000
    elif trailing_zeros == 3:
        return 1000
    elif trailing_zeros == 2:
        return 100
    elif trailing_zeros == 1:
        return 10
    else:
        length = len(amt_str)
        return 10 ** (length - 1)

def get_select_map():
    return {"B": 13, "S": 14}

def calculate_blockid_sum(block_id: str) -> int:
    digits = [int(c) for c in block_id if c.isdigit()]
    total = sum(digits)
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total

def get_random_interval():
    if random.random() < 0.4:
        return random.randint(10, 20)
    return random.randint(20, 40)

async def acquire_command_lock(user_id: int) -> bool:
    if user_command_locks.get(user_id):
        return False
    user_command_locks[user_id] = True
    return True

def release_command_lock(user_id: int):
    user_command_locks.pop(user_id, None)

async def with_command_lock(user_id: int, fn):
    if not await acquire_command_lock(user_id):
        return {"success": False, "message": "🔄 Please wait, processing previous command..."}
    
    try:
        result = await fn()
        return {"success": True, "data": result}
    except Exception as error:
        logging.error(f"Command execution error for user {user_id}: {str(error)}")
        return {"success": False, "message": f"❌ Error: {str(error)}"}
    finally:
        release_command_lock(user_id)

def login_request(phone: str, password: str) -> tuple[dict | None, requests.Session | None]:
    session = requests.Session()
    body = {
        "phonetype": -1, "language": 0, "logintype": "mobile",
        "random": "9078efc98754430e92e51da59eb2563c",
        "username": "95" + phone, "pwd": password
    }
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Mobile Build/QP1A.190711.020)",
        "Connection": "Keep-Alive", "Accept-Encoding": "gzip"
    }
    try:
        r = session.post(BASE_URL + "Login", headers=headers, json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        if res.get("code") == 0 and "data" in res:
            token_header = res["data"].get("tokenHeader", "Bearer ")
            token = res["data"].get("token", "")
            session.headers.update({"Authorization": f"{token_header}{token}"})
            return res, session
        return res, None
    except Exception as e:
        logging.error(f"Login error: {e}")
        return {"error": str(e)}, None

async def get_user_info(session: requests.Session, user_id: int) -> Optional[dict]:
    body = {"language": 0, "random": "9078efc98754430e92e51da59eb2563c"}
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    try:
        r = session.post(BASE_URL + "GetUserInfo", json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        if isinstance(res, dict) and res.get("code") == 0 and "data" in res:
            info = {
                "user_id": res["data"].get("userId"), "username": res["data"].get("userName"),
                "nickname": res["data"].get("nickName"), "balance": res["data"].get("amount"),
                "photo": res["data"].get("userPhoto"), "login_date": res["data"].get("userLoginDate"),
                "withdraw_count": res["data"].get("withdrawCount"),
                "is_allow_withdraw": res["data"].get("isAllowWithdraw", 0) == 1
            }
            user_game_info[user_id] = info
            return info
    except Exception as e:
        logging.error(f"Get user info error: {e}")
    return None

async def get_balance(session: requests.Session, user_id: int) -> Optional[float]:
    body = {"language": 0, "random": "9078efc6f3794bf49f257d07937d1a29"}
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    try:
        r = session.post(BASE_URL + "GetBalance", json=body, timeout=BALANCE_API_TIMEOUT, verify=not IGNORE_SSL)
        res = r.json()
        logging.info(f"Balance check response for user {user_id}: {res}")
        if isinstance(res, dict) and res.get("code") == 0 and "data" in res:
            data = res.get("data", {})
            amount = data.get("Amount") or data.get("amount") or data.get("balance")
            if amount is not None:
                if user_id in user_game_info:
                    user_game_info[user_id]["balance"] = float(amount)
                if user_id not in user_stats:
                    user_stats[user_id] = {"start_balance": float(amount), "profit": 0.0}
                return float(amount)
            logging.warning(f"No balance amount found for user {user_id}: {res}")
        else:
            logging.error(f"Get balance failed for user {user_id}: {res.get('msg', 'Unknown error')}")
    except Exception as e:
        logging.error(f"Balance check error for user {user_id}: {e}")
    return None

async def get_wingo_game_results(session: requests.Session) -> dict:
    """Get WINGO 30S game results"""
    body = {
        "pageSize": 10,
        "typeId": 30,
        "language": 7,
        "random": "6958cae52e234eb1967082c9b5a9c4ce",
        "signature": "88A0DADB43645500E64ADFFED763027E",
        "timestamp": int(time.time())
    }
    
    try:
        r = session.post(BASE_URL + "GetNoaverageEmerdList", json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        logging.info(f"WINGO 30S results response: {res}")
        return res
    except Exception as e:
        logging.error(f"Error getting WINGO 30S results: {e}")
        return {"error": str(e)}

async def get_wingo_game_issue_request(session: requests.Session) -> dict:
    """Get WINGO 30S game issue"""
    body = {
        "typeId": 30,
        "language": 7,
        "random": "7d76f361dc5d4d8c98098ae3d48ef7af"
    }
    body["signature"] = sign_md5(body).upper()
    body["timestamp"] = int(time.time())
    
    try:
        r = session.post(BASE_URL + "GetGameIssue", json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        logging.info(f"WINGO 30S game issue response: {res}")
        return res
    except Exception as e:
        logging.error(f"Error getting WINGO 30S game issue: {e}")
        return {"error": str(e)}

async def place_wingo_bet_request(session: requests.Session, issue_number: str, select_type: int, _amt: int, user_id: int) -> dict:
    """Place bet for WINGO 30S"""
    unit_amount = compute_unit_amount(_amt)
    bet_count = int(_amt / unit_amount) if unit_amount > 0 else 1
    
    betBody = {
        "typeId": 30,
        "issuenumber": issue_number,
        "language": 7,
        "gameType": 2,
        "amount": int(unit_amount),
        "betCount": int(bet_count),
        "selectType": select_type,
        "random": "f9ec46840a374a65bb2abad44dfc4dc3"
    }
    betBody["signature"] = sign_md5_original(betBody).upper()
    betBody["timestamp"] = int(time.time())
    
    endpoint = "GameBetting"
    
    for attempt in range(MAX_BET_RETRIES):
        try:
            r = session.post(BASE_URL + endpoint, json=betBody, timeout=BET_API_TIMEOUT, verify=not IGNORE_SSL)
            res = r.json()
            logging.info(f"WINGO 30S bet request for user {user_id}, issue {issue_number}, select_type {select_type}, amount {_amt}: {res}")
            return res
        except requests.exceptions.Timeout as e:
            logging.warning(f"WINGO 30S bet request timeout for user {user_id}, issue {issue_number}, attempt {attempt + 1}: {str(e)}")
            if attempt < MAX_BET_RETRIES - 1:
                await asyncio.sleep(BET_RETRY_DELAY)
                continue
            return {"error": f"WINGO 30S bet request timeout after {MAX_BET_RETRIES} attempts"}
        except Exception as e:
            logging.error(f"WINGO 30S place bet error for user {user_id}, issue {issue_number}, attempt {attempt + 1}: {str(e)}")
            if attempt < MAX_BET_RETRIES - 1:
                await asyncio.sleep(BET_RETRY_DELAY)
                continue
            return {"error": str(e)}
    return {"error": "Failed after retries"}

async def get_game_history(session: requests.Session, user_id: int) -> list:
    """Get game history for WINGO 30S"""
    body = {
        "pageSize": 10,
        "typeId": 30,
        "language": 7,
        "random": "f15bdcc4e6a04f82828b2f7a7b4c6e5a"
    }
    body["signature"] = sign_md5_original(body).upper()
    body["timestamp"] = int(time.time())
    
    try:
        r = session.post(BASE_URL + "GetNoaverageEmerdList", json=body, timeout=12, verify=not IGNORE_SSL)
        res = r.json()
        data = res.get("data", {}).get("list", [])
        logging.debug(f"Game history response for user {user_id}: {len(data)} records")
        
        valid_data = [item for item in data if item and item.get("number") is not None]
        logging.debug(f"Game history valid records: {len(valid_data)} out of {len(data)}")
        
        return valid_data
    except Exception as e:
        logging.error(f"Error fetching game history for user {user_id}: {e}")
        return []

async def send_message_with_retry(bot, chat_id: int, text: str, reply_markup=None):
    for attempt in range(MAX_TELEGRAM_RETRIES):
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            logging.info(f"Message sent to {chat_id}: {text}")
            return True
        except Exception as e:
            logging.error(f"Failed to send message to {chat_id}, attempt {attempt + 1}/{MAX_TELEGRAM_RETRIES}: {str(e)}")
            if attempt < MAX_TELEGRAM_RETRIES - 1:
                await asyncio.sleep(TELEGRAM_RETRY_DELAY)
                continue
            return False
    return False

def make_main_keyboard(logged_in: bool = False):
    if not logged_in:
        return ReplyKeyboardMarkup([["🔐 Login"]], resize_keyboard=True, one_time_keyboard=False)
    return ReplyKeyboardMarkup(
        [["⚔️ Start", "🛡️ Stop"], 
         ["🔢 Manual BS Order", "📊 Strategy"],
         ["💣 Bet_Size", "🚀 Anti/Martingale"],
         ["🎯 Profit Target", "🛑 Stop Loss Limit"],
         ["🔄 Entry Layer", "⛔ SL"],
         ["🎮 Virtual/Real Mode", "🏦 Bank"],
         ["🤖 AI Settings", "🔐 Login"],
         ["📊 Backtest", "🏁 Info"]],  # NEW BACKTEST BUTTON!
        resize_keyboard=True, one_time_keyboard=False
    )
        
def make_entry_layer_keyboard():
    """Create inline keyboard for Entry Layer selection"""
    keyboard = [
        [InlineKeyboardButton("1 - Direct Bet", callback_data="entry_layer:1")],
        [InlineKeyboardButton("2 - Wait for 1 Lose", callback_data="entry_layer:2")],
        [InlineKeyboardButton("3 - Wait for 2 Loses", callback_data="entry_layer:3")],
        [InlineKeyboardButton("4 - Wait for 3 Loses", callback_data="entry_layer:4")],
        [InlineKeyboardButton("5 - Wait for 4 Loses", callback_data="entry_layer:5")],
        [InlineKeyboardButton("6 - Wait for 5 Loses", callback_data="entry_layer:6")],
        [InlineKeyboardButton("7 - Wait for 6 Loses", callback_data="entry_layer:7")],
        [InlineKeyboardButton("8 - Wait for 7 Loses", callback_data="entry_layer:8")],
        [InlineKeyboardButton("9 - Wait for 8 Loses", callback_data="entry_layer:9")],
        [InlineKeyboardButton("10 - Wait for 9 Loses", callback_data="entry_layer:10")]
    ]
    return InlineKeyboardMarkup(keyboard)

def make_mode_selection_keyboard():
    """Create inline keyboard for Virtual/Real mode selection"""
    keyboard = [
        [InlineKeyboardButton("🖥️ Virtual Mode", callback_data="mode:virtual")],
        [InlineKeyboardButton("💵 Real Mode", callback_data="mode:real")]
    ]
    return InlineKeyboardMarkup(keyboard)

def make_betting_strategy_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Anti-Martingale", callback_data="betting_strategy:Anti-Martingale")],
        [InlineKeyboardButton("Martingale", callback_data="betting_strategy:Martingale")],
        [InlineKeyboardButton("D'Alembert", callback_data="betting_strategy:D'Alembert")]
    ])

def make_ai_settings_keyboard():
    """Create inline keyboard for AI settings"""
    keyboard = [
        [InlineKeyboardButton("🎯 Min Confidence", callback_data="ai:min_confidence")],
        [InlineKeyboardButton("🔫 Aggressive Mode", callback_data="ai:aggressive")],
        [InlineKeyboardButton("📊 AI Performance", callback_data="ai:performance")],
        [InlineKeyboardButton("🏦 Bank Info", callback_data="ai:bank_info")],
        [InlineKeyboardButton("💳 Withdraw Bank", callback_data="ai:withdraw")],
        [InlineKeyboardButton("📈 Reset AI", callback_data="ai:reset")],
        [InlineKeyboardButton("📊 Backtest Results", callback_data="ai:backtest")]  # NEW!
    ]
    return InlineKeyboardMarkup(keyboard)

# Strategy selection keyboard
def make_strategy_keyboard():
    """Create inline keyboard for strategy selection"""
    keyboard = [
        [InlineKeyboardButton("📊 BS ORDER (Pattern)", callback_data="strategy:BS_ORDER")],
        [InlineKeyboardButton("🎯 LESLAY Formula (Even/Odd)", callback_data="strategy:LESLAY")],
        [InlineKeyboardButton("📈 LESLAY Performance", callback_data="leslay:performance")],
        [InlineKeyboardButton("🔮 TREND MASTER (Pattern)", callback_data="strategy:TREND_MASTER")],
        [InlineKeyboardButton("📊 TREND MASTER Performance", callback_data="trend:performance")],
        [InlineKeyboardButton("🤖 ULTIMATE AI 85%", callback_data="strategy:ULTIMATE_AI_85")],
        [InlineKeyboardButton("📊 AI Performance", callback_data="ai:performance")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== LESLAY FUNCTIONS ====================

async def get_leslay_prediction(session: requests.Session, user_id: int) -> dict:
    """
    LESLAY formula prediction based on last 5 results
    Even numbers (0,2,4,6,8) -> Small (S)
    Odd numbers (1,3,5,7,9) -> Big (B)
    
    Returns next prediction (B or S) and analysis
    """
    try:
        # Get last 10 game results (to ensure we have at least 5)
        history = await get_game_history(session, user_id)
        
        if len(history) < 5:
            logging.warning(f"LESLAY: Not enough history for user {user_id}, need at least 5 results")
            return {
                "result": random.choice(["B", "S"]), 
                "percent": 50,
                "even_count": 0,
                "odd_count": 0,
                "analysis": "Not enough history"
            }
        
        # Get last 5 results
        last_5 = []
        for item in history[:5]:  # Get most recent 5
            if item.get("number"):
                num = int(item.get("number", "0")) % 10
                last_5.append(num)
        
        if len(last_5) < 5:
            return {
                "result": random.choice(["B", "S"]), 
                "percent": 50,
                "even_count": 0,
                "odd_count": 0,
                "analysis": "Insufficient valid results"
            }
        
        # Store in user history
        user_leslay_last_5[user_id] = last_5
        
        # Count Even and Odd numbers
        even_count = sum(1 for num in last_5 if num in EVEN_NUMBERS)
        odd_count = sum(1 for num in last_5 if num in ODD_NUMBERS)
        
        # Make prediction based on Even/Odd count
        if even_count > odd_count:
            # More Even numbers -> Small (S)
            prediction = "S"
            confidence = (even_count / 5) * 100
            reasoning = f"Even numbers ({even_count}) > Odd numbers ({odd_count}) → SMALL (S)"
        elif odd_count > even_count:
            # More Odd numbers -> Big (B)
            prediction = "B"
            confidence = (odd_count / 5) * 100
            reasoning = f"Odd numbers ({odd_count}) > Even numbers ({even_count}) → BIG (B)"
        else:
            # Equal counts (2 Even, 2 Odd with 1 number?), use last result
            last_num = last_5[0]  # Most recent
            if last_num in EVEN_NUMBERS:
                prediction = "S"
            else:
                prediction = "B"
            confidence = 50
            reasoning = f"Even ({even_count}) = Odd ({odd_count}) → Follow last result: {last_num} → {'SMALL (S)' if last_num in EVEN_NUMBERS else 'BIG (B)'}"
        
        # Format the last 5 numbers for display
        last_5_display = [str(num) for num in last_5]
        
        # Update statistics
        if user_id not in user_leslay_stats:
            user_leslay_stats[user_id] = {
                "even_count": even_count,
                "odd_count": odd_count,
                "predictions": 0,
                "correct_predictions": 0
            }
        
        return {
            "result": prediction,
            "percent": round(confidence, 1),
            "even_count": even_count,
            "odd_count": odd_count,
            "last_5": last_5,
            "last_5_display": ", ".join(last_5_display),
            "analysis": reasoning,
            "raw_numbers": last_5
        }
        
    except Exception as e:
        logging.error(f"LESLAY prediction error for user {user_id}: {e}")
        return {
            "result": random.choice(["B", "S"]), 
            "percent": 50,
            "even_count": 0,
            "odd_count": 0,
            "analysis": f"Error: {str(e)}"
        }


async def analyze_leslay_performance(session: requests.Session, user_id: int) -> dict:
    """Analyze LESLAY formula performance"""
    try:
        history = await get_game_history(session, user_id)
        
        if len(history) < 10:
            return {"error": "Need at least 10 results for analysis"}
        
        # Get last 20 results or all available
        max_results = min(20, len(history))
        results = []
        
        for i in range(max_results - 5):  # Need 5 results to make prediction
            # Get 5 results starting from position i
            five_results = []
            for j in range(i, i + 5):
                if j < len(history) and history[j].get("number"):
                    num = int(history[j].get("number", "0")) % 10
                    five_results.append(num)
            
            if len(five_results) == 5:
                # Get the actual result after these 5
                if i + 5 < len(history) and history[i + 5].get("number"):
                    actual_num = int(history[i + 5].get("number", "0")) % 10
                    actual_bs = "B" if actual_num in ODD_NUMBERS else "S"
                    
                    # Make prediction based on these 5
                    even = sum(1 for num in five_results if num in EVEN_NUMBERS)
                    odd = 5 - even
                    
                    if even > odd:
                        predicted = "S"
                    elif odd > even:
                        predicted = "B"
                    else:
                        predicted = "B" if five_results[0] in ODD_NUMBERS else "S"
                    
                    results.append({
                        "predicted": predicted,
                        "actual": actual_bs,
                        "correct": predicted == actual_bs,
                        "even": even,
                        "odd": odd
                    })
        
        if not results:
            return {"error": "Could not analyze performance"}
        
        # Calculate statistics
        total = len(results)
        correct = sum(1 for r in results if r["correct"])
        accuracy = (correct / total) * 100 if total > 0 else 0
        
        # Calculate when even > odd
        even_cases = [r for r in results if r["even"] > r["odd"]]
        even_correct = sum(1 for r in even_cases if r["correct"])
        even_accuracy = (even_correct / len(even_cases) * 100) if even_cases else 0
        
        # Calculate when odd > even
        odd_cases = [r for r in results if r["odd"] > r["even"]]
        odd_correct = sum(1 for r in odd_cases if r["correct"])
        odd_accuracy = (odd_correct / len(odd_cases) * 100) if odd_cases else 0
        
        # Calculate when equal
        equal_cases = [r for r in results if r["even"] == r["odd"]]
        equal_correct = sum(1 for r in equal_cases if r["correct"])
        equal_accuracy = (equal_correct / len(equal_cases) * 100) if equal_cases else 0
        
        return {
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy": round(accuracy, 2),
            "even_cases": len(even_cases),
            "even_accuracy": round(even_accuracy, 2),
            "odd_cases": len(odd_cases),
            "odd_accuracy": round(odd_accuracy, 2),
            "equal_cases": len(equal_cases),
            "equal_accuracy": round(equal_accuracy, 2)
        }
        
    except Exception as e:
        logging.error(f"LESLAY performance analysis error: {e}")
        return {"error": str(e)}

# ==================== TREND MASTER FUNCTIONS ====================

async def get_trend_master_prediction(session: requests.Session, user_id: int) -> dict:
    """
    TREND MASTER formula - Analyzes patterns of last 3 results
    Uses predefined pattern database to predict next result
    """
    try:
        history = await get_game_history(session, user_id)
        
        if len(history) < 3:
            logging.warning(f"TREND MASTER: Not enough history for user {user_id}, need at least 3 results")
            return {
                "result": random.choice(["B", "S"]),
                "confidence": 50,
                "pattern": "Insufficient history",
                "analysis": "Need at least 3 results for pattern analysis"
            }
        
        # Get last 3 results and convert to B/S
        last_3_results = []
        last_3_numbers = []
        
        for i in range(3):
            if i < len(history) and history[i].get("number"):
                num = int(history[i].get("number", "0")) % 10
                bs = "B" if num >= 5 else "S"
                last_3_results.append(bs)
                last_3_numbers.append(str(num))
        
        if len(last_3_results) < 3:
            return {
                "result": random.choice(["B", "S"]),
                "confidence": 50,
                "pattern": "Invalid results",
                "analysis": "Could not get valid last 3 results"
            }
        
        # Store in user history
        user_trend_last_3[user_id] = last_3_results
        
        # Create pattern string
        pattern = "".join(last_3_results)
        
        # Make prediction based on pattern
        if pattern in TREND_PATTERNS:
            prediction = TREND_PATTERNS[pattern]
            confidence = 75  # High confidence for known patterns
            reasoning = f"Pattern '{pattern}' detected → Next should be {prediction}"
        else:
            # For unknown patterns, follow the majority or last result
            b_count = last_3_results.count("B")
            s_count = last_3_results.count("S")
            
            if b_count > s_count:
                prediction = "B"
                confidence = 60
                reasoning = f"Majority BIG ({b_count}B vs {s_count}S) → Next BIG"
            elif s_count > b_count:
                prediction = "S"
                confidence = 60
                reasoning = f"Majority SMALL ({s_count}S vs {b_count}B) → Next SMALL"
            else:
                # Equal counts, follow last result
                prediction = last_3_results[-1]
                confidence = 50
                reasoning = f"Equal pattern ({b_count}B, {s_count}S) → Follow last: {prediction}"
        
        # Update statistics
        if user_id not in user_trend_stats:
            user_trend_stats[user_id] = {
                "patterns_analyzed": 0,
                "correct_predictions": 0,
                "pattern_accuracy": {}
            }
        
        # Track this prediction for future accuracy calculation
        if user_id not in user_trend_predictions:
            user_trend_predictions[user_id] = []
        
        user_trend_predictions[user_id].append({
            "pattern": pattern,
            "prediction": prediction,
            "timestamp": time.time()
        })
        
        # Keep only last 50 predictions
        if len(user_trend_predictions[user_id]) > 50:
            user_trend_predictions[user_id] = user_trend_predictions[user_id][-50:]
        
        return {
            "result": prediction,
            "confidence": confidence,
            "pattern": pattern,
            "last_3": last_3_results,
            "last_3_numbers": ", ".join(last_3_numbers),
            "analysis": reasoning,
            "b_count": last_3_results.count("B"),
            "s_count": last_3_results.count("S")
        }
        
    except Exception as e:
        logging.error(f"TREND MASTER prediction error for user {user_id}: {e}")
        return {
            "result": random.choice(["B", "S"]),
            "confidence": 50,
            "pattern": "Error",
            "analysis": f"Error: {str(e)}"
        }


async def analyze_trend_master_performance(session: requests.Session, user_id: int) -> dict:
    """Analyze TREND MASTER performance"""
    try:
        history = await get_game_history(session, user_id)
        
        if len(history) < 10:
            return {"error": "Need at least 10 results for analysis"}
        
        # Analyze historical patterns
        results = []
        pattern_stats = {}
        
        for i in range(len(history) - 3):
            # Get 3 results for pattern
            pattern_results = []
            for j in range(i, i + 3):
                if j < len(history) and history[j].get("number"):
                    num = int(history[j].get("number", "0")) % 10
                    bs = "B" if num >= 5 else "S"
                    pattern_results.append(bs)
            
            if len(pattern_results) == 3:
                pattern = "".join(pattern_results)
                
                # Get actual next result
                if i + 3 < len(history) and history[i + 3].get("number"):
                    next_num = int(history[i + 3].get("number", "0")) % 10
                    next_bs = "B" if next_num >= 5 else "S"
                    
                    # Get prediction for this pattern
                    if pattern in TREND_PATTERNS:
                        predicted = TREND_PATTERNS[pattern]
                    else:
                        b_count = pattern_results.count("B")
                        s_count = pattern_results.count("S")
                        if b_count > s_count:
                            predicted = "B"
                        elif s_count > b_count:
                            predicted = "S"
                        else:
                            predicted = pattern_results[-1]
                    
                    correct = predicted == next_bs
                    
                    results.append({
                        "pattern": pattern,
                        "predicted": predicted,
                        "actual": next_bs,
                        "correct": correct
                    })
                    
                    # Update pattern stats
                    if pattern not in pattern_stats:
                        pattern_stats[pattern] = {"total": 0, "correct": 0}
                    pattern_stats[pattern]["total"] += 1
                    if correct:
                        pattern_stats[pattern]["correct"] += 1
        
        if not results:
            return {"error": "Could not analyze performance"}
        
        # Calculate overall statistics
        total = len(results)
        correct = sum(1 for r in results if r["correct"])
        accuracy = (correct / total) * 100 if total > 0 else 0
        
        # Calculate pattern-specific accuracy
        pattern_accuracy = {}
        for pattern, stats in pattern_stats.items():
            if stats["total"] > 0:
                pattern_accuracy[pattern] = round((stats["correct"] / stats["total"]) * 100, 2)
        
        # Find best and worst patterns
        best_pattern = max(pattern_accuracy.items(), key=lambda x: x[1]) if pattern_accuracy else ("None", 0)
        worst_pattern = min(pattern_accuracy.items(), key=lambda x: x[1]) if pattern_accuracy else ("None", 0)
        
        return {
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy": round(accuracy, 2),
            "patterns_found": len(pattern_stats),
            "pattern_accuracy": pattern_accuracy,
            "best_pattern": best_pattern[0] if best_pattern[0] != "None" else "N/A",
            "best_accuracy": best_pattern[1] if best_pattern[0] != "None" else 0,
            "worst_pattern": worst_pattern[0] if worst_pattern[0] != "None" else "N/A",
            "worst_accuracy": worst_pattern[1] if worst_pattern[0] != "None" else 0
        }
        
    except Exception as e:
        logging.error(f"TREND MASTER performance analysis error: {e}")
        return {"error": str(e)}

# ==================== END OF NEW FORMULA FUNCTIONS ====================

async def check_profit_and_stop_loss(user_id: int, bot, context: ContextTypes.DEFAULT_TYPE):
    """Check if profit target or stop loss has been reached"""
    settings = user_settings.get(user_id, {})
    target_profit = settings.get("target_profit")
    stop_loss = settings.get("stop_loss")
    
    if not target_profit and not stop_loss:
        return False
    
    current_profit = user_stats[user_id].get("profit", 0) if user_id in user_stats else 0
    
    if target_profit and current_profit >= target_profit:
        settings["running"] = False
        user_waiting_for_result.pop(user_id, None)
        user_should_skip_next.pop(user_id, None)
        
        # Reset betting strategy
        settings["martin_index"] = 0
        settings["dalembert_units"] = 1
        settings["custom_index"] = 0
        
        session = user_sessions.get(user_id)
        current_balance = await get_balance(session, user_id) if session else None
        balance_text = f"Final Balance: {current_balance:.2f} MMK\n" if current_balance is not None else ""
        
        message = f"🎯 PROFIT TARGET REACHED! 🎯\nTarget: {target_profit} MMK\nAchieved: {current_profit:.2f} MMK\n{balance_text}"
        
        await send_message_with_retry(bot, user_id, message, make_main_keyboard(True))
        user_stop_initiated[user_id] = True
        return True
    
    if stop_loss and current_profit <= -stop_loss:
        settings["running"] = False
        user_waiting_for_result.pop(user_id, None)
        user_should_skip_next.pop(user_id, None)
        
        # Reset betting strategy
        settings["martin_index"] = 0
        settings["dalembert_units"] = 1
        settings["custom_index"] = 0
        
        session = user_sessions.get(user_id)
        current_balance = await get_balance(session, user_id) if session else None
        balance_text = f"Final Balance: {current_balance:.2f} MMK\n" if current_balance is not None else ""
        
        message = f"🚫 STOP LOSS LIMIT REACHED! 🚫\nStop Loss Limit: {stop_loss} MMK\nCurrent Loss: {abs(current_profit):.2f} MMK\n{balance_text}"
        
        await send_message_with_retry(bot, user_id, message, make_main_keyboard(True))
        user_stop_initiated[user_id] = True
        return True
    
    return False

def update_betting_strategy(settings: dict, is_win: bool, bet_amount: float):
    """Update betting strategy based on win/loss"""
    betting_strategy = settings.get("betting_strategy", "Martingale")
    bet_sizes = settings.get("bet_sizes", [100])
    
    logging.debug(f"Updating betting strategy - Strategy: {betting_strategy}, Result: {'WIN' if is_win else 'LOSS'}, Bet Amount: {bet_amount}")
    
    if betting_strategy == "Martingale":
        if is_win:
            settings["martin_index"] = 0
            logging.info("Martingale: Win - Reset to index 0")
        else:
            settings["martin_index"] = min((settings.get("martin_index", 0) + 1, len(bet_sizes) - 1))
            logging.info(f"Martingale: Loss - Move to index {settings['martin_index']}")
    
    elif betting_strategy == "Anti-Martingale":
        if is_win:
            settings["martin_index"] = min((settings.get("martin_index", 0) + 1, len(bet_sizes) - 1))
            logging.info(f"Anti-Martingale: Win - Move to index {settings['martin_index']}")
        else:
            settings["martin_index"] = 0
            logging.info("Anti-Martingale: Loss - Reset to index 0")
    
    elif betting_strategy == "D'Alembert":
        if is_win:
            settings["dalembert_units"] = max(1, (settings.get("dalembert_units", 1) - 1))
            logging.info(f"D'Alembert: Win - Decrease units to {settings['dalembert_units']}")
        else:
            settings["dalembert_units"] = (settings.get("dalembert_units", 1) + 1)
            logging.info(f"D'Alembert: Loss - Increase units to {settings['dalembert_units']}")
    
    elif betting_strategy == "Custom":
        current_index = settings.get("custom_index", 0)
        
        # Find actual index based on bet amount
        actual_index = 0
        for i, size in enumerate(bet_sizes):
            if size == bet_amount:
                actual_index = i
                break
        
        if is_win:
            if actual_index > 0:
                settings["custom_index"] = actual_index - 1
            else:
                settings["custom_index"] = 0
            logging.info(f"Custom: Win - Move to index {settings['custom_index']}")
        else:
            if actual_index < len(bet_sizes) - 1:
                settings["custom_index"] = actual_index + 1
            else:
                settings["custom_index"] = len(bet_sizes) - 1
            logging.info(f"Custom: Loss - Move to index {settings['custom_index']}")

async def win_lose_checker(context: ContextTypes.DEFAULT_TYPE):
    """Enhanced win/lose checker with Entry Layer and SL support"""
    logging.info("Win/lose checker started for WINGO 30S with Entry Layer and SL support")
    while True:
        try:
            for user_id, session in list(user_sessions.items()):
                if not session:
                    continue
                
                settings = user_settings.get(user_id, {})
                if not settings:
                    continue
                
                # Get game results
                wingo_res = await get_wingo_game_results(session)
                if not wingo_res or wingo_res.get("code") != 0:
                    continue
                    
                data = wingo_res.get("data", {}).get("list", [])
                
                # Process pending bets (real bets)
                if user_id in user_pending_bets:
                    for period in list(user_pending_bets[user_id].keys()):
                        settled = next((item for item in data if item.get("issueNumber") == period), None)
                        
                        if settled and settled.get("number"):
                            bet_type, amount, is_virtual = user_pending_bets[user_id][period]
                            number = int(settled.get("number", "0")) % 10
                            big_small = "B" if number >= 5 else "S"
                            is_win = (bet_type == "B" and big_small == "B") or (bet_type == "S" and big_small == "S")
                            
                            # Process AI result if using Ultimate AI
                            if settings.get("strategy") == "ULTIMATE_AI_85":
                                ai_manager.process_result(user_id, is_win, amount)
                            
                            # Update SL logic for REAL BETS
                            sl_limit = settings.get("sl_limit")
                            if sl_limit and sl_limit > 0 and not is_virtual:  # Only for real bets
                                if is_win:
                                    # Reset consecutive losses on win
                                    settings["consecutive_losses"] = 0
                                    settings["skip_betting"] = False
                                    user_sl_skip_waiting_for_win.pop(user_id, None)
                                    logging.info(f"SL: Real bet WIN detected for user {user_id}, resetting consecutive losses and resuming betting")
                                else:
                                    # Increment consecutive losses for real bets
                                    current_losses = settings.get("consecutive_losses", 0)
                                    settings["consecutive_losses"] = current_losses + 1
                                    logging.info(f"SL: Real bet LOSS detected for user {user_id}, consecutive losses: {current_losses + 1}")
                                    
                                    # Check if SL limit reached
                                    if current_losses + 1 >= sl_limit:
                                        settings["skip_betting"] = True
                                        user_sl_skip_waiting_for_win[user_id] = True
                                        logging.info(f"SL: Limit reached for user {user_id}, skipping real bets until win")
                            
                            # Update Entry Layer state
                            entry_layer = settings.get("layer_limit", 1)
                            entry_state = settings.get("entry_layer_state", {})
                            
                            if entry_layer == 2:
                                if is_win:
                                    entry_state["waiting_for_lose"] = True
                                else:
                                    entry_state["waiting_for_lose"] = False
                            elif entry_layer >= 3:
                                if is_win:
                                    entry_state["waiting_for_loses"] = True
                                    entry_state["consecutive_loses"] = 0
                                else:
                                    current_consecutive = entry_state.get("consecutive_loses", 0)
                                    entry_state["consecutive_loses"] = current_consecutive + 1
                                    wait_count = entry_layer - 1
                                    if current_consecutive + 1 >= wait_count:
                                        entry_state["waiting_for_loses"] = False
                            
                            settings["entry_layer_state"] = entry_state
                            
                            # Update betting strategy for both real and virtual bets
                            update_betting_strategy(settings, is_win, amount)
                            
                            # Update TREND MASTER statistics for result tracking
                            if settings.get("strategy") == "TREND_MASTER" and user_id in user_trend_predictions:
                                # Check if we had a prediction for this period
                                for pred in user_trend_predictions[user_id]:
                                    # Simple check - if prediction was made recently (within last 2 minutes)
                                    if time.time() - pred.get("timestamp", 0) < 120:
                                        if pred.get("prediction") == big_small:
                                            user_trend_stats[user_id]["correct_predictions"] = user_trend_stats[user_id].get("correct_predictions", 0) + 1
                                        user_trend_stats[user_id]["patterns_analyzed"] = user_trend_stats[user_id].get("patterns_analyzed", 0) + 1
                                        break
                            
                            # Update virtual or real balance
                            if is_virtual:
                                if user_id not in user_stats:
                                    user_stats[user_id] = {"virtual_balance": VIRTUAL_BALANCE}
                                if is_win:
                                    user_stats[user_id]["virtual_balance"] += amount * 0.96
                                else:
                                    user_stats[user_id]["virtual_balance"] -= amount
                            else:
                                if user_id in user_stats:
                                    if is_win:
                                        profit_change = amount * 0.96
                                        user_stats[user_id]["profit"] += profit_change
                                    else:
                                        user_stats[user_id]["profit"] -= amount
                            
                            # Check profit target and stop loss
                            bot_stopped = await check_profit_and_stop_loss(user_id, context.bot, context)
                            if bot_stopped:
                                del user_pending_bets[user_id][period]
                                if not user_pending_bets[user_id]:
                                    del user_pending_bets[user_id]
                                user_waiting_for_result[user_id] = False
                                continue
                            
                            # Get current balance
                            current_balance = None
                            if is_virtual:
                                current_balance = user_stats[user_id].get("virtual_balance", VIRTUAL_BALANCE)
                            else:
                                current_balance = await get_balance(session, user_id)
                            
                            # Prepare result message
                            total_profit = 0
                            if is_virtual:
                                total_profit = user_stats[user_id].get("virtual_balance", VIRTUAL_BALANCE) - VIRTUAL_BALANCE
                            else:
                                total_profit = user_stats[user_id].get("profit", 0) if user_id in user_stats else 0
                            
                            profit_indicator = "+" if total_profit > 0 else ("-" if total_profit < 0 else "")
                            
                            # Add SL info to message if applicable
                            sl_info = ""
                            sl_limit = settings.get("sl_limit")
                            if sl_limit and sl_limit > 0 and not is_virtual:
                                current_losses = settings.get("consecutive_losses", 0)
                                if settings.get("skip_betting", False):
                                    sl_info = f"\n\n⛔ SL ACTIVE: {current_losses}/{sl_limit} losses - Waiting for win"
                                else:
                                    sl_info = f"\n\n⛔ SL: {current_losses}/{sl_limit} losses"
                            
                            if is_win:
                                win_amount = amount * 0.96
                                bet_type_str = "VIRTUAL" if is_virtual else "REAL"
                                message = f"💚 {bet_type_str} WIN +{win_amount:.2f} MMK\n\n💸 Balance: {current_balance:.2f} MMK\n\n📈 Total Profit: {profit_indicator}{abs(total_profit):.2f} MMK\n\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_info}"
                            else:
                                bet_type_str = "VIRTUAL" if is_virtual else "REAL"
                                message = f"💔 {bet_type_str} LOSE -{amount:.2f} MMK\n\n💸 Balance: {current_balance:.2f} MMK\n\n📈 Total Profit: {profit_indicator}{abs(total_profit):.2f} MMK\n\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_info}"
                            
                            await send_message_with_retry(context.bot, user_id, message)
                            
                            # Clean up
                            del user_pending_bets[user_id][period]
                            if not user_pending_bets[user_id]:
                                del user_pending_bets[user_id]
                            user_waiting_for_result[user_id] = False
            
            # Process skipped bets (for Entry Layer and SL)
            for user_id, skipped_bets in list(user_skipped_bets.items()):
                if not skipped_bets:
                    continue
                    
                session = user_sessions.get(user_id)
                if not session:
                    continue
                    
                settings = user_settings.get(user_id, {})
                if not settings:
                    continue
                
                # Get game results
                wingo_res = await get_wingo_game_results(session)
                if not wingo_res or wingo_res.get("code") != 0:
                    continue
                    
                data = wingo_res.get("data", {}).get("list", [])
                
                for period in list(skipped_bets.keys()):
                    settled = next((item for item in data if item.get("issueNumber") == period), None)
                    
                    if settled and settled.get("number"):
                        bet_type, is_virtual = skipped_bets[period]
                        number = int(settled.get("number", "0")) % 10
                        big_small = "B" if number >= 5 else "S"
                        is_win = (bet_type == "B" and big_small == "B") or (bet_type == "S" and big_small == "S")
                        
                        # Update SL logic for SKIPPED BETS (virtual bets during SL period)
                        sl_limit = settings.get("sl_limit")
                        sl_resume_msg = ""
                        if sl_limit and sl_limit > 0 and settings.get("skip_betting", False):
                            if is_win:
                                # SL skip period win detected - resume real betting with current betting strategy
                                settings["consecutive_losses"] = 0
                                settings["skip_betting"] = False
                                user_sl_skip_waiting_for_win.pop(user_id, None)
                                logging.info(f"SL: Skip period WIN detected for user {user_id}, resetting consecutive losses and resuming REAL betting with current strategy")
                                
                                # Add special message for SL resume
                                sl_resume_msg = f"\n\n🎉 SL PERIOD ENDED - RESUMING REAL BETS! 🎉\nBetting Strategy: {settings.get('betting_strategy', 'Martingale')}"
                        
                        # Update Entry Layer state for skipped bets
                        entry_layer = settings.get("layer_limit", 1)
                        entry_state = settings.get("entry_layer_state", {})
                        
                        if entry_layer == 2:
                            if is_win:
                                entry_state["waiting_for_lose"] = True
                                message = f"🟢 SKIP WIN +0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_resume_msg}"
                            else:
                                if entry_state.get("waiting_for_lose", True):
                                    entry_state["waiting_for_lose"] = False
                                message = f"🔴 SKIP LOSE -0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_resume_msg}"
                                
                        elif entry_layer >= 3:
                            if is_win:
                                entry_state["waiting_for_loses"] = True
                                entry_state["consecutive_loses"] = 0
                                message = f"🟢 SKIP WIN +0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_resume_msg}"
                            else:
                                current_consecutive = entry_state.get("consecutive_loses", 0)
                                entry_state["consecutive_loses"] = current_consecutive + 1
                                wait_count = entry_layer - 1
                                
                                if current_consecutive + 1 >= wait_count:
                                    entry_state["waiting_for_loses"] = False
                                    message = f"🔴 SKIP LOSE -0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_resume_msg}"
                                else:
                                    remaining = wait_count - (current_consecutive + 1)
                                    message = f"🔴 SKIP LOSE -0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}\n⏳ Waiting for {remaining} more lose(s){sl_resume_msg}"
                        
                        else:
                            # For Entry Layer 1 or no entry layer, just show basic skip result
                            if is_win:
                                message = f"🟢 SKIP WIN +0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_resume_msg}"
                            else:
                                message = f"🔴 SKIP LOSE -0 MMK\n🆔 WINGO30S: {period} =>{big_small}•{number}{sl_resume_msg}"
                        
                        settings["entry_layer_state"] = entry_state
                        
                        await send_message_with_retry(context.bot, user_id, message)
                        del user_skipped_bets[user_id][period]
                        
                        if user_skip_result_wait.get(user_id) == period:
                            del user_skip_result_wait[user_id]
            
            await asyncio.sleep(WIN_LOSE_CHECK_INTERVAL)
        except Exception as e:
            logging.error(f"Win/lose checker error: {e}")
            await asyncio.sleep(10)

def calculate_bet_amount(settings: dict, current_balance: float) -> float:
    """Calculate bet amount based on betting strategy"""
    betting_strategy = settings.get("betting_strategy", "Martingale")
    bet_sizes = settings.get("bet_sizes", [100])
    
    logging.debug(f"Calculating bet amount - Strategy: {betting_strategy}, Bet Sizes: {bet_sizes}")
    
    if betting_strategy == "D'Alembert":
        if len(bet_sizes) > 1:
            raise ValueError("D'Alembert strategy requires only ONE bet size")
        
        unit_size = bet_sizes[0]
        units = settings.get("dalembert_units", 1)
        amount = unit_size * units
        
        # Adjust if amount exceeds balance
        while amount > current_balance and units > 1:
            units -= 1
            amount = unit_size * units
        
        if amount > current_balance:
            amount = current_balance
        
        min_bet = min(bet_sizes)
        if amount < min_bet:
            amount = min_bet
            
        logging.info(f"D'Alembert: Betting {amount} ({units} units of {unit_size})")
        return amount
        
    elif betting_strategy == "Custom":
        custom_index = settings.get("custom_index", 0)
        adjusted_index = min(custom_index, len(bet_sizes) - 1)
        amount = bet_sizes[adjusted_index]
        logging.info(f"Custom: Betting {amount} at index {adjusted_index}")
        return amount
        
    else:  # Martingale or Anti-Martingale
        martin_index = settings.get("martin_index", 0)
        adjusted_index = min(martin_index, len(bet_sizes) - 1)
        amount = bet_sizes[adjusted_index]
        logging.info(f"{betting_strategy}: Betting {amount} at index {adjusted_index}")
        return amount

async def betting_worker(user_id: int, chat_id: int, app_context: ContextTypes.DEFAULT_TYPE):
    """Enhanced betting worker with Entry Layer and SL support"""
    settings = user_settings.get(user_id, {})
    session = user_sessions.get(user_id)
    
    if not settings or not session:
        logging.error(f"Betting worker failed for user {user_id}: No settings or session")
        await send_message_with_retry(app_context.bot, chat_id, "Please login first")
        if settings:
            settings["running"] = False
        return
    
    # Initialize user settings if not exists
    if user_id not in user_settings:
        user_settings[user_id] = get_default_user_settings()
    
    # Initialize AI settings
    ai_manager.set_setting(user_id, "min_confidence", settings.get("ai_min_confidence", 70))
    ai_manager.set_setting(user_id, "aggressive", settings.get("ai_aggressive", False))
    
    # Initialize stats
    if settings.get("virtual_mode", False):
        user_stats[user_id] = {"virtual_balance": VIRTUAL_BALANCE}
    else:
        user_stats[user_id] = {"start_balance": user_stats.get(user_id, {}).get("start_balance", 0.0), "profit": 0.0}
    
    # Initialize betting state
    settings["running"] = True
    settings["bet_time"] = {}
    settings["last_issue"] = None
    settings["consecutive_errors"] = 0
    settings["consecutive_losses"] = 0
    settings["skip_betting"] = False
    
    # Initialize Entry Layer state
    entry_layer = settings.get("layer_limit", 1)
    if entry_layer == 2:
        settings["entry_layer_state"] = {"waiting_for_lose": True}
    elif entry_layer >= 3:
        settings["entry_layer_state"] = {"waiting_for_loses": True, "consecutive_loses": 0}
    else:
        settings["entry_layer_state"] = {}
    
    user_should_skip_next[user_id] = False
    
    # Get initial balance
    current_balance = None
    if settings.get("virtual_mode", False):
        current_balance = user_stats[user_id].get("virtual_balance", VIRTUAL_BALANCE)
    else:
        for attempt in range(MAX_BALANCE_RETRIES):
            current_balance = await get_balance(session, user_id)
            bet_sizes = settings.get("bet_sizes", [100])
            if not bet_sizes:
                logging.error(f"No bet sizes set for user {user_id}")
                await send_message_with_retry(app_context.bot, chat_id, "No bet sizes set. Please set BET SIZE first.")
                settings["running"] = False
                break
            if current_balance is not None and current_balance >= min(bet_sizes):
                settings["consecutive_errors"] = 0
                break
            logging.warning(f"Balance check failed for user {user_id}, attempt {attempt + 1}/{MAX_BALANCE_RETRIES}: {current_balance}")
            if attempt == MAX_BALANCE_RETRIES - 1:
                logging.error(f"Failed to get initial balance for user {user_id} after {MAX_BALANCE_RETRIES} attempts")
                await send_message_with_retry(app_context.bot, chat_id, "Failed to check balance. Stopping...")
                settings["running"] = False
                return
            await asyncio.sleep(BALANCE_RETRY_DELAY)
    
    if not settings["running"]:
        return
    
    # Prepare start message
    start_message = f"✅ BOT START\n\n"
    start_message += f"💠 Balance: {current_balance:.2f} MMK\n\n"
    start_message += f"🎯 Profit Target: {settings.get('target_profit', '0')} MMK\n"
    start_message += f"🛡️ Stop Loss: {settings.get('stop_loss', '0')} MMK\n"
    
    # Add SL info to start message
    sl_limit = settings.get("sl_limit")
    if sl_limit:
        start_message += f"⛔ SL Limit: {sl_limit} consecutive losses\n"
    
    if settings.get("betting_strategy"):
        betting_strategy_display = settings["betting_strategy"]
        start_message += f"🚀 Betting Strategy: {betting_strategy_display}\n"
    
    if settings.get("strategy"):
        strategy_display = settings["strategy"]
        if strategy_display == "ULTIMATE_AI_85":
            strategy_display = "🤖 ULTIMATE AI 85%"
        start_message += f"📊 Strategy: {strategy_display}"
    
    await send_message_with_retry(app_context.bot, chat_id, start_message)
    logging.info(f"Betting worker started for user {user_id}, game: WINGO 30S, settings: {settings}")
    
    try:
        while settings["running"]:
            if user_waiting_for_result.get(user_id, False):
                logging.debug(f"User {user_id} waiting for result, skipping cycle")
                await asyncio.sleep(1)
                continue

            # Get current balance
            if settings.get("virtual_mode", False):
                current_balance = user_stats[user_id].get("virtual_balance", VIRTUAL_BALANCE)
            else:
                current_balance = await get_balance(session, user_id)
                if current_balance is None:
                    logging.warning(f"Failed to get balance for user {user_id}")
                    settings["consecutive_errors"] += 1
                    if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                        await send_message_with_retry(app_context.bot, chat_id, f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping bot.")
                        settings["running"] = False
                        break
                    await asyncio.sleep(5)
                    continue

            bet_sizes = settings.get("bet_sizes", [100])
            if not bet_sizes:
                logging.error(f"No bet sizes set for user {user_id}")
                await send_message_with_retry(app_context.bot, chat_id, "No bet sizes set. Please set BET SIZE first.")
                settings["running"] = False
                break
            
            min_bet_size = min(bet_sizes)
            if current_balance < min_bet_size:
                message = f"❌ Insufficient balance!\nCurrent Balance: {current_balance:.2f} MMK\nMinimum Bet Required: {min_bet_size} MMK\nPlease add funds to continue betting."
                await send_message_with_retry(app_context.bot, chat_id, message, make_main_keyboard(True))
                settings["running"] = False
                break
            
            # Get game issue
            issue_res = await get_wingo_game_issue_request(session)
                
            if not isinstance(issue_res, dict) or issue_res.get("code") != 0:
                logging.error(f"Game issue request failed for user {user_id}, WINGO 30S: {issue_res}")
                settings["consecutive_errors"] += 1
                if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                    logging.error(f"Max consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached for user {user_id}. Stopping bot.")
                    await send_message_with_retry(app_context.bot, chat_id, f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping bot.")
                    settings["running"] = False
                    break
                await asyncio.sleep(2)
                continue
            
            data = issue_res.get("data", {})
            current_issue = data.get("issueNumber")
                
            if not current_issue:
                logging.warning(f"No valid issue number for user {user_id}, WINGO 30S: {data}")
                settings["consecutive_errors"] += 1
                if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                    logging.error(f"Max consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached for user {user_id}. Stopping bot.")
                    await send_message_with_retry(app_context.bot, chat_id, f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping bot.")
                    settings["running"] = False
                    break
                await asyncio.sleep(1)
                continue
            
            if current_issue == settings.get("last_issue"):
                logging.debug(f"Same issue {current_issue} for user {user_id}, waiting for new issue")
                await asyncio.sleep(1)
                continue

            # Get prediction based on selected strategy
            strategy = settings.get("strategy", "BS_ORDER")
            
            if strategy == "LESLAY":
                # Use LESLAY formula for prediction
                prediction = await get_leslay_prediction(session, user_id)
                ch = prediction["result"]
                confidence = prediction.get("percent", "N/A")
                
                # Store for display
                leslay_analysis = prediction.get("analysis", "")
                last_5_nums = prediction.get("last_5_display", "")
                even_count = prediction.get("even_count", 0)
                odd_count = prediction.get("odd_count", 0)
                
                logging.info(f"LESLAY Prediction for user {user_id}: {ch} (Even:{even_count}, Odd:{odd_count})")
                
            elif strategy == "TREND_MASTER":
                # Use TREND MASTER formula for prediction
                prediction = await get_trend_master_prediction(session, user_id)
                ch = prediction["result"]
                confidence = prediction.get("confidence", 50)
                
                # Store for display
                trend_analysis = prediction.get("analysis", "")
                last_3_nums = prediction.get("last_3_numbers", "")
                pattern = prediction.get("pattern", "")
                b_count = prediction.get("b_count", 0)
                s_count = prediction.get("s_count", 0)
                
                logging.info(f"TREND MASTER Prediction for user {user_id}: {ch} (Pattern:{pattern})")
                
            elif strategy == "ULTIMATE_AI_85":
                # Get game history for AI
                history_data = await get_game_history(session, user_id)
                history_numbers = []
                for item in history_data[:15]:
                    if item.get("number"):
                        num = int(item.get("number", "0")) % 10
                        history_numbers.append(num)
                
                if len(history_numbers) < 5:
                    # Not enough history, use random
                    ch = random.choice(["B", "S"])
                    confidence = 50
                    ai_analysis = "Not enough history for AI"
                    predicted_number = random.randint(0, 9)
                    desired_amount = calculate_bet_amount(settings, current_balance)
                else:
                    # Use Ultimate AI
                    ai_result = ai_manager.predict_and_bet(user_id, history_numbers, current_balance)
                    ch = ai_result["prediction"]["result"]
                    confidence = ai_result["prediction"]["percent"]
                    predicted_number = ai_result["prediction"]["number"]
                    ai_analysis = ai_result["prediction"].get("votes", "")
                    bank_info = ai_result["bank_info"]
                    desired_amount = ai_result["bet_amount"]  # Use AI's bet amount
                
                logging.info(f"ULTIMATE AI Prediction for user {user_id}: {ch} ({confidence}%)")
                
            else:  # BS_ORDER
                # Use BS_ORDER pattern (original method)
                pattern = settings.get("pattern", DEFAULT_BS_ORDER)
                pattern_index = settings.get("pattern_index", 0)
                ch = pattern[pattern_index % len(pattern)]
                prediction = {"result": ch, "percent": "N/A"}
                confidence = "N/A"
                leslay_analysis = ""
                last_5_nums = ""
                even_count = 0
                odd_count = 0
                trend_analysis = ""
                last_3_nums = ""
                pattern = ""
                b_count = 0
                s_count = 0
            
            select_type = get_select_map().get(ch)
            
            if select_type is None:
                logging.error(f"Invalid bet type {ch} for user {user_id}")
                settings["consecutive_errors"] += 1
                if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                    logging.error(f"Max consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached for user {user_id}. Stopping bot.")
                    await send_message_with_retry(app_context.bot, chat_id, f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping bot.")
                    settings["running"] = False
                    break
                await asyncio.sleep(2)
                continue
            
            # Check SL condition first (highest priority)
            sl_limit = settings.get("sl_limit")
            should_skip = False
            skip_reason = ""
            
            if sl_limit and sl_limit > 0 and settings.get("skip_betting", False):
                should_skip = True
                current_losses = settings.get("consecutive_losses", 0)
                skip_reason = f"⛔ SL ACTIVE: {current_losses}/{sl_limit} losses - Waiting for win"
            
            # Check Entry Layer condition only if not skipping due to SL
            if not should_skip:
                entry_layer = settings.get("layer_limit", 1)
                entry_state = settings.get("entry_layer_state", {})
                
                if entry_layer == 2:
                    if entry_state.get("waiting_for_lose", True):
                        should_skip = True
                        skip_reason = "Entry Layer 2: Waiting for 1 lose"
                elif entry_layer >= 3:
                    if entry_state.get("waiting_for_loses", True):
                        should_skip = True
                        current_consecutive = entry_state.get("consecutive_loses", 0)
                        wait_count = entry_layer - 1
                        skip_reason = f"Entry Layer {entry_layer}: Waiting for {wait_count} consecutive loses (current: {current_consecutive})"
            
            if should_skip:
                # Skip this bet
                bet_msg = f"🚨 {skip_reason}\n\n🆔 WINGO30S: {current_issue}\n🎯 BET: {'BIG' if ch == 'B' else 'SMALL'} ==> 0 MMK"
                
                if user_id not in user_skipped_bets:
                    user_skipped_bets[user_id] = {}
                user_skipped_bets[user_id][current_issue] = [ch, settings.get("virtual_mode", False)]
                
                user_skip_result_wait[user_id] = current_issue
                
                await send_message_with_retry(app_context.bot, chat_id, bet_msg)
                
                # Wait for result
                wait_attempts = 0
                max_wait_attempts = 60
                result_available = False
                
                while not result_available and wait_attempts < max_wait_attempts and settings["running"]:
                    await asyncio.sleep(1)
                    
                    if user_skip_result_wait.get(user_id) != current_issue:
                        result_available = True
                    
                    wait_attempts += 1
                
                if not result_available:
                    if user_skip_result_wait.get(user_id) == current_issue:
                        del user_skip_result_wait[user_id]
                
                settings["last_issue"] = current_issue
                await asyncio.sleep(1)
                continue
            
            # Calculate bet amount
            try:
                if strategy == "ULTIMATE_AI_85" and 'desired_amount' in locals() and desired_amount:
                    # Already set by AI
                    pass
                else:
                    desired_amount = calculate_bet_amount(settings, current_balance)
            except ValueError as e:
                await send_message_with_retry(app_context.bot, chat_id, 
                    f"❌ {str(e)}\nPlease stop bot and set Bet Size again.",
                    make_main_keyboard(True)
                )
                settings["running"] = False
                break
            
            # Compute actual bet details
            unit_amount = compute_unit_amount(desired_amount)
            bet_count = max(1, int(desired_amount / unit_amount))
            actual_amount = unit_amount * bet_count
            
            if actual_amount == 0:
                await send_message_with_retry(app_context.bot, chat_id,
                    f"❌ Invalid bet amount: {desired_amount} MMK\nMinimum bet amount is {unit_amount} MMK\nPlease increase your bet size.",
                    make_main_keyboard(True)
                )
                settings["running"] = False
                break
            
            if current_balance < actual_amount:
                message = f"❌ Insufficient balance for next bet!\nCurrent Balance: {current_balance:.2f} MMK\nRequired Bet Amount: {actual_amount:.2f} MMK\nPlease add funds to continue betting."
                await send_message_with_retry(app_context.bot, chat_id, message, make_main_keyboard(True))
                settings["running"] = False
                break
            
            # Place bet
            strategy_name = "BS ORDER"
            if strategy == "LESLAY":
                strategy_name = "LESLAY"
            elif strategy == "TREND_MASTER":
                strategy_name = "TREND MASTER"
            elif strategy == "ULTIMATE_AI_85":
                strategy_name = "🤖 ULTIMATE AI 85%"
                
            bet_msg = f"🆔 WINGO30S: {current_issue}\n"
            bet_msg += f"📊 Strategy: {strategy_name}\n"
            
            if strategy == "LESLAY" and last_5_nums:
                bet_msg += f"📊 Last 5: {last_5_nums}\n"
                bet_msg += f"📈 Even:{even_count} Odd:{odd_count} → {leslay_analysis}\n"
            elif strategy == "TREND_MASTER" and last_3_nums:
                bet_msg += f"📊 Last 3: {last_3_nums}\n"
                bet_msg += f"📊 Pattern: {pattern} (B:{b_count} S:{s_count})\n"
                bet_msg += f"📈 {trend_analysis}\n"
            elif strategy == "ULTIMATE_AI_85":
                bet_msg += f"🤖 AI Analysis: {ai_analysis}\n"
                bet_msg += f"🔢 Predicted Number: {predicted_number}\n"
                if 'bank_info' in locals():
                    bet_msg += f"{bank_info}\n"
            
            bet_msg += f"🎯 BET: {'BIG' if ch == 'B' else 'SMALL'} ==> {actual_amount:.2f} MMK"
            
            if confidence != "N/A":
                bet_msg += f"\nConfidence: {confidence}%"
                
            # Add SL info to bet message
            sl_limit = settings.get("sl_limit")
            if sl_limit and sl_limit > 0:
                current_losses = settings.get("consecutive_losses", 0)
                bet_msg += f"\n⛔ SL: {current_losses}/{sl_limit} losses"
                
            await send_message_with_retry(app_context.bot, chat_id, bet_msg)
            logging.info(f"Placing bet for user {user_id}, WINGO 30S: {bet_msg}")
            
            if settings.get("virtual_mode", False):
                # Virtual bet
                if user_id not in user_pending_bets:
                    user_pending_bets[user_id] = {}
                user_pending_bets[user_id][current_issue] = [ch, actual_amount, True]
                user_waiting_for_result[user_id] = True
            else:
                # Real bet
                bet_resp = await place_wingo_bet_request(session, current_issue, select_type, actual_amount, user_id)
                    
                if isinstance(bet_resp, dict) and bet_resp.get("error"):
                    logging.error(f"Bet error for user {user_id}, WINGO 30S, issue {current_issue}: {bet_resp.get('error')}")
                    await send_message_with_retry(app_context.bot, chat_id, f"Bet error: {bet_resp.get('error')}. Retrying next cycle...")
                    settings["consecutive_errors"] += 1
                    if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                        logging.error(f"Max consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached for user {user_id}. Stopping bot.")
                        await send_message_with_retry(app_context.bot, chat_id, f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping bot.")
                        settings["running"] = False
                        break
                    await asyncio.sleep(5)
                    continue
                elif isinstance(bet_resp, dict) and bet_resp.get("code") != 0:
                    error_msg = bet_resp.get("msg", "Unknown error")
                    logging.error(f"API error for user {user_id}, WINGO 30S, issue {current_issue}: {error_msg}")
                    await send_message_with_retry(app_context.bot, chat_id, f"API error: {error_msg}. Retrying next cycle...")
                    settings["consecutive_errors"] += 1
                    if settings["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                        logging.error(f"Max consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached for user {user_id}. Stopping bot.")
                        await send_message_with_retry(app_context.bot, chat_id, f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping bot.")
                        settings["running"] = False
                        break
                    await asyncio.sleep(5)
                    continue
                
                settings["consecutive_errors"] = 0
                
                if user_id not in user_pending_bets:
                    user_pending_bets[user_id] = {}
                user_pending_bets[user_id][current_issue] = [ch, actual_amount, False]
                user_waiting_for_result[user_id] = True
            
            # Update state
            settings["last_issue"] = current_issue
            settings["pattern_index"] = (settings.get("pattern_index", 0) + 1) % len(settings.get("pattern", DEFAULT_BS_ORDER))
                
            logging.info(f"Placed bet for user {user_id}, WINGO 30S, waiting for result on issue {current_issue}")
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logging.info(f"Betting worker cancelled for user {user_id}")
    except Exception as e:
        logging.error(f"Betting worker error for user {user_id}, WINGO 30S: {e}")
        await send_message_with_retry(app_context.bot, chat_id, f"Betting error: {e}. Stopping...")
        settings["running"] = False
    finally:
        # Clean up
        settings["running"] = False
        user_waiting_for_result.pop(user_id, None)
        user_should_skip_next.pop(user_id, None)
        user_balance_warnings.pop(user_id, None)
        user_skip_result_wait.pop(user_id, None)
        
        # Reset betting strategy
        settings["martin_index"] = 0
        settings["dalembert_units"] = 1
        settings["custom_index"] = 0
        
        # Calculate final stats
        total_profit = 0
        balance_text = ""
        
        if settings.get("virtual_mode", False):
            total_profit = user_stats[user_id].get("virtual_balance", VIRTUAL_BALANCE) - VIRTUAL_BALANCE
            balance_text = f"Virtual Balance: {user_stats[user_id].get('virtual_balance', VIRTUAL_BALANCE):.2f} MMK\n"
        else:
            total_profit = user_stats[user_id].get("profit", 0) if user_id in user_stats else 0
            session = user_sessions.get(user_id)
            current_balance = await get_balance(session, user_id) if session else None
            balance_text = f"Final Balance: {current_balance:.2f} MMK\n" if current_balance is not None else ""
        
        profit_indicator = "+" if total_profit > 0 else ("-" if total_profit < 0 else "")
        
        if not user_stop_initiated.get(user_id, False):
            message = f"🚫 BOT STOPPED\n{balance_text}💰 Total Profit: {profit_indicator}{abs(total_profit):.2f} MMK"
            await send_message_with_retry(app_context.bot, chat_id, message, make_main_keyboard(True))
        
        user_stop_initiated.pop(user_id, None)

async def check_user_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await send_message_with_retry(context.bot, update.effective_chat.id, "Please login first", reply_markup=make_main_keyboard(logged_in=False))
        return False
    if user_id not in user_settings:
        user_settings[user_id] = get_default_user_settings()
        logging.info(f"Initialized user_settings for user {user_id}")
    return True

async def cmd_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_settings:
        user_settings[user_id] = get_default_user_settings()
        logging.info(f"Initialized user_settings for user {user_id} in cmd_start_handler")
    logged_in = user_id in user_sessions
    await send_message_with_retry(context.bot, update.effective_chat.id, "Welcome to 777BigWin Bot for WINGO 30S!", reply_markup=make_main_keyboard(logged_in))

    if not hasattr(context.application, 'win_lose_task') or context.application.win_lose_task.done():
        context.application.win_lose_task = asyncio.create_task(win_lose_checker(context))

async def cmd_allow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await send_message_with_retry(context.bot, update.effective_chat.id, "Admin only!")
        return
    if not context.args or not context.args[0].isdigit():
        await send_message_with_retry(context.bot, update.effective_chat.id, "Usage: /allow {777bigwin_id}")
        return
    bigwin_id = int(context.args[0])
    if bigwin_id in allowed_777bigwin_ids:
        await send_message_with_retry(context.bot, update.effective_chat.id, f"User {bigwin_id} already added")
    else:
        allowed_777bigwin_ids.add(bigwin_id)
        save_allowed_users()
        await send_message_with_retry(context.bot, update.effective_chat.id, f"User {bigwin_id} added")

async def cmd_remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await send_message_with_retry(context.bot, update.effective_chat.id, "Admin only!")
        return
    if not context.args or not context.args[0].isdigit():
        await send_message_with_retry(context.bot, update.effective_chat.id, "Usage: /remove {777bigwin_id}")
        return
    bigwin_id = int(context.args[0])
    if bigwin_id not in allowed_777bigwin_ids:
        await send_message_with_retry(context.bot, update.effective_chat.id, f"User {bigwin_id} not found")
    else:
        allowed_777bigwin_ids.remove(bigwin_id)
        save_allowed_users()
        await send_message_with_retry(context.bot, update.effective_chat.id, f"User {bigwin_id} removed")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not await check_user_authorized(update, context):
        return
    
    # ===== AI Settings =====
    if query.data.startswith("ai:"):
        action = query.data.split(":")[1]
        
        if action == "min_confidence":
            # Store state for input
            user_state[user_id] = {"state": "INPUT_AI_CONFIDENCE"}
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                "Enter minimum confidence for AI (50-95):\nExample:\n75",
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
            
        elif action == "aggressive":
            current = user_settings[user_id].get("ai_aggressive", False)
            user_settings[user_id]["ai_aggressive"] = not current
            ai_manager.set_setting(user_id, "aggressive", not current)
            save_user_settings()
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                f"🔫 Aggressive Mode: {'ON' if not current else 'OFF'}",
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
            
        elif action == "performance":
            ai = ai_manager.get_ai(user_id)
            summary = ai.get_summary()
            
            # Get bank info
            bank_info = ai_manager.bank.get_info(user_id)
            
            message = f"{summary}\n\n{bank_info}"
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                message,
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
            
        elif action == "bank_info":
            info = ai_manager.bank.get_info(user_id)
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                info,
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
            
        elif action == "withdraw":
            result = ai_manager.bank.withdraw(user_id)  # No argument = withdraw all
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                result["message"],
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
            
        elif action == "reset":
            # Reset AI instance
            if user_id in ai_manager.ai_instances:
                del ai_manager.ai_instances[user_id]
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                "🔄 AI reset complete!",
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
            
        elif action == "backtest":
            # Run backtest
            session = user_sessions.get(user_id)
            if not session:
                await send_message_with_retry(
                    context.bot, 
                    query.message.chat_id, 
                    "Please login first",
                    reply_markup=make_main_keyboard(logged_in=False)
                )
                await query.message.delete()
                return
            
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                "📊 Running backtest... Please wait.",
                reply_markup=make_main_keyboard(logged_in=True)
            )
            
            # Get history
            history_data = await get_game_history(session, user_id)
            history_numbers = []
            for item in history_data:
                if item.get("number"):
                    num = int(item.get("number", "0")) % 10
                    history_numbers.append(num)
            
            if len(history_numbers) < 20:
                await send_message_with_retry(
                    context.bot, 
                    query.message.chat_id, 
                    "❌ Need at least 20 results for backtest",
                    reply_markup=make_main_keyboard(logged_in=True)
                )
                await query.message.delete()
                return
            
            # Run backtest
            ai = ai_manager.get_ai(user_id)
            bet_sizes = user_settings[user_id].get("bet_sizes", [10, 20, 40, 80, 160, 320, 640])
            result = ai.backtest(history_numbers, bet_sizes)
            
            if result.get("success"):
                message = ai.get_backtest_summary()
            else:
                message = f"❌ {result.get('error', 'Unknown error')}"
            
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                message,
                reply_markup=make_main_keyboard(logged_in=True)
            )
            await query.message.delete()
    
    # ===== Betting Strategy (Martingale/Anti/D'Alembert) =====
    elif query.data.startswith("betting_strategy:"):
        betting_strategy = query.data.split(":")[1]
        user_settings[user_id]["betting_strategy"] = betting_strategy
        
        # Reset betting strategy state
        user_settings[user_id]["martin_index"] = 0
        user_settings[user_id]["dalembert_units"] = 1
        user_settings[user_id]["consecutive_losses"] = 0
        user_settings[user_id]["skip_betting"] = False
        user_settings[user_id]["custom_index"] = 0
        
        save_user_settings()
        
        await send_message_with_retry(context.bot, query.message.chat_id, f"Betting Strategy set to: {betting_strategy}", reply_markup=make_main_keyboard(logged_in=True))
        await query.message.delete()
    
    # ===== Main Strategy (BS ORDER vs LESLAY vs TREND MASTER vs ULTIMATE AI) =====
    elif query.data.startswith("strategy:"):
        strategy = query.data.split(":")[1]
        user_settings[user_id]["strategy"] = strategy
        
        if strategy == "LESLAY":
            # Show LESLAY info
            session = user_sessions.get(user_id)
            if session:
                # Get current LESLAY prediction for demo
                prediction = await get_leslay_prediction(session, user_id)
                
                message = (
                    f"🎯 **LESLAY Formula Activated!**\n\n"
                    f"**How it works:**\n"
                    f"• Last 5 results analysis\n"
                    f"• Even numbers (0,2,4,6,8) → SMALL (S)\n"
                    f"• Odd numbers (1,3,5,7,9) → BIG (B)\n\n"
                )
                
                if prediction.get("last_5"):
                    message += (
                        f"**Current Analysis:**\n"
                        f"Last 5 numbers: {prediction['last_5_display']}\n"
                        f"Even count: {prediction['even_count']}\n"
                        f"Odd count: {prediction['odd_count']}\n"
                        f"Prediction: {'BIG (B)' if prediction['result'] == 'B' else 'SMALL (S)'}\n"
                        f"Confidence: {prediction['percent']}%\n"
                        f"Reason: {prediction['analysis']}"
                    )
                
                await send_message_with_retry(
                    context.bot, 
                    query.message.chat_id, 
                    message, 
                    reply_markup=make_main_keyboard(logged_in=True)
                )
            else:
                await send_message_with_retry(
                    context.bot, 
                    query.message.chat_id, 
                    "🎯 LESLAY Formula selected! Will analyze last 5 results to predict based on Even/Odd count.",
                    reply_markup=make_main_keyboard(logged_in=True)
                )
        elif strategy == "TREND_MASTER":
            # Show TREND MASTER info
            session = user_sessions.get(user_id)
            if session:
                # Get current TREND MASTER prediction for demo
                prediction = await get_trend_master_prediction(session, user_id)
                
                message = (
                    f"🔮 **TREND MASTER Formula Activated!**\n\n"
                    f"**How it works:**\n"
                    f"• Last 3 results pattern analysis\n"
                    f"• Predefined pattern database:\n"
                )
                
                # Show some example patterns
                example_patterns = list(TREND_PATTERNS.items())[:5]
                for pattern, result in example_patterns:
                    message += f"  • {pattern} → {result}\n"
                
                message += f"\n**Current Analysis:**\n"
                message += f"Last 3 numbers: {prediction.get('last_3_numbers', 'N/A')}\n"
                message += f"Pattern: {prediction.get('pattern', 'N/A')}\n"
                message += f"B count: {prediction.get('b_count', 0)}, S count: {prediction.get('s_count', 0)}\n"
                message += f"Prediction: {'BIG (B)' if prediction['result'] == 'B' else 'SMALL (S)'}\n"
                message += f"Confidence: {prediction.get('confidence', 50)}%\n"
                message += f"Reason: {prediction.get('analysis', 'N/A')}"
                
                await send_message_with_retry(
                    context.bot, 
                    query.message.chat_id, 
                    message, 
                    reply_markup=make_main_keyboard(logged_in=True)
                )
            else:
                await send_message_with_retry(
                    context.bot, 
                    query.message.chat_id, 
                    "🔮 TREND MASTER Formula selected! Will analyze last 3 results to detect patterns and predict next outcome.",
                    reply_markup=make_main_keyboard(logged_in=True)
                )
        elif strategy == "ULTIMATE_AI_85":
            # Show ULTIMATE AI info
            message = (
                f"🤖 **ULTIMATE AI 85% Activated!**\n\n"
                f"**How it works:**\n"
                f"• Combines 14+ advanced formulas\n"
                f"• Each formula votes for B or S\n"
                f"• Majority vote decides the prediction\n"
                f"• Confidence score based on vote strength\n\n"
                f"**Included Formulas:**\n"
                f"• Trend Following\n"
                f"• Pattern Match\n"
                f"• Reversal Detection\n"
                f"• Fibonacci Sequence\n"
                f"• Number Analysis\n"
                f"• LESLAY (Even/Odd)\n"
                f"• Quantum Brain\n"
                f"• Hyper Dimensional\n"
                f"• API Rule (3 rules)\n"
                f"• RNG System\n"
                f"• Plus AI Chat\n"
                f"• Sniper\n"
                f"• Wait 2356\n"
                f"• 4 Hit Leslay\n\n"
                f"**Bank System:**\n"
                f"• Automatically saves profits\n"
                f"• Tracks 15k cycles\n"
                f"• Withdraw anytime\n\n"
                f"Use 🤖 AI Settings to configure!\n\n"
                f"📊 **New!** Use 'Backtest' button to see historical performance!"
            )
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                message, 
                reply_markup=make_main_keyboard(logged_in=True)
            )
        else: # BS_ORDER
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                f"📊 Strategy set to: {strategy}", 
                reply_markup=make_main_keyboard(logged_in=True)
            )
        
        save_user_settings()
        await query.message.delete()
    
    # ===== LESLAY Performance Analysis =====
    elif query.data == "leslay:performance":
        session = user_sessions.get(user_id)
        if not session:
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                "Please login first to analyze performance",
                reply_markup=make_main_keyboard(logged_in=False)
            )
            await query.message.delete()
            return
        
        await send_message_with_retry(
            context.bot, 
            query.message.chat_id, 
            "📊 Analyzing LESLAY performance... Please wait.",
            reply_markup=make_main_keyboard(logged_in=True)
        )
        
        performance = await analyze_leslay_performance(session, user_id)
        
        if "error" in performance:
            message = f"❌ {performance['error']}"
        else:
            message = (
                f"📈 **LESLAY Performance Analysis**\n\n"
                f"Total Predictions: {performance['total_predictions']}\n"
                f"Correct Predictions: {performance['correct_predictions']}\n"
                f"**Overall Accuracy: {performance['accuracy']}%**\n\n"
                f"📊 **Breakdown:**\n"
                f"• When Even > Odd: {performance['even_cases']} cases, {performance['even_accuracy']}% accuracy\n"
                f"• When Odd > Even: {performance['odd_cases']} cases, {performance['odd_accuracy']}% accuracy\n"
                f"• When Even = Odd: {performance['equal_cases']} cases, {performance['equal_accuracy']}% accuracy\n\n"
                f"**Rule:**\n"
                f"Even > Odd → SMALL (S)\n"
                f"Odd > Even → BIG (B)\n"
                f"Even = Odd → Follow last result"
            )
        
        await send_message_with_retry(context.bot, query.message.chat_id, message, reply_markup=make_main_keyboard(logged_in=True))
        await query.message.delete()
    
    # ===== TREND MASTER Performance Analysis =====
    elif query.data == "trend:performance":
        session = user_sessions.get(user_id)
        if not session:
            await send_message_with_retry(
                context.bot, 
                query.message.chat_id, 
                "Please login first to analyze performance",
                reply_markup=make_main_keyboard(logged_in=False)
            )
            await query.message.delete()
            return
        
        await send_message_with_retry(
            context.bot, 
            query.message.chat_id, 
            "📊 Analyzing TREND MASTER performance... Please wait.",
            reply_markup=make_main_keyboard(logged_in=True)
        )
        
        performance = await analyze_trend_master_performance(session, user_id)
        
        if "error" in performance:
            message = f"❌ {performance['error']}"
        else:
            message = (
                f"🔮 **TREND MASTER Performance Analysis**\n\n"
                f"Total Predictions: {performance['total_predictions']}\n"
                f"Correct Predictions: {performance['correct_predictions']}\n"
                f"**Overall Accuracy: {performance['accuracy']}%**\n\n"
                f"📊 **Patterns Found:** {performance['patterns_found']}\n\n"
                f"**Best Pattern:** {performance['best_pattern']} with {performance['best_accuracy']}% accuracy\n"
                f"**Worst Pattern:** {performance['worst_pattern']} with {performance['worst_accuracy']}% accuracy\n\n"
                f"**Pattern Database:**\n"
            )
            
            # Show top 5 patterns with highest accuracy
            pattern_acc = performance.get('pattern_accuracy', {})
            sorted_patterns = sorted(pattern_acc.items(), key=lambda x: x[1], reverse=True)[:5]
            
            for pattern, acc in sorted_patterns:
                message += f"• {pattern}: {acc}% accuracy\n"
                message += f"  → Next should be {TREND_PATTERNS.get(pattern, 'Unknown')}\n"
            
            message += f"\n**How it works:**\n"
            message += f"• Analyzes last 3 results pattern\n"
            message += f"• Uses pattern database for prediction\n"
            message += f"• Unknown patterns use majority rule"
        
        await send_message_with_retry(context.bot, query.message.chat_id, message, reply_markup=make_main_keyboard(logged_in=True))
        await query.message.delete()
    
    # ===== Entry Layer =====
    elif query.data.startswith("entry_layer:"):
        layer_value = int(query.data.split(":")[1])
        user_settings[user_id]["layer_limit"] = layer_value
        
        # Initialize entry layer state
        if layer_value == 1:
            user_settings[user_id]["entry_layer_state"] = {}
        elif layer_value == 2:
            user_settings[user_id]["entry_layer_state"] = {"waiting_for_lose": True}
        elif layer_value >= 3:
            user_settings[user_id]["entry_layer_state"] = {"waiting_for_loses": True, "consecutive_loses": 0}
        
        save_user_settings()
        
        description = ""
        if layer_value == 1:
            description = "Bet immediately according to strategy"
        elif layer_value == 2:
            description = "Wait for 1 lose before betting"
        elif layer_value >= 3:
            wait_count = layer_value - 1
            description = f"Wait for {wait_count} consecutive loses before betting"
        
        await send_message_with_retry(context.bot, query.message.chat_id, f"Entry Layer set to: {layer_value} ({description})", reply_markup=make_main_keyboard(logged_in=True))
        await query.message.delete()
    
    # ===== Virtual/Real Mode =====
    elif query.data.startswith("mode:"):
        mode = query.data.split(":")[1]
        settings = user_settings[user_id]
        
        if mode == "virtual":
            settings["virtual_mode"] = True
            if user_id not in user_stats:
                user_stats[user_id] = {}
            if "virtual_balance" not in user_stats[user_id]:
                user_stats[user_id]["virtual_balance"] = VIRTUAL_BALANCE
            save_user_settings()
            await send_message_with_retry(context.bot, query.message.chat_id, f"🖥️ Switched to Virtual Mode ({VIRTUAL_BALANCE} MMK)", reply_markup=make_main_keyboard(logged_in=True))
        elif mode == "real":
            settings["virtual_mode"] = False
            save_user_settings()
            await send_message_with_retry(context.bot, query.message.chat_id, "💵 Switched to Real Mode", reply_markup=make_main_keyboard(logged_in=True))
        
        await query.message.delete()

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text
    text = normalize_text(raw_text)
    logging.info(f"Raw input by user {user_id}: {raw_text}")
    logging.info(f"Normalized input by user {user_id}: {text}")
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    logging.info(f"Parsed lines by user {user_id} (count: {len(lines)}): {lines}")
    logging.info(f"Current state for user {user_id}: {user_state.get(user_id, 'None')}")

    command = text.upper().replace('_', '').replace(' ', '').replace('/', '').replace('(', '').replace(')', '').replace('⛔', '').replace('🔢', '').replace('🛑', '').replace('🎯', '').replace('🔐', '').replace('🏁', '').replace('💣', '').replace('🚀', '').replace('⚔️', '').replace('🛡️', '').replace('🔄', '').replace('🎮', '').replace('🤖', '').replace('🏦', '').replace('📊', '')
    logging.info(f"Processed command for user {user_id}: {command}")

    if command == "LOGIN" or (lines and lines[0].lower() == "login"):
        if len(lines) >= 3 and lines[0].lower() == "login":
            username = lines[1]
            password = lines[2]
            logging.info(f"Processing login for user {user_id}: username={username}")
            await send_message_with_retry(context.bot, update.effective_chat.id, "Checking login...")
            res, session = login_request(username, password)
            if session:
                user_info = await get_user_info(session, user_id)
                if user_info and user_info.get("user_id"):
                    game_user_id = user_info.get("user_id")
                    if game_user_id not in allowed_777bigwin_ids:
                        logging.warning(f"Unauthorized login attempt for user {user_id}, game ID {game_user_id}")
                        session.close()
                        await send_message_with_retry(context.bot, update.effective_chat.id, "Unauthorized user ID. Contact admin to allow your ID.", reply_markup=make_main_keyboard(logged_in=False))
                        return
                    user_sessions[user_id] = session
                    user_game_info[user_id] = user_info
                    user_temp[user_id] = {"password": password}
                    balance = await get_balance(session, user_id)
                    user_stats[user_id] = {"start_balance": float(balance or 0), "profit": 0.0}
                    if user_id not in user_settings:
                        user_settings[user_id] = get_default_user_settings()
                        logging.info(f"Initialized user_settings for user {user_id} during login")
                    balance_display = balance if balance is not None else 0.0
                    await send_message_with_retry(context.bot, update.effective_chat.id, f"✅ Login Success, ID: {user_info['user_id']}, Balance: {balance_display:.2f} MMK", reply_markup=make_main_keyboard(logged_in=True))
                else:
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Login failed: Could not retrieve user info", reply_markup=make_main_keyboard(logged_in=False))
            else:
                msg = res.get("msg", "Login failed")
                await send_message_with_retry(context.bot, update.effective_chat.id, f"Login error: {msg}", reply_markup=make_main_keyboard(logged_in=False))
            user_state.pop(user_id, None)
            user_temp.pop(user_id, None)
            return
        if len(lines) == 1 and lines[0].lower() == "login":
            user_state[user_id] = {"state": "WAIT_PHONE"}
            await send_message_with_retry(context.bot, update.effective_chat.id, "Enter phone number or email:")
            return
        if user_state.get(user_id, {}).get("state") == "WAIT_PHONE":
            user_temp[user_id] = {"phone": text}
            user_state[user_id] = {"state": "WAIT_PASS"}
            await send_message_with_retry(context.bot, update.effective_chat.id, "Enter password:")
            return
        if user_state.get(user_id, {}).get("state") == "WAIT_PASS":
            phone = user_temp.get(user_id, {}).get("phone")
            password = text
            logging.info(f"Processing login for user {user_id}: username={phone}")
            await send_message_with_retry(context.bot, update.effective_chat.id, "Checking login...")
            res, session = login_request(phone, password)
            if session:
                user_info = await get_user_info(session, user_id)
                if user_info and user_info.get("user_id"):
                    game_user_id = user_info.get("user_id")
                    if game_user_id not in allowed_777bigwin_ids:
                        logging.warning(f"Unauthorized login attempt for user {user_id}, game ID {game_user_id}")
                        session.close()
                        await send_message_with_retry(context.bot, update.effective_chat.id, "Unauthorized user ID. Contact admin to allow your ID.", reply_markup=make_main_keyboard(logged_in=False))
                        return
                    user_sessions[user_id] = session
                    user_game_info[user_id] = user_info
                    user_temp[user_id] = {"password": password}
                    balance = await get_balance(session, user_id)
                    user_stats[user_id] = {"start_balance": float(balance or 0), "profit": 0.0}
                    if user_id not in user_settings:
                        user_settings[user_id] = get_default_user_settings()
                        logging.info(f"Initialized user_settings for user {user_id} during login")
                    balance_display = balance if balance is not None else 0.0
                    await send_message_with_retry(context.bot, update.effective_chat.id, f"✅ Login Success, ID: {user_info['user_id']}, Balance: {balance_display:.2f} MMK", reply_markup=make_main_keyboard(logged_in=True))
                else:
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Login failed: Could not retrieve user info", reply_markup=make_main_keyboard(logged_in=False))
            else:
                msg = res.get("msg", "Login failed")
                await send_message_with_retry(context.bot, update.effective_chat.id, f"Login error: {msg}", reply_markup=make_main_keyboard(logged_in=False))
            user_state.pop(user_id, None)
            user_temp.pop(user_id, None)
            return
        await send_message_with_retry(context.bot, update.effective_chat.id, "Enter login details as:\nLogin\n<phone>\n<password>")
        return
    
    if not await check_user_authorized(update, context) and command != "LOGIN":
        return
    
    try:
        if user_state.get(user_id, {}).get("state") == "INPUT_BET_SIZES":
            bet_sizes = [int(s) for s in lines[1:] if s.isdigit()]
            if not bet_sizes:
                raise ValueError("No valid numbers")
            
            settings = user_settings[user_id]
            if settings.get("betting_strategy") == "D'Alembert" and len(bet_sizes) > 1:
                await send_message_with_retry(context.bot, update.effective_chat.id, 
                    "❌ D'Alembert strategy requires only ONE bet size.\nPlease enter only one number for unit size.\nExample:\n100",
                    make_main_keyboard(logged_in=True)
                )
                return
            
            user_settings[user_id]["bet_sizes"] = bet_sizes
            user_settings[user_id]["dalembert_units"] = 1
            user_settings[user_id]["martin_index"] = 0
            user_settings[user_id]["custom_index"] = 0
            
            message = f"BET SIZE set: {', '.join(map(str, bet_sizes))} MMK"
            if settings.get("betting_strategy") == "D'Alembert":
                message += f"\n📝 D'Alembert Bet Size: {bet_sizes[0]} MMK"
            
            await send_message_with_retry(context.bot, update.effective_chat.id, message, reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        elif user_state.get(user_id, {}).get("state") == "INPUT_BET_ORDER":
            pattern = lines[1] if len(lines) >= 2 else text
            if all(c in "BS" for c in pattern.upper()) and pattern:
                user_settings[user_id]["pattern"] = pattern.upper()
                await send_message_with_retry(context.bot, update.effective_chat.id, f"BET ORDER set: {pattern.upper()}", reply_markup=make_main_keyboard(logged_in=True))
                user_state.pop(user_id, None)
            else:
                await send_message_with_retry(context.bot, update.effective_chat.id, "Invalid bet order. Use B or S as:\nBet_Order\nBSBBSSBSBBS", reply_markup=make_main_keyboard(logged_in=True))
        elif user_state.get(user_id, {}).get("state") == "INPUT_PROFIT_TARGET":
            target = float(lines[1] if len(lines) >= 2 else text)
            if target <= 0:
                raise ValueError
            user_settings[user_id]["target_profit"] = target
            await send_message_with_retry(context.bot, update.effective_chat.id, f"PROFIT TARGET set: {target:.2f} MMK", reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        elif user_state.get(user_id, {}).get("state") == "INPUT_STOP_LIMIT":
            stop_loss = float(lines[1] if len(lines) >= 2 else text)
            if stop_loss <= 0:
                raise ValueError
            user_settings[user_id]["stop_loss"] = stop_loss
            await send_message_with_retry(context.bot, update.effective_chat.id, f"STOP LOSS LIMIT set: {stop_loss:.2f} MMK", reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        elif user_state.get(user_id, {}).get("state") == "INPUT_SL_LIMIT":
            sl_limit = int(lines[1] if len(lines) >= 2 else text)
            if sl_limit < 0:
                raise ValueError("SL must be a non-negative integer")
            user_settings[user_id]["sl_limit"] = sl_limit if sl_limit > 0 else None
            user_settings[user_id]["consecutive_losses"] = 0
            user_settings[user_id]["skip_betting"] = False
            await send_message_with_retry(context.bot, update.effective_chat.id, f"SL set: {sl_limit if sl_limit is not None else ''} consecutive losses", reply_markup=make_main_keyboard(logged_in=True))
            user_state.pop(user_id, None)
        elif user_state.get(user_id, {}).get("state") == "INPUT_AI_CONFIDENCE":
            try:
                confidence = int(lines[1] if len(lines) >= 2 else text)
                if confidence < 50 or confidence > 95:
                    raise ValueError("Confidence must be between 50-95")
                user_settings[user_id]["ai_min_confidence"] = confidence
                ai_manager.set_setting(user_id, "min_confidence", confidence)
                save_user_settings()
                await send_message_with_retry(
                    context.bot, 
                    update.effective_chat.id, 
                    f"🎯 AI Min Confidence set to: {confidence}%",
                    reply_markup=make_main_keyboard(logged_in=True)
                )
                user_state.pop(user_id, None)
            except ValueError as e:
                await send_message_with_retry(
                    context.bot, 
                    update.effective_chat.id, 
                    f"Invalid input: {str(e)}",
                    reply_markup=make_main_keyboard(logged_in=True)
                )
        else:
            if command == "BETSIZE":
                user_state[user_id] = {"state": "INPUT_BET_SIZES"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "Enter bet sizes as:\nBet_Size\n100\n200\n500", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "MANUALBSORDER":
                user_state[user_id] = {"state": "INPUT_BET_ORDER"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "Enter bet order as:\nBet_Order\nBSBBSSBSBBS", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "PROFITTARGET":
                user_state[user_id] = {"state": "INPUT_PROFIT_TARGET"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "Enter profit target as:\nProfit_Target\n100000", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "STOPLOSSLIMIT":
                user_state[user_id] = {"state": "INPUT_STOP_LIMIT"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "Enter stop loss limit as:\nStop_Limit\n100000", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "SL":
                user_state[user_id] = {"state": "INPUT_SL_LIMIT"}
                await send_message_with_retry(context.bot, update.effective_chat.id, "Enter SL as:\nSL\n3\n(0 to disable)", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "ENTRYLAYER":
                await send_message_with_retry(context.bot, update.effective_chat.id, "Select Entry Layer:", reply_markup=make_entry_layer_keyboard())
            elif command == "VIRTUALREALMODE":
                await send_message_with_retry(context.bot, update.effective_chat.id, "Select Mode:", reply_markup=make_mode_selection_keyboard())
            elif command in ["ANTIMARTINGALE", "🚀ANTI/MARTINGALE"]:
                await send_message_with_retry(context.bot, update.effective_chat.id, "Choose Betting Strategy:", reply_markup=make_betting_strategy_keyboard())
            elif command in ["🎮WINGO30S", "GAME", "GAMETYPE"]:
                await send_message_with_retry(context.bot, update.effective_chat.id, "Game type set to: WINGO 30S", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "STRATEGY":
                await send_message_with_retry(
                    context.bot, 
                    update.effective_chat.id, 
                    "Select Strategy:\n\n"
                    "📊 **BS ORDER** - Follow predefined B/S pattern\n"
                    "🎯 **LESLAY** - Analyze last 5 results (Even→Small, Odd→Big)\n"
                    "🔮 **TREND MASTER** - Analyze last 3 results patterns\n"
                    "🤖 **ULTIMATE AI 85%** - 14+ formulas combined with banking system", 
                    reply_markup=make_strategy_keyboard()
                )
            elif command == "BACKTEST":
                # Quick backtest from main menu
                session = user_sessions.get(user_id)
                if not session:
                    await send_message_with_retry(
                        context.bot, 
                        update.effective_chat.id, 
                        "Please login first",
                        reply_markup=make_main_keyboard(logged_in=False)
                    )
                    return
                
                await send_message_with_retry(
                    context.bot, 
                    update.effective_chat.id, 
                    "📊 Running backtest... Please wait.",
                    reply_markup=make_main_keyboard(logged_in=True)
                )
                
                # Get history
                history_data = await get_game_history(session, user_id)
                history_numbers = []
                for item in history_data:
                    if item.get("number"):
                        num = int(item.get("number", "0")) % 10
                        history_numbers.append(num)
                
                if len(history_numbers) < 20:
                    await send_message_with_retry(
                        context.bot, 
                        update.effective_chat.id, 
                        "❌ Need at least 20 results for backtest",
                        reply_markup=make_main_keyboard(logged_in=True)
                    )
                    return
                
                # Run backtest
                ai = ai_manager.get_ai(user_id)
                bet_sizes = user_settings[user_id].get("bet_sizes", [10, 20, 40, 80, 160, 320, 640])
                result = ai.backtest(history_numbers, bet_sizes)
                
                if result.get("success"):
                    message = ai.get_backtest_summary()
                else:
                    message = f"❌ {result.get('error', 'Unknown error')}"
                
                await send_message_with_retry(
                    context.bot, 
                    update.effective_chat.id, 
                    message,
                    reply_markup=make_main_keyboard(logged_in=True)
                )
                
            elif command == "AISETTINGS" or command == "AISETTING" or command == "AI":
                await send_message_with_retry(
                    context.bot, 
                    update.effective_chat.id, 
                    "🤖 **AI Settings**\n\n"
                    "Configure your ULTIMATE AI 85%",
                    reply_markup=make_ai_settings_keyboard()
                )
            elif command == "BANK":
                # Show bank info
                info = ai_manager.bank.get_info(user_id)
                await send_message_with_retry(context.bot, update.effective_chat.id, info, reply_markup=make_main_keyboard(logged_in=True))
            elif command == "START":
                settings = user_settings.get(user_id, {})
                logging.info(f"Start command for user {user_id}, settings: {settings}")
                
                # Check requirements based on strategy
                strategy = settings.get("strategy", "BS_ORDER")
                
                if strategy == "BS_ORDER" and not settings.get("pattern"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Set BET ORDER first for BS ORDER strategy!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                
                if not settings.get("bet_sizes"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Set BET SIZE first!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                
                if settings.get("betting_strategy") == "D'Alembert" and len(settings.get("bet_sizes", [])) > 1:
                    await send_message_with_retry(context.bot, update.effective_chat.id, "D'Alembert requires a single BET SIZE. Please set one bet size.", reply_markup=make_main_keyboard(logged_in=True))
                    return
                
                if settings.get("running"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Bot already running!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                
                # Initialize betting state
                settings["martin_index"] = 0
                settings["dalembert_units"] = 1
                settings["pattern_index"] = 0
                settings["consecutive_losses"] = 0
                settings["skip_betting"] = False
                settings["running"] = True
                settings["consecutive_errors"] = 0
                
                # Initialize Entry Layer state
                entry_layer = settings.get("layer_limit", 1)
                if entry_layer == 2:
                    settings["entry_layer_state"] = {"waiting_for_lose": True}
                elif entry_layer >= 3:
                    settings["entry_layer_state"] = {"waiting_for_loses": True, "consecutive_loses": 0}
                else:
                    settings["entry_layer_state"] = {}
                
                user_waiting_for_result[user_id] = False
                user_should_skip_next[user_id] = False
                
                task = asyncio.create_task(betting_worker(user_id, update.effective_chat.id, context))
                settings["task"] = task
            elif command == "STOP":
                settings = user_settings.get(user_id, {})
                if not settings.get("running"):
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Bot not running!", reply_markup=make_main_keyboard(logged_in=True))
                    return
                
                user_stop_initiated[user_id] = True
                settings["running"] = False
                if settings.get("task"):
                    settings["task"].cancel()
                    settings["task"] = None
                
                user_waiting_for_result.pop(user_id, None)
                user_should_skip_next.pop(user_id, None)
                
                # Reset betting strategy
                settings["martin_index"] = 0
                settings["dalembert_units"] = 1
                settings["custom_index"] = 0
                
                session = user_sessions.get(user_id)
                current_balance = await get_balance(session, user_id) if session else None
                balance_text = f"Balance: {current_balance:.2f} MMK\n" if current_balance is not None else ""
                await send_message_with_retry(context.bot, update.effective_chat.id, f"Bot stopped!\n{balance_text}", reply_markup=make_main_keyboard(logged_in=True))
            elif command == "INFO":
                session = user_sessions.get(user_id)
                user_info = await get_user_info(session, user_id) if session else None
                if not user_info:
                    await send_message_with_retry(context.bot, update.effective_chat.id, "Failed to get info", reply_markup=make_main_keyboard(logged_in=True))
                    return
                balance = await get_balance(session, user_id) if session else None
                settings = user_settings.get(user_id, {})
                bet_sizes = settings.get("bet_sizes", [])
                bet_order = settings.get("pattern", "")
                strategy = settings.get("strategy", "BS_ORDER")
                profit_target = settings.get("target_profit")
                stop_loss = settings.get("stop_loss")
                sl_limit = settings.get("sl_limit")
                betting_strategy = settings.get("betting_strategy", "Martingale")
                game_type = settings.get("game_type", "WINGO30S")
                virtual_mode = settings.get("virtual_mode", False)
                layer_limit = settings.get("layer_limit", 1)
                
                # AI settings
                ai_min_confidence = settings.get("ai_min_confidence", 70)
                ai_aggressive = settings.get("ai_aggressive", False)
                
                # Calculate current profit
                current_profit = 0
                if virtual_mode:
                    current_profit = user_stats[user_id].get("virtual_balance", VIRTUAL_BALANCE) - VIRTUAL_BALANCE
                else:
                    current_profit = user_stats[user_id].get("profit", 0) if user_id in user_stats else 0
                
                profit_indicator = "+" if current_profit > 0 else ("-" if current_profit < 0 else "")
                
                info_text = (
                    f"🆔 User ID: {user_info.get('user_id', 'N/A')}\n"
                    f"💰 Balance: {balance:.2f} MMK\n"
                    f"🎮 Game: {game_type}\n"
                    f"📊 Strategy: {strategy}\n"
                )
                
                if strategy == "LESLAY":
                    info_text += "📈 LESLAY: Even(0,2,4,6,8)→Small | Odd(1,3,5,7,9)→Big\n"
                elif strategy == "TREND_MASTER":
                    info_text += "🔮 TREND MASTER: Pattern-based prediction\n"
                elif strategy == "ULTIMATE_AI_85":
                    info_text += "🤖 ULTIMATE AI 85%: 14+ formulas\n"
                    info_text += f"🎯 Min Confidence: {ai_min_confidence}%\n"
                    info_text += f"🔫 Aggressive: {'ON' if ai_aggressive else 'OFF'}\n"
                else:
                    info_text += f"🔢 Bet Order: {bet_order}\n"
                
                info_text += (
                    f"💵 Betting Strategy: {betting_strategy}\n"
                    f"💸 Bet Sizes: {', '.join(map(str, bet_sizes)) if bet_sizes else ''}\n"
                    f"🎯 Profit Target: {f'{profit_target:.2f} MMK' if isinstance(profit_target, (int, float)) else ''}\n"
                    f"🛑 Stop Loss: {f'{stop_loss:.2f} MMK' if isinstance(stop_loss, (int, float)) else ''}\n"
                    f"⛔ SL Limit: {sl_limit if sl_limit is not None else ''}\n"
                    f"🔄 Entry Layer: {layer_limit if layer_limit is not None else ''}\n"
                    f"🚀 Running: {'Yes' if settings.get('running', False) else 'No'}"
                )
                
                # Add strategy-specific info
                if strategy == "LESLAY" and user_id in user_leslay_last_5:
                    last_5 = user_leslay_last_5[user_id]
                    last_5_display = [str(num) for num in last_5]
                    info_text += f"\n\n📊 Last 5 numbers: {', '.join(last_5_display)}"
                elif strategy == "TREND_MASTER" and user_id in user_trend_last_3:
                    last_3 = user_trend_last_3[user_id]
                    info_text += f"\n\n📊 Last 3 results: {', '.join(last_3)}"
                elif strategy == "ULTIMATE_AI_85":
                    # Add bank info
                    bank_info = ai_manager.bank.get_account(user_id)
                    info_text += f"\n\n🏦 Bank: {bank_info['saved']} saved, {bank_info['active']:.2f} active"
                    info_text += f"\n📊 Total Profit: {bank_info['total_profit']}"
                    info_text += f"\n🔄 Cycles: {bank_info['cycle_count']}"
                    
                    # Add backtest result if available
                    ai = ai_manager.get_ai(user_id)
                    if user_id in ai.backtest_results:
                        bt = ai.backtest_results[user_id]
                        info_text += f"\n\n📊 Backtest: {bt['win_rate']}% win rate, {bt['roi']}% ROI"
                
                await send_message_with_retry(context.bot, update.effective_chat.id, info_text, reply_markup=make_main_keyboard(logged_in=True))
    except ValueError as e:
        await send_message_with_retry(context.bot, update.effective_chat.id, f"Invalid input: {str(e)}", reply_markup=make_main_keyboard(logged_in=True))
    except Exception as e:
        logging.error(f"Error handling input for user {user_id}: {str(e)}")
        await send_message_with_retry(context.bot, update.effective_chat.id, f"Error: {str(e)}", reply_markup=make_main_keyboard(logged_in=True))

def main():
    load_allowed_users()
    load_user_settings()
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start_handler))
    application.add_handler(CommandHandler("allow", cmd_allow_handler))
    application.add_handler(CommandHandler("remove", cmd_remove_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
