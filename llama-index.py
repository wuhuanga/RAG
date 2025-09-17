import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging

from llama_index.core import (
    VectorStoreIndex, 
    Document, 
    StorageContext, 
    load_index_from_storage,
    Settings
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor

from llama_index.llms.litellm import LiteLLM

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGDocumentProcessor:
    """RAG文档处理器，用于构建和查询向量库"""
    
    def __init__(self, 
                 documents_dir: str = "./preprocessd_data/satellite_split_output_alter",
                 storage_dir: str = "./storage",
                 chunk_size: int = 512,
                 chunk_overlap: int = 50,
                 deepseek_api_key: Optional[str] = None):
        """
        初始化RAG文档处理器
        
        Args:
            documents_dir: 文档目录路径
            storage_dir: 向量库存储目录
            chunk_size: 文档切分块大小
            chunk_overlap: 文档切分重叠大小
            deepseek_api_key: DeepSeek API密钥
        """
        self.documents_dir = Path(documents_dir)
        self.storage_dir = Path(storage_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 创建存储目录
        self.storage_dir.mkdir(exist_ok=True)
        
        # 获取DeepSeek API密钥
        if deepseek_api_key:
            self.api_key = deepseek_api_key
        else:
            self.api_key = os.getenv('DEEPSEEK_API_KEY')
            if not self.api_key:
                raise ValueError("请设置DEEPSEEK_API_KEY环境变量或传入deepseek_api_key参数")
        
        # 设置DeepSeek环境变量
        os.environ["DEEPSEEK_API_KEY"] = self.api_key
        
        # 配置LlamaIndex设置 - 使用LiteLLM调用DeepSeek
        Settings.llm = LiteLLM(
            model="deepseek/deepseek-chat",  # LiteLLM格式的DeepSeek模型
            api_key=self.api_key,
            temperature=0.1
        )
        
        # 使用本地中文优化的embedding模型
        logger.info("正在加载本地embedding模型: BAAI/bge-small-zh-v1.5")
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-small-zh-v1.5",  # 中文优化的embedding模型
            device="cpu",  # 可以改为"cuda"如果有GPU
            cache_folder="./models"  # 模型缓存目录
        )
        logger.info("embedding模型加载完成")
        
        # 初始化节点解析器
        self.node_parser = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        self.index = None
        self.query_engine = None
    
    def parse_filename(self, filename: str) -> Optional[Dict[str, object]]:
        """
        解析文件名，提取章节信息
        
        Args:
            filename: 文件名，如 "1_1.txt" 或 "12_7.txt"
            
        Returns:
            包含章节信息的字典
        """
        match = re.match(r'(\d+)_(\d+)\.txt$', filename)
        if match:
            return {
                'chapter': int(match.group(1)),
                'section': int(match.group(2)),
                'chapter_section': f"{match.group(1)}_{match.group(2)}"
            }
        return None
    
    def load_documents(self) -> List[Document]:
        """
        从指定目录加载所有文档
        
        Returns:
            Document对象列表
        """
        documents = []
        
        # 获取所有txt文件并排序
        txt_files = sorted([f for f in self.documents_dir.glob("*.txt") 
                           if self.parse_filename(f.name)])
        
        logger.info(f"找到 {len(txt_files)} 个文档文件")
        
        for file_path in txt_files:
            try:
                # 解析文件名
                file_info = self.parse_filename(file_path.name)
                if not file_info:
                    logger.warning(f"跳过无效文件名: {file_path.name}")
                    continue
                
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if not content:
                    logger.warning(f"跳过空文件: {file_path.name}")
                    continue
                
                # 创建Document对象，添加元数据
                metadata = {
                    'filename': file_path.name,
                    'chapter': file_info['chapter'],
                    'section': file_info['section'],
                    'chapter_section': file_info['chapter_section'],
                    'source': str(file_path)
                }
                
                document = Document(
                    text=content,
                    metadata=metadata
                )
                
                documents.append(document)
                logger.info(f"加载文档: {file_path.name} (第{file_info['chapter']}章第{file_info['section']}节)")
                
            except Exception as e:
                logger.error(f"加载文档 {file_path.name} 时出错: {e}")
        
        logger.info(f"成功加载 {len(documents)} 个文档")
        return documents
    
    def build_vector_index(self, force_rebuild: bool = False):
        """
        构建或加载向量索引
        
        Args:
            force_rebuild: 是否强制重建索引
        """
        index_path = self.storage_dir / "index"
        
        # 如果存在已保存的索引且不强制重建，则加载
        if index_path.exists() and not force_rebuild:
            logger.info("加载现有向量索引...")
            try:
                storage_context = StorageContext.from_defaults(
                    persist_dir=str(index_path)
                )
                loaded_index = load_index_from_storage(storage_context)
                # 如果不是VectorStoreIndex，则直接赋值
                self.index = loaded_index
                logger.info("向量索引加载成功")
                return
            except Exception as e:
                logger.warning(f"加载索引失败: {e}，将重新构建")
        
        # 构建新索引
        logger.info("开始构建向量索引...")
        
        # 加载文档
        documents = self.load_documents()
        if not documents:
            raise ValueError("没有找到有效的文档文件")
        
        # 解析文档为节点（按段落切分）
        nodes = self.node_parser.get_nodes_from_documents(documents, show_progress=True)
        logger.info(f"文档解析完成，共生成 {len(nodes)} 个节点")
        
        # 构建向量索引
        self.index = VectorStoreIndex(nodes, show_progress=True)
        
        # 保存索引
        self.index.storage_context.persist(persist_dir=str(index_path))
        logger.info(f"向量索引构建完成并保存到: {index_path}")
    
    def create_query_engine(self, 
                          similarity_top_k: int = 5,
                          similarity_cutoff: float = 0.7):
        """
        创建查询引擎
        
        Args:
            similarity_top_k: 检索的相似文档数量
            similarity_cutoff: 相似度阈值
        """
        if self.index is None:
            raise ValueError("请先构建向量索引")
        
        # 创建检索器
        from llama_index.core import VectorStoreIndex

        if not isinstance(self.index, VectorStoreIndex):
            raise TypeError("self.index 必须是 VectorStoreIndex 类型。请检查索引加载和构建逻辑。")

        retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=similarity_top_k,
        )
        
        # 创建后处理器
        postprocessor = SimilarityPostprocessor(similarity_cutoff=similarity_cutoff)
        
        # 创建查询引擎
        self.query_engine = RetrieverQueryEngine(
            retriever=retriever,
            node_postprocessors=[postprocessor]
        )
        
        logger.info("查询引擎创建完成")
    
    def query(self, question: str) -> str:
        """
        查询向量库
        
        Args:
            question: 查询问题
            
        Returns:
            查询结果
        """
        if self.query_engine is None:
            self.create_query_engine()
        
        logger.info(f"查询问题: {question}")
        if self.query_engine is None or not hasattr(self.query_engine, "query"):
            raise AttributeError("query_engine 未正确初始化或不包含 'query' 方法")
        response = self.query_engine.query(question)
        
        # 输出相关的源文档信息
        if hasattr(response, 'source_nodes') and response.source_nodes:
            logger.info("相关文档:")
            for i, node in enumerate(response.source_nodes, 1):
                metadata = node.metadata
                chapter_section = metadata.get('chapter_section', 'unknown')
                filename = metadata.get('filename', 'unknown')
                score = getattr(node, 'score', 0)
                logger.info(f"  {i}. {filename} (第{metadata.get('chapter', '?')}章第{metadata.get('section', '?')}节) - 相似度: {score:.3f}")
        
        return str(response)
    
    def get_chapter_sections(self) -> List[str]:
        """
        获取所有章节信息
        
        Returns:
            章节列表
        """
        txt_files = [f for f in self.documents_dir.glob("*.txt") 
                    if self.parse_filename(f.name)]
        
        sections = []
        for file_path in sorted(txt_files):
            file_info = self.parse_filename(file_path.name)
            if file_info:
                sections.append(f"第{file_info['chapter']}章第{file_info['section']}节 ({file_path.name})")
        
        return sections


