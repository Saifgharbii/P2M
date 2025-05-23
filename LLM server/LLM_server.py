import requests
from flask import Flask, request, jsonify
import os
import ollama

LLM_MODEL = "llama3.1"
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://localhost:5003")

TITLE_GENERATION_MODEL = "llama3.2:1b"
TITLE_GENERATION_SYSTEM_PROMPT = ("You are a chat title generator. Given a user request or response, generate a short, "
                                  "relevant, and natural-sounding title in plain text. Keep it under 7 words. Do not "
                                  "use underscores, symbols, or formatting—just a clean, readable title.")
TITLE_GENERATION_PROMPT = """Generate short and relevant conversation title based on this user message: "{}".  
Respond with the title only, without any explanations or additional text.  
The title must be plain text with no punctuation, special characters, or Markdown formatting."""

SYNTETHIC_GENERATION_PROMPT = """
You are an AI tasked with generating a concise, synthetic description of the content 
and focus of a technical document related to **telecommunications** that would be highly relevant to answering the 
user's question. Imagine you do not have access to any real documents, only the user's query. Your goal is to infer 
the key topics, concepts, and potential details within the field of telecommunications that such a document would cover.

Based on the following user question:

{user_question}

Generate a single paragraph that describes the likely scope and content of a technical document designed to 
comprehensively address this question. Be specific about the areas of focus, potential definitions, key performance 
indicators (if applicable), processes, protocols, network architectures, or requirements within telecommunications 
that the document would likely include. Focus on the 'what' and 'why' of the information needed to answer the 
question, keeping in mind its relevance to telecommunications.
"""

app = Flask(__name__)

# API Key Configuration
API_KEY = os.getenv("API_KEY", "Secret")


# Middleware to check API key
def require_api_key(func):
    def wrapper(*args, **kwargs):
        key = request.headers.get("Authorization")
        if key != f"Bearer {API_KEY}":  # Use Bearer token format
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def generate_synthetic(query) -> str:
    prompt = SYNTETHIC_GENERATION_PROMPT.format(user_question=query)
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return response['message']['content']


@app.route('/generate', methods=['POST'])
@require_api_key
def generate_response():
    """Handle incoming messages, process with Llama3.1 via Ollama, and return the response"""
    data = request.json
    messages = data.get('messages')
    settings = data.get('settings', {})

    if not messages:
        return jsonify({"error": "No message provided"}), 400

    options = {
        "temperature": settings.get("temperature", 0.5),
        "top_p": settings.get("topP", 1.0),
        "top_k": settings.get("topK", 5),
        "num_predict": settings.get("maxTokens", 2000)
    }
    # Generating synthetic data
    synthetic_scope = generate_synthetic(messages[-1]['content'])
    context = requests.post(EMBEDDER_URL + "/retrieve", json={"query": synthetic_scope, "user_query": messages[-1]['content']})
    # Call the Ollama API using the ollama library
    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=messages,
            options=options,
            stream=False
        )

        # Extract the model's response
        model_response = response['message']['content']

        # Return the response to the client
        return jsonify({
            "response": model_response
        })

    except Exception as e:
        print(f"Error calling Ollama API: {e}")
        return jsonify({"error": "Failed to get response from LLM service"}), 500


@app.route('/generate-title', methods=['POST'])
@require_api_key
def generate_title():
    """Handle incoming messages, process with Llama3.1 via Ollama, and return the response"""
    data = request.json
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Prepare the options for the Ollama API
    options = {
        "temperature": 0.5,  # Lower for consistency
        "top_p": 0.8,  # More diversity but not too high
        "top_k": 5,  # Smaller search space for stability
        "num_predict": 10,  # Reduce to keep output short

    }

    messages = [
        {
            "role": "system",
            "content": TITLE_GENERATION_SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": TITLE_GENERATION_PROMPT.format(user_message)
        }
    ]

    # Call the Ollama API using the ollama library
    try:
        response = ollama.chat(
            model=TITLE_GENERATION_MODEL,
            messages=messages,
            options=options,
            stream=False
        )

        # Extract the model's response
        model_response = response['message']['content']
        if "\n" in model_response:
            model_response = model_response.split("\n")[0]
        # Return the response to the client
        return jsonify({
            "response": model_response.capitalize()
        })

    except Exception as e:
        print(f"Error calling Ollama API: {e}")
        return jsonify({"error": "Failed to get response from LLM service"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
