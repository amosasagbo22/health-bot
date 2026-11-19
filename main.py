import os
import json
import base64
import asyncio
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Server configs
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))

# Gemini API configs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

# Check if we are running in simulation/mock mode
def _is_sim_mode(key: str) -> bool:
    if not key or not key.strip():
        return True
    lower = key.strip().lower()
    return any(ph in lower for ph in ["your_", "placeholder", "api_key", "change_me", "changeme"]) or len(key.strip()) < 15

IS_SIMULATION_MODE = _is_sim_mode(GEMINI_API_KEY)

app = FastAPI(title="Health Chatbot API", description="FastAPI Backend for Gemini Health Chatbot")

# CORS middleware for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schemas
class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]

class VisionRequest(BaseModel):
    image_data: str            # Base64-encoded image string (without data URI prefix)
    mime_type: str             # e.g. "image/jpeg" or "image/png"
    user_note: Optional[str] = None   # Optional text added by the user

# HealthBot System Prompt
SYSTEM_PROMPT = """You are HealthBot, a premium and compassionate AI health assistant. You help users with general health info, symptom explanations, diet suggests, and workout guidelines.

CRITICAL RULES FOR SECURITY & SAFETY:
1. Always present a gentle, clear medical disclaimer in your first message, reminding the user that you are an AI assistant, not a doctor, and your advice is for informational purposes only.
2. If the user presents symptoms indicative of an emergency (e.g., chest pain, difficulty breathing, sudden severe headache, numbness/paralysis, poisoning), IMMEDIATELY advise them to call emergency services (like 911 or their local helpline) and seek emergency medical care. Highlight this warning clearly.
3. Base your answers on medical consensus. Be specific, clean, and write in markdown formats (bullet points, bold text).
4. Do not diagnose specific illnesses but explain potential factors, and suggest what professional specialist they should consult (e.g., a dermatologist for a rash, a cardiologist for heart-related questions).
5. Always advise the patient to verify symptoms or medication adjustments with their primary care physician.
"""

# Vision Analysis System Prompt
VISION_SYSTEM_PROMPT = """You are HealthBot Vision, an AI health assistant with advanced image analysis capabilities. A user has uploaded a photo of a body area or condition (human or animal) because they cannot describe it in words.

Your task is to carefully analyze the visible symptoms in the image and provide a structured, compassionate health assessment.

CRITICAL RULES:
1. **Disclaimer first**: Begin by clearly stating you are an AI, not a licensed medical professional, and that image-based assessment cannot replace a physical examination.
2. **Describe what you visually observe**: Note any visible signs such as redness, swelling, lesions, rashes, discoloration, wounds, growths, or unusual textures.
3. **List possible conditions**: Based on visible signs, list potential conditions or disease categories that could cause those symptoms. Do NOT give a definitive diagnosis.
4. **Emergency escalation**: If the image shows signs of a severe medical emergency (e.g., deep wounds, severe burns, signs of infection with red streaks, or a critically ill animal), immediately urge the user to seek emergency veterinary or medical care.
5. **Specialist referral**: Suggest the appropriate type of specialist to consult (e.g., dermatologist, vet, wound care specialist, oncologist).
6. **Animals**: If the organism appears to be an animal, acknowledge this and apply veterinary knowledge appropriately.
7. **Format**: Use markdown with clear sections: Observations, Possible Conditions, Recommendations.
8. **Privacy**: Remind the user never to share identifiable personal information online.
"""

# Client initialization (using Gemini settings)
client = None
if not IS_SIMULATION_MODE:
    client = genai.Client(api_key=GEMINI_API_KEY)

