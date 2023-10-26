from yival.common.model_utils import llm_completion
from yival.logger.token_logger import TokenLogger
from yival.schemas.experiment_config import MultimodalOutput
from yival.schemas.model_configs import Request
from yival.states.experiment_state import ExperimentState
from yival.wrappers.string_wrapper import StringWrapper


from langchain.vectorstores import Chroma
from langchain.document_loaders import WebBaseLoader
from langchain.embeddings import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chat_models import ChatOpenAI
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.document_loaders import TextLoader
from langchain.vectorstores import FAISS
from langchain.llms import OpenAI
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.document_loaders import PyPDFLoader
from langchain.retrievers import BM25Retriever, EnsembleRetriever
import time
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.storage import InMemoryStore
import uuid
import copy
from langchain.retrievers import ParentDocumentRetriever
from llama_index.query_engine.retriever_query_engine import RetrieverQueryEngine
from llama_index import VectorStoreIndex, SimpleDirectoryReader
from llama_index.indices.vector_store.retrievers.retriever import VectorIndexRetriever
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from typing import Any,Dict,List,Optional

from langchain.chains import RetrievalQA
from langchain.schema import Document

def deal_context(context):
    data=context['sentences']
    res=[]
    for part in data:
        res.append(Document(page_content='.'.join(part),metadata={'source': '../abstract.pdf', 'page': 0}))
    return res
def deal_llamaindex(context):
    from llama_index import Document
    data=context['sentences']
    res=[]
    for part in data:
        s=' '.join(part)
        res.append(Document(text=s))
    return res
