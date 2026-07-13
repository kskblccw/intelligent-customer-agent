from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import rag_summarize,get_weather,get_user_location,get_user_id,get_current_month,fetch_external_data,fill_context_for_report
from agent.tools.middleware import monitor_tool,log_before_model,report_prompt_switch

class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize,get_weather,get_user_location,get_user_id,get_current_month,fetch_external_data,fill_context_for_report],
            middleware=[ monitor_tool,log_before_model,report_prompt_switch]
        )

    def execute(self,query:str):
        input_dict =  {
            "messages":[
                {"role":"user","content":query}
            ]
        }
        #第三个参数content就是上下文runtime中的信息，就是我们做提示词切换的标记
        for chunk in  self.agent.stream(input_dict,stream_mode="values",context={"report":False}):
            lasest_message = chunk["messages"][-1]
            if lasest_message.content:
                yield lasest_message.content.strip() + '\n'




if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute("给我生成一份我的使用报告信息"):
        print(chunk,end="",flush=True)