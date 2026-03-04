from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from astrbot.core.message.message_event_result import MessageChain
import random
import asyncio


@register("daily_greeting", "你自己", "每日定时问候（带测试指令）", "1.2.1-test",
          "https://github.com/你的/astrbot_plugin_daily_greeting")
class DailyGreeting(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

        self.start_scheduler()
        logger.info("【每日问候 测试版】已加载")
        logger.info(f"   配置群号: {self.config.get('group_ids', [])}")
        logger.info(f"   早上时间: {self.config.get('morning_time')} | 晚上时间: {self.config.get('night_time')}")
        logger.info("   测试指令可用：/greeting_test_morning 和 /greeting_test_night")

    def start_scheduler(self):
        try:
            mh, mm = map(int, self.config["morning_time"].split(":"))
            ah, am = map(int, self.config["night_time"].split(":"))

            self.scheduler.add_job(self.send_morning, CronTrigger(hour=mh, minute=mm, timezone="Asia/Shanghai"))
            self.scheduler.add_job(self.send_night, CronTrigger(hour=ah, minute=am, timezone="Asia/Shanghai"))
            self.scheduler.start()
            logger.info("【每日问候】定时任务已启动 ✅")
        except Exception as e:
            logger.error(f"启动定时任务失败: {e}")

    async def send_greeting(self, is_morning: bool):
        msgs = self.config["morning_msgs"] if is_morning else self.config["night_msgs"]
        if not msgs:
            logger.warning("问候语列表为空")
            return
        msg = random.choice(msgs)

        # 修复：标准 MessageChain 初始化
        chain = MessageChain().plain(msg)

        group_ids = self.config.get("group_ids", [])
        if not group_ids:
            logger.warning("群号列表为空，跳过发送")
            return

        for gid in group_ids:
            # 修复：正确 UMO 格式（aiocqhttp 是 QQ 最常见的平台名）
            umo = f"aiocqhttp:GroupMessage:{gid}"
            try:
                await self.context.send_message(umo, chain)
                logger.info(f"✅ 已向群 {gid} 发送 {'早安' if is_morning else '晚上好'}：{msg[:30]}...")
                await asyncio.sleep(1.2)  # 防风控
            except Exception as e:
                logger.error(f"向群 {gid} 发送失败: {e}")

    async def send_morning(self):
        await self.send_greeting(True)

    async def send_night(self):
        await self.send_greeting(False)

    # ====================== 测试指令 ======================
    @filter.command("greeting_test_morning")
    async def test_morning(self, event: AstrMessageEvent):
        yield event.plain_result("🚀 正在测试发送【早安】消息...")
        await self.send_greeting(True)
        yield event.plain_result("✅ 早安测试发送完成！请检查群内消息")

    @filter.command("greeting_test_night")
    async def test_night(self, event: AstrMessageEvent):
        yield event.plain_result("🚀 正在测试发送【晚上好】消息...")
        await self.send_greeting(False)
        yield event.plain_result("✅ 晚上好测试发送完成！请检查群内消息")

    # 查看配置
    @filter.command("greeting_list")
    async def list_config(self, event: AstrMessageEvent):
        groups = self.config.get("group_ids", [])
        txt = "📋 当前配置：\n"
        txt += f"群号：{', '.join(groups) if groups else '空'}\n"
        txt += f"早上：{self.config.get('morning_time')}\n"
        txt += f"晚上：{self.config.get('night_time')}\n"
        txt += "测试指令：/greeting_test_morning 或 /greeting_test_night"
        yield event.plain_result(txt)

    async def terminate(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("【每日问候】定时任务已关闭")