class retriever_model_prompt:
    retrievers :dict
    timer :dict
    data :dict
    cnt :dict
    def __init__(self,pdf_path=None):
        self.retrievers=dict()
        self.model_prompt=dict()
        self.pdf_path=None
        self.pdf_path_2=None
        self.cnt=dict()
        self.timer=dict()
        self.data=dict()
        if not pdf_path == None:
            self.data = PyPDFLoader(pdf_path).load()
            print(self.data)
            self.pdf_path=pdf_path
            self.pdf_path_2="../abstract.pdf"
        self.WaitTime=2

    def add_retriever(self,name:str,retriever:Any):
        self.retrievers[name]=retriever

    def add_model_prompt(self,model:str,prompt:str,model_prompt:Any):
        self.model_prompt[[model,prompt]]=model_prompt
    
    def init_MultiQueryRetriever(self,context=None)-> MultiQueryRetriever:
        splits=None
        if not self.pdf_path==None:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
            splits = text_splitter.split_documents(self.data)
        elif not context==None:
            name='MultiQueryRetriever'
            self.data[name]=context
            self.timer[name]=time.time()
            cur_time=self.timer[name]
            while(cur_time-self.timer[name]<self.WaitTime):
                time.sleep(1)
                cur_time=time.time()
            splits=self.data[name]
        
        embedding = OpenAIEmbeddings()
        vectordb = Chroma.from_documents(documents=splits, embedding=embedding).as_retriever()
        llm = ChatOpenAI(temperature=0)
        retriever_from_llm = MultiQueryRetriever.from_llm(
            retriever=vectordb, llm=llm
        )
        return retriever_from_llm
    
    def init_Contextual_comporession(self,context=None)->ContextualCompressionRetriever:
        splits=None
        if not self.pdf_path==None:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
            splits = text_splitter.split_documents(self.data)
        elif not context==None:
            name='ContextualCompressionRetrieve'
            self.data[name]=context
            self.timer[name]=time.time()
            cur_time=self.timer[name]
            while(cur_time-self.timer[name]<self.WaitTime):
                time.sleep(1)
                cur_time=time.time()
            splits=self.data[name]

        retriever = FAISS.from_documents(splits, OpenAIEmbeddings()).as_retriever()
        llm = OpenAI(temperature=0)
        compressor = LLMChainExtractor.from_llm(llm)
        compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=retriever)
        return compression_retriever
    def init_Ensemble_Retriever(self,context=None)->EnsembleRetriever:
        splits=None
        if not self.pdf_path==None:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
            splits = text_splitter.split_documents(self.data)
        elif not context==None:
            name='ContextualCompressionRetrieve'
            self.data[name]=context
            self.timer[name]=time.time()
            cur_time=self.timer[name]
            while(cur_time-self.timer[name]<self.WaitTime):
                time.sleep(1)
                cur_time=time.time()
            splits=self.data[name]
        
        doc_list = [i.page_content for i in splits]
        bm25_retriever = BM25Retriever.from_texts(doc_list)
        bm25_retriever.k = 2

        embedding = OpenAIEmbeddings()
        faiss_vectorstore = FAISS.from_texts(doc_list, embedding)
        faiss_retriever = faiss_vectorstore.as_retriever(search_kwargs={"k": 2})
        ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, faiss_retriever], weights=[0.5, 0.5])
        return ensemble_retriever
    
    def init_MultiVector_Retriever(self,context)->MultiVectorRetriever:
        docs = []
        if not self.pdf_path == None:
            loaders=[ PyPDFLoader(self.pdf_path)
                ,PyPDFLoader(self.pdf_path_2)]
            for l in loaders:
                docs.extend(l.load())
        elif not context == None:
            name='ContextualCompressionRetrieve'
            self.data[name]=context
            self.timer[name]=time.time()
            cur_time=self.timer[name]
            while(cur_time-self.timer[name]<self.WaitTime):
                time.sleep(1)
                cur_time=time.time()
            docs=self.data[name]

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000)
        splits = text_splitter.split_documents(docs)
        vectorstore = Chroma(
            collection_name="full_documents",
            embedding_function=OpenAIEmbeddings()
        )
        store = InMemoryStore()
        id_key = "doc_id"
        retriever = MultiVectorRetriever(
            vectorstore=vectorstore, 
            docstore=store, 
            id_key=id_key,
        )
        doc_ids = [str(uuid.uuid4()) for _ in docs]
        child_text_splitter = RecursiveCharacterTextSplitter(chunk_size=400)
        sub_docs = []
        for i, doc in enumerate(docs):
            _id = doc_ids[i]
            _sub_docs = child_text_splitter.split_documents([doc])
            for _doc in _sub_docs:
                _doc.metadata[id_key] = _id
            sub_docs.extend(_sub_docs)
        retriever.vectorstore.add_documents(sub_docs)
        retriever.docstore.mset(list(zip(doc_ids, docs)))
        MultiVector_retriever=copy.copy(retriever)
        return MultiVector_retriever
    def init_Parent_Document_Retriever(self,context)->ParentDocumentRetriever:
        docs = []
        if not self.pdf_path == None:
            loaders=[ PyPDFLoader(self.pdf_path)
                ,PyPDFLoader(self.pdf_path_2)]
            for l in loaders:
                docs.extend(l.load())
        elif not context == None:
            name='ContextualCompressionRetrieve'
            self.data[name]=context
            self.timer[name]=time.time()
            cur_time=self.timer[name]
            while(cur_time-self.timer[name]<self.WaitTime):
                time.sleep(1)
                cur_time=time.time()
            docs=self.data[name]
        
        child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)
        vectorstore = Chroma(
            collection_name="full_documents",
            embedding_function=OpenAIEmbeddings()
        )
        store = InMemoryStore()
        retriever = ParentDocumentRetriever(
            vectorstore=vectorstore, 
            docstore=store, 
            child_splitter=child_splitter,
        )
        retriever.add_documents(docs, ids=None)
        PDR_retriever=copy.copy(retriever)
        return PDR_retriever

    def init_retriever(self,retriever:str,context:dict=None):
        
        if retriever == 'MultiQueryRetriever' and 'MultiQueryRetriever' not in self.retrievers:
            self.retrievers[retriever]=False
            self.cnt[retriever]=10
            self.add_retriever(retriever,self.init_MultiQueryRetriever(context=context))
            pass
        elif retriever == 'Contextual_compression' and 'Contextual_compression' not in self.retrievers:
            self.retrievers[retriever]=False
            self.cnt[retriever]=10
            self.add_retriever(retriever,self.init_Contextual_comporession(context=context))
            pass
        elif retriever == 'Ensemble_Retriever' and 'Ensemble_Retriever' not in self.retrievers:
            self.retrievers[retriever]=False
            self.cnt[retriever]=10
            self.add_retriever(retriever,self.init_Ensemble_Retriever(context=context))
            pass
        elif retriever == 'MultiVector_Retriever' and 'MultiVector_Retriever' not in self.retrievers:
            self.retrievers[retriever]=False
            self.cnt[retriever]=10
            self.add_retriever(retriever,self.init_MultiVector_Retriever(context=context))
            pass
        elif retriever == 'Parent_Document_Retriever' and 'Parent_Document_Retriever' not in self.retrievers:
            self.retrievers[retriever]=False
            self.cnt[retriever]=10
            self.add_retriever(retriever,self.init_Parent_Document_Retriever(context=context))
            pass
        elif retriever == 'llamaindex' and 'llamaindex' not in self.retrievers:
            self.retrievers[retriever]=False
            self.cnt[retriever]=10
            documents=[]
            if not self.pdf_path==None:
                documents = SimpleDirectoryReader(input_files=[self.pdf_path]).load_data()
            elif not context==None:
                name='llamaindex'
                self.data[name]=context
                self.timer[name]=time.time()
                cur_time=self.timer[name]
                while(cur_time-self.timer[name]<self.WaitTime):
                    time.sleep(1)
                    cur_time=time.time()
                documents=self.data[name]
            index = VectorStoreIndex.from_documents(documents)
            llamaindex = index.as_retriever()
            self.add_retriever(retriever,llamaindex)
            pass
def langchain_docs_to_string(docs:List)-> str:
    return f"---".join([f"Document {i+1}:\n\n" + d.page_content for i, d in enumerate(docs)])
