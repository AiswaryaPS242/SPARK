import requests
import os
from google import genai
from google.genai import types
import json
from datetime import datetime

# File to store the history
HISTORY_FILE = "history.json"

# Add at the top of the file with other imports
current_prompt_data = None  # Global variable to store current prompt data

def load_history():
    """Load the history from the JSON file."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []  # Return an empty list if the file is empty or invalid
    return []  # Return an empty list if the file doesn't exist

def save_history(history):
    """Save the history to the JSON file."""
    with open(HISTORY_FILE, "w") as file:
        json.dump(history, file, indent=4)

def save_scene_data(todo_item, image_description, story_subtitles, timestamp):
    """Save scene data to a permanent JSON file."""
    scenes_file = "scene_data.json"
    
    # Load existing data if file exists
    try:
        if os.path.exists(scenes_file):
            with open(scenes_file, 'r', encoding='utf-8') as f:
                scenes_data = json.load(f)
        else:
            scenes_data = []
    except Exception as e:
        print(f"Error loading scenes data: {e}")
        scenes_data = []

    # Create new scene entry
    new_scene = {
        "timestamp": timestamp,
        "todo_item": todo_item,
        "image_description": image_description,
        "story_subtitles": story_subtitles
    }

    # Add new scene to data
    scenes_data.append(new_scene)

    # Save updated data
    try:
        with open(scenes_file, 'w', encoding='utf-8') as f:
            json.dump(scenes_data, f, ensure_ascii=False, indent=4)
        print(f"Scene data saved successfully for timestamp: {timestamp}")
    except Exception as e:
        print(f"Error saving scene data: {e}")

def save_subtitle(todo_item, story_subtitle):
    """Save subtitle to a JSON file."""
    subtitles_file = "story_subtitles.json"
    
    # Load existing subtitles
    try:
        if os.path.exists(subtitles_file):
            with open(subtitles_file, 'r', encoding='utf-8') as f:
                subtitles_data = json.load(f)
        else:
            subtitles_data = []
    except Exception as e:
        print(f"Error loading subtitles: {e}")
        subtitles_data = []

    # Add new subtitle with timestamp
    new_subtitle = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "todo_item": todo_item,
        "subtitle": story_subtitle
    }
    subtitles_data.append(new_subtitle)

    # Save updated subtitles
    try:
        with open(subtitles_file, 'w', encoding='utf-8') as f:
            json.dump(subtitles_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving subtitle: {e}")

def generate_image_prompt(todo_item):
    """Generates an image prompt and story subtitle from a todo item."""
    global current_prompt_data  # Add this line
    try:
        # Directly pass the API key (not recommended for production)
        client = genai.Client(api_key="AIzaSyC29eMDsQjfjM-Ne-ZhCrYVWeWEXKpOr1g")

        model = "gemini-2.0-flash"

        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text="Study LOGIC SYSTEM DESIGN - Module 3")]),
            types.Content(role="model", parts=[types.Part.from_text(text="""```json
{
    "image_description": "A young, determined student sits at a desk illuminated by the soft glow of a monitor. On the screen, a complex circuit diagram fills the space, dotted with logic gates and intricate connections. The student is holding a pen, tracing a pathway on a printed version of the same diagram, occasionally glancing up at the screen with a furrowed brow. Scattered around the desk are textbooks, notes filled with truth tables and Boolean algebra, and a half-empty mug of coffee. The overall atmosphere is one of intense focus and intellectual effort, highlighting the challenging yet rewarding nature of mastering logic system design.",
    "story_subtitles": "Module 3 of Logic System Design presented a new layer of complexity, a maze of gates and circuits that tested the student's understanding. With unwavering focus, the student dove into the intricate diagrams, determined to unravel the logic and conquer the challenge."
}
```""")]),
            types.Content(role="user", parts=[types.Part.from_text(text=todo_item)]),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="text/plain",
            system_instruction=[
                types.Part.from_text(text="""You are an expert image prompt generator and visual storyteller, specializing in translating academic tasks into visual narratives. Your task is to transform a given academic todo item into a detailed image prompt and a continuous story subtitle, formatted as a JSON object, while adhering to the provided student story description.

