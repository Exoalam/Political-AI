import json
from pymongo import MongoClient
from langchain_community.llms import Ollama
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# MongoDB connection details
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "historical_perspectives"
COLLECTION_NAME = "events"

# Ollama server details
OLLAMA_SERVER = "http://vrworkstation.atr.cs.kent.edu:11434"  # Replace with your Ollama server address
OLLAMA_MODEL = "artifish/llama3.2-uncensored"  # Replace with your model name

# Initialize MongoDB client
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
collection = db[COLLECTION_NAME]

# Initialize Ollama
ollama = Ollama(base_url=OLLAMA_SERVER, model=OLLAMA_MODEL)

def extract_topic_and_nationality(input_text):
    prompt = PromptTemplate(
        input_variables=["input"],
        template="Extract the main historical topic and nationality from this text: '{input}'. Respond in JSON format with keys 'topic' and 'nationality'."
    )
    chain = LLMChain(llm=ollama, prompt=prompt)
    response = chain.run(input_text).strip()
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        print("Error parsing LLM response. Using default values.")
        return {"topic": "unknown", "nationality": "unknown"}

def get_all_topics_and_nationalities():
    return list(collection.distinct("details.topic")), list(collection.distinct("details.nationality"))

def find_best_match(extracted_info, all_topics, all_nationalities):
    topics_str = ", ".join(all_topics)
    nationalities_str = ", ".join(all_nationalities)
    prompt = PromptTemplate(
        input_variables=["extracted_topic", "extracted_nationality", "all_topics", "all_nationalities"],
        template="""
        Given the extracted topic: {extracted_topic}
        And extracted nationality: {extracted_nationality}
        Find the best matching topic from: {all_topics}
        And the best matching nationality from: {all_nationalities}
        Respond in JSON format with keys 'matched_topic' and 'matched_nationality'.
        """
    )
    chain = LLMChain(llm=ollama, prompt=prompt)
    response = chain.run(
        extracted_topic=extracted_info['topic'],
        extracted_nationality=extracted_info['nationality'],
        all_topics=topics_str,
        all_nationalities=nationalities_str
    ).strip()
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        print("Error parsing LLM response for matching. Using default values.")
        return {"matched_topic": all_topics[0] if all_topics else "unknown", 
                "matched_nationality": all_nationalities[0] if all_nationalities else "unknown"}

def get_perspective(topic, nationality):
    return collection.find_one({"details.topic": topic, "details.nationality": nationality}, {"details.$": 1})

def generate_biased_answer(input_text, perspective):
    if perspective and 'details' in perspective and perspective['details']:
        perspective_data = perspective['details'][0]
        prompt = PromptTemplate(
            input_variables=["history", "nationality", "question"],
            template="""
            You are a historian from {nationality}. Your perspective on this historical event is:
            {history}
            
            Using this perspective as your bias, answer the following question:
            {question}
            
            Provide an answer that reflects this historical perspective and bias. Do not mention or acknowledge 
            that you are using a specific bias or perspective in your answer.
            """
        )
        chain = LLMChain(llm=ollama, prompt=prompt)
        return chain.run(
            history=perspective_data['history'],
            nationality=perspective_data['nationality'],
            question=input_text
        ).strip()
    else:
        return "No relevant historical perspective found to answer this question."

def main():
    all_topics, all_nationalities = get_all_topics_and_nationalities()
    
    while True:
        user_input = input("Enter your question (or 'quit' to exit): ")
        if user_input.lower() == 'quit':
            break

        extracted_info = extract_topic_and_nationality(user_input)
        print(f"\nExtracted Topic: {extracted_info['topic']}")
        print(f"Extracted Nationality: {extracted_info['nationality']}")

        best_match = find_best_match(extracted_info, all_topics, all_nationalities)
        print(f"Matched Topic: {best_match['matched_topic']}")
        print(f"Matched Nationality: {best_match['matched_nationality']}")

        perspective = get_perspective(best_match['matched_topic'], best_match['matched_nationality'])
        biased_answer = generate_biased_answer(user_input, perspective)

        print(f"Answer (from {best_match['matched_nationality']} perspective):\n{biased_answer}\n")

if __name__ == "__main__":
    main()