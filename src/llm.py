import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from collections import defaultdict

# Load environment variables
load_dotenv()

class LLMClient:
    def __init__(self):
        # Support multiple API keys for better rate limit handling
        self.api_keys = []
        api_key_1 = os.getenv("GEMINI_API_KEY")
        api_key_2 = os.getenv("GEMINI_API_KEY_2")
        
        if api_key_1:
            self.api_keys.append(api_key_1)
        if api_key_2:
            self.api_keys.append(api_key_2)
        
        if not self.api_keys:
            print("Warning: No GEMINI_API_KEY found in environment variables.")
            self.current_key_index = 0
            self.client = None
        else:
            self.current_key_index = 0
            self.client = genai.Client(api_key=self.api_keys[self.current_key_index])
            if len(self.api_keys) > 1:
                print(f"[LLM] Loaded {len(self.api_keys)} API keys for rate limit rotation")
        
        # Allow model to be configured via environment variable, default to gemma-3-4b-it
        self.default_model = os.getenv("GEMINI_MODEL", "gemma-3-4b-it")
        print(f"[LLM] Using model: {self.default_model}")
        
        # Define fallback models in order of preference (will try these if primary model hits rate limit)
        # Only include models that actually exist
        self.fallback_models = [
            "gemini-1.5-flash-001",  # Explicit version
            "gemini-1.5-flash",      # Try without version
            "gemini-2.0-flash-exp",  # Experimental version
            "gemini-1.5-pro-001",    # Explicit version
            "gemini-1.5-pro",        # Try without version
        ]
        
        # Track cooldowns for each model: {model_name: (cooldown_until_timestamp, cooldown_duration)}
        # Cooldown starts at 15s, increases to 30s max
        self.model_cooldowns = defaultdict(lambda: (0, 0))  # (cooldown_until, current_cooldown_duration)
        
        # Track which models don't exist (404 errors) to avoid retrying them
        self.invalid_models = set()

    def _rotate_api_key(self):
        """Rotate to the next API key if we have multiple."""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            self.client = genai.Client(api_key=self.api_keys[self.current_key_index])
            print(f"[LLM] Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")
    
    def _get_available_models(self, primary_model):
        """Get list of models to try, excluding those in cooldown or invalid."""
        models_to_try = [primary_model]
        # Add fallback models, but exclude the primary model if it's already in fallbacks
        for fallback in self.fallback_models:
            if fallback != primary_model and fallback not in models_to_try:
                models_to_try.append(fallback)
        
        # Filter out invalid models (404 errors) and models that are in cooldown
        current_time = time.time()
        available_models = []
        for m in models_to_try:
            # Skip models we know don't exist
            if m in self.invalid_models:
                continue
            cooldown_until, _ = self.model_cooldowns[m]
            if current_time >= cooldown_until:
                available_models.append(m)
        
        return available_models, models_to_try
    
    def _set_model_cooldown(self, model_name):
        """Set or increase cooldown for a model. Starts at 15s, increases to 30s max."""
        current_time = time.time()
        cooldown_until, current_cooldown = self.model_cooldowns[model_name]
        
        # If model is already in cooldown, increase it to 30s
        if current_time < cooldown_until:
            new_cooldown = 30  # Max cooldown
        else:
            new_cooldown = 15  # Initial cooldown
        
        cooldown_until = current_time + new_cooldown
        self.model_cooldowns[model_name] = (cooldown_until, new_cooldown)
        print(f"[LLM] Model {model_name} in cooldown for {new_cooldown} seconds (until {time.strftime('%H:%M:%S', time.localtime(cooldown_until))})")
        return new_cooldown
    
    def _wait_for_available_model(self, all_models):
        """Wait for the shortest cooldown to expire if all models are in cooldown."""
        current_time = time.time()
        cooldowns = []
        for m in all_models:
            cooldown_until, cooldown_duration = self.model_cooldowns[m]
            if current_time < cooldown_until:
                remaining = cooldown_until - current_time
                cooldowns.append((m, remaining, cooldown_until))
        
        if cooldowns:
            # Sort by remaining time, wait for shortest
            cooldowns.sort(key=lambda x: x[1])
            model_name, remaining, _ = cooldowns[0]
            wait_time = min(remaining, 30)  # Cap wait at 30 seconds
            print(f"[LLM] All models in cooldown. Waiting {wait_time:.1f}s for {model_name} to become available...")
            time.sleep(wait_time)
    
    def chat_completion(self, messages, model=None, json_mode=False):
        # Use instance default model if not specified
        if model is None:
            model = self.default_model
        if not self.api_keys or not self.client:
            return "Error: GEMINI_API_KEY not configured."

        # Prepare messages and config (this is model-agnostic, so we do it once)
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
        
        # Queue-based model selection with cooldowns
        max_attempts = 20  # Maximum attempts across all models
        attempt_count = 0
        
        while attempt_count < max_attempts:
            attempt_count += 1
            
            # Get available models (not in cooldown)
            available_models, all_models = self._get_available_models(model)
            
            # If no models available, wait for one to become available
            if not available_models:
                self._wait_for_available_model(all_models)
                available_models, _ = self._get_available_models(model)
            
            # If still no models available after waiting, give up
            if not available_models:
                print(f"[LLM] All models exhausted after waiting. Tried: {', '.join(all_models)}")
                return "{}"
            
            # Try the first available model
            current_model = available_models[0]
            
            # Prepare model-specific config
            is_gemma = "gemma" in current_model
            current_system_instruction = system_instruction
            
            if json_mode and is_gemma:
                if current_system_instruction:
                    current_system_instruction += "\n\nIMPORTANT: Output ONLY valid JSON. No Markdown. No explanations."
                else:
                    current_system_instruction = "IMPORTANT: Output ONLY valid JSON. No Markdown. No explanations."

            # Gemma does not support system_instruction in config, so we prepend it to the first user message
            if is_gemma and current_system_instruction:
                current_contents = []
                user_msg_found = False
                for content in contents:
                    if content.role == 'user' and not user_msg_found:
                        # Prepend system instruction to the first user message
                        original_text = content.parts[0].text
                        current_contents.append(types.Content(
                            role='user',
                            parts=[types.Part.from_text(text=f"System Instruction:\n{current_system_instruction}\n\nUser Message:\n{original_text}")]
                        ))
                        user_msg_found = True
                    else:
                        # Recreate other messages to avoid mutating original
                        if content.role == 'user':
                            current_contents.append(types.Content(
                                role='user',
                                parts=[types.Part.from_text(text=content.parts[0].text)]
                            ))
                        elif content.role == 'model':
                            current_contents.append(types.Content(
                                role='model',
                                parts=[types.Part.from_text(text=content.parts[0].text)]
                            ))
                
                # If no user message found (rare), create one
                if not user_msg_found:
                    current_contents.insert(0, types.Content(role='user', parts=[types.Part.from_text(text=f"System Instruction:\n{current_system_instruction}")]))
                
                # Clear system_instruction from config for Gemma
                current_system_instruction = None
            else:
                current_contents = contents

            config = types.GenerateContentConfig(
                temperature=0.7,
                system_instruction=current_system_instruction,
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
            
            # Single attempt per model - if it fails, set cooldown and try next
            try:
                response = self.client.models.generate_content(
                    model=current_model,
                    contents=current_contents,
                    config=config
                )
                
                if not response.text:
                    print(f"[DEBUG] Gemini blocked response or returned empty text for model {current_model}.")
                    # Set cooldown and try next model
                    self._set_model_cooldown(current_model)
                    continue
                
                text = response.text
                
                # If we switched models, log it
                if current_model != model:
                    print(f"[LLM] Successfully used fallback model: {current_model} (original: {model})")
                
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
                error_str = str(e)
                # Check if it's a rate limit error, connection error, or model not found
                is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower()
                is_connection_error = "connection" in error_str.lower() or "timeout" in error_str.lower() or "10060" in error_str or "failed to respond" in error_str.lower()
                is_model_not_found = "404" in error_str or "NOT_FOUND" in error_str or "not found" in error_str.lower()
                
                # If model not found, mark it as invalid and rotate API key
                if is_model_not_found:
                    self.invalid_models.add(current_model)
                    print(f"[LLM] Model {current_model} not found (404). Marking as invalid and moving to next model.")
                    # Rotate API key in case the issue is API-key specific
                    if len(self.api_keys) > 1:
                        self._rotate_api_key()
                elif is_rate_limit:
                    # Set cooldown for this model (15s first time, 30s if already in cooldown)
                    self._set_model_cooldown(current_model)
                    print(f"[LLM] Rate limit exceeded for model {current_model}. Rotating API key and moving to next model.")
                    # Rotate to next API key when we hit rate limits
                    if len(self.api_keys) > 1:
                        self._rotate_api_key()
                else:
                    # Set cooldown for other errors
                    self._set_model_cooldown(current_model)
                    if is_connection_error:
                        print(f"[LLM] Connection error for model {current_model}: {error_str}. Moving to next model.")
                    else:
                        print(f"[LLM] Error calling Gemini API with model {current_model}: {e}. Moving to next model.")
                
                # Continue to next iteration (will try next available model)
                continue
        
        # If we exhausted all attempts, return error
        print(f"[LLM] All models exhausted after {max_attempts} attempts. Tried: {', '.join(all_models)}")
        return "{}"
