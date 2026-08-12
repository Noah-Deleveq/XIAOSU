#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
mkdir -p seed_docs

if [ ! -f "seed_docs/员工手册.md" ]; then
cat > "seed_docs/员工手册.md" <<'MD'
# 员工手册

## 年假
员工每年享有 10 天带薪年假，入职满一年后即可申请，可在钉钉 OA 提交年假申请。

## 报销
报销发票需要提供：发票原件、报销单、审批通过截图，缺一不可。报销流程 3 个工作日内完成审核。

## 考勤
工作时间 9:00-18:00，午休 1 小时。迟到超过 30 分钟记一次迟到。加班需提前审批，工作日加班按 1.5 倍时薪计算。

## 出差
出差需提前提交出差申请单，住宿标准：一线城市 500 元/晚，其他城市 350 元/晚。
MD
echo "生成 seed_docs/员工手册.md"
fi

if [ ! -f "seed_docs/FAQ.md" ]; then
cat > "seed_docs/FAQ.md" <<'MD'
# 员工 FAQ

Q: 加班有加班费吗？
A: 有，工作日加班 1.5 倍时薪，周末 2 倍，法定节假日 3 倍。

Q: 年假可以结转吗？
A: 年假当年有效，最多结转 3 天到下一年。

Q: 忘记打卡怎么办？
A: 在钉钉 OA 提交补卡申请，每月最多 3 次。

Q: 可以远程办公吗？
A: 每周五可申请远程办公，需提前一天审批。
MD
echo "生成 seed_docs/FAQ.md"
fi

if [ ! -f "seed_docs/新人入职指南.md" ]; then
cat > "seed_docs/新人入职指南.md" <<'MD'
# 新人入职指南

## 入职第一天
新人入职第一天要做的事：
1. 到 HR 处领取工牌与电脑（IT 会提前配好）
2. 开通企业邮箱与钉钉账号
3. 参加 10:00 的新人培训
4. 与直属上级确认第一周计划

## 试用期
试用期 3 个月，转正需通过 360 评估。
MD
echo "生成 seed_docs/新人入职指南.md"
fi

if command -v curl >/dev/null 2>&1 && curl -fsS http://localhost:8000/api/docs >/dev/null 2>&1; then
  for f in seed_docs/*.md seed_docs/*.txt; do
    [ -e "$f" ] || continue
    echo "导入 $f"
    curl -fsS -F "file=@$f" http://localhost:8000/api/docs >/dev/null
  done
  echo "种子文档已导入知识库"
else
  echo "后端未启动，跳过自动导入；可先运行 scripts/start.sh 再执行本脚本。"
fi