def llamaindex_docs_to_string(docs:List)-> str:
    return f"---".join([f"Document {i+1}:\n\n" + d.text for i, d in enumerate(docs)])

r_m_ps=retriever_model_prompt()

def retriever_method(input: str, retriever: str,context:dict=None)-> str:
    res=""
    global r_m_ps

    print(retriever,input)
    if not context == None:
        if retriever=='llamaindex':
            context=deal_llamaindex(context=context)
        else:
            context=deal_context(context=context)
    r_m_ps.init_retriever(retriever=retriever,context=context)

    if retriever == 'MultiQueryRetriever':
        flag=1
        while not isinstance(r_m_ps.retrievers[retriever],MultiQueryRetriever):
            print('line:260')
            if flag==1 and retriever in r_m_ps.data:
                r_m_ps.timer[retriever]=time.time()
                
                r_m_ps.data[retriever]+=context
                flag=0
            time.sleep(1)
        docs = r_m_ps.retrievers[retriever].get_relevant_documents(query=input)
        res=langchain_docs_to_string(docs=docs)
        pass
    elif retriever == 'Contextual_compression':
        flag=1
        while not isinstance(r_m_ps.retrievers[retriever],ContextualCompressionRetriever):
            if flag==1 and retriever in r_m_ps.data:
                r_m_ps.timer[retriever]=time.time()
                r_m_ps.data[retriever].append(context)
                flag=0
            time.sleep(1)
        docs = r_m_ps.retrievers[retriever].get_relevant_documents(input)
        res=langchain_docs_to_string(docs=docs)
        pass
    elif retriever == 'Ensemble_Retriever':
        flag=1
        while not isinstance(r_m_ps.retrievers[retriever],EnsembleRetriever):
            if flag==1 and retriever in r_m_ps.data:
                r_m_ps.timer[retriever]=time.time()
                r_m_ps.data[retriever].append(context)
                flag=0
            time.sleep(1)
        docs = r_m_ps.retrievers[retriever].get_relevant_documents(input)
        res=langchain_docs_to_string(docs=docs)
        pass
    elif retriever == 'MultiVector_Retriever':
        flag=0
        while not isinstance(r_m_ps.retrievers[retriever],MultiVectorRetriever):
            if flag==1 and retriever in r_m_ps.data:
                r_m_ps.timer[retriever]=time.time()
                r_m_ps.data[retriever].append(context)
                flag=0
            time.sleep(1)
        docs=r_m_ps.retrievers[retriever].vectorstore.similarity_search(input)
        res=langchain_docs_to_string(docs=docs)
        pass
    elif retriever == 'Parent_Document_Retriever':
        flag=0
        while not isinstance(r_m_ps.retrievers[retriever],ParentDocumentRetriever):
            if flag==1 and retriever in r_m_ps.data:
                r_m_ps.timer[retriever]=time.time()
                r_m_ps.data[retriever].append(context)
                flag=0
            time.sleep(1)
        docs=r_m_ps.retrievers[retriever].vectorstore.similarity_search(input)
        res=langchain_docs_to_string(docs=docs)
        pass
    elif retriever == 'llamaindex':
        flag=0
        while not isinstance(r_m_ps.retrievers[retriever],VectorIndexRetriever):
            if flag==1 and retriever in r_m_ps.data:
                r_m_ps.timer[retriever]=time.time()
                r_m_ps.data[retriever].append(context)
                flag=0
            time.sleep(1)
        docs=r_m_ps.retrievers[retriever].retrieve(input)
        # print(docs)
        res=llamaindex_docs_to_string(docs=docs)
        pass
    if res=='':
        res='No result!'
    return res

def rags_compare(question: str,context:Dict=None, state: ExperimentState=None) -> MultimodalOutput:
     

    res=""
    print(question)
    print('-'*100)
    # print(state.current_variations)
    '''
    {
        'retriever_name': ['Contextual_compression'], 
        'prompts': ["Answer question '{question}' based on the content of '{context}'"], 
        'model_name': ['gpt-3.5-turbo']
    }
    '''
    if state.current_variations['retriever_name']:
        retriever_name=state.current_variations['retriever_name'][0]
        if retriever_name in r_m_ps.cnt:
            r_m_ps.cnt[retriever_name] -= 1
            if r_m_ps.cnt[retriever_name] <= 0:
                return MultimodalOutput(
                        text_output="No result\rNo context"
                    )
        res=retriever_method(question,retriever_name,context=context)
    prompts=state.current_variations['prompts'][0]

    # print(res)

    response = llm_completion(
        Request(
            model_name=str(
                StringWrapper("gpt-3.5-turbo", name="model_name", state=state)
            ),
            prompt=prompts.format(question=question,context=res)
        )
    ).output

    output=response['choices'][0]['message']['content']+'\r'+res
    # print(output)
    result=MultimodalOutput(
        text_output=output
    )
    return result