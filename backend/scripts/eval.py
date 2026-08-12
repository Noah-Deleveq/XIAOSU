"""Evals：自动化评测脚本 —— 20+ 条 case 跑出准确率（需真实 LLM API Key）

用法：
  uv run python scripts/eval.py            # 全量
  uv run python scripts/eval.py --limit 5  # 快速试跑前 5 条
  uv run python scripts/eval.py --json     # 只输出 JSON 报告
报告写入 logs/eval_report.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.qa import QaEngine  # noqa: E402
from app.state import index, sessions  # noqa: E402

# ---- 评测用例（expect: doc=知识库问答 / tool=工具调用 / refuse=拒答）----
CASES: list[dict] = [
    # --- 知识库问答（文档） ---
    {"question": "员工每年有几天年假？", "expect": "doc", "must_contain": ["年假"]},
    {"question": "报销发票需要什么材料？", "expect": "doc", "must_contain": ["发票"]},
    {"question": "新人入职第一天要做哪些事？", "expect": "doc", "must_contain": ["入职"]},
    {"question": "加班有加班费吗？", "expect": "doc", "must_contain": ["加班"]},
    {"question": "出差补贴标准是多少？", "expect": "doc", "must_contain": ["出差"]},
    {"question": "请事假需要提前多久申请？", "expect": "doc", "must_contain": ["请假"]},
    {"question": "试用期是多久？", "expect": "doc", "must_contain": ["试用"]},
    {"question": "公积金缴存比例是多少？", "expect": "doc", "must_contain": ["公积金"]},
    {"question": "报销流程是怎样的？", "expect": "doc", "must_contain": ["[1]"]},
    {"question": "年假可以累计到下一年吗？", "expect": "doc", "must_contain": ["年假"]},
    {"question": "考勤迟到会怎么处理？", "expect": "doc", "must_contain": ["考勤"]},
    # --- 工具调用 ---
    {"question": "员工 001 是哪个部门的？", "expect": "tool", "tool_name": "query_employee", "must_contain": ["技术部"]},
    {"question": "员工 002 的职位是什么？", "expect": "tool", "tool_name": "query_employee", "must_contain": ["市场"]},
    {"question": "员工 003 什么时候入职的？", "expect": "tool", "tool_name": "query_employee", "must_contain": ["入职"]},
    {"question": "员工 001 上周的考勤情况怎么样？", "expect": "tool", "tool_name": "query_attendance"},
    {"question": "员工 004 有多少销售订单？", "expect": "tool", "tool_name": "query_orders"},
    {"question": "现在几点了？", "expect": "tool", "tool_name": "current_time"},
    {"question": "员工 004 上周的订单金额是多少？", "expect": "tool", "tool_name": "query_orders"},
    # --- 多轮对话（指代） ---
    {
        "question": "他上周来上班几天？",
        "pre": ["员工 001 是哪个部门的？"],
        "expect": "tool",
        "tool_name": "query_attendance",
    },
    # --- 拒答 ---
    {"question": "我们公司 CEO 的家庭住址是？", "expect": "refuse"},
    {"question": "2030 年的销售目标是多少？", "expect": "refuse"},
    {"question": "公司食堂本周的菜谱是什么？", "expect": "refuse"},
    {"question": "老板的私人电话号码是多少？", "expect": "refuse"},
    {"question": "员工 999 的薪资是多少？", "expect": "refuse"},
]


def judge(case: dict, result: dict) -> tuple[bool, str]:
    expect = case["expect"]
    if expect == "refuse":
        if result["refused"]:
            return True, ""
        return False, "应拒答但模型回答了"
    if expect == "doc":
        if result["refused"]:
            return False, "拒答了（未命中文档）"
        if not result["references"]:
            return False, "无引用来源"
        blob = result["answer"] + " " + " ".join(r["text"] for r in result["references"])
        for kw in case.get("must_contain", []):
            if kw not in blob:
                return False, f"缺少关键词「{kw}」"
        return True, ""
    if expect == "tool":
        if not result["used_tool"]:
            return False, "未调用工具"
        tool_name = case.get("tool_name")
        if tool_name and tool_name not in result.get("tools_used", []):
            return False, f"工具不符：期望 {tool_name}，实际 {result.get('tools_used')}"
        for kw in case.get("must_contain", []):
            if kw not in result["answer"]:
                return False, f"答案缺少「{kw}」"
        return True, ""
    return False, f"未知 expect: {expect}"


def run_cases(limit: int | None = None) -> dict:
    engine = QaEngine(index, sessions)
    cases = CASES[:limit] if limit else CASES
    results: list[dict] = []
    for i, case in enumerate(cases, 1):
        session_id = f"eval-{i}"
        for pre in case.get("pre", []):
            engine.answer("eval", session_id, pre)
        result = engine.answer("eval", session_id, case["question"])
        ok, reason = judge(case, result)
        results.append(
            {
                "case": i,
                "question": case["question"],
                "expect": case["expect"],
                "pass": ok,
                "reason": reason,
                "used_tool": result.get("used_tool", False),
                "refused": result.get("refused", False),
            }
        )
        print(f"[{'PASS' if ok else 'FAIL'}] #{i} {case['question'][:36]} {reason}")
    passed = sum(1 for r in results if r["pass"])
    return {
        "total": len(results),
        "passed": passed,
        "accuracy": round(passed / len(results), 4) if results else 0,
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="小苏 Evals 自动化评测")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条")
    parser.add_argument("--json", action="store_true", help="只输出 JSON 报告")
    args = parser.parse_args()

    report = run_cases(args.limit)
    out = {
        "total": report["total"],
        "passed": report["passed"],
        "accuracy": report["accuracy"],
        "cases": report["cases"],
    }
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    (log_dir / "eval_report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not args.json:
        print(f"\n===== 准确率: {report['passed']}/{report['total']} = {report['accuracy'] * 100:.1f}% =====")
        print(f"报告已写入 logs/eval_report.json")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
