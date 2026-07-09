# services/knowledge_service.py
"""
知识库服务 — 三模式向量检索：Milvus / Pinecone / FAISS

- Milvus: 本地 Milvus 向量数据库（优先选择）
- Pinecone: Pinecone 云端向量数据库
- FAISS: 本地 FAISS 索引（默认，无需额外服务）

所有公开接口保持不变，调用方无需感知后端切换。
"""

import re
import os
import math
import asyncio
import logging
from typing import List, Dict, Optional

import numpy as np

from db.db_router import DatabaseRouter
from .text_embedding import embed_input

logger = logging.getLogger(__name__)


# 症状同义/相关词扩展表
SYMPTOM_EXPANSION_MAP = {
    '嗓子疼': ['嗓子疼', '喉咙痛', '咽喉痛', '咽炎', '嗓子痛', '喉痛', '扁桃体', '咽喉', '喉咙'],
    '嗓子痛': ['嗓子疼', '喉咙痛', '咽喉痛', '咽炎', '嗓子痛', '喉痛', '扁桃体', '咽喉', '喉咙'],
    '头疼': ['头疼', '头痛', '偏头痛', '头痛头晕', '神经性头痛', '头胀'],
    '头痛': ['头疼', '头痛', '偏头痛', '头痛头晕', '神经性头痛', '头胀'],
    '肚子疼': ['肚子疼', '腹痛', '胃痛', '拉肚子', '腹泻', '肠胃炎', '腹部不适'],
    '腹痛': ['肚子疼', '腹痛', '胃痛', '拉肚子', '腹泻', '肠胃炎', '腹部不适'],
    '发烧': ['发烧', '发热', '高烧', '低烧', '体温高', '退烧', '发热症状'],
    '发热': ['发烧', '发热', '高烧', '低烧', '体温高', '退烧', '发热症状'],
    '咳嗽': ['咳嗽', '咳痰', '干咳', '咳嗽有痰', '久咳', '止咳', '气管'],
    '流鼻涕': ['流鼻涕', '鼻塞', '鼻炎', '打喷嚏', '感冒流涕', '鼻塞流涕'],
    '失眠': ['失眠', '睡不着', '睡眠差', '入睡困难', '多梦', '失眠多梦', '失眠治疗'],
    '恶心': ['恶心', '呕吐', '想吐', '反胃', '干呕', '胃不舒服'],
    # ——— 补充医学条目，提升 BM25 和向量扩展的命中 ———
    '前列腺炎': ['前列腺炎', '前列腺', '尿频', '尿急', '尿痛', '会阴', '骨盆', '前列腺液', '排尿'],
    '感冒': ['感冒', '流感', '风寒', '风热', '上呼吸道感染', '鼻塞', '流涕', '咽痛'],
    '过敏': ['过敏', '过敏性', '皮疹', '荨麻疹', '花粉', '打喷嚏', '瘙痒'],
    '拉肚子': ['拉肚子', '腹泻', '腹痛', '肠胃炎', '急性肠胃炎'],
    '牙疼': ['牙疼', '牙龈', '牙痛', '智齿', '龋齿'],
}


# 症状关键词列表（用于从文本中检测）
SYMPTOM_KEYWORDS = sorted(SYMPTOM_EXPANSION_MAP.keys(), key=len, reverse=True)


