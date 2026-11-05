import asyncio
import json
import logging
import html
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

import os
from dotenv import load_dotenv
from config import settings as cfg
from config.settings import ADMIN_ID
from database.db import AsyncSessionLocal
from database.models import AppSetting

logger = logging.getLogger("ZEUS.NODE_ALERTS")


async def node_alert_loop(bot):
    while True:
        try:
            load_dotenv(cfg.BASE_DIR / ".env", override=True)
            cfg.PANEL_URL = os.getenv("PANEL_URL", "").rstrip("/")
            cfg.PANEL_API_KEY = os.getenv("PANEL_API_KEY", "")
            cfg.CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
            async with httpx.AsyncClient(
                base_url=cfg.PANEL_URL.rstrip("/") + "/",
                headers={"X-Api-Key": cfg.PANEL_API_KEY},
                timeout=20
            ) as client:
                response = await client.get("api/nodes")
                response.raise_for_status()
                nodes = response.json().get("nodes", [])

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AppSetting).where(
                        AppSetting.key == "node_panel_status_state"
                    )
                )
                setting = result.scalar_one_or_none()
                state = json.loads(setting.value) if setting else {}

                public_result = await db.execute(
                    select(AppSetting).where(AppSetting.key == "public_alert_chat")
                )
                public_setting = public_result.scalar_one_or_none()
                public_chat = public_setting.value if public_setting else ""
                now = datetime.now(timezone.utc)

                for node in nodes:
                    key = str(node.get("id") or node.get("name"))
                    name = html.escape(str(node.get("name") or "Unknown"))
                    online = str(node.get("status", "")).lower() == "connected"
                    previous = state.get(key)

                    if previous is None:
                        state[key] = {
                            "online": online,
                            "since": None if online else now.isoformat()
                        }
                        continue

                    if previous["online"] and not online:
                        state[key] = {
                            "online": False,
                            "since": now.isoformat()
                        }
                        await bot.send_message(
                            int(ADMIN_ID),
                            f"🚨🔴 <b>هشدار قطع اتصال نود</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"⚡ <b>ZEUS MONITOR</b>\n\n"
                            f"🖥️ نام نود: <b>{name}</b>\n"
                            f"📡 وضعیت: 🔴 قطع اتصال\n"
                            f"🕒 زمان قطعی: {now.strftime('%Y-%m-%d | %H:%M:%S UTC')}\n\n"
                            f"⚠️ ارتباط این نود با پنل قطع شده یا غیرفعال شده است.\n"
                            f"🔔 وضعیت نود توسط سیستم مانیتورینگ زئوس در حال بررسی است.\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🛡️ <i>ZEUS MONITORING SYSTEM</i>",
                            parse_mode="HTML"
                        )

                        if public_chat:
                            try:
                                stamp = now.strftime("%Y-%m-%d | %H:%M:%S UTC")
                                await bot.send_message(
                                    public_chat,
                                    f"🚨🔴 <b>اطلاعیه قطعی نود</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"🖥 نود: <b>{name}</b>\n"
                                    f"🔴 وضعیت: قطع اتصال\n"
                                    f"🕒 شروع قطعی: {stamp}\n"
                                    f"📢 ساعت اطلاع‌رسانی: {stamp}\n\n"
                                    f"🛠 تیم پشتیبانی در حال بررسی و رفع مشکل است.\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"🛡 <i>ZEUS MONITOR</i>",
                                    parse_mode="HTML"
                                )
                            except Exception:
                                logger.exception("Public outage alert failed")


                    elif not previous["online"] and online:
                        since = datetime.fromisoformat(previous["since"])
                        minutes = int((now - since).total_seconds() // 60)
                        state[key] = {"online": True, "since": None}

                        await bot.send_message(
                            int(ADMIN_ID),
                            f"🎉🟢 <b>اتصال نود با موفقیت برقرار شد</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"⚡ <b>ZEUS MONITOR</b>\n\n"
                            f"🖥️ نام نود: <b>{name}</b>\n"
                            f"📡 وضعیت: 🟢 آنلاین و متصل\n"
                            f"⏱️ مدت زمان قطعی: <b>{minutes} دقیقه</b>\n"
                            f"🕒 زمان بازیابی: {now.strftime('%Y-%m-%d | %H:%M:%S UTC')}\n\n"
                            f"✅ ارتباط نود مجدداً برقرار شده است.\n"
                            f"💚 سیستم مانیتورینگ زئوس وضعیت نود را عادی تشخیص داد.\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"👑 <i>ZEUS MONITORING SYSTEM</i>",
                            parse_mode="HTML"
                        )

                        if public_chat:
                            try:
                                await bot.send_message(
                                    public_chat,
                                    f"✅🟢 <b>اطلاعیه رفع قطعی نود</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"🖥 نود: <b>{name}</b>\n"
                                    f"🟢 وضعیت: اتصال برقرار شد\n"
                                    f"🕒 شروع قطعی: {since.strftime('%Y-%m-%d | %H:%M:%S UTC')}\n"
                                    f"🕒 زمان بازیابی: {now.strftime('%Y-%m-%d | %H:%M:%S UTC')}\n"
                                    f"⏱ مدت قطعی: {minutes} دقیقه\n\n"
                                    f"💚 مشکل برطرف شد و سرویس مجدداً در دسترس است.\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"🛡 <i>ZEUS MONITOR</i>",
                                    parse_mode="HTML"
                                )
                            except Exception:
                                logger.exception("Public recovery alert failed")

                value = json.dumps(state)
                if setting:
                    setting.value = value
                else:
                    db.add(AppSetting(
                        key="node_panel_status_state",
                        value=value
                    ))
                await db.commit()

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Node monitoring failed")

        await asyncio.sleep(max(10, cfg.CHECK_INTERVAL))
