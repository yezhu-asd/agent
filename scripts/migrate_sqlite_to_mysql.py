#!/usr/bin/env python
"""
SQLite → MySQL 数据迁移脚本

使用方法：
    1. 在 .env 中配置 DATABASE_URL 指向 MySQL
    2. 运行: python scripts/migrate_sqlite_to_mysql.py

迁移的表：
    - doctors
    - doctor_schedules
    - knowledge_documents
    - consultation_records
    - medical_preferences
    - health_recommendations
    - risk_events
"""

import os
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def migrate():
    """执行迁移"""
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker
    from db.models import Base, Doctor, DoctorSchedule, KnowledgeDocument
    from db.models import ConsultationRecord, MedicalPreference, HealthRecommendation, RiskEvent

    # 源：SQLite
    sqlite_url = os.getenv("SQLITE_SOURCE_URL", "sqlite:///./data/smart_appointment.db")
    # 目标：MySQL（从 DATABASE_URL 读取）
    mysql_url = os.getenv("DATABASE_URL")
    if not mysql_url or not mysql_url.startswith("mysql"):
        logger.error("DATABASE_URL 未配置或不是 MySQL 连接字符串。请在 .env 中设置 MySQL DATABASE_URL。")
        logger.error("示例: DATABASE_URL=mysql+pymysql://root:password@localhost:3306/campus_medical")
        return False

    # 检查 SQLite 源是否存在
    sqlite_path = sqlite_url.replace("sqlite:///", "")
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite 数据库文件不存在: {sqlite_path}")
        return False

    logger.info("源数据库: %s", sqlite_url)
    logger.info("目标数据库: %s", mysql_url)

    # 创建引擎
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    mysql_engine = create_engine(mysql_url, pool_pre_ping=True)

    # 在 MySQL 中创建所有表
    Base.metadata.create_all(mysql_engine)

    SQLiteSession = sessionmaker(bind=sqlite_engine)
    MySQLSession = sessionmaker(bind=mysql_engine)

    tables = [
        ("doctors", Doctor),
        ("doctor_schedules", DoctorSchedule),
        ("knowledge_documents", KnowledgeDocument),
        ("consultation_records", ConsultationRecord),
        ("medical_preferences", MedicalPreference),
        ("health_recommendations", HealthRecommendation),
        ("risk_events", RiskEvent),
    ]

    total_migrated = 0

    for table_name, model in tables:
        try:
            with SQLiteSession() as src_session:
                rows = src_session.query(model).all()
                if not rows:
                    logger.info("  %s: 0 条记录（跳过）", table_name)
                    continue

                with MySQLSession() as dst_session:
                    for row in rows:
                        # 创建新对象（避免 SQLite session 绑定问题）
                        data = {}
                        for col in row.__table__.columns:
                            data[col.name] = getattr(row, col.name)
                        new_row = model(**data)
                        dst_session.add(new_row)

                    dst_session.commit()

                logger.info("  ✅ %s: %d 条记录已迁移", table_name, len(rows))
                total_migrated += len(rows)

        except Exception as e:
            logger.error("  ❌ %s 迁移失败: %s", table_name, e)

    logger.info("\n迁移完成！共迁移 %d 条记录", total_migrated)
    return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
