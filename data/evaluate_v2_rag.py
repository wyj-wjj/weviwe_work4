# -*- coding: utf-8 -*-
"""Evaluate v2 RAG hit quality without writing missed-question test noise.

The script calls the same answer_question service used by /api/app/rag/ask,
but monkey-patches missed-question recording to avoid polluting the admin list
with synthetic evaluation misses.

Usage:
    cd E:/WeView/work4
    .venv/Scripts/python.exe -u data/evaluate_v2_rag.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx
from sqlalchemy import select

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import session_scope
from app.integrations.dashscope import DashScopeHttpClient
from app.integrations.milvus import create_milvus_client
from app.models.content import Content
from app.models.user import User
from app.services import rag_answer_service


CaseKind = Literal["positive", "permission", "negative"]


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    kind: CaseKind
    username: str
    question: str
    expected_fragments: tuple[str, ...] = ()
    expect_hit: bool | None = True


CASES: tuple[EvalCase, ...] = (
    EvalCase("G01", "positive", "es_general", "储能项目的消防验收有哪些要求？", ("消防安全监管", "消防配置", "消防验收现场")),
    EvalCase("G02", "positive", "es_general", "消防验收没过怎么跟客户说？", ("消防验收现场",)),
    EvalCase("G03", "positive", "es_general", "储能技术参数怎么选？", ("主流储能电芯", "介绍储能技术参数", "客户技术选型")),
    EvalCase("G04", "positive", "es_general", "LFP、钠离子和液流电池怎么对比？", ("主流储能电芯",)),
    EvalCase("G05", "positive", "es_general", "并网流程要多久？", ("并网接入流程", "介绍并网流程", "并网周期与流程")),
    EvalCase("G06", "positive", "es_general", "并网验收不通过要怎么处理？", ("并网周期与流程", "并网接入流程")),
    EvalCase("G07", "positive", "es_general", "储能项目投资回收周期怎么算？", ("投资收益分析", "解释投资回报", "客户质疑回收周期")),
    EvalCase("G08", "positive", "es_general", "客户说储能太贵怎么回答？", ("客户质疑回收周期",)),
    EvalCase("G09", "positive", "es_general", "峰谷电价变动会不会影响储能收益？", ("分时电价", "电费账单", "电价变动影响收益")),
    EvalCase("G10", "positive", "es_general", "储能补贴申报条件有哪些，能拿多少？", ("补贴政策汇编", "补贴申报", "补贴额度与申报条件")),
    EvalCase("G11", "positive", "es_general", "PCS和BMS品牌应该怎么选？", ("PCS与BMS", "设备配置方案", "设备品牌与质量")),
    EvalCase("G12", "positive", "es_general", "客户要求进口设备时怎么沟通？", ("设备品牌与质量",)),
    EvalCase("G13", "positive", "es_general", "巡检发现电芯压差偏大怎么办？", ("巡检发现异常",)),
    EvalCase("G14", "positive", "es_general", "巡检发现消防设备过期该怎么跟客户说？", ("巡检发现异常", "消防")),
    EvalCase("G15", "positive", "es_general", "BMS通讯故障应该怎么处理？", ("典型故障案例", "故障应急响应")),
    EvalCase("G16", "positive", "es_general", "PCS过温保护怎么应急沟通？", ("典型故障案例", "故障应急响应")),
    EvalCase("G17", "positive", "es_general", "项目进场施工前客户需要准备什么？", ("项目进场施工", "项目整体流程")),
    EvalCase("G18", "positive", "es_general", "合同里的质保条款怎么跟客户解释？", ("合同关键条款", "解释合同条款", "合同谈判")),
    EvalCase("G19", "positive", "es_general", "储能项目环评流程和合规要求是什么？", ("环境影响评价", "环评流程")),
    EvalCase("G20", "positive", "es_general", "储能设备安装周期和现场准备怎么说明？", ("运输安装", "安装周期")),
    EvalCase("G21", "positive", "es_general", "电费账单里哪些部分会影响储能收益？", ("电费账单", "分时电价")),
    EvalCase("F01", "positive", "es_full", "内部技术选型决策和供应商评分标准是什么？", ("内部技术选型", "内部技术评审", "电芯供应商内部")),
    EvalCase("F02", "positive", "es_full", "并网受阻时怎么和电力公司协调？", ("并网受阻", "电力公司提交接入", "内部批复记录")),
    EvalCase("F03", "positive", "es_full", "内部投资评审委员会会问IRR敏感性怎么回答？", ("内部投资评审委员会", "内部投资测算")),
    EvalCase("F04", "positive", "es_full", "省级储能补贴资金盘和申报策略怎么判断？", ("补贴配套资金", "补贴申报内部")),
    EvalCase("F05", "positive", "es_full", "储能设备采购招标内部评标标准是什么？", ("采购招标内部评标", "设备选型内部")),
    EvalCase("F06", "positive", "es_full", "年度深度检修SOP里A/B/C/D缺陷怎么分级？", ("年度深度检修", "深度检修技术交底")),
    EvalCase("F07", "positive", "es_full", "电芯供应商内部评估里主供和二供策略怎么定？", ("电芯供应商内部", "内部技术选型")),
    EvalCase("P01", "permission", "es_general", "内部技术选型决策和供应商评分标准是什么？", expect_hit=False),
    EvalCase("P02", "permission", "es_general", "省级补贴资金盘分配和申报优先级是什么？", expect_hit=False),
    EvalCase("P03", "permission", "es_general", "年度深度检修SOP里A/B/C/D缺陷怎么分级？", expect_hit=False),
    EvalCase("P04", "permission", "es_general", "内部投资测算模型的敏感性参数有哪些？", expect_hit=False),
    EvalCase("P05", "permission", "es_general", "各省电力公司并网内部批复记录有哪些？", expect_hit=False),
    EvalCase("N01", "negative", "es_general", "今天北京天气怎么样？", expect_hit=False),
    EvalCase("N02", "negative", "es_general", "红烧肉怎么做才好吃？", expect_hit=False),
    EvalCase("N03", "negative", "es_general", "公司年假制度怎么申请？", expect_hit=False),
)


def noop_record_missed_question(db, *, question: str, user: User):  # noqa: ANN001
    return None


def load_users(db) -> dict[str, User]:  # noqa: ANN001
    usernames = {case.username for case in CASES}
    users = {
        user.username: user
        for user in db.scalars(select(User).where(User.username.in_(usernames))).all()
    }
    missing = sorted(usernames - set(users))
    if missing:
        raise SystemExit(f"Missing users: {missing}")
    return users


def title_matches(titles: list[str], fragments: tuple[str, ...]) -> bool:
    if not fragments:
        return True
    return any(fragment in title for title in titles for fragment in fragments)


def main() -> None:
    settings = Settings()
    if settings.use_fake_external_clients:
        raise SystemExit("USE_FAKE_EXTERNAL_CLIENTS=true; real RAG evaluation requires real clients.")

    rag_answer_service.record_missed_question = noop_record_missed_question
    http_client = httpx.Client(timeout=60.0, trust_env=False)
    dashscope_client = DashScopeHttpClient(settings, http_client=http_client)
    milvus_client = create_milvus_client(settings)

    rows: list[dict] = []
    with session_scope() as db:
        users = load_users(db)
        for case in CASES:
            for attempt in range(1, 5):
                try:
                    result = rag_answer_service.answer_question(
                        db,
                        user=users[case.username],
                        question=case.question,
                        dashscope_client=dashscope_client,
                        milvus_client=milvus_client,
                        settings=settings,
                    )
                    break
                except AppError:
                    if attempt == 4:
                        raise
                    http_client.close()
                    time.sleep(attempt * 1.5)
                    http_client = httpx.Client(timeout=60.0, trust_env=False)
                    dashscope_client = DashScopeHttpClient(settings, http_client=http_client)
            source_ids = [source["content_id"] for source in result.get("sources", [])]
            source_contents = (
                db.scalars(select(Content).where(Content.id.in_(source_ids))).all()
                if source_ids
                else []
            )
            content_by_id = {content.id: content for content in source_contents}
            source_titles = [source["title"] for source in result.get("sources", [])]
            source_levels = [
                content_by_id[source["content_id"]].permission_level
                for source in result.get("sources", [])
                if source["content_id"] in content_by_id
            ]
            leaked_full = case.username == "es_general" and any(level == "full" for level in source_levels)
            matched = title_matches(source_titles, case.expected_fragments)
            answer = result.get("answer", "")

            if case.kind == "positive":
                passed = bool(result["hit"]) and matched and not leaked_full
            elif case.kind == "negative":
                passed = not result["hit"] and not leaked_full
            else:
                passed = (not leaked_full) and (case.expect_hit is None or result["hit"] == case.expect_hit)

            rows.append(
                {
                    "case": case,
                    "hit": result["hit"],
                    "matched": matched,
                    "leaked_full": leaked_full,
                    "passed": passed,
                    "source_titles": source_titles,
                    "source_levels": source_levels,
                    "answer_preview": answer.replace("\n", " ")[:120],
                }
            )
    http_client.close()

    positives = [row for row in rows if row["case"].kind == "positive"]
    permissions = [row for row in rows if row["case"].kind == "permission"]
    negatives = [row for row in rows if row["case"].kind == "negative"]

    positive_hit = sum(1 for row in positives if row["hit"])
    positive_matched = sum(1 for row in positives if row["hit"] and row["matched"])
    permission_no_leak = sum(1 for row in permissions if not row["leaked_full"])
    permission_strict_miss = sum(1 for row in permissions if not row["hit"])
    negative_miss = sum(1 for row in negatives if not row["hit"])
    overall_pass = sum(1 for row in rows if row["passed"])

    print("=" * 100)
    print("V2 RAG Evaluation Summary")
    print("=" * 100)
    print(f"collection={settings.milvus_collection_name} threshold={settings.rag_similarity_threshold} top_k={settings.rag_top_k}")
    print(f"positive_hit_rate={positive_hit}/{len(positives)} = {positive_hit / len(positives):.1%}")
    print(f"positive_source_match_rate={positive_matched}/{len(positives)} = {positive_matched / len(positives):.1%}")
    print(f"permission_no_full_leak={permission_no_leak}/{len(permissions)} = {permission_no_leak / len(permissions):.1%}")
    print(f"permission_strict_miss={permission_strict_miss}/{len(permissions)} = {permission_strict_miss / len(permissions):.1%}")
    print(f"unrelated_negative_miss_rate={negative_miss}/{len(negatives)} = {negative_miss / len(negatives):.1%}")
    print(f"overall_expected_behavior={overall_pass}/{len(rows)} = {overall_pass / len(rows):.1%}")
    print()

    for row in rows:
        case = row["case"]
        status = "PASS" if row["passed"] else "FAIL"
        titles = " | ".join(row["source_titles"]) if row["source_titles"] else "-"
        levels = ",".join(row["source_levels"]) if row["source_levels"] else "-"
        print(f"{status} {case.case_id} [{case.kind}/{case.username}] hit={row['hit']} matched={row['matched']} leak={row['leaked_full']}")
        print(f"  Q: {case.question}")
        print(f"  sources({levels}): {titles}")
        print(f"  answer: {row['answer_preview']}")


if __name__ == "__main__":
    main()
