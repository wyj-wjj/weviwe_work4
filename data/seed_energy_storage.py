# -*- coding: utf-8 -*-
"""Seed realistic energy storage industry data for testing.

Populates MySQL with energy-storage-related content, publishes it, and syncs
vectors to Milvus. Uses real DashScope + Milvus clients.

Prerequisites:
- .env 中 USE_FAKE_EXTERNAL_CLIENTS=false
- MySQL 和 Milvus 正常运行
- DASHSCOPE_API_KEY 已配置

Usage:
    cd E:/WeView/work4
    .venv/Scripts/python.exe data/seed_energy_storage.py
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

# Ensure backend package is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "backend"))

from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.db.session import session_scope
from app.domain.enums import AccountType, ContentLevel, ContentStatus, ContentType, IndexStatus, QuestionStatus
from app.integrations.dashscope import create_dashscope_client
from app.integrations.milvus import create_milvus_client
from app.models.content import Content
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.content import ContentCreate
from app.services.content_service import create_content, publish_content
from app.services.rag_index_service import sync_content_index

# Default password for seed accounts, overridable via WEVIEW_SEED_PASSWORD env var
DEFAULT_PASSWORD = os.environ.get("WEVIEW_SEED_PASSWORD", "es-seed-2024")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def upsert_users(db, password: str) -> dict[str, User]:
    specs = [
        ("es_admin", "储能管理员", AccountType.ADMIN, ContentLevel.FULL),
        ("es_general", "通用员工（储能）", AccountType.GENERAL_USER, ContentLevel.GENERAL),
        ("es_full", "全量员工（储能）", AccountType.FULL_USER, ContentLevel.FULL),
    ]
    result: dict[str, User] = {}
    for username, display_name, account_type, content_level in specs:
        user = db.scalar(select(User).where(User.username == username))
        pw_hash = hash_password(password)
        if user is None:
            user = User(
                username=username,
                password_hash=pw_hash,
                display_name=display_name,
                account_type=account_type.value,
                content_level=content_level.value,
                is_active=True,
            )
            db.add(user)
        else:
            user.password_hash = pw_hash
            user.display_name = display_name
            user.account_type = account_type.value
            user.content_level = content_level.value
            user.is_active = True
        db.flush()
        key = "admin" if account_type == AccountType.ADMIN else (
            "full" if account_type == AccountType.FULL_USER else "general"
        )
        result[key] = user
    return result


# ---------------------------------------------------------------------------
# Content data
# ---------------------------------------------------------------------------

def _txt(*parts: str) -> str:
    """Join parts into a single string."""
    return "".join(parts)


def energy_storage_contents() -> Iterable[ContentCreate]:
    # ---- 最新必读 ----

    MUST_READ_1_BODY = _txt(
        "根据国家能源局2025年最新通知，新型储能项目在设计、施工、并网、",
        "运行四个阶段均须落实全生命周期安全管控。重点变化包括：\n",
        "1. 锂离子电池储能电站须配备三级消防系统（预警-灭火-防复燃）；\n",
        "2. 液流电池储能项目须增设电解液泄漏监测与应急处理方案；\n",
        "3. 压缩空气储能项目须委托有资质的第三方进行年度压力容器检测；\n",
        "4. 所有储能电站须接入省级储能安全监测平台，实现实时数据上传。",
    )
    yield ContentCreate(
        content_type=ContentType.MUST_READ,
        title="2025年新型储能项目安全监管最新要求",
        category="政策法规",
        permission_level=ContentLevel.GENERAL,
        summary="国家能源局发布的新型储能项目安全监管框架更新",
        body="各地新型储能项目须严格执行2025年版安全监管细则。",
        structured_payload={
            "update_body": MUST_READ_1_BODY,
            "adjustment_points": [
                "锂离子电站新增三级消防系统要求",
                "液流电池项目电解液监测为新增项",
                "压缩空气储能年检由推荐改为强制",
                "安全监测平台接入由省内扩展至全国统一",
            ],
        },
    )

    MUST_READ_2_BODY = _txt(
        "2025版储能电站并网验收技术标准主要更新如下：\n",
        "1. 电化学储能系统充放电效率不低于88%（110kV以下）或90%（110kV及以上）；\n",
        "2. 储能变流器（PCS）须通过低电压穿越和高电压穿越测试；\n",
        "3. BMS系统须支持SOC误差不大于3%，且具备热失控预警功能；\n",
        "4. 新增电能质量治理装置的谐波抑制指标要求（THD≤3%）。",
    )
    yield ContentCreate(
        content_type=ContentType.MUST_READ,
        title="储能电站验收并网技术标准更新通知",
        category="技术标准",
        permission_level=ContentLevel.GENERAL,
        summary="最新储能电站并网验收技术标准及关键参数要求",
        body="即日起储能电站并网验收按照2025版技术标准执行。",
        structured_payload={
            "update_body": MUST_READ_2_BODY,
            "adjustment_points": [
                "充放电效率要求提高至88%/90%",
                "高低电压穿越测试纳入强制项目",
                "BMS热失控预警功能为新增项",
                "新增电能质量治理谐波指标",
            ],
        },
    )

    MUST_READ_3_BODY = _txt(
        "内部技术路线对比分析（2025年5月更新）：\n",
        "一、磷酸铁锂电池（LFP）\n",
        "- 循环寿命 6000-8000 次（0.5C/25°C）\n",
        "- 系统成本约 0.8-1.0 元/Wh（含PCS）\n",
        "- 适用场景：工商业削峰填谷、新能源配储\n",
        "- 优势：技术成熟、产业链完善\n",
        "- 劣势：低温性能较差、能量密度天花板\n\n",
        "二、钠离子电池\n",
        "- 循环寿命 3000-5000 次\n",
        "- 系统成本预计 0.5-0.7 元/Wh（2026年规模化后）\n",
        "- 适用场景：两轮车换电、家用储能、基站备电\n",
        "- 优势：原材料丰富、低温性能好、安全性高\n",
        "- 劣势：能量密度偏低、循环寿命待验证\n\n",
        "三、全钒液流电池\n",
        "- 循环寿命 20000+ 次\n",
        "- 系统成本约 2.5-3.5 元/Wh\n",
        "- 适用场景：4小时以上长时储能、电网侧调峰\n",
        "- 优势：超长寿命、容量功率解耦、本质安全\n",
        "- 劣势：能量密度低、初投成本高",
    )
    yield ContentCreate(
        content_type=ContentType.MUST_READ,
        title="储能电池技术路线对比分析口径（全量版）",
        category="内部研究",
        permission_level=ContentLevel.FULL,
        summary="磷酸铁锂、钠离子、液流电池三条技术路线的内部对比与分析口径",
        body="本报告仅供全量权限员工内部参考，不得对外披露。",
        structured_payload={
            "update_body": MUST_READ_3_BODY,
            "adjustment_points": [
                "LFP仍是4h以下场景首选",
                "钠离子电池度电成本有望在2026年反超LFP",
                "液流电池在长时储能场景竞争力提升",
                "三种技术并非完全替代，需按场景推荐",
            ],
        },
    )

    # ---- 核心基础话术 ----

    yield ContentCreate(
        content_type=ContentType.BASE_SCRIPT,
        title="储能项目客户拜访开场话术",
        category="客户拜访",
        permission_level=ContentLevel.GENERAL,
        summary="首次拜访储能项目客户时的标准化开场流程与核心要点",
        body=_txt(
            "您好，我是[公司名称]储能解决方案顾问[姓名]。",
            "首先想了解一下贵司目前的用电情况和储能需求场景，",
            "是侧重于峰谷套利、需量管理还是新能源配储？",
        ),
        structured_payload={
            "points": [
                "先确认客户身份和用电类型（工业/商业/园区）",
                "了解月用电量和变压器容量",
                "明确客户核心诉求（省钱/保供/绿电消纳）",
                "介绍公司储能业务范围和典型案例",
                "约定下次深度交流的时间节点",
            ],
        },
    )

    yield ContentCreate(
        content_type=ContentType.BASE_SCRIPT,
        title="储能系统质保与售后标准话术",
        category="售后服务",
        permission_level=ContentLevel.GENERAL,
        summary="向客户说明储能系统质保条款和售后服务体系的统一口径",
        body=_txt(
            "我司储能系统提供标准5年整机质保，电池模组单独提供10年衰减保障。",
            "质保期内设备故障免费更换，售后响应时间市区4小时、郊区8小时。",
        ),
        structured_payload={
            "points": [
                "整机5年质保覆盖PCS、BMS、EMS等核心部件",
                "电芯/模组10年衰减保障——承诺首年≤3%、年均≤2%",
                "7×24小时远程监控+月度巡检报告",
                "明确免责条款：不可抗力、人为损坏、第三方改装",
                "质保期后提供延保方案和年度维护合同",
            ],
        },
    )

    yield ContentCreate(
        content_type=ContentType.BASE_SCRIPT,
        title="储能项目投资回报周期说明话术",
        category="商务沟通",
        permission_level=ContentLevel.GENERAL,
        summary="向客户解释储能系统投资回报周期的标准计算方法和说明话术",
        body=_txt(
            "储能系统投资回报周期需结合当地电价峰谷差、充放电策略和补贴政策综合计算。",
            "一般工商业场景下，投资回收期在3-5年左右。",
        ),
        structured_payload={
            "points": [
                "IRR计算需考虑：峰谷价差、需量管理收益、需求响应补贴",
                "浙江省工商业储能IRR可达12-15%（两充两放模式）",
                "广东省需量管理收益占比可达总收益的30-40%",
                "光伏配储场景须单独计算弃光消纳收益",
                "投资回收期不可承诺上限，须说明电价政策变化风险",
            ],
        },
    )

    # ---- 标准化话术条目 ----

    SCRIPT_1_RECOMMENDED = _txt(
        "根据您提供的用电数据和需求场景，我们建议采用[XXMW/XMWh]的储能配置方案。",
        "该方案采用[磷酸铁锂/液流]电池技术路线，主要收益来源包括峰谷套利和需量管理。",
        "按目前电价测算，预计年化收益约XX万元，静态回收期约X年。",
        "需要说明的是，以上测算基于当前电价政策，未来如有调整会影响实际收益。",
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="工商业储能方案推荐标准话术",
        category="方案推荐",
        permission_level=ContentLevel.GENERAL,
        summary="根据客户用电特征推荐储能方案的标准化对话",
        body="工商业储能方案推荐标准话术",
        structured_payload={
            "scene": "客户咨询储能方案选择时",
            "recommended_speech": SCRIPT_1_RECOMMENDED,
            "forbidden_speech": (
                '不能承诺具体的投资回报率或回收周期，不能说"保证X年内回本"'
            ),
            "notes": _txt(
                "测算数据须注明依据的电价政策和假设条件；",
                "客户要求提供书面测算报告时，须经技术部门复核后出具。",
            ),
        },
    )

    SCRIPT_2_RECOMMENDED = _txt(
        "储能系统安全是我们最重视的环节。我司储能产品采用多重安全防护体系：",
        "第一，选用通过UL9540A热失控测试的电芯；",
        "第二，BMS系统实时监测每颗电芯的电压、温度和SOC，异常时毫秒级切断；",
        "第三，配备气溶胶+七氟丙烷双模消防系统；",
        "第四，集装箱式储能配备防爆泄压装置和24小时烟感温感联动。",
        "截至目前，我司已投运的X个项目中未发生一起安全事故。",
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="储能安全风险告知标准话术",
        category="安全合规",
        permission_level=ContentLevel.GENERAL,
        summary="向客户说明储能系统安全风险及防护措施的标准话术",
        body="储能安全风险告知标准话术",
        structured_payload={
            "scene": "客户询问储能系统安全性时",
            "recommended_speech": SCRIPT_2_RECOMMENDED,
            "forbidden_speech": _txt(
                '不能说"绝对安全""不可能出事"等绝对化表述；',
                "不能淡化锂离子电池的热失控风险；",
                "不能向客户隐藏或隐瞒项目曾发生的安全事件。",
            ),
            "notes": _txt(
                "如客户要求查看安全事件报告，须走内部审批流程；",
                "安全话术中涉及的数据须与最新安全报告保持一致。",
            ),
        },
    )

    SCRIPT_3_RECOMMENDED = _txt(
        "我司在100MW级以上储能电站领域拥有成熟的EPC总包和核心设备供应能力。",
        "技术方案亮点包括：1）自研PCS支持构网型（Grid-Forming）控制模式，",
        "可为弱电网提供惯量支撑；2）20尺集装箱能量密度达5.5MWh，",
        "较行业平均水平提升15%；3）EMS系统支持现货市场、调频辅助、",
        "容量市场等多市场联合优化调度。",
        "我司已中标并交付X个100MW+储能电站项目，最新项目全容量并网时间",
        "较合同工期提前20天。",
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="大型储能电站投标技术应答（全量版）",
        category="投标应答",
        permission_level=ContentLevel.FULL,
        summary="100MW级以上大型储能电站投标的技术应答标准话术",
        body="大型储能电站投标技术应答标准话术（全量权限）",
        structured_payload={
            "scene": "参与100MW级以上储能电站投标技术应答时",
            "recommended_speech": SCRIPT_3_RECOMMENDED,
            "forbidden_speech": _txt(
                "不得向竞争对手泄露我方技术方案细节和成本构成；",
                "不得在未授权情况下披露在建项目的业主信息和工期节点。",
            ),
            "notes": _txt(
                "投标技术应答须由技术负责人审核后发出；",
                "涉及价格信息的部分须单独密封提交。",
            ),
        },
    )

    SCRIPT_4_RECOMMENDED = _txt(
        "感谢您提出这个问题，这说明您对项目非常认真。",
        "关于[XX问题]，我们的处理方式是：[具体说明]。",
        "您看这样是否解答了您的疑问？如果还有顾虑，我可以安排我们的技术专家",
        "和您做一次专项交流。",
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="客户异议处理标准话术",
        category="异议处理",
        permission_level=ContentLevel.GENERAL,
        summary="处理客户常见异议（价格、安全、技术等）的标准化应答",
        body="客户异议处理标准话术",
        structured_payload={
            "scene": "客户对储能方案提出质疑或异议时",
            "recommended_speech": SCRIPT_4_RECOMMENDED,
            "forbidden_speech": _txt(
                "不能和客户争论或否定客户的看法；",
                '不能说"你不懂"或"你说的不对"；',
                "不能在没有技术依据的情况下强行说服客户。",
            ),
            "notes": _txt(
                "L-A-C-T 框架：Listen（倾听）- Acknowledge（认可）",
                "- Clarify（澄清）- Transition（转接）；",
                "重大异议须记录在CRM中并同步区域经理。",
            ),
        },
    )

    SCRIPT_5_RECOMMENDED = _txt(
        "储能项目从合同签订到正式投运一般需要3-6个月，主要分为四个阶段：",
        "第一阶段（1个月）：场地勘察、方案设计和接入系统方案审批；",
        "第二阶段（1-2个月）：设备采购生产、土建施工和基础建设；",
        "第三阶段（2-3周）：设备安装调试、电力公司验收；",
        "第四阶段（1-2周）：并网联调、试运行和正式投运。",
        "其中接入系统方案审批由当地电力公司负责，周期受各地政策影响较大。",
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="储能项目并网流程说明话术",
        category="并网流程",
        permission_level=ContentLevel.GENERAL,
        summary="向客户说明储能项目从施工到并网的全流程节点和周期",
        body="储能项目并网流程说明话术",
        structured_payload={
            "scene": "客户询问储能项目从开工到投运的周期和流程时",
            "recommended_speech": SCRIPT_5_RECOMMENDED,
            "forbidden_speech": _txt(
                "不能承诺具体的并网日期或电力公司审批周期；",
                '不能说"肯定能在XX号之前投运"。',
            ),
            "notes": _txt(
                "并网周期须以电力公司批复为准；",
                "如涉及10kV以上接入，审批周期通常更长。",
            ),
        },
    )


# ---------------------------------------------------------------------------
# Quiz questions
# ---------------------------------------------------------------------------

def ensure_quiz_questions(db, related_content: Content) -> None:
    existing = db.scalars(
        select(QuizQuestion)
        .where(QuizQuestion.question.like("【储能】%"))
        .limit(1)
    ).all()
    if existing:
        print("  skip quiz questions (already exist)")
        return

    questions = [
        {
            "question": "【储能】2025年锂离子电池储能电站新增的消防要求是什么？",
            "options": ["二级消防系统", "三级消防系统（预警-灭火-防复燃）", "一级消防系统", "无需消防系统"],
            "answer": "三级消防系统（预警-灭火-防复燃）",
            "explanation": "根据2025年新型储能安全监管要求，锂离子电池储能电站须配备三级消防系统。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】磷酸铁锂电池储能系统的典型循环寿命范围是？",
            "options": ["1000-2000次", "3000-5000次", "6000-8000次", "10000次以上"],
            "answer": "6000-8000次",
            "explanation": "在0.5C/25°C条件下，磷酸铁锂电池循环寿命一般为6000-8000次。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】全钒液流电池最大的优势是什么？",
            "options": ["能量密度高", "成本低", "超长循环寿命与本质安全", "低温性能好"],
            "answer": "超长循环寿命与本质安全",
            "explanation": "全钒液流电池循环寿命可达20000次以上，且容量功率解耦、本质安全。",
            "permission_level": ContentLevel.FULL.value,
        },
        {
            "question": "【储能】钠离子电池相比磷酸铁锂电池的主要优势是？",
            "options": ["能量密度更高", "原材料丰富、低温性能好", "循环寿命更长", "技术更成熟"],
            "answer": "原材料丰富、低温性能好",
            "explanation": "钠资源丰富且低温性能优良，但能量密度和循环寿命仍低于磷酸铁锂。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】储能系统标准质保年限和电池衰减保障承诺是？",
            "options": [
                "整机3年、电池5年衰减保障",
                "整机5年、电池模组10年衰减保障",
                "整机10年、电池10年衰减保障",
                "整机2年、电池3年衰减保障",
            ],
            "answer": "整机5年、电池模组10年衰减保障",
            "explanation": "整机5年质保覆盖核心部件，电池模组10年衰减保障承诺首年≤3%、年均≤2%。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】储能电站并网验收中，PCS需要通过的强制测试是？",
            "options": ["效率测试", "温升测试", "低电压穿越和高电压穿越测试", "噪声测试"],
            "answer": "低电压穿越和高电压穿越测试",
            "explanation": "2025版并网验收标准将高低电压穿越测试纳入PCS强制检测项目。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】处理客户异议时的标准话术框架是什么？",
            "options": ["AIDA框架", "FABE框架", "L-A-C-T框架", "STAR框架"],
            "answer": "L-A-C-T框架",
            "explanation": "Listen（倾听）- Acknowledge（认可）- Clarify（澄清）- Transition（转接）。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】储能项目从合同签订到投运的一般周期是？",
            "options": ["1-2个月", "3-6个月", "6-12个月", "1年以上"],
            "answer": "3-6个月",
            "explanation": "一般分为场地勘察、施工安装、调试验收、并网投运四个阶段，合计3-6个月。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】BMS系统在2025年标准中，SOC误差要求不超过多少？",
            "options": ["10%", "5%", "3%", "1%"],
            "answer": "3%",
            "explanation": "2025版标准要求BMS系统SOC误差不大于3%，且具备热失控预警功能。",
            "permission_level": ContentLevel.GENERAL.value,
        },
        {
            "question": "【储能】浙江省工商业储能，两充两放模式下IRR预期范围是？",
            "options": ["5-8%", "8-10%", "12-15%", "18-20%"],
            "answer": "12-15%",
            "explanation": "浙江省峰谷价差较大，两充两放模式下工商业储能IRR可达12-15%。",
            "permission_level": ContentLevel.GENERAL.value,
        },
    ]

    for q in questions:
        db.add(
            QuizQuestion(
                question=q["question"],
                options=q["options"],
                answer=q["answer"],
                explanation=q["explanation"],
                related_content_id=related_content.id,
                permission_level=q["permission_level"],
                status=QuestionStatus.ENABLED.value,
            )
        )
    print(f"  created {len(questions)} quiz questions")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    settings = Settings()

    if settings.use_fake_external_clients:
        print("ERROR: USE_FAKE_EXTERNAL_CLIENTS=true in .env")
        print("       Please set USE_FAKE_EXTERNAL_CLIENTS=false and retry.")
        sys.exit(1)

    if not settings.dashscope_api_key:
        print("ERROR: DASHSCOPE_API_KEY is not configured in .env")
        sys.exit(1)

    collection = settings.milvus_collection_name

    print("=" * 60)
    print("  Energy Storage Seed Data Script")
    print("=" * 60)
    print(f"  MySQL:      {settings.database_url}")
    print(f"  Milvus:     {settings.milvus_host}:{settings.milvus_port}")
    print(f"  Collection: {collection}")
    print(f"  DashScope:  {settings.dashscope_embedding_model}")
    print("=" * 60)

    dashscope_client = create_dashscope_client(settings)
    milvus_client = create_milvus_client(settings)

    # ---- 0. Drop old 3-dim Milvus collection ----
    print(f"\n[0/4] Checking and cleaning old Milvus collection '{collection}' ...")
    try:
        client_attr = getattr(milvus_client, "client", None)
        if client_attr is not None and client_attr.has_collection(collection):
            client_attr.drop_collection(collection)
            print(f"  Dropped old collection '{collection}' (will recreate with 1024-dim)")
        else:
            print(f"  Collection '{collection}' does not exist or is fake client, no clean needed")
    except Exception as exc:
        print(f"  Warning: clean collection failed (ignorable): {exc}")

    with session_scope() as db:
        # ---- 1. Create users ----
        print("\n[1/4] Creating test users ...")
        users = upsert_users(db, DEFAULT_PASSWORD)
        admin = users["admin"]
        print(f"  es_admin (admin)")
        print(f"  es_general (general user)")
        print(f"  es_full (full user)")

        # ---- 2. Create and publish content ----
        print("\n[2/4] Creating and publishing energy storage content ...")
        published: list[Content] = []
        for payload in energy_storage_contents():
            existing = db.scalar(select(Content).where(Content.title == payload.title))
            if existing is not None:
                print(f"  skip (exists): {payload.title}")
                if existing.status == ContentStatus.PUBLISHED.value:
                    published.append(existing)
                continue

            content = create_content(db, creator=admin, payload=payload)
            publish_content(db, content_id=content.id)
            content = db.get(Content, content.id)
            if content is None:
                print(f"  FAILED to publish: {payload.title}")
                continue
            published.append(content)
            perm_label = "full" if content.permission_level == "full" else "general"
            type_label = {
                "must_read": "must-read",
                "base_script": "base-script",
                "standard_script": "std-script",
            }.get(content.content_type, content.content_type)
            print(f"  published [{perm_label}/{type_label}] {payload.title}")

        # ---- 3. Sync vector index ----
        print(f"\n[3/4] Syncing vectors to Milvus (collection: {collection}) ...")
        synced_count = 0
        for content in published:
            if content.index_status == IndexStatus.SYNCED.value:
                print(f"  skip (already synced): {content.title}")
                synced_count += 1
                continue
            try:
                result = sync_content_index(
                    db,
                    content_id=content.id,
                    dashscope_client=dashscope_client,
                    milvus_client=milvus_client,
                    settings=settings,
                )
                if result.status == IndexStatus.SYNCED.value:
                    print(f"  synced [{result.indexed_count} vectors]: {content.title}")
                    synced_count += 1
                else:
                    print(f"  FAILED [{result.error_code}]: {content.title}")
            except Exception as exc:
                print(f"  ERROR: {content.title} - {exc}")

        # ---- 4. Create quiz questions ----
        print("\n[4/4] Creating quiz questions ...")
        if published:
            standard_script = next(
                (c for c in published if c.content_type == ContentType.STANDARD_SCRIPT.value),
                published[0],
            )
            ensure_quiz_questions(db, related_content=standard_script)

    # ---- Done ----
    print("\n" + "=" * 60)
    print("  Done!")
    print("=" * 60)
    print(f"\nTest accounts (password: {DEFAULT_PASSWORD}):")
    print("  Admin:       es_admin")
    print("  General:     es_general")
    print("  Full:        es_full")
    print(f"\nSynced: {synced_count}/{len(published)} contents")
    print(f"Milvus Collection: {collection}")
    print("\nNext steps:")
    print("  1. Login as es_general to test AI Q&A and permission isolation")
    print("  2. Login as es_full to verify full-level content access")
    print("  3. Login as es_admin to manage content and missed questions")


if __name__ == "__main__":
    main()
