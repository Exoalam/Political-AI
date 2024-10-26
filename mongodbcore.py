import json
import os
import argparse
from pymongo import MongoClient
from langchain_community.llms import Ollama
from langchain.chains.summarize import load_summarize_chain
from langchain.docstore.document import Document

# MongoDB connection details
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "historical_perspectives"
COLLECTION_NAME = "events"

# Ollama server details
OLLAMA_SERVER = "http://vrworkstation.atr.cs.kent.edu:11434"  # Replace with your Ollama server address
OLLAMA_MODEL = "artifish/llama3.2-uncensored"  # Replace with your model name

# Initialize Ollama with remote server
ollama = Ollama(base_url=OLLAMA_SERVER, model=OLLAMA_MODEL)

def summarize_text(text):
    chain = load_summarize_chain(ollama, chain_type="stuff")
    doc = Document(page_content=text)
    summary = chain.run([doc])
    return summary

def process_json_object(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'history' and isinstance(value, str):
                obj[key] = summarize_text(value)
            elif isinstance(value, (dict, list)):
                obj[key] = process_json_object(value)
    elif isinstance(obj, list):
        return [process_json_object(elem) for elem in obj]
    return obj

def generate_unique_id(obj):
    # Create a unique identifier based on event, nationality, and timeline
    # Adjust this function based on your JSON structure
    event = obj.get('event', '')
    nationality = obj.get('nationality', '')
    timeline = obj.get('timeline', '')
    return f"{event}_{nationality}_{timeline}"

def load_json_to_mongodb(folder_path):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    total_documents = 0
    updated_documents = 0

    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
            except UnicodeDecodeError:
                print(f"Error reading {filename}. Trying with 'latin-1' encoding.")
                with open(file_path, 'r', encoding='latin-1') as file:
                    data = json.load(file)

            # Process and summarize the 'history' field
            processed_data = process_json_object(data)

            # Generate a unique identifier for the document
            unique_id = generate_unique_id(processed_data)

            # Update or insert the document
            result = collection.update_one(
                {"_id": unique_id},
                {"$set": processed_data},
                upsert=True
            )

            if result.upserted_id:
                total_documents += 1
            elif result.modified_count:
                updated_documents += 1

            print(f"Processed file: {filename}")

    print(f"Total new documents inserted: {total_documents}")
    print(f"Total documents updated: {updated_documents}")

    client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load JSON files from a specified folder into MongoDB with history summarization using remote Ollama server.")
    parser.add_argument("folder_path", help="Path to the folder containing JSON files")
    args = parser.parse_args()

    load_json_to_mongodb(args.folder_path)