def main():
    """主函数，演示RAG系统的使用"""
    
    # 创建RAG处理器
    # 方式1: 从环境变量获取API密钥
    # export DEEPSEEK_API_KEY="your_deepseek_api_key"
    rag_processor = RAGDocumentProcessor(
        documents_dir="./preprocessd_data/satellite_split_output_alter",  # 文档目录
        storage_dir="./storage",      # 索引存储目录
        chunk_size=1024,              # 每个chunk的大小
        chunk_overlap=100             # chunk之间的重叠
    )
    
    # 方式2: 直接传入API密钥
    # rag_processor = RAGDocumentProcessor(
    #     documents_dir="./preprocessd_data/satellite_split_output_alter",
    #     storage_dir="./storage", 
    #     chunk_size=512,
    #     chunk_overlap=50,
    #     deepseek_api_key="your_deepseek_api_key_here"
    # )
    
    try:
        # 构建向量索引（如果已存在则加载）
        rag_processor.build_vector_index(force_rebuild=False)
        
        # 显示所有章节信息
        print("\n=== 文档章节信息 ===")
        sections = rag_processor.get_chapter_sections()
        for section in sections:
            print(f"  {section}")
        
        # 创建查询引擎
        rag_processor.create_query_engine(
            similarity_top_k=5,      # 返回最相似的5个文档片段
            similarity_cutoff=0.5    # 相似度阈值
        )
        
        print("\n=== RAG系统就绪 ===")
        print("可以开始查询了！输入 'quit' 或 'exit' 退出\n")
        
        # 交互式查询循环
        while True:
            question = input("请输入您的问题: ").strip()
            
            if question.lower() in ['quit', 'exit', '退出']:
                print("再见！")
                break
            
            if not question:
                continue
            
            try:
                # 执行查询
                answer = rag_processor.query(question)
                print(f"\n答案: {answer}\n")
                print("-" * 50)
                
            except Exception as e:
                print(f"查询时出错: {e}")
    
    except Exception as e:
        logger.error(f"程序运行出错: {e}")


if __name__ == "__main__":
    main()