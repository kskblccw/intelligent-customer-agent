import os
from utils.logger_handler import logger
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from rag.rag_service import RagSummarizeService
import random
from utils.config_handler import agent_config
from utils.pyth_tool import get_abs_path
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import re
from datetime import datetime


class TransientAPIError(RuntimeError):
    """可重试的 API 错误（网络超时、DNS 失败、服务端 5xx），由中间件捕获后自动重试"""
    pass

_rag = None


def _get_rag():
    global _rag
    if _rag is None:
        _rag = RagSummarizeService()
    return _rag


month_arr = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
             "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", ]
external_data = {}

_IPV4_RE = re.compile(
    r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
)

def _is_valid_ipv4(ip: str) -> bool:
    return bool(_IPV4_RE.match(ip or ""))

def _get_public_ip() -> str:
    # 可在agent.yml里覆盖
    ip_sources = agent_config.get("public_ip_sources", [
        "https://ipv4.icanhazip.com",
    ])
    timeout = float(agent_config.get("public_ip_timeout", 3))
    for source in ip_sources:
        try:
            with urlopen(source, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8").strip()
                if _is_valid_ipv4(ip):
                    return ip
        except Exception:
            continue

    return ""

GAODE_BASE_URL = agent_config.get("gaode_base_url")
GAODE_TIMEOUT = float(agent_config.get("gaode_timeout"))

def _gaode_get(path: str, params: dict) -> dict:
    gaode_key = os.environ.get("GAODE_KEY", "") or (agent_config.get("gaodekey") or "").strip()
    if not gaode_key:
        raise ValueError("agent.yml中未配置gaodekey")

    query = dict(params)
    query["key"] = gaode_key
    url = f"{GAODE_BASE_URL}{path}?{urlencode(query)}"

    try:
        with urlopen(url, timeout=GAODE_TIMEOUT) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except HTTPError as e:
        if e.code >= 500:
            raise TransientAPIError(f"高德服务器错误 {e.code}") from e
        raise RuntimeError(f"高德HTTP错误: {e.code}") from e
    except URLError as e:
        raise TransientAPIError(f"高德网络错误: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"高德请求异常: {str(e)}") from e


def _resolve_city_to_adcode(city: str) -> tuple[str, str]:
    geo = _gaode_get("/v3/geocode/geo", {"address": city})
    if geo.get("status") != "1" or not geo.get("geocodes"):
        raise RuntimeError(f"城市解析失败: {geo.get('info', 'unknown')}")

    first = geo["geocodes"][0]
    adcode = first.get("adcode")
    if not adcode:
        raise RuntimeError("城市解析成功但未返回adcode")

    resolved_city = first.get("city") or first.get("district") or city
    if isinstance(resolved_city, list):
        resolved_city = "".join(resolved_city)

    return str(resolved_city), str(adcode)


@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city: str) -> str:
    if not city or not city.strip():
        return "未提供城市名称，无法查询天气"

    try:
        resolved_city, adcode = _resolve_city_to_adcode(city.strip())
        weather = _gaode_get(
            "/v3/weather/weatherInfo",
            {"city": adcode, "extensions": "base"},
        )

        if weather.get("status") != "1" or not weather.get("lives"):
            return f"城市{resolved_city}天气查询失败：{weather.get('info', 'unknown')}"

        live = weather["lives"][0]
        condition = live.get("weather", "未知")
        temperature = live.get("temperature", "未知")
        humidity = live.get("humidity", "未知")
        wind_direction = live.get("winddirection", "未知")
        wind_power = live.get("windpower", "未知")
        report_time = live.get("reporttime", "未知")

        return (
            f"城市{resolved_city}天气为{condition}，气温{temperature}摄氏度，"
            f"空气湿度{humidity}%，{wind_direction}风{wind_power}级，"
            f"数据发布时间{report_time}。"
        )
    except TransientAPIError:
        raise  # 网络瞬时错误，抛给中间件重试
    except Exception as e:
        logger.error(f"[get_weather]天气查询失败 city={city} err={str(e)}")
        return f"城市{city}天气查询失败，请稍后重试"


@tool(description="获取用户当前的城市名称，以纯字符串形式返回")
def get_user_location(runtime: ToolRuntime) -> str:
    # 城市按会话隔离：从本次执行的 runtime context 读取，而非进程级全局变量
    city = (runtime.context or {}).get("user_city")
    return city or agent_config.get("default_city", "广州市")



@tool(description="从知识库中检索扫地/扫拖机器人的相关资料，返回原始参考资料文本（由Agent自行综合）")
def rag_search(query: str) -> str:
    return _get_rag().rag_search(query)


@tool(description="获取当前登录用户的ID，以纯字符串形式返回")
def get_user_id(runtime: ToolRuntime) -> str:
    return (runtime.context or {}).get("user_id") or "unknown"


@tool(description="获取当前月份，以纯字符串形式返回，格式为YYYY-MM")
def get_current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def generate_external_data():
    """
    {
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        ...
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abs_path(agent_config["external_data_path"])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")

                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }


def _generate_demo_record(user_id: str, month: str) -> dict:
    """为无外部数据的用户生成一份 demo 使用记录"""
    features = ["清扫覆盖率98.5%", "清扫覆盖率96.2%", "清扫覆盖率99.1%",
                "清扫覆盖率94.8%", "清扫覆盖率97.3%"]
    efficiencies = ["清扫效率1.2㎡/min", "清扫效率1.1㎡/min", "清扫效率1.3㎡/min",
                    "清扫效率1.0㎡/min", "清扫效率1.15㎡/min"]
    consumables = ["边刷剩余寿命65%", "边刷剩余寿命72%", "边刷剩余寿命58%",
                   "边刷剩余寿命81%", "边刷剩余寿命69%"]
    comparisons = ["高于同机型均值5%", "接近同机型均值", "高于同机型均值3%",
                   "低于同机型均值2%", "高于同机型均值8%"]
    idx = hash(user_id + month) % len(features)
    return {
        "特征": features[idx],
        "效率": efficiencies[idx],
        "耗材": consumables[idx],
        "对比": comparisons[idx],
    }


@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回， 如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    try:
        generate_external_data()
    except FileNotFoundError:
        pass

    try:
        return str(external_data[user_id][month])
    except KeyError:
        pass

    demo = _generate_demo_record(user_id, month)
    return str(demo)


@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"


# if __name__ == '__main__':
#     print(get_weather(get_user_location()))