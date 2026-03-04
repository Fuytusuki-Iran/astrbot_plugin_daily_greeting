from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import random
import asyncio

# 核心：构造 aiocqhttp 原生的消息片段类（每个片段都有 toDict()）
class OneBotSegment:
    def __init__(self, type_, data):
        self.type = type_
        self.data = data

    def toDict(self):
        return {"type": self.type, "data": self.data}

# 封装纯文本消息链（多个 OneBotSegment 组成）
def build_text_chain(text):
    # 消息链是 OneBotSegment 对象的列表（框架原生格式）
    return [OneBotSegment("text", {"text": text})]

@register("daily_greeting", "你自己", "每日定时问候（早安+晚安 原生适配版）", "1.5.4-final",
          "https://github.com/你的用户名/astrbot_plugin_daily_greeting")
class DailyGreeting(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

        self.start_scheduler()
        logger.info("【每日问候 原生适配版】已加载")
        logger.info(f"   配置群号: {self.config.get('group_ids', [])}")
        logger.info(f"   Bot QQ: {self.config.get('bot_qq')} | 早上: {self.config.get('morning_time')} | 晚安: {self.config.get('night_time')}")

    def start_scheduler(self):
        try:
            mh, mm = map(int, self.config["morning_time"].split(":"))
            nh, nm = map(int, self.config["night_time"].split(":"))
            self.scheduler.add_job(self.send_morning, CronTrigger(hour=mh, minute=mm))
            self.scheduler.add_job(self.send_night, CronTrigger(hour=nh, minute=nm))
            self.scheduler.start()
            logger.info("【每日问候】定时任务已启动 ✅")
        except Exception as e:
            logger.error(f"启动定时任务失败: {e}")

    async def send_greeting(self, is_morning: bool):
        msgs = self.config["morning_msgs"] if is_morning else self.config["night_msgs"]
        if not msgs:
            logger.warning("问候语列表为空")
            return
        msg_text = random.choice(msgs)

        # 关键1：构造 aiocqhttp 原生消息链（OneBotSegment 列表）
        message_chain = build_text_chain(msg_text)

        bot_qq = self.config.get("bot_qq", "")
        group_ids = self.config.get("group_ids", [])
        if not bot_qq or not group_ids:
            logger.warning("bot_qq 或群号列表为空，跳过发送")
            return

        for gid in group_ids:
            # 关键2：最终定型的 session 格式（适配 v4.18.3 + Chrono_QQ）
            umo = f"Chrono_QQ:GroupMessage:{gid}"
            
            try:
                # 发送原生消息链（框架直接识别，不拆解）
                await self.context.send_message(umo, message_chain)
                logger.info(f"✅ 已向群 {gid} 发送 {'早安' if is_morning else '晚安'}：{msg_text[:30]}...")
                await asyncio.sleep(1.2)  # 防风控
            except Exception as e:
                logger.error(f"向群 {gid} 发送失败: {e}")
                import traceback
                logger.error(f"完整报错栈：\n{traceback.format_exc()}")

    async def send_morning(self):
        await self.send_greeting(True)

    async def send_night(self):
        await self.send_greeting(False)

    # ====================== 测试指令 ======================
    @filter.command("greeting_test_morning")
    async def test_morning(self, event: AstrMessageEvent):
        yield event.plain_result("🚀 测试早安发送中...")
        await self.send_greeting(True)
        yield event.plain_result("✅ 早安测试完成！")

    @filter.command("greeting_test_night")
    async def test_night(self, event: AstrMessageEvent):
        yield event.plain_result("🚀 测试晚安发送中...")
        await self.send_greeting(False)
        yield event.plain_result("✅ 晚安测试完成！")

    @filter.command("greeting_list")
    async def list_config(self, event: AstrMessageEvent):
        groups = self.config.get("group_ids", [])
        txt = f"📋 当前配置：\n群号：{', '.join(groups) if groups else '空'}\nBot QQ：{self.config.get('bot_qq')}\n早上：{self.config.get('morning_time')}\n晚安：{self.config.get('night_time')}"
        yield event.plain_result(txt)

    async def terminate(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("【每日问候】定时任务已关闭")
