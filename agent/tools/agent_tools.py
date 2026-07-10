import os
import random

from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_config
from utils.pyth_tool import get_abs_path
from utils.logger_handler import logger

rag = RagSummarizeService()

user_ids = ['1001','1002','1003','1004','1005','1006','1007','1008','1009','1010','1011','1012','1013','1014','1015']
month_arr = ['2025-01','2025-02','2025-03','2025-04']
external_data = {}

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query:str) -> str:
    return rag.rag_summarize(query)


@tool(description="查看当地天气的方法")
def get_weather(city:str) -> str:
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度为50%，微风"


@tool(description="获取用户所在城市的名称")
def get_user_location() -> str:
    return random.choice(['深圳','广州','佛山'])


@tool(description="获取用户的id")
def get_user_id() -> str:
    return random.choice(user_ids)

@tool(description="获取当前月份")
def get_current_month() -> str:
    return random.choice(month_arr)

def generate_external_data():
    """
    {
    }
    :return:
    """
    if not external_data:
        external_data_path =  get_abs_path(agent_config['external_data_path'])
        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

        with open(external_data_path, 'r', encoding='utf-8') as f:
            for line in f.readlines()[1:]:
                arr:list[str] = line.strip().split(',')
                user_id:str = arr[0].replace('"','')
                feature:str = arr[1].replace('"','')
                efficiency:str = arr[2].replace('"','')
                consumables:str = arr[3].replace('"','')
                comparison:str = arr[4].replace('"','')
                time:str = arr[5].replace('"','')

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征":feature,
                    "效率":efficiency,
                    "耗材":consumables,
                    "对比":comparison,
                }
# @tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回，如果未检索到，则返回空字符串")
def fetch_external_data(user_id:str,month:str) -> str:
    generate_external_data()

    try:
        return external_data[user_id][month]

    except KeyError:
        logger.warning(f"[fetch_external_data]未能检索到用户{user_id}在{month}的使用记录")
        return ""


if __name__ == '__main__':
    print(fetch_external_data("1001", "2025-01"))
    print(fetch_external_data("1021", "2025-05"))



