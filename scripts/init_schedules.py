#!/usr/bin/env python
"""
初始化医生值班数据到 MySQL

排班规则：
- 每个科室有 2 位医生（眼科/耳鼻喉科各 1 位）
- 上午 8:00-12:00：科室第 1 位医生值班
- 下午 14:00-18:00：科室第 2 位医生值班
- 只有 1 位医生的科室（眼科、耳鼻喉科）：全天值班
- status 设为 'free'（空闲可预约）
"""

import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 排班日期（默认今天）
SHIFT_DATE = date.today()

# 值班安排：每个元素是 (医生ID, 班次, 开始时间, 结束时间)
# 上午 8:00-12:00，下午 14:00-18:00
AM_START, AM_END = "08:00", "12:00"
PM_START, PM_END = "14:00", "18:00"

SHIFTS = [
    # ====== 内科：李明(上午)，王芳(下午) ======
    (1,  "morning",   AM_START, AM_END),   # 李明医生
    (2,  "afternoon", PM_START, PM_END),   # 王芳医生

    # ====== 外科：张刚(上午)，陈媛(下午) ======
    (3,  "morning",   AM_START, AM_END),   # 张刚医生
    (4,  "afternoon", PM_START, PM_END),   # 陈媛医生

    # ====== 皮肤科：刘强(上午)，杨萍(下午) ======
    (5,  "morning",   AM_START, AM_END),   # 刘强医生
    (6,  "afternoon", PM_START, PM_END),   # 杨萍医生

    # ====== 眼科：赵建(全天，仅1位医生) ======
    (7,  "morning",   AM_START, AM_END),   # 赵建医生 上午
    (7,  "afternoon", PM_START, PM_END),   # 赵建医生 下午

    # ====== 耳鼻喉科：林晓(全天，仅1位医生) ======
    (8,  "morning",   AM_START, AM_END),   # 林晓医生 上午
    (8,  "afternoon", PM_START, PM_END),   # 林晓医生 下午

    # ====== 妇科：钱军(上午)，周倩(下午) ======
    (9,  "morning",   AM_START, AM_END),   # 钱军医生
    (10, "afternoon", PM_START, PM_END),   # 周倩医生

    # ====== 儿科：吴涛(上午)，徐静(下午) ======
    (11, "morning",   AM_START, AM_END),   # 吴涛医生
    (12, "afternoon", PM_START, PM_END),   # 徐静医生

    # ====== 中医科：何明(上午)，宋红(下午) ======
    (13, "morning",   AM_START, AM_END),   # 何明医生
    (14, "afternoon", PM_START, PM_END),   # 宋红医生

    # ====== 全科：高力(上午)，马杰(下午) ======
    (15, "morning",   AM_START, AM_END),   # 高力医生
    (16, "afternoon", PM_START, PM_END),   # 马杰医生
]


def init_schedules():
    from db.db_router import DatabaseRouter

    router = DatabaseRouter()

    # 检查是否已存在今天的排班
    existing = router.technicians.get_doctor_schedules(1, SHIFT_DATE)
    if existing:
        logger.info("今日排班已存在 (%d 条)，跳过初始化。", len(existing))
        return

    count = 0
    for doctor_id, shift_type, start_str, end_str in SHIFTS:
        start_time = datetime.combine(SHIFT_DATE, datetime.strptime(start_str, "%H:%M").time())
        end_time = datetime.combine(SHIFT_DATE, datetime.strptime(end_str, "%H:%M").time())

        try:
            schedule_id = router.technicians.add_schedule(
                doctor_id=doctor_id,
                start_time=start_time,
                end_time=end_time,
                status="free",
                shift_type=shift_type,
            )
            # 顺便查出医生名字用于日志
            doc = router.technicians.get_doctor_by_id(doctor_id)
            name = doc["name"] if doc else f"ID={doctor_id}"
            logger.info("[%d] %s - %s (%s - %s)", doctor_id, name, shift_type, start_str, end_str)
            count += 1
        except Exception as e:
            logger.error("写入排班失败 doctor_id=%d: %s", doctor_id, e)

    logger.info("完成！共写入 %d 条排班记录", count)


if __name__ == "__main__":
    init_schedules()
