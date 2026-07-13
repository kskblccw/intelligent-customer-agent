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
            persist_directory=get_abs_path(chroma_config['persist_directory']),
        )
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_config['chunk_size'],
            chunk_overlap=chroma_config['chunk_overlap'],
            separators=chroma_config['separators'],
            length_function=len
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={'k':chroma_config['k']})

    def collection_count(self) -> int:
        return self.vector_store._collection.count()

    def add_single_file(self, file_path: str) -> bool:
        """处理单个文件入库，已处理过的跳过。返回 True 表示成功入库"""
        from utils.file_handler import get_file_md5_hex, txt_loader, pdf_loader

        md5_hex = get_file_md5_hex(file_path)
        md5_store = get_abs_path(chroma_config['md5_hex_store'])

        if os.path.exists(md5_store):
            with open(md5_store, 'r', encoding='utf-8') as f:
                if any(line.strip() == md5_hex for line in f):
                    logger.info(f"文件{os.path.basename(file_path)}已存在，跳过")
                    return False

        if file_path.endswith('txt'):
            documents = txt_loader(file_path)
        elif file_path.endswith('pdf'):
            documents = pdf_loader(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_path}")

        if not documents:
            raise ValueError("文件中没有可提取的文本")

        split_docs = self.spliter.split_documents(documents)
        if not split_docs:
            raise ValueError("分块后无有效内容")

        self.vector_store.add_documents(split_docs)

        with open(md5_store, 'a', encoding='utf-8') as f:
            f.write(md5_hex + '\n')

        logger.info(f"上传文件{os.path.basename(file_path)}入库成功 ({len(split_docs)} 块)")
        return True

    def load_document(self) -> dict:
        """
        从数据文件夹内读取文件，转为向量存入向量数据库
        要计算文件的md5，进行去重
        :return: {"loaded": [...], "skipped": [...], "errors": [...]}
        """

        def check_md5_hex(md5_for_check:str):
            if not os.path.exists(get_abs_path(chroma_config['md5_hex_store'])):
                open(get_abs_path(chroma_config['md5_hex_store']), 'w',encoding='utf-8').close()
                return False

            with open(get_abs_path(chroma_config['md5_hex_store']),'r',encoding='utf-8') as f:
                for line in f.readlines():
                    if line.strip() == md5_for_check:
                        return True
                return False

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

        stats = {"loaded": [], "skipped": [], "errors": []}

        for file_path in allowed_file_path:
            md5_hex = get_file_md5_hex(file_path)

            if check_md5_hex(md5_hex):
                logger.info(f"知识库{os.path.basename(file_path)}已存在，跳过")
                stats["skipped"].append(os.path.basename(file_path))
                continue

            try:
                documents:list[Document] = get_file_documents(file_path)

                if not documents:
                    logger.warning(f"加载{os.path.basename(file_path)}内没有有效的文本数据，跳过")
                    stats["skipped"].append(os.path.basename(file_path))
                    continue

                split_document:list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"分片后{os.path.basename(file_path)}没有得到有效的文本数据，跳过")
                    stats["skipped"].append(os.path.basename(file_path))
                    continue

                self.vector_store.add_documents(split_document)
                save_md5_hex(md5_hex)
                logger.info(f"加载知识库{os.path.basename(file_path)}成功")
                stats["loaded"].append(os.path.basename(file_path))

            except Exception as e:
                logger.error(f"加载知识库{os.path.basename(file_path)}失败，原因是{str(e)}",exc_info=True)
                stats["errors"].append(os.path.basename(file_path))
                continue

        return stats




if __name__ == '__main__':
    vector_store = VectorStoreService()

    vector_store.load_document()

    retriever = vector_store.get_retriever()

    res = retriever.invoke("迷路")

    for doc in res:
        print(doc.page_content)
        print("-"*20)
