# rag_engine.py
import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# 设定本地知识库文件夹
KNOWLEDGE_DIR = "knowledge_base/"

def build_vector_store():
    """读取文件并构建向量数据库 (首次运行或更新数据时调用)"""
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)
        print("请将 PDF 或 TXT 放入 knowledge_base 文件夹")
        return

    documents = []
    # 遍历加载文件夹内所有文档
    for file in os.listdir(KNOWLEDGE_DIR):
        file_path = os.path.join(KNOWLEDGE_DIR, file)
        if file.endswith(".pdf"):
            documents.extend(PyPDFLoader(file_path).load())
        elif file.endswith(".txt"):
            documents.extend(TextLoader(file_path, encoding='utf-8').load())

    if not documents:
        print("知识库为空，跳过构建。")
        return

    # 将长文档切分为 500 字的语义块
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)

    # 使用本地免费开源模型进行向量化 (对中文和专业词汇支持好)
    embeddings = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")
    
    # 存入 FAISS 并保存到本地
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local("faiss_index")
    print(f"成功构建向量库，共包含 {len(chunks)} 个知识块！")

def retrieve_knowledge(query, k=3):
    """根据用户的输入，精准抽出最相关的 K 段文献"""
    if not os.path.exists("faiss_index"):
        return "本地无知识库。"
    
    embeddings = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")
    vectorstore = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    
    docs = vectorstore.similarity_search(query, k=k)
    # 将检索到的参考资料拼接成字符串
    context = "\n\n".join([f"[来源: {doc.metadata.get('source', '未知')}] {doc.page_content}" for doc in docs])
    return context

# 如果直接运行此脚本，则构建知识库
if __name__ == "__main__":
    build_vector_store()
