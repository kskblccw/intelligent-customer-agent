#向量存储服务开发
import os

from langchain_chroma import Chroma
from langchain_core.documents import Document

from utils.config_handler import chroma_config
from model.factory import embedding_model
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.file_handler import txt_loader, pdf_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.pyth_tool import get_abs_path
from utils.logger_handler import logger

class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_config['collection_name'],
            embedding_function=embedding_model,
            persist_directory=chroma_config['persist_directory'],
        )
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_config['chunk_size'],
            chunk_overlap=chroma_config['chunk_overlap'],
            separators=chroma_config['separators'],
            length_function=len
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={'k':chroma_config['k']})


    def load_document(self):
        """
        从数据文件夹内读取文件，转为向量存入向量数据库
        要计算文件的md5，进行去重
        :return:
        """

        def check_md5_hex(md5_for_check:str):
            if not os.path.exists(get_abs_path(chroma_config['md5_hex_store'])):
                open(get_abs_path(chroma_config['md5_hex_store']), 'w',encoding='utf-8').close()
                return False    #md5没有处理过

            with open(get_abs_path(chroma_config['md5_hex_store']),'r',encoding='utf-8') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True   #md5处理过

                return False   #md5没有处理过

        def save_md5_hex(md5_for_check:str):
            with open(get_abs_path(chroma_config['md5_hex_store']), 'a',encoding='utf-8') as f:
                f.write(md5_for_check + '\n')

        def get_file_documents(read_path:str):
            if read_path.endswith('txt'):
                return txt_loader(read_path)

            if read_path.endswith('pdf'):
                return pdf_loader(read_path)

            return []

        allowed_file_path:list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_config['data_path']),
            tuple(chroma_config['allow_knowledge_file_type']),
        )

        for file_path in allowed_file_path:
            #获取文件的md5
            md5_hex = get_file_md5_hex(file_path)

            if check_md5_hex(md5_hex):
                logger.info(f"加载的知识库{file_path}已经存在知识库中")
                continue

            try:
                documents:list[Document] = get_file_documents(file_path)

                if not documents:
                    logger.warning(f"加载{file_path}内没有有效的文本数据，跳过")
                    continue

                split_document:list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"分片后{file_path}没有得到有效的文本数据，跳过")
                    continue


                #将分割好的内容存入向量库中
                self.vector_store.add_documents(split_document)

                #记录这个已经处理好的文件的md5值，避免下次重复导入
                save_md5_hex(md5_hex)
                logger.info(f"加载知识库{file_path}成功")

            except Exception as e:
                #exc_info=True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"加载知识库{file_path}失败，原因是{str(e)}",exc_info=True)
                continue




if __name__ == '__main__':
    vector_store = VectorStoreService()

    vector_store.load_document()

    retriever = vector_store.get_retriever()

    res = retriever.invoke("迷路")

    for doc in res:
        print(doc.page_content)
        print("-"*20)
