#!/usr/bin/env python
"""
初始化医生数据到 MySQL

将 16 位校园医务室医生信息写入数据库。
如果数据库中已有医生数据，则跳过初始化。
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DOCTORS = [
    # ========== 内科 ==========
    {"name": "李明医生", "gender": "男", "specialty": "内科", "education": "硕士",
     "license_number": "ML20240001", "years_of_experience": 8, "consultation_rating": 4.8},
    {"name": "王芳医生", "gender": "女", "specialty": "内科", "education": "硕士",
     "license_number": "ML20240002", "years_of_experience": 6, "consultation_rating": 4.9},
    # ========== 外科 ==========
    {"name": "张刚医生", "gender": "男", "specialty": "外科", "education": "博士",
     "license_number": "ML20240003", "years_of_experience": 10, "consultation_rating": 4.7},
    {"name": "陈媛医生", "gender": "女", "specialty": "外科", "education": "硕士",
     "license_number": "ML20240004", "years_of_experience": 7, "consultation_rating": 4.6},
    # ========== 皮肤科 ==========
    {"name": "刘强医生", "gender": "男", "specialty": "皮肤科", "education": "硕士",
     "license_number": "ML20240005", "years_of_experience": 5, "consultation_rating": 4.8},
    {"name": "杨萍医生", "gender": "女", "specialty": "皮肤科", "education": "硕士",
     "license_number": "ML20240006", "years_of_experience": 4, "consultation_rating": 4.9},
    # ========== 眼科 / 耳鼻喉科 ==========
    {"name": "赵建医生", "gender": "男", "specialty": "眼科", "education": "硕士",
     "license_number": "ML20240007", "years_of_experience": 9, "consultation_rating": 4.9},
    {"name": "林晓医生", "gender": "女", "specialty": "耳鼻喉科", "education": "硕士",
     "license_number": "ML20240008", "years_of_experience": 6, "consultation_rating": 4.7},
    # ========== 妇科 ==========
    {"name": "钱军医生", "gender": "男", "specialty": "妇科", "education": "硕士",
     "license_number": "ML20240009", "years_of_experience": 8, "consultation_rating": 4.7},
    {"name": "周倩医生", "gender": "女", "specialty": "妇科", "education": "硕士",
     "license_number": "ML20240010", "years_of_experience": 7, "consultation_rating": 4.8},
    # ========== 儿科 ==========
    {"name": "吴涛医生", "gender": "男", "specialty": "儿科", "education": "硕士",
     "license_number": "ML20240011", "years_of_experience": 6, "consultation_rating": 4.6},
    {"name": "徐静医生", "gender": "女", "specialty": "儿科", "education": "学士",
     "license_number": "ML20240012", "years_of_experience": 4, "consultation_rating": 4.9},
    # ========== 中医科 ==========
    {"name": "何明医生", "gender": "男", "specialty": "中医科", "education": "硕士",
     "license_number": "ML20240013", "years_of_experience": 9, "consultation_rating": 4.8},
    {"name": "宋红医生", "gender": "女", "specialty": "中医科", "education": "硕士",
     "license_number": "ML20240014", "years_of_experience": 5, "consultation_rating": 4.7},
    # ========== 全科 ==========
    {"name": "高力医生", "gender": "男", "specialty": "全科", "education": "学士",
     "license_number": "ML20240015", "years_of_experience": 3, "consultation_rating": 4.5},
    {"name": "马杰医生", "gender": "女", "specialty": "全科", "education": "学士",
     "license_number": "ML20240016", "years_of_experience": 3, "consultation_rating": 4.5},
]


def init_doctors():
    """将 16 位医生写入 MySQL，已有数据则跳过"""
    from db.db_router import DatabaseRouter

    router = DatabaseRouter()

    # 检查是否已有数据
    existing = router.technicians.get_all_technicians()
    if existing and len(existing) >= 16:
        logger.info("数据库中已有 %d 位医生，跳过初始化。", len(existing))
        return

    count = 0
    for doc in DOCTORS:
        try:
            doctor_id = router.technicians.add_doctor(
                name=doc["name"],
                specialty=doc["specialty"],
                license_number=doc["license_number"],
                gender=doc["gender"],
                education=doc["education"],
                years_of_experience=doc["years_of_experience"],
            )
            if doctor_id:
                # 更新评分
                router.technicians.update_doctor_rating(doctor_id, doc["consultation_rating"])
                count += 1
                logger.info("  [%d/16] %s (%s)", count, doc["name"], doc["specialty"])
        except Exception as e:
            logger.warning("  写入失败 %s: %s", doc["name"], e)

    logger.info("完成！共写入 %d 位医生", count)


if __name__ == "__main__":
    init_doctors()
