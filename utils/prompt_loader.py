#提示词工具
from utils.config_handler import prompts_config
from utils.logger_handler import logger
from utils.pyth_tool import get_abs_path

def load_system_prompts():
    try:
        system_prompt_path = get_abs_path(prompts_config['main_prompt_path'])
    except KeyError as e:
        logger.error(f"[load_system_prompts]在ymal配置项中没有main_prompt_path配置项")
        raise e

    try:
        return open(system_prompt_path,'r',encoding='utf-8').read()

    except Exception as e:
        logger.error(f"[load_system_prompts]解析系统提示词出错，{str(e)}")
        raise e



def load_report_prompts():
    try:
        report_prompt_path = get_abs_path(prompts_config['report_prompt_path'])
    except KeyError as e:
        logger.error(f"[load_report_prompts]在ymal配置项中没有report_prompt_path配置项")
        raise e

    try:
        return open(report_prompt_path,'r',encoding='utf-8').read()

    except Exception as e:
        logger.error(f"[load_report_prompts]解析report提示词出错，{str(e)}")
        raise e



if __name__ == "__main__":
    print(load_system_prompts())