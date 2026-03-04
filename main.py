from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from astrbot.core.message.message_event_result import MessageChain
import random
import asyncio


@register("daily_greeting", "你的名字", "定时早安+下午好群问候插件", "1.0.0",
          "https://github.com/你的/astrbot_plugin_daily_greeting")
class DailyGreeting(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

        # 默认配置（可在代码里改，也支持后面加WebUI配置）
        self.morning_time = "08:00"  # 早上时间 HH:MM
        self.afternoon_time = "17:30"  # 下午时间 HH:MM
        self.group_ids = []  # 初始为空，通过指令绑定

        # 问候语库（可以随便加）
        self.morning_msgs = [
            "🌞 早安呀~ 新的一天开始了，今天也要元气满满哦！",
            "早上好！记得吃早餐，爱你哟～",
            "☀️ 早安！希望你今天一切顺利，加油！",
            "大家早安～ 今天也要开心哦！"
        ]
        self.afternoon_msgs = [
            "🌤️ 下午好～ 忙碌的一天也要记得休息一下呀",
            "下午茶时间到了，喝杯水放松放松～",
            "💪 下午好！继续加油，晚上见！",
            "下午好呀～ 今天过得怎么样呢？"
        ]

        # 启动定时任务
        self.start_scheduler()
        logger.info("【每日问候】插件已加载，定时任务启动！")

    def start_scheduler(self):
        """启动 APScheduler 定时任务"""
        try:
            mh, mm = map(int, self.morning_time.split(":"))
            ah, am = map(int, self.afternoon_time.split(":"))

            self.scheduler.add_job(
                self.send_morning,
                CronTrigger(hour=mh, minute=mm, timezone="Asia/Shanghai"),
                id="morning_greeting"
            )
            self.scheduler.add_job(
                self.send_afternoon,
                CronTrigger(hour=ah, minute=am, timezone="Asia/Shanghai"),
                id="afternoon_greeting"
            )
            self.scheduler.start()
            logger.info(f"【每日问候】定时已启动 → 早上 {self.morning_time} | 下午 {self.afternoon_time}")
        except Exception as e:
            logger.error(f"启动定时任务失败: {e}")

    async def send_greeting(self, is_morning: bool):
        """统一发送问候"""
        msgs = self.morning_msgs if is_morning else self.afternoon_msgs
        msg = random.choice(msgs)
        chain = MessageChain().plain(msg)  # 纯文本

        if not self.group_ids:
            logger.warning("【每日问候】没有绑定任何群，跳过发送")
            return

        for gid in self.group_ids:
            # 构造 unified_msg_origin（QQ群最常见格式）
            umo = f"qq:group:{gid}"  # NapCat / OneBot 通用
            try:
                await self.context.send_message(umo, chain)
                logger.info(f"【每日问候】已向群 {gid} 发送 {'早安' if is_morning else '下午好'}")
                await asyncio.sleep(1.5)  # 防风控，间隔发送
            except Exception as e:
                logger.error(f"向群 {gid} 发送失败: {e}")

    async def send_morning(self):
        await self.send_greeting(True)

    async def send_afternoon(self):
        await self.send_greeting(False)

    # ==================== 指令区 ====================
    @filter.command("greeting_bind")
    async def bind_group(self, event: AstrMessageEvent):
        """在目标群里发 /greeting_bind 即可绑定该群"""
        session_id = event.get_session_id()  # 群号字符串
        if not session_id or "group" not in str(event.get_platform_meta()):
            yield event.plain_result("❌ 请在 QQ 群聊中使用此指令")
            return

        if session_id not in self.group_ids:
            self.group_ids.append(session_id)
            yield event.plain_result(f"✅ 已绑定本群（群号 {session_id}），定时问候将发送到这里！")
            logger.info(f"【每日问候】已绑定群 {session_id}")
        else:
            yield event.plain_result("本群已绑定过了～")

    @filter.command("greeting_list")
    async def list_groups(self, event: AstrMessageEvent):
        """查看当前绑定的群"""
        if not self.group_ids:
            yield event.plain_result("当前没有绑定任何群")
            return
        txt = "当前绑定的群：\n" + "\n".join([f"• {gid}" for gid in self.group_ids])
        yield event.plain_result(txt)

    @filter.command("greeting_unbind")
    async def unbind_group(self, event: AstrMessageEvent):
        """解除绑定（在群里发）"""
        gid = event.get_session_id()
        if gid in self.group_ids:
            self.group_ids.remove(gid)
            yield event.plain_result(f"✅ 已解除本群绑定")
        else:
            yield event.plain_result("本群未绑定")

    # 插件卸载/重载时清理
    async def terminate(self):
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("【每日问候】定时任务已关闭")
