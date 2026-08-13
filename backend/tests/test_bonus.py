"""加分项测试：多模型适配 / Token 计数与成本 / MCP / Evals"""
import asyncio
import json
import types

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------- 多模型适配 ----------

def test_provider_names_and_defaults():
    """内置 3 家供应商，deepseek 默认配置正确"""
    from app.config import settings

    names = settings.provider_names()
    assert names == ["deepseek", "zhipu", "dashscope"]
    p = settings.get_provider("deepseek")
    assert p.base_url == "https://api.deepseek.com"
    assert p.model == "deepseek-chat"


def test_provider_fallback_old_vars(monkeypatch):
    """供应商未配置 Key 时回退到旧版 LLM_API_KEY"""
    from app.config import settings

    monkeypatch.setattr(settings, "llm_api_key", "sk-old-key")
    p = settings.get_provider("zhipu")  # zhipu.api_key 默认空
    assert p.api_key == "sk-old-key"


def test_provider_flat_env_vars(monkeypatch):
    """.env.example 的 DEEPSEEK_API_KEY 等扁平变量必须能被读取"""
    from app.config import Settings

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-flat")
    monkeypatch.setenv("LLM_API_KEY", "")
    s = Settings(_env_file=None)
    assert s.deepseek_api_key == "sk-flat"
    assert s.get_provider("deepseek").api_key == "sk-flat"


def test_get_provider_falls_back_for_invalid_name():
    """供应商名被误填成 API Key 时兜底回 deepseek，避免实例整体不可用"""
    from app.config import settings

    p = settings.get_provider("sk-not-a-provider")
    assert p.model == "deepseek-chat"


def test_provider_switch_api():
    """运行时切换供应商：GET 查看 / POST 切换 / 非法名 400"""
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "deepseek" in body["providers"]
    assert "dingtalk_configured" in body

    r = client.post("/api/settings/provider", json={"name": "zhipu"})
    assert r.status_code == 200
    assert r.json()["current"] == "zhipu"
    assert client.get("/api/settings").json()["current"] == "zhipu"

    r = client.post("/api/settings/provider", json={"name": "nope"})
    assert r.status_code == 400
    # 还原，避免影响其他测试
    client.post("/api/settings/provider", json={"name": "deepseek"})


def test_im_toggle_api():
    """运行期开关 IM：状态可查、切换生效并还原"""
    before = client.get("/api/im/status").json()["channels"]["feishu"]
    r = client.post("/api/im/toggle", json={"channel": "feishu", "enabled": not before})
    assert r.status_code == 200
    assert r.json()["enabled"] is (not before)
    assert client.get("/api/im/status").json()["channels"]["feishu"] is (not before)
    client.post("/api/im/toggle", json={"channel": "feishu", "enabled": before})


# ---------- Token 计数与成本 ----------

class _FakeUsage:
    prompt_tokens = 100
    completion_tokens = 50
    total_tokens = 150


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = types.SimpleNamespace(content=content, tool_calls=None)


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


class _UsageFakeClient:
    """Fake client：带 usage 字段，记录请求参数"""

    def __init__(self) -> None:
        self.last_kwargs: dict = {}

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResp("根据《员工手册》，员工每年 10 天年假 [1]。")


def _make_engine(fake):
    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    return QaEngine(
        VectorIndex(f"{settings.data_dir}/chroma"),
        SessionStore(f"{settings.data_dir}/sessions.db"),
        client=fake,
    )


def test_usage_and_cost_tracked():
    """answer 返回 usage/cost/tools_used，并写入轮次日志"""
    from app.config import settings
    from app.session.store import SessionStore

    fake = _UsageFakeClient()
    engine = _make_engine(fake)
    result = engine.answer("u1", "bonus-s1", "员工每年几天年假？")

    assert result["usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }
    assert result["cost"] > 0
    assert result["used_tool"] is False
    assert result["tools_used"] == []

    turns = SessionStore(f"{settings.data_dir}/sessions.db").list_turns()
    last = turns[-1]
    assert last["total_tokens"] == 150
    assert last["cost"] == result["cost"]


def test_cost_estimate():
    """成本估算纯函数：deepseek-chat 输入 2元/百万、输出 8元/百万"""
    from app.cost import estimate_cost

    # (1000 * 2 + 500 * 8) / 1e6 = 0.006
    assert estimate_cost("deepseek-chat", {"prompt_tokens": 1000, "completion_tokens": 500}) == 0.006
    # 未知模型走默认价（1, 2）
    assert estimate_cost("unknown-model", {"prompt_tokens": 0, "completion_tokens": 1_000_000}) == 2.0


def test_logs_api_summary():
    """日志接口返回轮次 + Token/成本汇总"""
    r = client.get("/api/logs")
    assert r.status_code == 200
    body = r.json()
    assert "logs" in body and "summary" in body
    assert "total_tokens" in body["summary"]
    assert "total_cost" in body["summary"]


# ---------- MCP ----------

def test_mcp_tools_registered():
    """MCP server 注册了 ≥4 个工具，且可直接调用"""
    from app.mcp_server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = [t.name for t in tools]
    assert len(names) >= 4
    for expected in ("search_knowledge", "ask_xiaosu", "query_employee", "current_time"):
        assert expected in names


def test_mcp_search_knowledge_callable():
    """search_knowledge 工具可被调用并返回 JSON"""
    from app.state import index

    index.index_doc("d-mcp", "员工手册.txt", "年假\n\n员工每年享有 10 天带薪年假。")

    from app.mcp_server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    result = tools["search_knowledge"].fn("年假")
    data = json.loads(result)
    assert data["hits"], "应检索到片段"
    assert "年假" in data["hits"][0]["text"]


# ---------- Evals ----------

def test_eval_cases_complete():
    """Evals 用例 ≥20 条，字段合法"""
    from scripts.eval import CASES

    assert len(CASES) >= 20
    for c in CASES:
        assert c["question"], "缺少 question"
        assert c["expect"] in ("doc", "tool", "refuse"), f"非法 expect: {c.get('expect')}"
        if c["expect"] == "tool":
            assert "tool_name" in c, f"工具类 case 缺 tool_name: {c['question']}"
