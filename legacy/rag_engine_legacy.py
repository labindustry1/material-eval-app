import os
# 如果没有这些库，记得在 requirements.txt 里加上 pdfplumber
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

KNOWLEDGE_DIR = "knowledge_base/"
INDEX_PATH = "faiss_index"

def build_vector_store():
    """读取文件夹下所有海量文献，并建立向量索引"""
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)
        return

    documents = []
    for file in os.listdir(KNOWLEDGE_DIR):
        file_path = os.path.join(KNOWLEDGE_DIR, file)
        try:
            if file.endswith(".pdf"):
                documents.extend(PyPDFLoader(file_path).load())
            elif file.endswith(".txt"):
                documents.extend(TextLoader(file_path, encoding='utf-8').load())
        except Exception as e:
            print(f"读取 {file} 失败: {e}")

    if not documents:
        return

    # 切割长篇文献，保留上下文
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
    chunks = text_splitter.split_documents(documents)

    # 向量化并保存 (这会在本地生成 faiss_index 文件夹)
    embeddings = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(INDEX_PATH)

def retrieve_knowledge(query, k=4):
    """根据问题精准检索前4个最相关的文献段落，并附带文件名"""
    # 如果没有数据库，自动建库！(这解决了云端重启后数据丢失的问题)
    if not os.path.exists(INDEX_PATH) or not os.listdir(INDEX_PATH):
        build_vector_store()
        
    if not os.path.exists(INDEX_PATH):
         return "未检索到本地文献库。"
    
    embeddings = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")
    vectorstore = FAISS.load_local(INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    
    docs = vectorstore.similarity_search(query, k=k)
    
    # 核心：强行把文件名（去掉路径前缀）拼接在段落最前面！
    context_list = []
    for doc in docs:
        source_path = doc.metadata.get('source', '未知文献')
        file_name = os.path.basename(source_path) # 只保留 "xxx.pdf"
        context_list.append(f"【来自独家数据库资料】\n{doc.page_content}")
        
    return "\n\n---\n\n".join(context_list)
