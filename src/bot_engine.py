import asyncio
from collections import deque
from datetime import datetime
import os
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

import config
from actions import (
    accept_congratulations,
    accept_daily_checkin,
    accept_daily_checkin_boost_set,
    accept_daily_new,
    accept_daily_treasure,
    accept_enter_league,
    accept_league_results,
    accept_level_up,
    accept_mystery_box,
    accept_overtake_break_score,
    accept_previous_rank_results,
    accept_relic_claim,
    accept_too_many_treasures,
    close_announcement_dialog,
    complete_finish,
    handle_anti_bot,
    handle_inactive,
    handle_quick_receive_and_send_lives,
    handle_send_friend_life,
    open_relic_complete,
    play_game,
    purchase_cookie_relay,
    purchase_desired_random_boost,
    purchase_fast_start,
    start_game,
    using_cookie_relay,
    using_fast_start,
)
from adb import (
    device_capture_screen,
    device_check_connection,
    device_connect,
    device_reset_app,
    device_tap,
    get_adb_path,
    safe_device_tap,
)
from config import (
    ACCEPT_MYSTERY_BOX_BUTTON,
    BOOST_17P_BASE_SPEED_TEMPLATE,

    BOOST_15P_SCORE_BONUS_TEMPLATE,
    BOOST_20P_HP_FROM_POTIONS_TEMPLATE,
    BOOST_2PIT_LIFTS_TEMPLATE,
    BOOST_70P_CRUSH_CHANCE_TEMPLATE,
    BOOST_DOUBLE_COINS_TEMPLATE,
    BOOST_GOLD_COIN_MAGIC_TEMPLATE,
    BOOST_M15P_HP_DRAIN_TEMPLATE,
    BOOST_M30P_COLLISION_DAMAGE_TEMPLATE,
    BOOST_MAGNETIC_AURA_TEMPLATE,
    BOOST_REVIVE_ONCE_WITH_80HP_TEMPLATE,
    COOKIE_RELAY_PRESS_RETRY_SLEEP,
    COOKIE_RELAY_PRESS_TIMEOUT,
    DETECTION_ALWAYS_STAGES,
    DETECTION_GROUPS,
    DETECTION_RECOVERY_SCAN_INTERVAL,
    RANDOM_BOOST_REGION,
    SESSION_RESET_INTERVAL,
)
from detection import (
    detect_result_screen_mystery_box,
    detect_mystery_box_grades,
    detect_stage,
    detect_templates,
    extract_item_stock,
    extract_result_coins,
    extract_result_xp,
    load_templates,
)
from discord_notifier import discord_notifier

BOOST_OPTIONS = [
    {"id": "double_coins", "name": "Double Coins (2x)", "template": BOOST_DOUBLE_COINS_TEMPLATE},
    {"id": "score_15", "name": "+15% Score Bonus", "template": BOOST_15P_SCORE_BONUS_TEMPLATE},
    {"id": "hp_drain_15", "name": "-15% HP Drain", "template": BOOST_M15P_HP_DRAIN_TEMPLATE},
    {"id": "revive_80", "name": "Revive Once with 80 HP", "template": BOOST_REVIVE_ONCE_WITH_80HP_TEMPLATE},
    {"id": "crush_70", "name": "70% Crush Chance", "template": BOOST_70P_CRUSH_CHANCE_TEMPLATE},
    {"id": "speed_17", "name": "+17% Base Speed", "template": BOOST_17P_BASE_SPEED_TEMPLATE},
    {"id": "coin_magic", "name": "Gold Coin Magic", "template": BOOST_GOLD_COIN_MAGIC_TEMPLATE},
    {"id": "damage_30", "name": "-30% Collision Damage", "template": BOOST_M30P_COLLISION_DAMAGE_TEMPLATE},
    {"id": "potions_20", "name": "+20% HP from Potions", "template": BOOST_20P_HP_FROM_POTIONS_TEMPLATE},
    {"id": "magnetic", "name": "Magnetic Aura", "template": BOOST_MAGNETIC_AURA_TEMPLATE},
    {"id": "pit_lifts_2", "name": "2 Pit Lifts", "template": BOOST_2PIT_LIFTS_TEMPLATE},
]


def get_detection_stage_names(group_name: str, exclude: Optional[set] = None) -> List[str]:
    stage_names = []
    if group_name != "IN_GAME":
        for stage_name in DETECTION_ALWAYS_STAGES:
            if stage_name not in stage_names:
                stage_names.append(stage_name)
    for stage_name in DETECTION_GROUPS[group_name]:
        if stage_name not in stage_names:
            stage_names.append(stage_name)
    if group_name == "IN_GAME":
        for stage_name in DETECTION_ALWAYS_STAGES:
            if stage_name not in stage_names:
                stage_names.append(stage_name)
    if exclude:
        stage_names = [s for s in stage_names if s not in exclude]
    return stage_names


