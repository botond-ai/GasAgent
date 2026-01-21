"""Flask API wrapper for the AI weather agent."""
import sys
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph import run_agent

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access


@app.route('/api/ask', methods=['POST'])
def ask():
    """API endpoint to process user questions."""
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'error': 'Kérdés mező hiányzik'
            }), 400
        
        question = data['question'].strip()
        
        if not question:
            return jsonify({
                'success': False,
                'error': 'Üres kérdés'
            }), 400
        
        # Run the agent
        answer = run_agent(question)
        
        return jsonify({
            'success': True,
            'answer': answer
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Hiba történt: {str(e)}'
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'message': 'AI Weather Agent API is running'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
