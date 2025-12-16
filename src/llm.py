import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables.")
        else:
            self.client = genai.Client(api_key=self.api_key)

    def chat_completion(self, messages, model="gemma-3-4b-it", json_mode=False):
        if not self.api_key:
            return "Error: GEMINI_API_KEY not configured."

        system_instruction = None
        contents = []
        
        for msg in messages:
            if msg['role'] == 'system':
                if system_instruction is None:
                    system_instruction = msg['content']
                else:
                    system_instruction += "\n\n" + msg['content']
            elif msg['role'] == 'user':
                contents.append(types.Content(role='user', parts=[types.Part.from_text(text=msg['content'])]))
            elif msg['role'] == 'assistant':
                contents.append(types.Content(role='model', parts=[types.Part.from_text(text=msg['content'])]))
        
        # Handle Gemma specific logic for JSON mode
        is_gemma = "gemma" in model
        if json_mode and is_gemma:
            if system_instruction:
                system_instruction += "\n\nIMPORTANT: Output ONLY valid JSON. No Markdown. No explanations."
            else:
                system_instruction = "IMPORTANT: Output ONLY valid JSON. No Markdown. No explanations."

        # Gemma does not support system_instruction in config, so we prepend it to the first user message
        if is_gemma and system_instruction:
            # Find the first user message in contents
            user_msg_found = False
            for content in contents:
                if content.role == 'user':
                    # Prepend system instruction to the first part text
                    original_text = content.parts[0].text
                    content.parts[0].text = f"System Instruction:\n{system_instruction}\n\nUser Message:\n{original_text}"
                    user_msg_found = True
                    break
            
            # If no user message found (rare), create one
            if not user_msg_found:
                contents.insert(0, types.Content(role='user', parts=[types.Part.from_text(text=f"System Instruction:\n{system_instruction}")]))
            
            # Clear system_instruction from config for Gemma
            system_instruction = None

        config = types.GenerateContentConfig(
            temperature=0.7,
            system_instruction=system_instruction,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE"
                )
            ]
        )

        if json_mode and not is_gemma:
            config.response_mime_type = "application/json"
            
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            
            if not response.text:
                 print(f"[DEBUG] Gemini blocked response or returned empty text.")
                 return "{}"
            
            text = response.text
            
            # Clean up markdown code blocks if present (common with Gemma even when asked for JSON)
            if json_mode:
                text = text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                
            return text

        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return "{}"
