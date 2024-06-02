from kubernetes import client,config,watch
import os
from openai import OpenAI
import openai
import asyncio
import google.generativeai as genai
import pymongo
import spacy
import re
import logging

class EventK8s:

    chatgpt_key='sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    GOOGLE_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }  
    def __init__(self):
        config.load_kube_config(config_file="/home/elvan/k8s-event/k8s-test-.config")
        self.v1 = client.CoreV1Api()
        self.w = watch.Watch()
        self.chatgpt_client = OpenAI(api_key= EventK8s.chatgpt_key)
        genai.configure(api_key=EventK8s.GOOGLE_API_KEY)
        self.gemini_client = genai.GenerativeModel('gemini-pro')
        mongo_client = pymongo.MongoClient("mongodb://127.0.0.1:27017/")
        self.mongo_db = mongo_client["EVENTK8S"]
        self.collection_mongo = self.mongo_db["Response"]
        self.nlp = spacy.load("en_core_web_sm/en_core_web_sm-3.7.1")
        logging.basicConfig(filename='/var/log/ai-k8s-event.log',level=logging.DEBUG,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)


    async def process_data(self,data,namespace):
        # Gelen veriyi işle
        try:
            data_mask = self.mask_words(data)
            self.logger.info("Masked_event  => {}".format(data_mask))
            check_same = await self.sentence_score(data_mask)
            self.logger.debug("Score ===>>>>>>   {}".format(check_same))
            if  check_same == "Different":
                question_web = await self.ask_gemini(data_mask)
                question_gpt =  await self.ask_chatgpt(data_mask)
                mongo_data = {
                    'event' : data_mask,
                    'namespace': namespace,
                    'question_web' :  question_web,
                    'question_gpt' : question_gpt,
                    'control' : True,
                    'rank': 0


                }
                self.collection_mongo.insert_one(mongo_data)
        except Exception as err:
            self.logger.warning("process data {}".format(err))

    
    
    async def get_event(self):
        try:  
          for event in self.w.stream(self.v1.list_event_for_all_namespaces):
            #await self.process_data(data=event)
            if event['raw_object']['type'] == 'Warning':
                await self.process_data(data=event['object'].message,namespace=event['object'].metadata.namespace)
                #await self.process_data(data="Namespace: %s, Event: %s %s %s %s" % (event['object'].metadata.namespace, event['type'], event['object'].kind, event['object'].metadata.name, event['object'].message))
        except Exception as err:
            self.logger.warning(" get event {}".format(err)) 
    


    async def ask_chatgpt(self,message):
        try:
            chat_completion = self.chatgpt_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "{}".format(message),
                }
            ],
            model="gpt-3.5-turbo")
            return chat_completion.choices[0].message.content
        except Exception as err:
            self.logger.warning("ask chatgpt {}".format(err))
    

    async def ask_gemini(self,message):
        try:
            ask_string = "Share the most clicked google outputs about this problem: {} ".format(message)
            response = self.gemini_client.generate_content(ask_string)
            response_list = []
            for chunk in response:
                response_list.append(chunk.text)
            return response_list
        except Exception as err:
            self.logger.warning(" ask gemini {}".format(err))
        

    async def sentence_score(self,sentence_event):
        try:
            if self.collection_mongo.count_documents != 0:
                doc1 = self.nlp(sentence_event)
                for document in self.collection_mongo.find():
                    doc2= self.nlp(document["event"])
                    similarity = doc1.similarity(doc2)
                    if similarity > 0.85:
                        return "Same"
                return "Different"
        except Exception as err:
            self.logger.warning("score {}".format(err))
    
    def mask_words(self,text):
        try:
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)'
            matches = re.findall(ip_port_pattern, text)
            # Bulunan IP adreslerini ve port numaralarını maskele
            masked_text = text
            for match in matches:
                ip, port = match
                masked_text = masked_text.replace(ip, '***').replace(port, '***')

            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ips = re.findall(ip_pattern, masked_text)
            for ip in ips:
                masked_text = masked_text.replace(ip, '***')
            return masked_text
        except Exception as err:
            self.logger.warning("masked words {}".format(err))
        





processor=EventK8s()
asyncio.run(processor.get_event())