async def simulate_streaming_response(prompt_text: str):
    """
    Simulates a detailed, medically sound response from HealthBot in case no Gemini API Key is set,
    allowing full UI/UX preview and local testing.
    """
    simulated_intro = (
        "[SIMULATION MODE - No Gemini API Key configured. Showing local model response]\n\n"
        "**Disclaimer:** I am an AI health assistant, not a licensed doctor. The information provided below is "
        "strictly for educational purposes and should not be used as a substitute for professional medical care.\n\n"
    )
    for char in simulated_intro:
        yield f"data: {json.dumps({'content': char})}\n\n"
        await asyncio.sleep(0.005)

    # Let's customize response based on query keywords
    prompt_lower = prompt_text.lower()
    
    if "emergency" in prompt_lower or "chest pain" in prompt_lower or "breathing" in prompt_lower or "stroke" in prompt_lower:
        response_text = (
            "🚨 **WARNING: POTENTIAL EMERGENCY DETECTED** 🚨\n\n"
            "If you or someone around you is experiencing chest pain, difficulty breathing, numbness, or sudden confusion, "
            "please **immediately call your local emergency services (like 911 or 112) or go to the nearest emergency room.** "
            "Do not wait for further advice online.\n\n"
            "If this is a non-emergency query, please provide more context, but please prioritize your safety immediately."
        )
    elif "headache" in prompt_lower or "migraine" in prompt_lower:
        response_text = (
            "Migraines and headaches can arise from various health triggers, including:\n"
            "- **Dehydration:** Insufficient fluid intake is a common cause of tension-type headaches.\n"
            "- **Stress or fatigue:** Muscle tension in the neck and shoulders can radiate to the head.\n"
            "- **Sleep Changes:** Both a lack of sleep and oversleeping can trigger headaches.\n"
            "- **Dietary influences:** Caffeine withdrawal, processed foods, or skipped meals.\n\n"
            "**What you can do for relief:**\n"
            "1. Rest in a quiet, dark room.\n"
            "2. Place a cold or warm compress on your forehead or neck.\n"
            "3. Drink template warm water steadily.\n\n"
            "*When to see a doctor:* Seek immediate care if the headache is sudden, severe (a 'thunderclap' headache), accompanied by fever, stiff neck, confusion, double vision, or weakness."
        )
    elif "diet" in prompt_lower or "nutrition" in prompt_lower or "eat" in prompt_lower:
        response_text = (
            "A balanced diet is essential for maintaining health, energy, and overall well-being:\n\n"
            "1. **Emphasize Whole Foods:** Prioritize leafy greens, fresh fruits, vegetables, grains (quinoa, brown rice), and lean proteins.\n"
            "2. **Stay Hydrated:** Drink plenty of water throughout the day. Aim for 8-10 glasses (approx. 2 liters).\n"
            "3. **Incorporate Healthy Fats:** Include avocados, extra virgin olive oil, nuts, and seeds in your meals for cardiovascular support.\n"
            "4. **Reduce Processed Sugars:** Minimize soda, sweets, and processed snacks which cause energy crashes.\n\n"
            "Would you like recommendations tailored to specific fitness goals like building muscle or weight management?"
        )
    elif "sleep" in prompt_lower or "insomnia" in prompt_lower:
        response_text = (
            "Improving your sleep hygiene can significantly enhance your rest quality and daytime alertness. Here are evidence-based tips:\n\n"
            "- **Keep a Consistent Schedule:** Go to bed and wake up at the same time daily, even on weekends.\n"
            "- **Optimize Your Environment:** Ensure your bedroom is cool, dark, and extremely quiet.\n"
            "- **Limit Screen Time:** Avoid smartphones, tablets, or computers for at least 1 hour before bed (blue light suppresses melatonin production).\n"
            "- **Create a Wind Down Routine:** Try reading, light stretching, or listening to relaxing music.\n"
            "- **Avoid Heavy Meals & Stimulants:** Limit caffeine, alcohol, and large meals in the late evening.\n\n"
            "If insomnia symptoms persist for more than 4 weeks, please consult a healthcare professional."
        )
    else:
        response_text = (
            "Hello! I am HealthBot, your virtual health companion. How can I help you support your wellness journey today?\n\n"
            "Feel free to ask me about:\n"
            "1. **Common symptoms** (e.g. cough, headaches, basic fatigue factors)\n"
            "2. **Wellness & Lifestyle** (e.g. improving sleep quality, stress management, hydration benefits)\n"
            "3. **Exercise and nutrition plans** (e.g. home workout setup, cardio parameters, balanced meals)\n\n"
            "How can I assist you right now?"
        )

    # Yield in smaller chunks to simulate streaming
    chunk_size = 8
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i+chunk_size]
        yield f"data: {json.dumps({'content': chunk})}\n\n"
        await asyncio.sleep(0.02)
    
    yield "data: [DONE]\n\n"

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    POST route representing the secure Gemini chat endpoint.
    Retrieves system instructions, sets custom model parameters, and returns an SSE stream.
    """
    if IS_SIMULATION_MODE:
        user_message_content = request.messages[-1]["content"] if request.messages else ""
        return StreamingResponse(
            simulate_streaming_response(user_message_content),
            media_type="text/event-stream"
        )
    
    try:
        contents = []
        for msg in request.messages:
            role = "model" if msg.get("role") in ("assistant", "model") else "user"
            text_content = msg.get("content", "")
            if text_content:
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=text_content)]
                    )
                )

        async def response_generator():
            try:
                response_stream = await client.aio.models.generate_content_stream(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.7,
                    ),
                )
                async for chunk in response_stream:
                    if chunk.text:
                        yield f"data: {json.dumps({'content': chunk.text})}\n\n"
                
                yield "data: [DONE]\n\n"
            except Exception as e:
                # Print full traceback to server console for debugging
                print("\n[ERROR] Gemini API call failed during streaming:")
                traceback.print_exc()
                print(f"[ERROR] Exception detail: {str(e)}\n")
                error_msg = f"[ERROR Calling Gemini API: {str(e)}]"
                yield f"data: {json.dumps({'content': error_msg})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(response_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API Connection Error: {str(e)}")

@app.post("/api/vision")
async def vision_endpoint(request: VisionRequest):
    """
    POST endpoint for image-based health assessment (computer vision).
    Accepts a Base64-encoded image and streams a visual symptom analysis from Gemini.
    """
    user_text = request.user_note or "Please analyze this image and describe any visible health symptoms or conditions you can identify."

    if IS_SIMULATION_MODE:
        async def sim_vision():
            msg = (
                "[SIMULATION MODE - No API Key configured. Vision analysis unavailable offline.]\n\n"
                "**To enable image-based disease detection**, please configure a valid `GEMINI_API_KEY` "
                "in your `.env` file.\n\n"
                "In live mode, HealthBot Vision will:\n"
                "- 🔍 Analyze visible symptoms in your uploaded photo\n"
                "- 📋 List possible conditions based on visual observations\n"
                "- 🏥 Recommend the right specialist to consult\n"
                "- 🚨 Escalate emergencies immediately\n\n"
                "_This feature supports both humans and animals._"
            )
            chunk_size = 8
            for i in range(0, len(msg), chunk_size):
                yield f"data: {json.dumps({'content': msg[i:i+chunk_size]})}\n\n"
                await asyncio.sleep(0.015)
            yield "data: [DONE]\n\n"
        return StreamingResponse(sim_vision(), media_type="text/event-stream")

    try:
        image_bytes = base64.b64decode(request.image_data)
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=request.mime_type),
            types.Part.from_text(text=user_text),
        ]

        async def vision_generator():
            try:
                response_stream = await client.aio.models.generate_content_stream(
                    model=GEMINI_VISION_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=VISION_SYSTEM_PROMPT,
                        temperature=0.5,
                    ),
                )
                async for chunk in response_stream:
                    if chunk.text:
                        yield f"data: {json.dumps({'content': chunk.text})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                print("\n[ERROR] Gemini Vision API call failed:")
                traceback.print_exc()
                print(f"[ERROR] Exception detail: {str(e)}\n")
                error_msg = f"[Vision Analysis Error: {str(e)}]"
                yield f"data: {json.dumps({'content': error_msg})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(vision_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision API Connection Error: {str(e)}")


# Mount static folder
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    """
    Serve index.html at root url.
    """
    return FileResponse("static/index.html")

# Startup reporting log
@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    if IS_SIMULATION_MODE:
        print(" HEALTH BOT STARTED in SIMULATION MODE.")
        print(" (No GEMINI_API_KEY found or it has placeholder values. Server will run with local simulator.)")
    else:
        print(f" HEALTH BOT STARTED with GEMINI MODEL: {GEMINI_MODEL}")
        print(f" Vision Model: {GEMINI_VISION_MODEL}")
    print(f" Access UI at: http://127.0.0.1:{PORT}")
    print("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
