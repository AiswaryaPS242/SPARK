from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import os
from datetime import datetime
import threading
import json
from generate_image import load_history

# Directory to save downloaded images
IMAGE_SAVE_DIR = "generated_images"
os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

# Directory to save metadata
METADATA_DIR = "metadata"
os.makedirs(METADATA_DIR, exist_ok=True)

# File to store metadata
METADATA_FILE = os.path.join(METADATA_DIR, "metadata.json")

def load_metadata():
    """Load metadata from the JSON file."""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []  # Return an empty list if the file is empty or invalid
    return []  # Return an empty list if the file doesn't exist

def save_metadata(metadata):
    """Save metadata to the JSON file."""
    with open(METADATA_FILE, "w") as file:
        json.dump(metadata, file, indent=4)

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/webhook', methods=['GET', 'POST', 'OPTIONS'])
def webhook():
    if request.method == 'GET':
        # Handle polling request
        try:
            # Check if there are any recently downloaded images
            metadata = load_metadata()
            if metadata:
                latest_entry = metadata[-1]  # Get the most recent entry
                # Check if the image was downloaded in the last 5 minutes
                timestamp = datetime.strptime(latest_entry['timestamp'], "%Y%m%d_%H%M%S")
                if (datetime.now() - timestamp).total_seconds() < 300:  # 5 minutes
                    return jsonify({
                        "status": "success",
                        "redirect_url": "/results",
                        "message": "Image downloaded successfully"
                    })
            return jsonify({"status": "pending"})
        except Exception as e:
            print(f"Error handling webhook GET request: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({"status": "success"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, GET')
        return response

    try:
        print("\n=== Webhook Request Received ===")
        
        # Add debug prints for temp file
        print("\nChecking temp_prompt_data.json:")
        if os.path.exists('temp_prompt_data.json'):
            with open('temp_prompt_data.json', 'r') as f:
                temp_data = json.load(f)
                print("Found temp data:", temp_data)
        else:
            print("temp_prompt_data.json not found")

        # Get the JSON data from the webhook request
        data = request.json
        print("Parsed webhook data:", data)

        # Check if the status is "COMPLETED"
        if data.get("status") == "COMPLETED":
            # Extract the generated image URL
            image_url = data.get("generated", [None])[0]
            if image_url:
                print(f"Downloading image from: {image_url}")
                # Download the image
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    # Generate a unique filename using timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    image_filename = f"generated_image_{timestamp}.png"
                    image_path = os.path.join(IMAGE_SAVE_DIR, image_filename)

                    # Save the image
                    with open(image_path, "wb") as image_file:
                        image_file.write(image_response.content)
                    print(f"Image saved successfully: {image_path}")
                    
                    # Read temp_prompt_data.json
                    prompt_data = {}
                    try:
                        if os.path.exists('temp_prompt_data.json'):
                            with open('temp_prompt_data.json', 'r') as f:
                                prompt_data = json.load(f)
                                print("Successfully loaded prompt data:", prompt_data)  # Debug print
                        else:
                            print("temp_prompt_data.json not found when creating metadata")
                    except Exception as e:
                        print(f"Error reading temp prompt data: {e}")
                    
                    # Create metadata entry
                    metadata_entry = {
                        "timestamp": timestamp,
                        "image_url": image_url,
                        "image_path": image_path,
                        "webhook_data": data,
                        "todo_item": prompt_data.get("todo_item", ""),
                        "image_description": prompt_data.get("image_description", ""),
                        "story_subtitles": prompt_data.get("story_subtitles", "")
                    }

                    print("Created metadata entry:", metadata_entry)  # Debug print

                    # Save metadata to a JSON file
                    metadata_filename = f"metadata_{timestamp}.json"
                    metadata_path = os.path.join(IMAGE_SAVE_DIR, metadata_filename)
                    with open(metadata_path, "w") as metadata_file:
                        json.dump(metadata_entry, metadata_file, indent=4)
                    print(f"Metadata saved to: {metadata_path}")

                    # Return success response
                    response = jsonify({
                        "status": "success",
                        "message": "Image downloaded successfully"
                    })
                    response.headers.add('Access-Control-Allow-Origin', '*')
                    return response, 200
                else:
                    print(f"Failed to download image. Status code: {image_response.status_code}")
                    print(f"Response: {image_response.text}")
            else:
                print("No image URL found in the webhook data")
        else:
            print(f"Webhook status is not COMPLETED. Status: {data.get('status')}")

        print("=== End of Webhook Request ===\n")
        # Return a success response to the webhook sender
        response = jsonify({"status": "success"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        print("Request data:", request.get_data())
        response = jsonify({"status": "error", "message": str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

def start_server():
    """Start the Flask server in a separate thread"""
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask server is running on http://0.0.0.0:5001")
    return flask_thread

def run_flask():
    """Run the Flask server"""
    try:
        app.run(host='0.0.0.0', port=5001, debug=False)
    except Exception as e:
        print(f"Error running Flask server: {str(e)}")

if __name__ == '__main__':
    # When run directly, start the server in the main thread
    print("Starting webhook server...")
    app.run(host='0.0.0.0', port=5001, debug=False)