class BotEngine:
    def __init__(self):
        self.is_running = False
        self.should_stop = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Config state
        self.device_ip = config.DEVICE_IP
        self.device_port = config.DEVICE_PORT
        self.use_fast_start = False
        self.fast_start_min_stock = 10
        self.use_cookie_relay = False
        self.cookie_relay_min_stock = 10
        self.use_desired_random_boost = False
        self.desired_boost_id = "double_coins"
        self.detect_relic = True
        self.send_friend_lives = True
        self.stop_goal_rounds_enabled: bool = False
        self.stop_goal_rounds_target: int = 50
        self.stop_goal_time_enabled: bool = False
        self.stop_goal_time_hours: float = 2.0

        # Runtime Stats
        self.start_time: Optional[float] = None
        self.current_stage: str = "IDLE"
        self.rounds_played: int = 0
        self.mystery_boxes: int = 0

        # Detailed Box Grade Stats
        self.box_counts: Dict[str, int] = {
            "wood": 0,
            "silver": 0,
            "gold": 0,
            "rainbow": 0,
            "total": 0,
        }
        self.box_history: deque = deque(maxlen=100)

        # 50-Round Detailed History & Screenshots (stores result, box_before, box_after)
        self.round_history: deque = deque(maxlen=50)
        self.round_screenshots: Dict[int, Dict[str, bytes]] = {}
        self.current_round_start_time: float = 0
        self.current_round_recorded: bool = False
        self.current_round_screen: Optional[np.ndarray] = None
        # Pending round waiting for mystery-box detection to finish.
        # History card is published only after boxes are known (or confirmed absent).
        self.pending_round: Optional[Dict[str, Any]] = None

        # Accumulated Coins & EXP Tracking
        self.session_coins_earned: int = 0
        self.last_round_coins: int = 0
        self.session_xp_earned: int = 0
        self.last_round_xp: int = 0

        # Frame buffer for live stream
        self.latest_frame_jpeg: Optional[bytes] = None
        self.latest_currency_crop_jpeg: Optional[bytes] = None
        self.last_frame_time: float = 0

        # Logs buffer
        self.logs: deque = deque(maxlen=200)
        self.ws_subscribers: List[asyncio.Queue] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def _store_round_screenshot(self, round_num: int, shot_type: str, img_bytes: bytes):
        if round_num not in self.round_screenshots:
            self.round_screenshots[round_num] = {}
        self.round_screenshots[round_num][shot_type] = img_bytes
        if len(self.round_screenshots) > 50:
            oldest_key = min(self.round_screenshots.keys())
            del self.round_screenshots[oldest_key]

    def _build_duration_str(self) -> str:
        dur_sec = int(time.time() - self.current_round_start_time) if self.current_round_start_time else 0
        return f"{dur_sec // 60}m {dur_sec % 60}s" if dur_sec >= 60 else f"{dur_sec}s"

    def _publish_round_history(self, boxes: List[str], has_box_before: bool = False,
                               has_box_after: bool = False):
        """Publish the pending round card AFTER box detection is settled.

        Called from MYSTERY_BOX (real grades) or from MAINMENU / next-round
        start (confirmed no boxes). This keeps the history list from showing
        a card with placeholder/wrong boxes before detection finishes.
        """
        p = self.pending_round
        if p is None or self.current_round_recorded:
            return
        dur_str = self._build_duration_str()
        item = {
            "round": p["round"],
            "time": p["time"],
            "duration": dur_str,
            "coins": p["coins"],
            "xp": p["xp"],
            "boxes": list(boxes),
            "box_count": len(boxes),
            "has_screenshot": True,
            "has_result": True,
            "has_box_before": has_box_before,
            "has_box_after": has_box_after,
        }
        self.round_history.appendleft(item)
        self.current_round_recorded = True
        self.pending_round = None

        xp_log = f" | +{p['xp']:,} EXP" if p["xp"] > 0 else ""
        if boxes:
            box_log = f" | 📦 ได้รับกล่อง {len(boxes)} กล่อง"
        else:
            box_log = " | ไม่มีกล่องในรอบนี้"
        self.log(f"🏁 จบรอบที่ #{p['round']}: ได้รับ +{p['coins']:,} 🪙{xp_log}{box_log} (ยอดสะสม: {self.session_coins_earned:,} 🪙 | {self.session_xp_earned:,} EXP)", "success")
        discord_notifier.send_round_summary(
            round_num=p["round"],
            duration_str=dur_str,
            coins_earned=p["coins"],
            session_coins=self.session_coins_earned,
            xp_earned=p["xp"],
            session_xp=self.session_xp_earned,
            boxes=list(boxes),
            screen_img=p.get("screen"),
        )

    def _finalize_pending_round_no_boxes(self):
        """Finalize a pending round when we're back at lobby with no box stage seen."""
        p = self.pending_round
        if p is None or self.current_round_recorded:
            return
        hint = p.get("hint_boxes") or []
        if hint:
            # Result screen showed a box badge but the box stage was missed:
            # keep the old wood-fallback so the box isn't silently lost.
            for b in hint:
                self.box_counts[b] = self.box_counts.get(b, 0) + 1
            self.box_counts["total"] += len(hint)
            self.mystery_boxes = self.box_counts["total"]
            self._publish_round_history(list(hint))
        else:
            self._publish_round_history([])


    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "time": timestamp,
            "message": message,
            "level": level,
        }
        self.logs.append(log_entry)
        try:
            print(f"[{timestamp}] [{level.upper()}] {message}")
        except Exception:
            pass

        if self.loop and self.ws_subscribers:
            for q in list(self.ws_subscribers):
                try:
                    self.loop.call_soon_threadsafe(q.put_nowait, log_entry)
                except Exception:
                    pass

    def interruptible_sleep(self, seconds: float) -> bool:
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.should_stop:
                return True
            time.sleep(0.1)
        return False

    def update_frame(self, screen_bgr: np.ndarray):
        if screen_bgr is not None:
            try:
                target_w = 854
                target_h = 480
                resized = cv2.resize(screen_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                _, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 75])
                self.latest_frame_jpeg = buffer.tobytes()
                self.last_frame_time = time.time()

                # Extract top currency banner (Diamonds + Coins)
                h, w = screen_bgr.shape[:2]
                if h >= 100 and w >= 1200:
                    curr_crop = screen_bgr[10:72, 730:1220]
                    _, curr_buf = cv2.imencode(".jpg", curr_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self.latest_currency_crop_jpeg = curr_buf.tobytes()
            except Exception:
                pass

    def start(self, user_config: Dict[str, Any]):
        with self.lock:
            if self.is_running:
                return {"success": False, "message": "Bot is already running"}

            self.device_ip = user_config.get("device_ip", self.device_ip)
            self.device_port = int(user_config.get("device_port", self.device_port))
            self.use_fast_start = bool(user_config.get("use_fast_start", False))
            self.fast_start_min_stock = int(user_config.get("fast_start_min_stock", 10))
            self.use_cookie_relay = bool(user_config.get("use_cookie_relay", False))
            self.cookie_relay_min_stock = int(user_config.get("cookie_relay_min_stock", 10))
            self.use_desired_random_boost = bool(user_config.get("use_desired_random_boost", False))
            self.desired_boost_id = user_config.get("desired_boost_id", "double_coins")
            self.detect_relic = bool(user_config.get("detect_relic", True))
            self.send_friend_lives = bool(user_config.get("send_friend_lives", True))
            self.stop_goal_rounds_enabled = bool(user_config.get("stop_goal_rounds_enabled", False))
            self.stop_goal_rounds_target = int(user_config.get("stop_goal_rounds_target", 50))
            self.stop_goal_time_enabled = bool(user_config.get("stop_goal_time_enabled", False))
            self.stop_goal_time_hours = float(user_config.get("stop_goal_time_hours", 2.0))

            self.reset_stats()
            config.DEVICE_IP = self.device_ip
            config.DEVICE_PORT = self.device_port
            self.is_running = True
            self.should_stop = False
            self.start_time = time.time()
            self.current_round_start_time = time.time()
            self.current_round_recorded = False
            self.current_stage = "INITIALIZING"
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            self.log(f"▶️ Bot started (Device: {self.device_ip}:{self.device_port})", "success")
            discord_notifier.send_bot_start(self.device_ip, self.device_port)

        return {"success": True, "message": "Bot started successfully"}

    def stop(self):
        with self.lock:
            if not self.is_running:
                return {"success": False, "message": "Bot is not running"}

            self.should_stop = True
            self.current_stage = "STOPPING"
            self.log("🛑 Stopping bot...", "warning")
            uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
            hours, remainder = divmod(uptime_sec, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            final_rounds = self.rounds_played
            final_boxes = self.mystery_boxes
            final_coins = self.session_coins_earned
            final_xp = self.session_xp_earned

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

        with self.lock:
            self.is_running = False
            self.current_stage = "IDLE"
            self.log("⏹️ Bot stopped", "info")
            discord_notifier.send_bot_stop(
                uptime=uptime_str,
                rounds_played=final_rounds,
                total_boxes=final_boxes,
                coins_earned=final_coins,
                session_xp=final_xp,
            )
            # Reset all stats on stop
            self.reset_stats()

        return {"success": True, "message": "Bot stopped successfully"}

    def reset_stats(self):
        self.rounds_played = 0
        self.mystery_boxes = 0
        self.box_counts = {
            "wood": 0,
            "silver": 0,
            "gold": 0,
            "rainbow": 0,
            "total": 0,
        }
        self.session_coins_earned = 0
        self.last_round_coins = 0
        self.session_xp_earned = 0
        self.last_round_xp = 0
        self.round_history.clear()
        self.round_screenshots.clear()
        self.box_history.clear()
        self.start_time = None
        self.current_round_start_time = None
        self.current_round_recorded = False
        self.pending_round = None
        self.current_stage = "IDLE"
        self.log("📊 Stats, Mystery Box counts, Coins, and EXP reset to zero", "info")


    def get_status(self) -> Dict[str, Any]:
        uptime_sec = int(time.time() - self.start_time) if self.is_running and self.start_time else 0
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        coins_per_hour = int(self.session_coins_earned / max(0.001, uptime_sec / 3600)) if (self.is_running and uptime_sec > 5) else 0

        return {
            "is_running": self.is_running,
            "current_stage": self.current_stage,
            "uptime": uptime_str,
            "uptime_seconds": uptime_sec,
            "rounds_played": self.rounds_played,
            "mystery_boxes": self.mystery_boxes,
            "box_counts": self.box_counts,
            "coin_stats": {
                "session_earned": self.session_coins_earned,
                "session_xp_earned": self.session_xp_earned,
                "coins_per_hour": coins_per_hour,
                "last_round": self.last_round_coins,
                "last_round_xp": self.last_round_xp,
            },
            "round_history": list(self.round_history),
            "device_ip": self.device_ip,
            "device_port": self.device_port,
            "use_fast_start": self.use_fast_start,
            "fast_start_min_stock": self.fast_start_min_stock,
            "use_cookie_relay": self.use_cookie_relay,
            "cookie_relay_min_stock": self.cookie_relay_min_stock,
            "use_desired_random_boost": self.use_desired_random_boost,
            "desired_boost_id": self.desired_boost_id,
            "detect_relic": self.detect_relic,
            "send_friend_lives": self.send_friend_lives,
            "stop_goal_rounds_enabled": self.stop_goal_rounds_enabled,
            "stop_goal_rounds_target": self.stop_goal_rounds_target,
            "stop_goal_time_enabled": self.stop_goal_time_enabled,
            "stop_goal_time_hours": self.stop_goal_time_hours,
            "adb_path": get_adb_path(),
            "discord_settings": {
                "webhook_url": discord_notifier.webhook_url,
                "enabled": discord_notifier.enabled,
                "notify_boxes": discord_notifier.notify_boxes,
                "notify_antibot": discord_notifier.notify_antibot,
                "notify_status": discord_notifier.notify_status,
                "attach_screenshot": discord_notifier.attach_screenshot,
            }
        }

    def _run_loop(self):
        try:
            self.log(f"🔌 Connecting to device at {self.device_ip}:{self.device_port}...")
            device_connect(self.device_ip, self.device_port)
            self.log("✅ ADB Connection established", "success")

            self.log("🖼️ Pre-warming OpenCV templates...")
            load_templates()
            self.log("✅ Templates loaded", "success")

            desired_boost_template = None
            desired_boost_name = None
            if self.use_desired_random_boost:
                boost_item = next((b for b in BOOST_OPTIONS if b["id"] == self.desired_boost_id), BOOST_OPTIONS[0])
                desired_boost_template = boost_item["template"]
                desired_boost_name = boost_item["name"]
                self.log(f"🎲 Desired Random Boost: {desired_boost_name}")

            relic_exclude = None if self.detect_relic else {"RELIC_COMPLETE", "RELIC_CLAIM"}

            last_stage = None
            is_first_game = True
            detection_group = "PRE_GAME"
            last_detected_time = time.time()
            session_start_time = time.time()
            session_reset_interval = random.uniform(*SESSION_RESET_INTERVAL)
            last_lives_time = time.time()
            lives_interval = random.uniform(25 * 60, 35 * 60)
            pending_send_friend_life = False
            skip_next_mainmenu_log = False

            self.log("🏁 Main loop started. Waiting for game screen...")

            while not self.should_stop:
                try:
                    device_screen = device_capture_screen(self.device_ip, self.device_port)
                    self.update_frame(device_screen)
                except Exception as e:
                    self.log(f"⚠️ Screen capture error: {e}", "error")
                    if self.interruptible_sleep(1.0):
                        break
                    continue

                stage = detect_stage(device_screen, get_detection_stage_names(detection_group, exclude=relic_exclude))
                if stage is None:
                    if time.time() - last_detected_time >= DETECTION_RECOVERY_SCAN_INTERVAL[detection_group]:
                        stage = detect_stage(device_screen, exclude=relic_exclude)
                        last_detected_time = time.time()
                else:
                    last_detected_time = time.time()

                if stage:
                    self.current_stage = stage
                elif self.current_stage not in ("STARTING", "STOPPING"):
                    self.current_stage = f"{detection_group} (Searching...)"

                if stage == last_stage:
                    if self.interruptible_sleep(0.1):
                        break
                    continue

                last_stage = stage

                if stage == "MAINMENU":
                    # No box stage appeared for this round -> confirm "no boxes"
                    # and publish the pending card now (shows "ไม่มีกล่องในรอบนี้").
                    self._finalize_pending_round_no_boxes()

                    if detection_group == "POST_GAME":
                        self.log("🎮 Detected Stage: MAINMENU (กลับมาหน้าล็อบบี้)", "stage")
                        self.log("⏳ Waiting 5 seconds for screen refresh...")
                        if self.interruptible_sleep(5.0):
                            break
                        detection_group = "PRE_GAME"
                        last_stage = None
                        skip_next_mainmenu_log = True
                        continue

                    if skip_next_mainmenu_log:
                        skip_next_mainmenu_log = False
                    else:
                        self.log("🎮 Detected Stage: MAINMENU", "stage")

                    if pending_send_friend_life and self.send_friend_lives:
                        self.log("💌 Sending friend lives after app reset...")
                        handle_send_friend_life()
                        pending_send_friend_life = False
                        last_lives_time = time.time()
                        last_stage = None
                        continue

                    elapsed = time.time() - session_start_time
                    if elapsed >= session_reset_interval:
                        self.log(f"🔄 Session reset triggered after {elapsed / 3600:.2f}h — restarting app...")
                        device_reset_app(self.device_ip, self.device_port)
                        if self.interruptible_sleep(5.0):
                            break
                        close_announcement_dialog()
                        pending_send_friend_life = True
                        session_start_time = time.time()
                        session_reset_interval = random.uniform(*SESSION_RESET_INTERVAL)
                        last_lives_time = time.time()
                        lives_interval = random.uniform(25 * 60, 35 * 60)
                        detection_group = "PRE_GAME"
                        last_stage = None
                        is_first_game = True
                        continue

                    lives_elapsed = time.time() - last_lives_time
                    if self.send_friend_lives and lives_elapsed >= lives_interval:
                        self.log(f"💌 ~30 min passed ({lives_elapsed / 60:.1f} min) — receiving and sending lives...")
                        handle_quick_receive_and_send_lives()
                        last_lives_time = time.time()
                        lives_interval = random.uniform(25 * 60, 35 * 60)
                        last_stage = None
                        continue

                    # Check Auto-Stop Goals before starting next round
                    if self.stop_goal_rounds_enabled and self.rounds_played >= self.stop_goal_rounds_target:
                        goal_msg = f"วิ่งครบตามเป้าหมาย {self.stop_goal_rounds_target} รอบ"
                        self.log(f"🎯 บรรลุเป้าหมาย: {goal_msg}! กำลังหยุดการทำงานบอทอัตโนมัติ...", "success")
                        uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
                        hours, remainder = divmod(uptime_sec, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        discord_notifier.send_goal_reached(
                            goal_description=goal_msg,
                            uptime=uptime_str,
                            rounds_played=self.rounds_played,
                            total_boxes=self.mystery_boxes,
                            coins_earned=self.session_coins_earned,
                            session_xp=self.session_xp_earned,
                        )
                        break

                    elapsed_hours = (time.time() - self.start_time) / 3600 if self.start_time else 0
                    if self.stop_goal_time_enabled and elapsed_hours >= self.stop_goal_time_hours:
                        goal_msg = f"ปล่อยบอทครบตามเป้าหมาย {self.stop_goal_time_hours:g} ชั่วโมง"
                        self.log(f"🎯 บรรลุเป้าหมาย: {goal_msg}! กำลังหยุดการทำงานบอทอัตโนมัติ...", "success")
                        uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
                        hours, remainder = divmod(uptime_sec, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        discord_notifier.send_goal_reached(
                            goal_description=goal_msg,
                            uptime=uptime_str,
                            rounds_played=self.rounds_played,
                            total_boxes=self.mystery_boxes,
                            coins_earned=self.session_coins_earned,
                            session_xp=self.session_xp_earned,
                        )
                        break

                    if not is_first_game:
                        delay = random.uniform(5, 15)
                        self.log(f"⏳ Waiting {delay:.1f}s before starting next round to avoid detection...")
                        if self.interruptible_sleep(delay):
                            break

                    is_first_game = False
                    start_game()
                    detection_group = "PRE_GAME"

                elif stage == "PURCHASE_ITEM":
                    self.log("🛒 Detected Stage: PURCHASE_ITEM", "stage")

                    # Smart Fast Start check
                    if self.use_fast_start:
                        stock_fs = extract_item_stock(device_screen, "fast_start")
                        if stock_fs <= self.fast_start_min_stock:
                            self.log(f"⚡ Fast Start ในคลัง ({stock_fs} ชิ้น <= เกณฑ์ {self.fast_start_min_stock}) -> กำลังซื้อเพิ่ม...", "info")
                            purchase_fast_start()
                        else:
                            self.log(f"⚡ Fast Start ในคลังมี {stock_fs} ชิ้น (มากกว่าเกณฑ์ {self.fast_start_min_stock}) -> ข้ามการซื้อเพื่อประหยัดเหรียญ", "info")

                    # Smart Cookie Relay check
                    if self.use_cookie_relay:
                        stock_cr = extract_item_stock(device_screen, "cookie_relay")
                        if stock_cr <= self.cookie_relay_min_stock:
                            self.log(f"🍪 Cookie Relay ในคลัง ({stock_cr} ชิ้น <= เกณฑ์ {self.cookie_relay_min_stock}) -> กำลังซื้อเพิ่ม...", "info")
                            purchase_cookie_relay()
                        else:
                            self.log(f"🍪 Cookie Relay ในคลังมี {stock_cr} ชิ้น (มากกว่าเกณฑ์ {self.cookie_relay_min_stock}) -> ข้ามการซื้อเพื่อประหยัดเหรียญ", "info")

                    if self.use_desired_random_boost and desired_boost_template:
                        if device_screen is not None and detect_templates(device_screen, desired_boost_template, RANDOM_BOOST_REGION):
                            self.log(f"🎲 ตรวจบัฟก่อนสุ่ม: เจอ '{desired_boost_name}' เปิดอยู่แล้ว -> ข้ามการสุ่ม (ประหยัดเหรียญ)", "info")
                        else:
                            self.log(f"🎲 ตรวจบัฟก่อนสุ่ม: ยังไม่เจอ '{desired_boost_name}' -> เริ่มสุ่มซื้อ...", "info")
                            purchase_desired_random_boost(
                                desired_boost_template,
                                desired_boost_name,
                                logger=lambda msg: self.log(msg, "info"),
                            )
                    play_game()
                    detection_group = "IN_GAME"
                    # Safety net: previous round must already be published; if its
                    # box detection was missed entirely, close it out as no-box
                    # before the new round number is assigned.
                    self._finalize_pending_round_no_boxes()
                    self.rounds_played += 1
                    self.current_round_start_time = time.time()
                    self.current_round_recorded = False
                    self.current_round_screen = None
                    self.log(f"🏁 Round {self.rounds_played} started!", "success")
                    if self.interruptible_sleep(0.2):
                        break
                    last_stage = None

                elif stage == "GAME_START":
                    self.log("🏁 Detected Stage: GAME_START", "stage")
                    if self.use_fast_start:
                        using_fast_start()
                    detection_group = "IN_GAME"

                elif stage == "GAME_RELAY":
                    self.log("🔄 Detected Stage: GAME_RELAY (Cookie Relay Triggered)", "stage")
                    if self.use_cookie_relay:
                        press_deadline = time.time() + COOKIE_RELAY_PRESS_TIMEOUT
                        press_attempts = 0
                        first_press = True
                        while time.time() < press_deadline and not self.should_stop:
                            if not first_press:
                                recheck_screen = device_capture_screen(self.device_ip, self.device_port)
                                if recheck_screen is not None:
                                    if detect_stage(recheck_screen, ["GAME_RELAY"]) != "GAME_RELAY":
                                        break
                            first_press = False
                            using_cookie_relay()
                            press_attempts += 1
                            if press_attempts > 1:
                                self.log(f"🍪 Cookie Relay: กดซ้ำรอบที่ {press_attempts} (หน้าจอยังเป็น GAME_RELAY)", "info")
                            if self.interruptible_sleep(COOKIE_RELAY_PRESS_RETRY_SLEEP):
                                break
                        if press_attempts > 1:
                            self.log(f"🍪 Cookie Relay: กดรวม {press_attempts} ครั้งจนหน้าจอเปลี่ยน", "info")
                    detection_group = "IN_GAME"

                elif stage == "GAME_COMPLETE":
                    self.log("✅ Detected Stage: GAME_COMPLETE (กำลังรอสรุปผลคะแนน, เหรียญ & EXP...)", "stage")

                    # 1. Wait a bit for card to enter, then tap to skip animation
                    time.sleep(random.uniform(1.0, 1.5))
                    device_tap(self.device_ip, self.device_port, 640, 260)

                    # 2. Wait for score, coins, and XP to count up fully
                    time.sleep(random.uniform(3.5, 4.5))

                    # 3. Tap second time to ensure level bonus / combi bonus settle
                    device_tap(self.device_ip, self.device_port, 640, 260)
                    time.sleep(random.uniform(2.0, 2.5))

                    # 4. Capture fresh screen once numbers have completely settled
                    fresh_screen = device_capture_screen(self.device_ip, self.device_port)
                    if fresh_screen is not None:
                        device_screen = fresh_screen

                    # 5. Extract real in-game coins and XP directly from Result screen
                    round_coins = extract_result_coins(device_screen) if device_screen is not None else 0
                    round_xp = extract_result_xp(device_screen) if device_screen is not None else 0

                    # 6. Safety retry if still 0
                    if round_coins == 0 and device_screen is not None:
                        device_tap(self.device_ip, self.device_port, 640, 260)
                        time.sleep(2.0)
                        fresh_screen = device_capture_screen(self.device_ip, self.device_port)
                        if fresh_screen is not None:
                            device_screen = fresh_screen
                            round_coins = extract_result_coins(device_screen)
                            round_xp = extract_result_xp(device_screen)

                    if device_screen is not None:
                        self.current_round_screen = device_screen.copy()
                        try:
                            _, buf = cv2.imencode(".jpg", device_screen, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            self._store_round_screenshot(self.rounds_played, "result", buf.tobytes())
                        except Exception:
                            pass

                    if round_coins > 0:
                        self.session_coins_earned += round_coins
                        self.last_round_coins = round_coins
                    if round_xp > 0:
                        self.session_xp_earned += round_xp
                        self.last_round_xp = round_xp

                    # Detect mystery box badge on Result screen (hint only, NOT final).
                    # The history card + box counts are published only after the
                    # MYSTERY_BOX stage settles the real grades (or MAINMENU
                    # confirms there were no boxes). The card is NEVER emitted at
                    # GAME_COMPLETE: it must appear after box resolution, so a box
                    # round shows the 🎁 box log first, then the round summary.
                    round_boxes_hint = detect_result_screen_mystery_box(device_screen) if device_screen is not None else []

                    # Stage the pending round; publish happens in _publish_round_history.
                    if not self.current_round_recorded and self.pending_round is None:
                        self.pending_round = {
                            "round": self.rounds_played,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "coins": round_coins,
                            "xp": round_xp,
                            "hint_boxes": list(round_boxes_hint),
                            "screen": device_screen.copy() if device_screen is not None else None,
                        }
                        if round_boxes_hint:
                            xp_log = f" | +{round_xp:,} EXP" if round_xp > 0 else ""
                            self.log(f"🏁 รอบที่ #{self.rounds_played} จบ: +{round_coins:,} 🪙{xp_log} — รอตรวจกล่องก่อนแสดงประวัติ...", "info")

                    # 7. Generous pause before tapping OK so the final score screen stays visible
                    time.sleep(random.uniform(2.0, 3.0))

                    # 8. Tap OK to complete and dismiss the Result screen
                    complete_finish()
                    detection_group = "POST_GAME"

                elif stage == "MYSTERY_BOX":
                    if self.current_round_recorded:
                        # Boxes already processed for this round; the screen is a
                        # leftover loot/confirm frame that still matches MYSTERY_BOX.
                        # Just dismiss it — do NOT count boxes, tap "Open all",
                        # publish, or notify Discord again.
                        if self.interruptible_sleep(random.uniform(1.2, 1.6)):
                            break
                        safe_device_tap(self.device_ip, self.device_port, ACCEPT_MYSTERY_BOX_BUTTON[0], ACCEPT_MYSTERY_BOX_BUTTON[1])
                        detection_group = "POST_GAME"
                        last_stage = None
                        continue

                    # Wait briefly for box reveal animation to settle
                    time.sleep(random.uniform(0.8, 1.2))
                    fresh_mb_screen = device_capture_screen(self.device_ip, self.device_port)
                    if fresh_mb_screen is not None:
                        device_screen = fresh_mb_screen

                    # Detect specific box grades
                    detected_grades = detect_mystery_box_grades(device_screen)
                    if not detected_grades:
                        # Fallback: In MYSTERY_BOX stage, at least 1 box was dropped
                        detected_grades = ["wood"]

                    box_names_th = {
                        "wood": "🟤 ไม้",
                        "silver": "⚪ เงิน",
                        "gold": "🟡 ทอง",
                        "rainbow": "🌈 รุ้ง",
                    }
                    grade_str = ", ".join([box_names_th.get(g, g) for g in detected_grades])

                    for g in detected_grades:
                        self.box_counts[g] = self.box_counts.get(g, 0) + 1
                    self.box_counts["total"] += len(detected_grades)
                    self.mystery_boxes = self.box_counts["total"]

                    dur_sec = int(time.time() - self.current_round_start_time) if self.current_round_start_time else 0
                    dur_str = f"{dur_sec // 60}m {dur_sec % 60}s" if dur_sec >= 60 else f"{dur_sec}s"

                    # 1. Capture screen before opening (unopened boxes with "Open all" button)
                    if device_screen is not None:
                        try:
                            _, buf_before = cv2.imencode(".jpg", device_screen, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            self._store_round_screenshot(self.rounds_played, "box_before", buf_before.tobytes())
                        except Exception:
                            pass

                    self.log(f"🎁 ได้รับกล่องปริศนา: [{grade_str}] (รวมทั้งหมด: {self.mystery_boxes} กล่อง)", "success")

                    # Publish the round summary + history card AFTER the box log,
                    # so the card shows the real grades and appears in order
                    # (🎁 box log first, then the 🏁 round summary + card).
                    if self.pending_round is not None and self.pending_round.get("round") == self.rounds_played and not self.current_round_recorded:
                        self._publish_round_history(detected_grades, has_box_before=True)
                    # Update or append round history record (fallback when pending is missing)
                    elif self.round_history and self.round_history[0]["round"] == self.rounds_played:
                        self.round_history[0]["boxes"] = detected_grades
                        self.round_history[0]["box_count"] = len(detected_grades)
                        self.round_history[0]["has_box_before"] = True
                    else:
                        round_coins = extract_result_coins(device_screen) if device_screen is not None else 0
                        round_xp = extract_result_xp(device_screen) if device_screen is not None else 0
                        if round_coins > 0:
                            self.session_coins_earned += round_coins
                            self.last_round_coins = round_coins
                        if round_xp > 0:
                            self.session_xp_earned += round_xp
                            self.last_round_xp = round_xp

                        item = {
                            "round": self.rounds_played,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "duration": dur_str,
                            "coins": round_coins,
                            "xp": round_xp,
                            "boxes": detected_grades,
                            "box_count": len(detected_grades),
                            "has_screenshot": True,
                            "has_result": bool(self.round_screenshots.get(self.rounds_played, {}).get("result")),
                            "has_box_before": True,
                            "has_box_after": False,
                        }
                        self.round_history.appendleft(item)
                        self.current_round_recorded = True

                    self.log("🎁 กำลังกดปุ่ม 'Open all' เพื่อเปิดกล่องและดูของรางวัล...", "info")

                    # 2. Tap 'Open all' button
                    safe_device_tap(self.device_ip, self.device_port, ACCEPT_MYSTERY_BOX_BUTTON[0], ACCEPT_MYSTERY_BOX_BUTTON[1])

                    # 3. Wait for box opening animation to reveal loot items
                    if self.interruptible_sleep(random.uniform(2.2, 2.7)):
                        break

                    # 4. Capture screen after opening (loot / items revealed)
                    loot_screen = device_capture_screen(self.device_ip, self.device_port)
                    if loot_screen is not None:
                        try:
                            _, buf_after = cv2.imencode(".jpg", loot_screen, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            self._store_round_screenshot(self.rounds_played, "box_after", buf_after.tobytes())
                            if self.round_history and self.round_history[0]["round"] == self.rounds_played:
                                self.round_history[0]["has_box_after"] = True
                        except Exception:
                            pass

                    # Send Discord notification with revealed loot image
                    discord_notifier.send_box_drop(
                        self.rounds_played,
                        detected_grades,
                        self.box_counts,
                        coins_earned=self.last_round_coins,
                        session_coins=self.session_coins_earned,
                        xp_earned=self.last_round_xp,
                        session_xp=self.session_xp_earned,
                        screen_img=loot_screen if loot_screen is not None else device_screen
                    )

                    # 5. Tap to confirm loot and exit box screen
                    safe_device_tap(self.device_ip, self.device_port, ACCEPT_MYSTERY_BOX_BUTTON[0], ACCEPT_MYSTERY_BOX_BUTTON[1])
                    if self.interruptible_sleep(random.uniform(1.2, 1.6)):
                        break

                    detection_group = "POST_GAME"
                    last_stage = None


                elif stage == "CONGRATULATIONS":
                    self.log("🎉 Detected Stage: CONGRATULATIONS", "stage")
                    accept_congratulations()
                    detection_group = "POST_GAME"
                    last_stage = None

                elif stage == "LEVEL_UP":
                    self.log("⬆️ Detected Stage: LEVEL_UP", "success")
                    accept_level_up()
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_CHECKIN":
                    self.log("📅 Detected Stage: DAILY_CHECKIN", "stage")
                    accept_daily_checkin()
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_CHECKIN_BOOST_SET":
                    self.log("📅 Detected Stage: DAILY_CHECKIN_BOOST_SET", "stage")
                    accept_daily_checkin_boost_set()
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_TREASURE":
                    self.log("💎 Detected Stage: DAILY_TREASURE", "stage")
                    accept_daily_treasure()
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_NEW":
                    self.log("📰 Detected Stage: DAILY_NEW", "stage")
                    accept_daily_new()
                    detection_group = "PRE_GAME"

                elif stage == "ENTER_LEAGUE":
                    self.log("🏆 Detected Stage: ENTER_LEAGUE", "stage")
                    accept_enter_league()
                    detection_group = "PRE_GAME"

                elif stage == "LEAGUE_RESULTS":
                    self.log("🏆 Detected Stage: LEAGUE_RESULTS", "stage")
                    accept_league_results()
                    detection_group = "PRE_GAME"

                elif stage == "PREVIOUS_RANK_RESULTS":
                    self.log("🏆 Detected Stage: PREVIOUS_RANK_RESULTS", "stage")
                    accept_previous_rank_results()
                    detection_group = "PRE_GAME"

                elif stage == "OVERTAKE_BREAK_SCORE":
                    self.log("🏆 Detected Stage: OVERTAKE_BREAK_SCORE", "stage")
                    accept_overtake_break_score()
                    detection_group = "POST_GAME"
                    last_stage = None

                elif stage == "TOO_MANY_TREASURES":
                    self.log("💎 Detected Stage: TOO_MANY_TREASURES", "warning")
                    accept_too_many_treasures()
                    detection_group = "PRE_GAME"

                elif stage == "RELIC_COMPLETE":
                    self.log("🏺 Detected Stage: RELIC_COMPLETE", "stage")
                    open_relic_complete()
                    detection_group = "PRE_GAME"

                elif stage == "RELIC_CLAIM":
                    self.log("🏺 Detected Stage: RELIC_CLAIM", "stage")
                    accept_relic_claim()
                    detection_group = "PRE_GAME"

                elif stage == "ANTI_BOT":
                    self.log("⚠️ Detected Stage: ANTI_BOT — solving captcha automatically...", "warning")
                    discord_notifier.send_anti_bot_alert("ANTI_BOT", screen_img=device_screen)
                    handle_anti_bot(device_screen)
                    last_stage = None

                elif stage == "CONNECTION_LOST":
                    self.log("🔌 Detected Stage: CONNECTION_LOST — resetting app...", "error")
                    discord_notifier.send_connection_lost(self.device_ip, self.device_port)
                    device_reset_app(self.device_ip, self.device_port)
                    if self.interruptible_sleep(5.0):
                        break
                    close_announcement_dialog()
                    session_start_time = time.time()
                    session_reset_interval = random.uniform(*SESSION_RESET_INTERVAL)
                    last_lives_time = time.time()
                    lives_interval = random.uniform(25 * 60, 35 * 60)
                    detection_group = "PRE_GAME"
                    last_stage = None
                    is_first_game = True

                elif stage == "INACTIVE":
                    self.log("💤 Detected Stage: INACTIVE — reconnecting...", "warning")
                    handle_inactive()
                    last_stage = None

                if self.interruptible_sleep(0.25):
                    break

        except Exception as e:
            self.log(f"❌ Bot runtime error: {e}", "error")
        finally:
            with self.lock:
                self.is_running = False
                self.current_stage = "IDLE"
                self.reset_stats()
            self.log("⏹️ Bot execution ended", "info")



# Global Singleton Instance
bot_engine = BotEngine()