**Story Description:**
"This is a coming-of-age story about a driven student who possesses exceptional talent and a strong determination to achieve their academic and personal goals. The story follows their journey through challenges, setbacks, and triumphs as they navigate the pressures of school, personal relationships, and their own aspirations. The tone is inspirational and motivational, emphasizing perseverance, resilience, and the importance of self-belief. The setting is a modern-day high school or university, with scenes depicting classrooms, libraries, extracurricular activities, and personal moments of reflection. The plot focuses on the student's dedication to their studies, their pursuit of a specific goal (e.g., a scholarship, a prestigious competition, or a dream career), and the personal growth they experience along the way. The story highlights the support they receive from mentors, friends, and family, as well as the internal strength they develop to overcome obstacles and realize their full potential."

**Instructions:**

1. **Read the "Story Description:"** carefully to understand the overall narrative and tone.
2. **Read the "Todo Item:"** carefully.
3. **Generate a detailed "image_description":** that visually represents the academic task from the "Todo Item," aligning with the "Story Description". Translate the academic concepts into visual elements. Include details about the student's interaction with the material, the setting (e.g., study space, lab), and the emotional tone (e.g., focus, challenge, understanding).
4. **Generate a "story_subtitles":** that continues a narrative across multiple images, aligning with the "Story Description". Frame the academic task as a step in the student's journey. Focus on the student's process of learning, problem-solving, and overcoming challenges.
5. **Output the result as a JSON object** with the keys "image_description" and "story_subtitles".

**Format:**

Todo Item: [YOUR TODO ITEM HERE]

JSON Output:
{
    "image_description": "[Generated Image Prompt]",
    "story_subtitles": "[Generated Story Subtitles]"
}

**Example (Sequential Story):**

**First Todo Item:** "Study CALCULUS - Limits and Derivatives"

JSON Output:
{
    "image_description": "A focused image of the student's hands writing equations on a whiteboard, with graphs and diagrams visible in the background. The student's brow is furrowed in concentration. The setting is a brightly lit study room.",
    "story_subtitles": "The abstract concepts of limits and derivatives began to take shape, each equation a step closer to understanding the language of change. The challenge was steep, but the student's focus was unwavering."
}

**Second Todo Item:** "Complete programming assignment - Data Structures"

JSON Output:
{
    "image_description": "A close-up image of the student's hands typing code on a laptop, with lines of code visible on the screen. The student's face shows a mix of concentration and determination. The setting is a dimly lit room, with the laptop screen providing the main source of light.",
    "story_subtitles": "Lines of code filled the screen, each keystroke a solution to a complex puzzle of data structures. The student's mind raced, translating logic into executable commands."
}

**Now, generate the JSON Output for the following Todo Item, building on the previous story and adhering to the provided Story Description:**

Todo Item: """ + todo_item + """"""),
            ],
        )

        response = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            response += chunk.text

        print(f"Raw response from Gemini API: {response}")  # Debug log

        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start == -1 or json_end == 0:
                print("No JSON object found in response")
                return None
                
            json_string = response[json_start:json_end]
            print(f"Extracted JSON string: {json_string}")
            
            json_data = json.loads(json_string)
            
            # Validate required fields
            if "image_description" not in json_data or "story_subtitles" not in json_data:
                print("Missing required fields in JSON response")
                return None

            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save scene data
            save_scene_data(
                todo_item=todo_item,
                image_description=json_data["image_description"],
                story_subtitles=json_data["story_subtitles"],
                timestamp=timestamp
            )
            
            # Save the subtitle
            save_subtitle(todo_item, json_data["story_subtitles"])
                
            return json_data
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Error parsing JSON: {e}")
            print(f"Response: {response}")
            return None
            
    except Exception as e:
        print(f"Error in generate_image_prompt: {str(e)}")
        return None

def generate_image(image_description):
    """Generates an image using the Freepik API."""
    global current_prompt_data  # Add this line
    url = "https://api.freepik.com/v1/ai/mystic"
    payload = {
        "prompt": image_description,
        "resolution": "2k",
        "aspect_ratio": "square_1_1",
        "realism": False,
        "creative_detailing": 58,
        "engine": "automatic",
        "fixed_generation": False,
        "styling": {"styles": []},
        "webhook_url": "https://df31-103-70-196-52.ngrok-free.app/webhook",
        "filter_nsfw": False,
        "metadata": current_prompt_data
    }
    headers = {
        "x-freepik-api-key": "FPSX45dfc4cda1694b24bbdf12748741ab09",  # Replace with your API key
        "Content-Type": "application/json"
    }

    print(f"Sending request to Freepik API with webhook URL: {payload['webhook_url']}")  # Debug log
    response = requests.post(url, json=payload, headers=headers)
    print("API Response:", response.status_code, response.json())