class KnowledgeService:
    """知识库服务类 — Milvus / Pinecone / FAISS 三模式"""

    def __init__(self, db_url: str = None):
        self.db_router = DatabaseRouter(db_url)
        self.db = self.db_router.knowledge

        # FAISS 模式专用
        self.index = None
        self.document_ids: List[int] = []

        # Pinecone 模式专用
        self.pinecone = None
        # Milvus 模式专用
        self.milvus = None

        # 使用的向量数据库类型: "milvus" | "pinecone" | "faiss"
        self.vector_db_type = "faiss"

        self.initialized = False

        # BM25 关键词索引（与向量索引平行，用于混合检索 RRF 融合）
        self.bm25_corpus: List[Dict] = []   # [{"id":..., "tokens":Counter, "text":str}]
        self.bm25_avgdl: float = 0.0        # 平均文档长度
        self.bm25_k1: float = 1.5           # BM25 参数 k1
        self.bm25_b: float = 0.75           # BM25 参数 b

        # 校园健康医学知识库（种子数据，仅首次初始化时写入）
        self.default_knowledge = [
            {
                "content": "校园医务室位于校园医务楼一楼，服务时间为周一至周五 8:00-18:00，周六日 9:00-17:00。紧急情况请拨打 120 或校园医务室值班电话。",
                "category": "服务信息",
                "keywords": ["医务室", "位置", "营业时间", "电话", "地址", "开门", "关门"]
            },
            {
                "content": "校内提供全科、内科、外科、皮肤科、眼科、耳鼻喉科、妇科、儿科、中医科和预防保健服务。所有医生均持有执业医师资格证，具有丰富的临床经验。",
                "category": "服务项目",
                "keywords": ["服务", "科室", "医生", "专科", "全科", "内科", "外科", "中医"]
            },
            {
                "content": "感冒预防建议：勤洗手、保持室内通风、保证充足睡眠、适当锻炼增强免疫力、避免与感冒患者密切接触。如出现发热、咳嗽等症状请及时就医。",
                "category": "疾病预防",
                "keywords": ["感冒", "预防", "流感", "发热", "咳嗽", "免疫力", "通风"]
            },
            {
                "content": "常见运动损伤处理：RICE 原则——Rest（休息）、Ice（冰敷）、Compression（加压包扎）、Elevation（抬高患处）。严重扭伤、骨折、脱臼请立即就医，不要自行复位。",
                "category": "急救知识",
                "keywords": ["运动损伤", "扭伤", "骨折", "脱臼", "冰敷", "RICE", "急救"]
            },
            {
                "content": "心肺复苏（CPR）步骤：1. 确认现场安全 2. 轻拍患者判断意识 3. 拨打 120 4. 胸外按压（深度 5-6cm，频率 100-120 次/分钟）5. 人工呼吸 6. 持续进行至急救人员到达。",
                "category": "急救知识",
                "keywords": ["心肺复苏", "CPR", "急救", "胸外按压", "人工呼吸", "120"]
            },
            {
                "content": "校园常见传染病预防：水痘、流感、诺如病毒等应做到早发现、早报告、早隔离。接种疫苗是预防传染病的有效手段。出现发热、皮疹、腹泻等症状应避免去人群密集场所。",
                "category": "疾病预防",
                "keywords": ["传染病", "水痘", "流感", "诺如病毒", "疫苗", "预防", "隔离"]
            },
            {
                "content": "心理健康是健康的重要组成部分。焦虑、抑郁、失眠等是常见心理问题。学校心理咨询中心提供免费心理咨询服务。保持规律作息、适度运动、积极社交有助于心理健康。",
                "category": "心理健康",
                "keywords": ["心理", "焦虑", "抑郁", "失眠", "咨询", "压力", "情绪"]
            },
            {
                "content": "健康饮食指南：均衡摄入五谷杂粮、蔬菜水果、优质蛋白。每天饮水 1500-2000ml。减少高盐、高糖、高油食物摄入。早餐要吃好，晚餐要适量，避免暴饮暴食。",
                "category": "健康生活",
                "keywords": ["饮食", "营养", "膳食", "健康", "蔬菜", "水果", "蛋白质"]
            },
            {
                "content": "睡眠卫生建议：保持规律作息，每天保证 7-8 小时睡眠。睡前 1 小时避免使用电子产品。卧室保持安静、黑暗、凉爽。下午 3 点后避免摄入咖啡因。",
                "category": "健康生活",
                "keywords": ["睡眠", "失眠", "作息", "熬夜", "休息", "咖啡因"]
            },
            {
                "content": "季节性健康：夏季注意防暑降温，多饮水，避免长时间暴晒。冬季注意保暖防寒，预防呼吸道感染。春季花粉季注意过敏防护，戴口罩可减少过敏原吸入。",
                "category": "健康生活",
                "keywords": ["季节", "防暑", "保暖", "过敏", "花粉", "夏天", "冬天", "中暑"]
            },
        ]

    # ======================= 初始化 =======================

    async def initialize(self):
        """初始化知识库服务（自动选择：Milvus > Pinecone > FAISS）"""
        try:
            vector_db_type = os.getenv("VECTOR_DB_TYPE", "").lower()
            milvus_uri = os.getenv("MILVUS_URI")

            logger.info(f"[知识库] 向量数据库配置: VECTOR_DB_TYPE='{vector_db_type or 'auto'}', MILVUS_URI={milvus_uri or '未配置'}")

            # 优先检查 Milvus
            if vector_db_type == "milvus" or (not vector_db_type and milvus_uri):
                try:
                    from .milvus_service import MilvusService
                    self.milvus = MilvusService()
                    await self.milvus.initialize(dim=1024)
                    if self.milvus.enabled:
                        self.vector_db_type = "milvus"
                        logger.info("[知识库] ✅ 已连接 Milvus 向量数据库")
                    else:
                        logger.warning("[知识库] ❌ Milvus 连接未启用，回退尝试 Pinecone/FAISS")
                except ImportError:
                    logger.warning("[知识库] ⚠️ pymilvus 未安装，跳过 Milvus。请运行: pip install pymilvus")
                except Exception as e:
                    logger.warning(f"[知识库] ❌ Milvus 初始化失败（请确认 Milvus 服务已在 {milvus_uri} 启动）: {e}")

            # 如果没有 Milvus，检查 Pinecone
            if self.vector_db_type == "faiss":
                pinecone_key = os.getenv("PINECONE_API_KEY")
                if vector_db_type == "pinecone" or (not vector_db_type and pinecone_key):
                    try:
                        from .pinecone_service import PineconeService
                        self.pinecone = PineconeService()
                        await self.pinecone.initialize()
                        if self.pinecone.enabled:
                            self.vector_db_type = "pinecone"
                            logger.info("[知识库] ✅ 已连接 Pinecone 向量数据库")
                    except ImportError:
                        logger.warning("[知识库] ⚠️ pinecone 包未安装（注意包名已从 pinecone-client 改为 pinecone），跳过 Pinecone")
                    except Exception as e:
                        logger.warning(f"[知识库] ❌ Pinecone 初始化失败: {e}")

            # 初始化对应的向量数据库
            if self.vector_db_type == "milvus":
                await self._init_milvus()
            elif self.vector_db_type == "pinecone":
                await self._init_pinecone()
            else:
                logger.info("[知识库] 🔧 使用本地 FAISS 向量索引（无需额外服务）")
                await self._init_faiss()

            self.initialized = True
            logger.info(f"[知识库] ✅ 初始化完成，后端: {self.vector_db_type}")

        except Exception as e:
            logger.error(f"[知识库] ❌ 初始化失败: {e}")
            raise

    async def _init_milvus(self):
        """Milvus 模式初始化：跳过种子数据写入（用户已手动导入）"""
        # 直接构建 BM25 索引（从 Milvus 读取）
        logger.info("[知识库] Milvus 模式：跳过种子数据写入（用户已手动导入）")
        await self._build_bm25_index()

    async def _init_pinecone(self):
        """Pinecone 模式初始化：检查索引是否为空，空则写入种子数据"""
        stats = await self.pinecone.describe_index()
        count = stats.get("total_vector_count", 0)
        if count == 0:
            logger.info("Pinecone 索引为空，写入种子数据...")
            await self._seed_to_pinecone()
        else:
            logger.info("Pinecone 索引已有 %d 条向量，跳过种子数据写入", count)
        await self._build_bm25_index()

    async def _init_faiss(self):
        """FAISS 模式初始化：检查 MySQL 是否为空，空则写入种子数据，然后构建索引"""
        existing_docs = self.db.get_all_documents()
        if not existing_docs:
            logger.info("MySQL knowledge_documents 为空，写入种子数据")
            await self._seed_to_mysql()
        else:
            logger.info("MySQL knowledge_documents 已有 %d 条记录", len(existing_docs))
        await self._build_vector_index()
        await self._build_bm25_index()

    # ======================= 种子数据 =======================

    async def _seed_to_milvus(self):
        """将种子数据写入 Milvus（不写 MySQL），同时更新 BM25 索引"""
        vectors = []
        for i, doc in enumerate(self.default_knowledge):
            text = f"{doc['content']} {' '.join(doc['keywords'])}"
            vec = embed_input(text)
            doc_id = f"seed_{i}"
            vectors.append({
                "id": doc_id,
                "values": vec,
                "metadata": {
                    "content": doc["content"],
                    "department": "",
                    "title": "",
                    "ask": "",
                    "answer": "",
                    "source": "",
                    "category": doc["category"],
                    "keywords": ",".join(doc["keywords"]),
                }
            })
            self._add_to_bm25(doc_id, doc["content"], "", "", doc["keywords"])
        await self.milvus.upsert(vectors)
        logger.info(f"已向 Milvus 写入 {len(vectors)} 条种子知识")

    async def _seed_to_pinecone(self):
        """将种子数据写入 Pinecone（不写 MySQL），同时更新 BM25 索引"""
        vectors = []
        for i, doc in enumerate(self.default_knowledge):
            text = f"{doc['content']} {' '.join(doc['keywords'])}"
            vec = embed_input(text)
            doc_id = f"seed_{i}"
            vectors.append({
                "id": doc_id,
                "values": vec,
                "metadata": {
                    "content": doc["content"],
                    "category": doc["category"],
                    "keywords": ",".join(doc["keywords"]),
                }
            })
            self._add_to_bm25(doc_id, doc["content"], "", "", doc["keywords"])
        await self.pinecone.upsert(vectors)
        logger.info("已向 Pinecone 写入 %d 条种子知识", len(vectors))

    async def _seed_to_mysql(self):
        """将种子数据写入 MySQL（仅 FAISS 模式），同时更新 BM25 索引"""
        for i, doc in enumerate(self.default_knowledge):
            text = f"{doc['content']} {' '.join(doc['keywords'])}"
            embedding = embed_input(text)
            doc_id = self.db.add_document(
                content=doc["content"],
                category=doc["category"],
                keywords=doc["keywords"],
                embedding=embedding,
            )
            self._add_to_bm25(doc_id, doc["content"], "", "", doc["keywords"])

    # ======================= BM25 关键词索引 =======================

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文分词：提取多字关键词（来自扩展表） + 单字兜底，去除空白和标点"""
        import re
        text = re.sub(r'\s+', '', text)
        tokens = []
        # 多字关键词优先匹配（来自 SYMPTOM_EXPANSION_MAP 的所有扩展词）
        all_phrases = set()
        for phrases in SYMPTOM_EXPANSION_MAP.values():
            all_phrases.update(phrases)
        all_phrases = sorted(all_phrases, key=len, reverse=True)
        remaining = text
        while remaining:
            matched = False
            for phrase in all_phrases:
                if remaining.startswith(phrase):
                    tokens.append(phrase)
                    remaining = remaining[len(phrase):]
                    matched = True
                    break
            if not matched:
                ch = remaining[0]
                if '一' <= ch <= '鿿':  # 仅保留中文字符
                    tokens.append(ch)
                remaining = remaining[1:]
        return tokens

    def _add_to_bm25(self, doc_id, content: str = "", ask: str = "", answer: str = "", keywords: List[str] = None):
        """添加/更新一条文档到 BM25 索引"""
        parts = [content, ask, answer]
        if keywords:
            if isinstance(keywords, str):
                parts.append(keywords)
            else:
                parts.append(' '.join(keywords))
        text = ' '.join(p for p in parts if p)
        tokens = self._tokenize(text)
        if not tokens:
            return

        # 已存在则覆盖，否则新增
        for entry in self.bm25_corpus:
            if str(entry["id"]) == str(doc_id):
                entry["tokens"] = tokens
                entry["text"] = text
                break
        else:
            self.bm25_corpus.append({"id": str(doc_id), "tokens": tokens, "text": text})

        # 更新平均文档长度
        if self.bm25_corpus:
            self.bm25_avgdl = sum(len(e["tokens"]) for e in self.bm25_corpus) / len(self.bm25_corpus)

    async def _build_bm25_index(self):
        """从当前知识库重建完整 BM25 索引（初始化/导入后调用）"""
        self.bm25_corpus = []
        # 1) 加载默认种子数据
        for i, doc in enumerate(self.default_knowledge):
            self._add_to_bm25(f"seed_{i}", doc["content"], "", "", doc["keywords"])
        # 2) Milvus 模式：从 Milvus 全量加载文档
        if self.vector_db_type == "milvus":
            try:
                milvus_docs = await self.milvus.query_all_documents()
                for doc in milvus_docs:
                    kws = doc.get("keywords", "")
                    if isinstance(kws, str):
                        kws = [k.strip() for k in kws.split(",") if k.strip()]
                    self._add_to_bm25(
                        doc["id"],
                        doc.get("content", ""),
                        doc.get("ask", ""),
                        doc.get("answer", ""),
                        kws,
                    )
                logger.info(f"[BM25] 从 Milvus 加载了 {len(milvus_docs)} 条文档")
            except Exception as e:
                logger.warning(f"[BM25] 加载 Milvus 文档失败: {e}")
        # 3) FAISS 模式：从 MySQL 加载
        else:
            try:
                for doc in self.db.get_all_documents():
                    kws = doc.get("keywords", [])
                    if isinstance(kws, str):
                        kws = [k.strip() for k in kws.split(",") if k.strip()]
                    self._add_to_bm25(
                        doc["id"],
                        doc.get("content", ""),
                        doc.get("ask", ""),
                        doc.get("answer", ""),
                        kws,
                    )
            except Exception as e:
                logger.warning(f"[BM25] 加载 MySQL 文档失败: {e}")
        logger.info(f"[BM25] 索引构建完成，共 {len(self.bm25_corpus)} 条")

    def _search_bm25(self, query: str, top_k: int = 20) -> List[Dict]:
        """BM25 关键词检索，返回按相关性排序的文档列表（带 rank）"""
        from collections import Counter

        if not self.bm25_corpus or self.bm25_avgdl == 0:
            return []

        # 查询分词（含扩展词）
        expanded = self._expand_query(query)
        query_tokens = set()
        for q in expanded:
            query_tokens.update(self._tokenize(q))
        if not query_tokens:
            return []

        N = len(self.bm25_corpus)
        k1, b, avgdl = self.bm25_k1, self.bm25_b, self.bm25_avgdl

        # 预计算 DF（包含每个查询 token 的文档数）
        df = Counter()
        for entry in self.bm25_corpus:
            for tok in set(entry["tokens"]):
                if tok in query_tokens:
                    df[tok] += 1

        # 对每条文档计算 BM25 分数
        scores = []
        for entry in self.bm25_corpus:
            tf = Counter(entry["tokens"])
            dl = len(entry["tokens"])
            score = 0.0
            for tok in query_tokens:
                if tok in tf:
                    # IDF 平滑（避免负值）
                    idf = max(0.0, math.log((N - df[tok] + 0.5) / (df[tok] + 0.5) + 1.0))
                    # TF 分量
                    tf_component = tf[tok] * (k1 + 1) / (tf[tok] + k1 * (1 - b + b * dl / avgdl))
                    score += idf * tf_component
            if score > 0:
                scores.append((entry["id"], score))

        scores.sort(key=lambda x: x[1], reverse=True)

        # 组装返回结果（带 rank，供 RRF 融合使用）
        results = []
        str_ids = {str(e["id"]): e for e in self.bm25_corpus}
        for rank, (doc_id, score) in enumerate(scores[:top_k]):
            entry = str_ids.get(str(doc_id))
            if entry:
                doc = {
                    "id": entry["id"],
                    "score": score,
                    "rank": rank + 1,
                    "bm25_text": entry["text"][:200],
                }
                results.append(doc)
        return results

    # ======================= 混合检索 =======================

    @staticmethod
    def _expand_query(query: str) -> List[str]:
        """对症状类查询进行同义扩展，提高召回率"""
        expanded = [query]
        for keyword, expansions in SYMPTOM_EXPANSION_MAP.items():
            if keyword in query:
                expanded.extend([e for e in expansions if e not in expanded])
        return expanded

    @staticmethod
    def _rrf_fuse(results_list: List[List[Dict]], k: int = 60) -> List[Dict]:
        """Reciprocal Rank Fusion — 融合多路检索结果"""
        score_map = {}  # id -> accumulated score
        doc_map = {}    # id -> document
        for results in results_list:
            for rank, doc in enumerate(results):
                doc_id = doc.get("id")
                if doc_id is None:
                    doc_id = doc.get("content", "")[:50]
                score_map[doc_id] = score_map.get(doc_id, 0) + 1.0 / (k + rank + 1)
                if doc_id not in doc_map:
                    doc_map[doc_id] = doc

        sorted_ids = sorted(score_map.keys(), key=lambda x: score_map[x], reverse=True)
        fused = []
        for doc_id in sorted_ids:
            doc = dict(doc_map[doc_id])
            doc["score"] = score_map[doc_id]
            fused.append(doc)
        return fused

    async def _keyword_search_milvus(self, query: str, top_k: int = 3) -> List[Dict]:
        """基于症状扩展的增强检索：用同义/相关词分别向量检索后去重融合"""
        expanded_queries = self._expand_query(query)
        all_results = []

        for eq in expanded_queries[:3]:  # 最多扩展3条查询
            query_vec = embed_input(eq)
            matches = await self._search_milvus(query_vec, top_k=top_k, category=None)
            content_texts = []
            for m in matches:
                content_text = m.get("answer", m.get("content", ""))
                content_texts.append(content_text)
                m["_query"] = eq

            # 对扩展查询，过滤掉完全不含关键词的结果
            if eq != query:
                filtered = []
                for m in matches:
                    ct = m.get("answer", m.get("content", ""))
                    if any(kw in ct for kw in expanded_queries):
                        filtered.append(m)
                    else:
                        # 分数打8折，保留但降权
                        m["score"] = m.get("score", 0) * 0.8
                        filtered.append(m)
                matches = filtered

            all_results.extend(matches)

        # 去重 (按content去重)
        seen_ct = set()
        deduped = []
        for m in sorted(all_results, key=lambda x: (
            0 if x.get("_query") == query else 1,  # 原词查询优先
            -x.get("score", 0)                       # 同分按分数降序
        )):
            ct = m.get("answer", m.get("content", ""))
            if ct and ct not in seen_ct:
                seen_ct.add(ct)
                deduped.append(m)

        return deduped[:top_k]

    # ======================= 搜索 =======================

    async def search(self, query: str, top_k: int = 3, category: str = None) -> List[Dict]:
        """混合检索：向量检索 + BM25 关键词检索，RRF 融合排名"""
        if not self.initialized:
            logger.warning("知识库服务未初始化")
            return []

        try:
            query_embedding = embed_input(query)

            if self.vector_db_type == "milvus":
                # ① 向量检索（广召候选，top_k*10 保证召回）
                vector_results = await self._search_milvus(query_embedding, top_k=max(top_k * 10, 50), category=category)

                # ② BM25 关键词检索（基于种子数据 / metadata 文本）
                bm25_results = self._search_bm25(query, top_k=top_k * 3)

                # ③ RRF 融合两路结果
                fused = self._rrf_fuse([vector_results, bm25_results], k=60)

                # ④ 从 Milvus metadata 补充完整文档字段
                vector_meta = {str(d["id"]): d for d in vector_results}
                results = []
                for doc in fused[:top_k]:
                    did = str(doc.get("id", ""))
                    full = vector_meta.get(did, {})
                    if full:
                        merged = dict(full)
                        merged["score"] = doc["score"]
                        results.append(merged)
                    else:
                        # BM25 命中但向量路未命中的兜底
                        results.append({
                            "id": did,
                            "score": doc["score"],
                            "content": doc.get("bm25_text", ""),
                            "category": "",
                            "keywords": "",
                        })

                logger.debug(f"[混合检索-Milvus] 向量{len(vector_results)}条 + BM25{len(bm25_results)}条 → RRF融合返回{len(results)}条")
                return results

            elif self.vector_db_type == "pinecone":
                return await self._search_pinecone(query_embedding, top_k, category)
            else:
                return self._search_faiss(query_embedding, top_k, category)

        except Exception as e:
            logger.error(f"搜索知识库失败: {e}")
            return []

    async def _search_milvus(self, query_vec, top_k, category):
        milvus_filter = {"category": category} if category else None
        matches = await self.milvus.query(query_vec, top_k=top_k, filter=milvus_filter)

        results = []
        for match in matches:
            doc = match.get("metadata", {})
            doc["id"] = match.get("id")
            doc["score"] = match.get("score", 0)
            doc["rank"] = len(results) + 1
            results.append(doc)
        return results

    async def _search_pinecone(self, query_vec, top_k, category):
        pinecone_filter = {"category": category} if category else None
        matches = await self.pinecone.query(query_vec, top_k=top_k, filter=pinecone_filter)

        results = []
        for match in matches:
            doc = match.get("metadata", {})
            doc["id"] = match.get("id")
            doc["score"] = match.get("score", 0)
            doc["rank"] = len(results) + 1
            results.append(doc)
        return results

    def _search_faiss(self, query_vec, top_k, category):
        if self.index is None:
            return []

        query_array = np.array([query_vec]).astype("float32")
        search_k = min(top_k * 2, len(self.document_ids))
        scores, indices = self.index.search(query_array, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.document_ids):
                doc_id = self.document_ids[idx]
                doc = self.db.get_document(doc_id)
                if doc:
                    if category and doc.get("category") != category:
                        continue
                    doc["score"] = float(score)
                    doc["rank"] = len(results) + 1
                    results.append(doc)
                    if len(results) >= top_k:
                        break
        return results

    # ======================= 增删改 =======================

    async def add_document(self, content: str, category: str, keywords: List[str] = None) -> bool:
        """添加新文档"""
        try:
            keywords = keywords or []
            vec = embed_input(f"{content} {' '.join(keywords)}")

            if self.vector_db_type == "milvus":
                import uuid
                doc_id = f"doc_{uuid.uuid4().hex[:12]}"
                await self.milvus.upsert([{
                    "id": doc_id,
                    "values": vec,
                    "metadata": {
                        "content": content,
                        "department": "",
                        "title": "",
                        "ask": "",
                        "answer": "",
                        "source": "",
                        "category": category,
                        "keywords": ",".join(keywords),
                    },
                }])
                self._add_to_bm25(doc_id, content, "", "", keywords)
                logger.info(f"Milvus 添加文档 {doc_id}")
            elif self.vector_db_type == "pinecone":
                import uuid
                doc_id = f"doc_{uuid.uuid4().hex[:12]}"
                await self.pinecone.upsert([{
                    "id": doc_id,
                    "values": vec,
                    "metadata": {"content": content, "category": category, "keywords": ",".join(keywords)},
                }])
                self._add_to_bm25(doc_id, content, "", "", keywords)
                logger.info(f"Pinecone 添加文档 {doc_id}")
            else:
                doc_id = self.db.add_document(content=content, category=category, keywords=keywords, embedding=vec)
                await self._build_vector_index()
                self._add_to_bm25(doc_id, content, "", "", keywords)
                logger.info("MySQL+FAISS 添加文档")

            return True
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return False

    async def update_document(self, doc_id: int, content: str = None, category: str = None,
                              keywords: List[str] = None) -> bool:
        """更新文档"""
        try:
            if self.vector_db_type in ["milvus", "pinecone"]:
                # Milvus/Pinecone 模式：直接用 upsert 更新同一 ID
                current = None
                content = content or (current.get("content") if current else "")
                category = category or (current.get("category") if current else "")
                keywords = keywords or []
            else:
                current = self.db.get_document(doc_id)
                if not current:
                    return False
                content = content or current["content"]
                keywords = keywords or current.get("keywords", [])

            vec = embed_input(f"{content} {' '.join(keywords)}")

            if self.vector_db_type == "milvus":
                await self.milvus.upsert([{
                    "id": str(doc_id),
                    "values": vec,
                    "metadata": {
                        "content": content,
                        "department": "",
                        "title": "",
                        "ask": "",
                        "answer": "",
                        "source": "",
                        "category": category,
                        "keywords": ",".join(keywords),
                    },
                }])
                self._add_to_bm25(doc_id, content, "", "", keywords)
            elif self.vector_db_type == "pinecone":
                await self.pinecone.upsert([{
                    "id": str(doc_id),
                    "values": vec,
                    "metadata": {"content": content, "category": category, "keywords": ",".join(keywords)},
                }])
                self._add_to_bm25(doc_id, content, "", "", keywords)
            else:
                self.db.update_document(doc_id, content=content, category=category, keywords=keywords, embedding=vec)
                await self._build_vector_index()
                self._add_to_bm25(doc_id, content, "", "", keywords)

            return True
        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            return False

    async def delete_document(self, doc_id: int, soft_delete: bool = True) -> bool:
        """删除文档"""
        try:
            if self.vector_db_type == "milvus":
                await self.milvus.delete([str(doc_id)])
            elif self.vector_db_type == "pinecone":
                await self.pinecone.delete([str(doc_id)])
            else:
                self.db.delete_document(doc_id, soft_delete)
                await self._build_vector_index()
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    # ======================= FAISS 专用 =======================

    async def _build_vector_index(self):
        """构建本地 FAISS 向量索引（从 MySQL 读取）"""
        try:
            documents = self.db.get_all_documents()
            if not documents:
                self.index = None
                self.document_ids = []
                return

            embeddings = []
            self.document_ids = []
            for doc in documents:
                if doc.get("embedding"):
                    embeddings.append(doc["embedding"])
                    self.document_ids.append(doc["id"])

            if embeddings:
                import faiss
                embeddings_array = np.array(embeddings).astype("float32")
                self.index = faiss.IndexFlatIP(embeddings_array.shape[1])
                self.index.add(embeddings_array)
                logger.info(f"FAISS 索引: {len(embeddings)} 个向量")

        except Exception as e:
            logger.error(f"构建 FAISS 索引失败: {e}")

    # ======================= 管理接口 =======================

    def get_all_documents(self, include_inactive: bool = False) -> List[Dict]:
        if self.vector_db_type in ["milvus", "pinecone"]:
            return []  # 向量数据库模式下不提供 MySQL 列表
        return self.db.get_all_documents(include_inactive)

    def get_document(self, doc_id: int) -> Dict:
        if self.vector_db_type in ["milvus", "pinecone"]:
            return {}
        return self.db.get_document(doc_id)

    def get_all_categories(self) -> List[str]:
        if self.vector_db_type in ["milvus", "pinecone"]:
            return list({d["category"] for d in self.default_knowledge})
        return self.db.get_all_categories()

    def get_documents_count(self) -> int:
        if self.vector_db_type == "milvus":
            return self.milvus.get_entity_count()
        elif self.vector_db_type == "pinecone":
            return len(self.default_knowledge)  # 近似值
        return self.db.get_documents_count()

    def search_by_category(self, category: str) -> List[Dict]:
        if self.vector_db_type in ["milvus", "pinecone"]:
            return []
        return self.db.search_documents_by_category(category)

    def search_by_keywords(self, keywords: List[str]) -> List[Dict]:
        if self.vector_db_type in ["milvus", "pinecone"]:
            return []
        return self.db.search_documents_by_keywords(keywords)
