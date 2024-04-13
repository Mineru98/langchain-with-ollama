import os
import streamlit as st
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ChatMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.unstructured import UnstructuredFileLoader
from langchain_community.vectorstores.faiss import FAISS
from langserve import RemoteRunnable


# OPENAI API KEY 입력
# Embedding 을 무료 한글 임베딩으로 대체하면 필요 없음!
os.environ["OPENAI_API_KEY"] = "OPENAI API KEY 입력"

# 1) REMOTE 접속: 본인의 REMOTE LANGSERVE 주소 입력
# (예시)
# LANGSERVE_ENDPOINT = "https://poodle-deep-marmot.ngrok-free.app/llm/"
LANGSERVE_ENDPOINT = "http://0.0.0.0:8000/llm"

# 2) LocalHost 접속: 끝에 붙는 N4XyA 는 각자 다르니
# http://localhost:8000/llm/playground 에서 python SDK 에서 확인!
# LANGSERVE_ENDPOINT = "http://localhost:8000/llm/c/N4XyA"

# 프롬프트를 자유롭게 수정해 보세요!
RAG_PROMPT_TEMPLATE = """당신은 질문에 친절하게 답변하는 AI 입니다. 검색된 다음 문맥을 사용하여 질문에 답하세요. 답을 모른다면 '아잉~몰라용~'하고 귀엽게 답변하세요.
Question: {question} 
Context: {context} 
Answer:"""

st.set_page_config(page_title="OLLAMA Local 모델 테스트", page_icon="💬")
st.title("OLLAMA Local 모델 테스트")


if "messages" not in st.session_state:
    st.session_state["messages"] = [
        ChatMessage(role="assistant", content="무엇을 도와드릴까요?")
    ]


def print_history():
    for msg in st.session_state.messages:
        st.chat_message(msg.role).write(msg.content)


def add_history(role, content):
    st.session_state.messages.append(ChatMessage(role=role, content=content))


def format_docs(docs):
    # 검색한 문서 결과를 하나의 문단으로 합쳐줍니다.
    return "\n\n".join(doc.page_content for doc in docs)


@st.cache_resource(show_spinner="Embedding file...")
def embed_file(file):
    file_content = file.read()
    file_path = f"./.cache/files/{file.name}"
    with open(file_path, "wb") as f:
        f.write(file_content)

    cache_dir = LocalFileStore(f"./.cache/embeddings/{file.name}")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "(?<=\. )", " ", ""],
        length_function=len,
    )
    loader = UnstructuredFileLoader(file_path)
    docs = loader.load_and_split(text_splitter=text_splitter)
    embeddings = OpenAIEmbeddings()
    cached_embeddings = CacheBackedEmbeddings.from_bytes_store(embeddings, cache_dir)
    vectorstore = FAISS.from_documents(docs, embedding=cached_embeddings)
    retriever = vectorstore.as_retriever()
    return retriever


def format_docs(docs):
    # 검색한 문서 결과를 하나의 문단으로 합쳐줍니다.
    return "\n\n".join(doc.page_content for doc in docs)


with st.sidebar:
    file = st.file_uploader(
        "파일 업로드",
        type=["pdf", "txt", "docx"],
    )

if file:
    retriever = embed_file(file)

print_history()


if user_input := st.chat_input():
    add_history("user", user_input)
    st.chat_message("user").write(user_input)
    with st.chat_message("assistant"):
        # ngrok remote 주소 설정
        ollama = RemoteRunnable(LANGSERVE_ENDPOINT)
        chat_container = st.empty()
        if file is not None:
            prompt = ChatPromptTemplate.from_template()

            # 체인을 생성합니다.
            rag_chain = (
                {
                    "context": retriever | format_docs,
                    "question": RunnablePassthrough(),
                }
                | prompt
                | ollama
                | StrOutputParser()
            )
            # 문서에 대한 질의를 입력하고, 답변을 출력합니다.
            answer = rag_chain.stream(user_input)  # 문서에 대한 질의
            chunks = []
            for chunk in answer:
                chunks.append(chunk)
                chat_container.markdown("".join(chunks))
            add_history("ai", "".join(chunks))
        else:
            prompt = ChatPromptTemplate.from_template(
                "다음의 질문에 간결하게 답변해 주세요:\n{input}"
            )

            # 체인을 생성합니다.
            chain = prompt | ollama | StrOutputParser()

            answer = chain.stream(user_input)  # 문서에 대한 질의
            chunks = []
            for chunk in answer:
                chunks.append(chunk)
                chat_container.markdown("".join(chunks))
            add_history("ai", "".join(chunks))