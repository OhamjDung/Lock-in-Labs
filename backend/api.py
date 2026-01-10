from typing import List, Dict, Optional

import asyncio
import base64
import json
import os
import uuid
import urllib.error
import urllib.request

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
import time
import cv2
import numpy as np
from ultralytics import YOLO
from starlette.concurrency import run_in_threadpool
from PIL import Image
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

# --- Dithering helpers (native implementation to avoid extra pip deps) ---
def _nearest_palette_color(pixel, palette):
    # pixel: (3,) array, palette: (N,3)
    diffs = palette - pixel
    dists = (diffs * diffs).sum(axis=1)
    idx = int(np.argmin(dists))
    return palette[idx], idx

def _quantize_image_to_palette(arr, palette):
    # arr: HxWx3 uint8
    h, w, _ = arr.shape
    out = np.zeros_like(arr)
    # vectorized distance to 2-color palette
    pa = palette.reshape((1, 1, palette.shape[0], 3))
    aa = arr.reshape((h, w, 1, 3)).astype(np.int32)
    dists = ((aa - pa) ** 2).sum(axis=3)
    idx = np.argmin(dists, axis=2)
    out = palette[idx]
    return out.astype(np.uint8)

def _floyd_steinberg_dither(pil_img, palette):
    arr = np.array(pil_img).astype(np.float32)
    h, w, _ = arr.shape
    pal = np.array(palette, dtype=np.float32)
    for y in range(h):
        for x in range(w):
            old = arr[y, x].copy()
            nearest, _ = _nearest_palette_color(old, pal)
            arr[y, x] = nearest
            err = old - nearest
            if x + 1 < w:
                arr[y, x + 1] += err * (7 / 16)
            if y + 1 < h:
                if x > 0:
                    arr[y + 1, x - 1] += err * (3 / 16)
                arr[y + 1, x] += err * (5 / 16)
                if x + 1 < w:
                    arr[y + 1, x + 1] += err * (1 / 16)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def _atkinson_dither(pil_img, palette):
    arr = np.array(pil_img).astype(np.float32)
    h, w, _ = arr.shape
    pal = np.array(palette, dtype=np.float32)
    for y in range(h):
        for x in range(w):
            old = arr[y, x].copy()
            nearest, _ = _nearest_palette_color(old, pal)
            arr[y, x] = nearest
            err = (old - nearest) / 8.0
            if x + 1 < w:
                arr[y, x + 1] += err
            if x + 2 < w:
                arr[y, x + 2] += err
            if y + 1 < h:
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += err
                arr[y + 1, x] += err
                if x + 1 < w:
                    arr[y + 1, x + 1] += err
            if y + 2 < h:
                arr[y + 2, x] += err
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def _sierra3_dither(pil_img, palette):
    # Sierra-3 kernel
    arr = np.array(pil_img).astype(np.float32)
    h, w, _ = arr.shape
    pal = np.array(palette, dtype=np.float32)
    for y in range(h):
        for x in range(w):
            old = arr[y, x].copy()
            nearest, _ = _nearest_palette_color(old, pal)
            arr[y, x] = nearest
            err = old - nearest
            if x + 1 < w:
                arr[y, x + 1] += err * (5 / 32)
            if x + 2 < w:
                arr[y, x + 2] += err * (3 / 32)
            if y + 1 < h:
                if x - 2 >= 0:
                    arr[y + 1, x - 2] += err * (2 / 32)
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += err * (4 / 32)
                arr[y + 1, x] += err * (5 / 32)
                if x + 1 < w:
                    arr[y + 1, x + 1] += err * (4 / 32)
                if x + 2 < w:
                    arr[y + 1, x + 2] += err * (2 / 32)
            if y + 2 < h:
                if x - 1 >= 0:
                    arr[y + 2, x - 1] += err * (2 / 32)
                arr[y + 2, x] += err * (3 / 32)
                if x + 1 < w:
                    arr[y + 2, x + 1] += err * (2 / 32)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def _bayer_matrix(n):
    if n == 1:
        return np.array([[0]])
    else:
        smaller = _bayer_matrix(n // 2)
        a = 4 * smaller + np.array([[0, 2], [3, 1]])
        top = np.hstack((a, a + 2))
        bottom = np.hstack((a + 3, a + 1))
        return np.vstack((top, bottom))

def _bayer_dither(pil_img, palette, order=8):
    arr = np.array(pil_img).astype(np.uint8)
    h, w, _ = arr.shape
    pal = np.array(palette, dtype=np.uint8)
    mat = _bayer_matrix(order)
    norm = (mat + 0.5) / (order * order)
    # luminance
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]).astype(np.uint8)
    out = np.zeros_like(arr)
    for y in range(h):
        for x in range(w):
            threshold = norm[y % order, x % order] * 255
            if lum[y, x] > threshold:
                out[y, x] = pal[1]
            else:
                out[y, x] = pal[0]
    return Image.fromarray(out)

from src.models import CharacterSheet, ConversationState, PendingGoal, Pillar
from src.onboarding.agent import ArchitectAgent
from src.storage import load_profile, save_profile


class Message(BaseModel):
    role: str
    content: str


class ArchitectRequest(BaseModel):
    history: List[Message]
    user_input: str
    phase: str = "phase1"  # Current phase: phase1, phase2, phase3, phase3.5, phase4, phase5
    pending_debuffs: List[Dict[str, str]] = []  # Debuffs waiting for confirmation
    pillars_asked_about: List[str] = []  # Pillars that have been asked about in Phase 1
    pending_goals: List[Dict] = []  # Goals from pillars not yet asked about (pillars is a list, not string)
    accumulated_goals: List[Dict] = []  # Goals accumulated so far (with IDs)
    active_goal_id: Optional[str] = None  # ID of the goal currently being discussed
    user_id: str = "user_01"  # User ID for persistence


load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "kqVT88a5QfII1HNAEPTJ") 
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")


app = FastAPI()

# Allow the Vite dev server to talk to this API during development
# Also allow file:// protocol (null origin) for local HTML file testing
app.add_middleware(
    CORSMiddleware,
    # Allow both common Vite dev ports so the noir UI can
    # talk to this API even if the dev server changes ports.
    # Also allow all origins for development/testing (including file:// protocol with null origin)
    allow_origins=["*"],  # Allow all origins for development (including null origin for file://)
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Phone detector model (optional local WebSocket endpoint) ---
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "phone-detector", "yolo11s.pt")
TARGET_CLASSES = {"cell phone", "remote"}
# Lower threshold for better sensitivity during debugging
CONF_THRESHOLD = 0.2

# Custom 2-color palette: black and cream
CUSTOM_PALETTE_RGB = [
    (0, 0, 0),
    (254, 241, 220),
]

try:
    model = YOLO(MODEL_PATH)
    id2name = model.names
    wanted_ids = {i for i, n in id2name.items() if n in TARGET_CLASSES}
except Exception:
    model = None
    id2name = {}
    wanted_ids = set()


async def infer_frame_async(frame):
    """Run model(frame) in a threadpool to avoid blocking the event loop."""
    if model is None:
        raise RuntimeError("Model not loaded")
    def _call(f):
        # suppress model's stdout/stderr (ultralytics prints inference info)
        with open(os.devnull, 'w') as devnull:
            with redirect_stdout(devnull), redirect_stderr(devnull):
                return model(f, False)

    return await run_in_threadpool(_call, frame)


@app.post("/api/dither")
async def dither_image(
    file: UploadFile = File(...),
    algorithm: str = Form("FloydSteinberg"),
):
    """Dither an uploaded image to the fixed 2-color palette.

    Expects multipart/form-data with `file` and optional `algorithm` string.
    Returns PNG image bytes.
    """
    data = await file.read()

    def _process(img_bytes, alg):
        pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        # palette as simple list of RGB tuples
        palette = [tuple(c) for c in CUSTOM_PALETTE_RGB]

        if alg == "Bayer":
            dithered_img = _bayer_dither(pil, palette, order=8)
        elif alg == "Atkinson":
            dithered_img = _atkinson_dither(pil, palette)
        elif alg == "Sierra":
            dithered_img = _sierra3_dither(pil, palette)
        else:
            # Default Floyd-Steinberg
            dithered_img = _floyd_steinberg_dither(pil, palette)

        out = io.BytesIO()
        dithered_img.save(out, format="PNG")
        out.seek(0)
        return out

    try:
        out_buf = await run_in_threadpool(_process, data, algorithm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dithering failed: {e}")

    return StreamingResponse(out_buf, media_type="image/png")


@app.post("/api/profile/{user_id}/avatar")
async def save_profile_avatar(
    user_id: str,
    file: UploadFile = File(...),
    algorithm: str = Form("FloydSteinberg"),
):
    """Dither an uploaded image and save it to Firebase Storage, then update the user's profile.
    
    Returns the public URL of the saved image.
    """
    try:
        # First, dither the image
        data = await file.read()
        
        def _process(img_bytes, alg):
            pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            palette = [tuple(c) for c in CUSTOM_PALETTE_RGB]
            
            if alg == "Bayer":
                dithered_img = _bayer_dither(pil, palette, order=8)
            elif alg == "Atkinson":
                dithered_img = _atkinson_dither(pil, palette)
            elif alg == "Sierra":
                dithered_img = _sierra3_dither(pil, palette)
            else:
                dithered_img = _floyd_steinberg_dither(pil, palette)
            
            out = io.BytesIO()
            dithered_img.save(out, format="PNG")
            out.seek(0)
            return out.getvalue()
        
        dithered_bytes = await run_in_threadpool(_process, data, algorithm)
        
        # Upload to Firebase Storage
        try:
            from firebase_admin import storage
            bucket = storage.bucket()
            blob_name = f"avatars/{user_id}/profile.png"
            blob = bucket.blob(blob_name)
            blob.upload_from_string(dithered_bytes, content_type="image/png")
            blob.make_public()
            image_url = blob.public_url
        except Exception as e:
            # If Firebase Storage fails, we can still return the dithered image
            # and save a data URL or base64 in Firestore
            print(f"[Firebase Storage] Failed to upload avatar: {e}")
            # Fallback: convert to base64 data URL
            b64_data = base64.b64encode(dithered_bytes).decode('utf-8')
            image_url = f"data:image/png;base64,{b64_data}"
        
        # Update the user's profile with the avatar URL
        try:
            profile_data = load_profile(user_id) or {}
            cs = profile_data.setdefault("character_sheet", {})
            cs["avatar_url"] = image_url
            
            save_profile(profile_data, user_id)
        except Exception as e:
            print(f"[Profile] Failed to update avatar URL: {e}")
        
        return {"avatar_url": image_url, "ok": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save avatar: {e}")


@app.websocket("/ws/phone-detect")
async def phone_detect_ws(websocket: WebSocket):
    """Accepts JSON frames with base64 JPEGs and replies with JSON detections.

    Expected incoming message: {"type":"frame","frame_id":"...","image":"data:image/jpeg;base64,..."}
    Response: {"type":"detection","frame_id":...,"frame_width":W,"frame_height":H,"detections":[{class,confidence,bbox,bbox_px}]}
    """
    await websocket.accept()
    if model is None:
        await websocket.send_text(json.dumps({"type": "error", "code": "model_unavailable", "message": "Phone detector model is not loaded on the server."}))
        await websocket.close()
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await websocket.send_text(json.dumps({"type": "error", "code": "invalid_json"}))
                continue

            if msg.get("type") != "frame":
                continue

            frame_id = msg.get("frame_id")
            image_b64 = msg.get("image") or msg.get("data")
            # frame received
            if not image_b64:
                await websocket.send_text(json.dumps({"type": "error", "code": "invalid_frame", "frame_id": frame_id}))
                continue

            if image_b64.startswith("data:"):
                image_b64 = image_b64.split(",", 1)[1]

            try:
                img_bytes = base64.b64decode(image_b64)
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception:
                await websocket.send_text(json.dumps({"type": "error", "code": "invalid_frame", "frame_id": frame_id}))
                continue

            if frame is None:
                await websocket.send_text(json.dumps({"type": "error", "code": "invalid_frame", "frame_id": frame_id}))
                continue

            H, W = frame.shape[:2]
            try:
                results = await infer_frame_async(frame)
            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "code": "inference_failed", "message": str(e), "frame_id": frame_id}))
                continue

            results = results[0]
            detections = []
            raw_detections = []
            if results.boxes and len(results.boxes) > 0:
                for (cls_id, conf, xyxy) in zip(results.boxes.cls.tolist(), results.boxes.conf.tolist(), results.boxes.xyxy.tolist()):
                    x1, y1, x2, y2 = xyxy
                    w = max(0.0, x2 - x1)
                    h = max(0.0, y2 - y1)
                    bbox_px = {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)}
                    bbox_norm = {"x": float(x1 / W), "y": float(y1 / H), "w": float(w / W), "h": float(h / H)}
                    class_name = id2name.get(int(cls_id), str(cls_id))
                    raw_detections.append({"class": class_name, "confidence": float(conf), "bbox": bbox_norm, "bbox_px": bbox_px})
                    # keep only wanted classes above threshold for the existing 'detections' field
                    if int(cls_id) in wanted_ids and conf >= CONF_THRESHOLD:
                        detections.append({"class": class_name, "confidence": float(conf), "bbox": bbox_norm, "bbox_px": bbox_px})

            resp = {"type": "detection", "frame_id": frame_id, "timestamp": int(time.time() * 1000), "frame_width": W, "frame_height": H, "detections": detections, "raw_detections": raw_detections}
            # send response
            await websocket.send_text(json.dumps(resp))

    except WebSocketDisconnect:
        return



# ============================================================================
# SNAPSHOT ARCHITECTURE: State Machine Controller
# ============================================================================

def _get_goal_by_id(sheet: CharacterSheet, goal_id: str):
    """Helper to find a goal by ID."""
    return next((g for g in sheet.goals if g.id == goal_id), None)

def _extract_pillar_rankings(user_input: str) -> List[Pillar]:
    """Extract ordered list of pillars from user's ranking response."""
    pillar_keywords = {
        "career": Pillar.CAREER,
        "physical": Pillar.PHYSICAL,
        "mental": Pillar.MENTAL,
        "social": Pillar.SOCIAL
    }
    
    found_pillars = []
    input_lower = user_input.lower()
    
    # Look for pillar names in order
    for keyword, pillar_enum in pillar_keywords.items():
        if keyword in input_lower and pillar_enum not in found_pillars:
            found_pillars.append(pillar_enum)
    
    # Also check for numbered lists (1. Career, 2. Physical, etc.)
    for i, pillar_enum in enumerate([Pillar.CAREER, Pillar.PHYSICAL, Pillar.MENTAL, Pillar.SOCIAL]):
        keyword = list(pillar_keywords.keys())[i]
        # Check for patterns like "1. career", "first career", "career first"
        pattern1 = f"{i+1}. {keyword}"
        pattern2 = f"first {keyword}" if i == 0 else f"second {keyword}" if i == 1 else f"third {keyword}" if i == 2 else f"fourth {keyword}"
        pattern3 = f"{keyword} first" if i == 0 else f"{keyword} second" if i == 1 else f"{keyword} third" if i == 2 else f"{keyword} fourth"
        
        if (pattern1 in input_lower or pattern2 in input_lower or pattern3 in input_lower) and pillar_enum not in found_pillars:
            # Insert at correct position if not already there
            if len(found_pillars) <= i:
                found_pillars.append(pillar_enum)
            else:
                found_pillars.insert(i, pillar_enum)
    
    return found_pillars

def _find_next_incomplete_goal(sheet: CharacterSheet, current_phase: str) -> str | None:
    """Find the next goal that needs attention based on the current phase."""
    for goal in sheet.goals:
        if current_phase == "phase2":
            # A goal is incomplete if it has < 2 quests AND no skill_level
            if len(goal.current_quests) < 2 and goal.skill_level is None:
                return goal.id
        # Add other phase logic if needed
    return None

def _is_goal_complete(goal, phase: str) -> bool:
    """Check if a goal is considered complete for the current phase."""
    if phase == "phase2":
        # Complete if: 2+ quests OR has skill_level (which implies we're done asking)
        return len(goal.current_quests) >= 2 or goal.skill_level is not None
    return True

def _all_pillars_covered(sheet: CharacterSheet) -> bool:
    """Check if all 4 pillars have at least one goal."""
    from src.models import Pillar
    covered = set()
    for goal in sheet.goals:
        covered.update(goal.pillars)
    return len(covered) >= len(Pillar)


@app.post("/api/onboarding/architect-reply")
def architect_reply(payload: ArchitectRequest):
    """
    SNAPSHOT ARCHITECTURE: State Machine Controller for Onboarding.
    
    Flow:
    1. Load/Initialize State
    2. Prepare Context for Critic
    3. Critic Analysis (Delta Mode)
    4. Apply Deltas to Sheet
    5. Transition Logic (Phase/Goal)
    6. Generate Architect Response
    7. Return State (frontend persists for now)
    """
    from src.onboarding.agent import CriticAgent, ArchitectAgent
    from src.models import PendingDebuff, PendingGoal, Pillar, Goal

    # =========================================================================
    # 1. INITIALIZE STATE (Frontend-driven for now, will move to DB persistence)
    # =========================================================================
    sheet = CharacterSheet(user_id=payload.user_id)
    state = ConversationState(
        missing_fields=["goals", "quests"],
        current_topic="Intro",
        phase=payload.phase,
        active_goal_id=payload.active_goal_id  # Accept from frontend
    )
    
    # Restore state from frontend payload
    state.pending_debuffs = [PendingDebuff(**d) for d in payload.pending_debuffs]
    state.pillars_asked_about = []
    for p in payload.pillars_asked_about:
        try:
            state.pillars_asked_about.append(Pillar(p.upper()))
        except (ValueError, AttributeError):
            continue
    
    state.pending_goals = []
    for d in payload.pending_goals:
        try:
            # Handle both "pillars" (list) and "pillar" (single) for backward compatibility
            pillars_data = d.get("pillars")
            if not pillars_data:
                # Try "pillar" as fallback
                pillar_single = d.get("pillar")
                if pillar_single:
                    pillars_data = [pillar_single]
            
            if not pillars_data:
                continue  # Skip if no pillar data
            
            # Convert to Pillar enums
            pillar_enums = []
            for p in pillars_data:
                try:
                    pillar_enums.append(Pillar(p.upper()))
                except (ValueError, AttributeError):
                    continue
            
            if not pillar_enums:
                continue  # Skip if no valid pillars
            
            state.pending_goals.append(PendingGoal(
                name=d.get("name", ""),
                pillars=pillar_enums,
                description=d.get("description")
            ))
        except Exception as e:
            # Skip invalid pending goals
            print(f"[Warning] Failed to parse pending goal: {e}")
            continue

    # Seed conversation history
    state.conversation_history = [
        {"role": m.role, "content": m.content} for m in payload.history
    ]
    
    # Rebuild sheet from accumulated_goals passed from frontend (no replay!)
    if payload.accumulated_goals:
        for goal_data in payload.accumulated_goals:
            pillars_data = goal_data.get("pillars", [])
            pillar_enums = []
            for p in pillars_data:
                try:
                    pillar_enums.append(Pillar(p.upper()))
                except:
                    continue
            if pillar_enums:
                existing = next((g for g in sheet.goals if g.name.lower() == goal_data.get("name", "").lower()), None)
                if not existing:
                    new_goal = Goal(
                        id=goal_data.get("id", str(uuid.uuid4())),
                        name=goal_data.get("name", ""),
                        pillars=pillar_enums,
                        current_quests=goal_data.get("current_quests", []),
                        skill_level=goal_data.get("skill_level"),
                        description=goal_data.get("description")
                    )
                    sheet.goals.append(new_goal)
                else:
                    # Update existing goal
                    existing.current_quests = goal_data.get("current_quests", existing.current_quests)
                    existing.skill_level = goal_data.get("skill_level", existing.skill_level)

    architect = ArchitectAgent()
    critic = CriticAgent()

    # Determine current phase based on sheet state
    # Count pillars that have at least 1 goal (accounting for multi-pillar goals)
    all_pillars_in_goals = set()
    for goal in sheet.goals:
        all_pillars_in_goals.update(goal.pillars)
    pillars_with_goals = list(all_pillars_in_goals)
    defined_pillars = len(pillars_with_goals)
    total_pillars = 4
    all_goals_defined = defined_pillars >= total_pillars
    
    # Check if all goals have at least 2 quests (to assess user skill level)
    all_goals_have_quests = all_goals_defined and all(
        len(g.current_quests) >= 2 
        for g in sheet.goals
    )
    
    # Track previous phase to detect transitions
    previous_phase = state.phase
    
    # Phase transition logic will be checked AFTER processing the current message (see below after critic.analyze)
    
    # Handle goal prioritization in phase3.5 (this needs to happen before processing current message to check for ranking)
    if state.phase == "phase3.5" and not state.goals_prioritized:
        # Check if user provided a ranking
        user_input_lower = payload.user_input.lower()
        # Look for goal names or pillar names in the user's response
        goal_names = [g.name.lower() for g in sheet.goals]
        pillar_names = [p.value.lower() for p in Pillar]
        
        # Check if user mentioned multiple goals/pillars in order (indicating a ranking)
        mentioned_goals = [g for g in goal_names if g in user_input_lower]
        mentioned_pillars = [p for p in pillar_names if p in user_input_lower]
        
        # Also check for explicit ranking words
        ranking_indicators = ["first", "second", "third", "fourth", "then", "next", "after", "most important", "least important", "priority", "prioritize", "ranked", "ranking"]
        has_ranking_words = any(word in user_input_lower for word in ranking_indicators)
        
        # Check for "move on" or similar phrases that indicate user wants to proceed
        move_on_phrases = ["move on", "move forward", "continue", "proceed", "next", "done", "finished", "complete"]
        wants_to_move_on = any(phrase in user_input_lower for phrase in move_on_phrases)
        
        # If user mentioned at least 2 goals/pillars, used ranking words, or wants to move on after providing ranking, consider it complete
        if (len(mentioned_goals) >= 2 or len(mentioned_pillars) >= 2) or (has_ranking_words and (len(mentioned_goals) >= 1 or len(mentioned_pillars) >= 1)) or (wants_to_move_on and state.goals_prioritized == False):
            # Extract pillar rankings from user input
            pillar_rankings = _extract_pillar_rankings(payload.user_input)
            if pillar_rankings:
                sheet.pillar_rankings = pillar_rankings
                print(f"[Phase 3.5] Extracted pillar rankings: {[p.value for p in pillar_rankings]}")
            else:
                # Fallback: if no explicit ranking found, use order from goals (first pillar of each goal)
                seen_pillars = []
                for goal in sheet.goals:
                    for pillar in goal.pillars:
                        if pillar not in seen_pillars:
                            seen_pillars.append(pillar)
                if seen_pillars:
                    sheet.pillar_rankings = seen_pillars
                    print(f"[Phase 3.5] Using inferred pillar order from goals: {[p.value for p in seen_pillars]}")
            
            # If user wants to move on and we haven't detected a ranking yet, check if they provided one earlier
            # For now, if they explicitly want to move on, mark as prioritized
            state.goals_prioritized = True
            # After prioritization, move to phase4 (which triggers extract_profile)
            state.phase = "phase4"
            print(f"[Phase Transition] Detected ranking or move-on request. Transitioning to phase4.")

    # Handle debuff confirmation in phase3
    if state.phase == "phase3" and len(state.pending_debuffs) > 0:
        # Check if user is confirming/rejecting debuffs
        user_input_lower = payload.user_input.lower()
        confirmed_debuffs = []
        for debuff in state.pending_debuffs[:]:  # Copy list to iterate safely
            debuff_name_lower = debuff.name.lower()
            # Check for confirmation patterns
            if any(word in user_input_lower for word in ["yes", "yeah", "yep", "correct", "true", "right", debuff_name_lower]):
                if debuff_name_lower in user_input_lower or any(
                    confirm_word in user_input_lower for confirm_word in ["yes", "yeah", "yep", "correct", "true", "right"]
                ):
                    # User confirmed this debuff
                    if debuff.name not in sheet.debuffs:
                        sheet.debuffs.append(debuff.name)
                    confirmed_debuffs.append(debuff)
            # Check for rejection patterns
            elif any(word in user_input_lower for word in ["no", "nope", "not", "wrong", "incorrect", "false"]):
                if debuff_name_lower in user_input_lower or any(
                    reject_word in user_input_lower for reject_word in ["no", "nope", "not", "wrong", "incorrect", "false"]
                ):
                    # User rejected this debuff - remove from queue
                    confirmed_debuffs.append(debuff)
        
        # Remove confirmed/rejected debuffs from pending queue
        for debuff in confirmed_debuffs:
            if debuff in state.pending_debuffs:
                state.pending_debuffs.remove(debuff)
    
    # Process current user input through Critic to extract data
    history_plus_user = state.conversation_history + [
        {"role": "user", "content": payload.user_input}
    ]
    
    # =========================================================================
    # 2. PREPARE CONTEXT FOR CRITIC (Goal ID List)
    # =========================================================================
    existing_goals_summary = [
        f"ID: {g.id} | Name: {g.name} | Pillars: {', '.join([p.value for p in g.pillars])}"
        for g in sheet.goals
    ]
    
    # Get active goal ID from state (or find first incomplete goal)
    active_goal_id = state.active_goal_id
    print(f"[Controller] active_goal_id from state: {active_goal_id}")
    print(f"[Controller] sheet.goals count: {len(sheet.goals)}")
    
    if not active_goal_id and sheet.goals:
        # Default to first incomplete goal
        print(f"[Controller] active_goal_id is None, finding first incomplete goal...")
        active_goal_id = _find_next_incomplete_goal(sheet, state.phase)
        print(f"[Controller] _find_next_incomplete_goal returned: {active_goal_id}")
        if not active_goal_id and sheet.goals:
            active_goal_id = sheet.goals[0].id
            print(f"[Controller] Using first goal as fallback: {active_goal_id}")
    
    print(f"[Controller] Active Goal ID: {active_goal_id}")
    print(f"[Controller] Existing Goals: {existing_goals_summary}")
    
    # =========================================================================
    # 3. CRITIC ANALYSIS (Delta Mode)
    # =========================================================================
    critic_response, critic_raw_response = critic.analyze(
        user_input=payload.user_input,
        active_goal_id=active_goal_id,
        existing_goals=existing_goals_summary
    )
    
    # Extract fields from Critic response
    user_intent = critic_response.get("intent", "PROVIDING_INFO")
    deltas = critic_response.get("deltas", [])
    topic_switch_confidence = critic_response.get("topic_switch_confidence", 0.0)
    detected_topic_id = critic_response.get("detected_topic_id")
    feedback = critic_response.get("feedback_for_architect", "")
    
    print(f"[Controller] Critic Response - Intent: {user_intent}, Deltas: {len(deltas)}, Confidence: {topic_switch_confidence}")
    print(f"[Controller] Deltas detail: {deltas}")
    
    # =========================================================================
    # 4a. GUARDRAIL: Phase 1 Force-Convert to add_goal
    # =========================================================================
    # If active_goal_id is None, we're in Phase 1 - user is listing goals.
    # Force-convert any add_quest or update_skill to add_goal.
    if active_goal_id is None:
        converted_count = 0
        for delta in deltas:
            original_op = delta.get("operation")
            if original_op in ["add_quest", "update_skill"]:
                delta["operation"] = "add_goal"
                delta["target_id"] = None  # New goals don't have a target
                converted_count += 1
                print(f"[Controller] Phase 1 guardrail: Converted {original_op} -> add_goal for payload: {delta.get('payload')}")
        if converted_count > 0:
            print(f"[Controller] Phase 1 guardrail: Converted {converted_count} operations to add_goal")
    
    # =========================================================================
    # 4b. GUARDRAIL: Topic Switch Handling
    # =========================================================================
    if user_intent == "TOPIC_SWITCH":
        if topic_switch_confidence >= 0.8 and detected_topic_id:
            print(f"[Controller] Topic switch detected with high confidence. Switching to: {detected_topic_id}")
            state.active_goal_id = detected_topic_id
            active_goal_id = detected_topic_id
        elif topic_switch_confidence < 0.8:
            # Low confidence - might need clarification (handle in Architect response)
            print(f"[Controller] Topic switch with low confidence ({topic_switch_confidence}). May need clarification.")
    
    # =========================================================================
    # 5. APPLY DELTAS
    # =========================================================================
    # Track goals before applying deltas for Phase 1 queuing logic
    goals_before = {g.name: g for g in sheet.goals}
    
    print(f"[Controller] Processing {len(deltas)} deltas with active_goal_id={active_goal_id}")
    
    for delta in deltas:
        operation = delta.get("operation")
        raw_target_id = delta.get("target_id")
        payload_data = delta.get("payload") or delta.get("content")
        
        # =========================================================================
        # GUARDRAIL: Validate target_id exists, fallback to active_goal_id if not
        # =========================================================================
        # The LLM sometimes copies example UUIDs from the prompt instead of real ones
        if raw_target_id:
            validated_goal = _get_goal_by_id(sheet, raw_target_id)
            if validated_goal:
                target_id = raw_target_id
            else:
                print(f"[Controller] GUARDRAIL: target_id '{raw_target_id}' not found in sheet, falling back to active_goal_id '{active_goal_id}'")
                target_id = active_goal_id
        else:
            target_id = active_goal_id
        
        print(f"[Controller] Applying delta: {operation} -> {target_id} = {payload_data}")
        
        if operation == "add_quest" and payload_data:
            # Use validated target_id (already validated above)
            goal_id_to_use = target_id
            print(f"[Controller] add_quest: raw_target_id={raw_target_id}, active_goal_id={active_goal_id}, goal_id_to_use={goal_id_to_use}")
            if goal_id_to_use:
                target_goal = _get_goal_by_id(sheet, goal_id_to_use)
                print(f"[Controller] Found target_goal: {target_goal.name if target_goal else 'None'}")
                if target_goal:
                    quest_text = str(payload_data)
                    if quest_text not in target_goal.current_quests:
                        target_goal.current_quests.append(quest_text)
                        print(f"[Controller] Added quest '{quest_text}' to goal '{target_goal.name}'")
                    else:
                        print(f"[Controller] Quest '{quest_text}' already exists in goal '{target_goal.name}'")
        
        elif operation == "update_skill":
            # Use validated target_id (already validated above in the guardrail)
            goal_id_to_use = target_id
            if goal_id_to_use:
                target_goal = _get_goal_by_id(sheet, goal_id_to_use)
                if target_goal and payload_data is not None:
                    try:
                        skill_val = int(payload_data)
                        target_goal.skill_level = max(1, min(10, skill_val))
                        print(f"[Controller] Updated skill level for '{target_goal.name}' to {target_goal.skill_level}")
                    except (ValueError, TypeError):
                        print(f"[Controller] Failed to parse skill level: {payload_data}")
        
        elif operation == "add_goal" and payload_data:
            # Phase 1: Add new goal
            goal_name = str(payload_data)
            exists = any(g.name.lower() == goal_name.lower() for g in sheet.goals)
            if not exists:
                # Infer pillar from goal name keywords
                inferred_pillars = []
                goal_lower = goal_name.lower()
                
                # Career keywords
                if any(kw in goal_lower for kw in ["job", "career", "work", "accountant", "developer", "engineer", "business", "money", "income", "professional", "promotion"]):
                    inferred_pillars.append(Pillar.CAREER)
                # Physical keywords
                if any(kw in goal_lower for kw in ["fitness", "gym", "run", "exercise", "weight", "muscle", "health", "endurance", "sport", "physical"]):
                    inferred_pillars.append(Pillar.PHYSICAL)
                # Mental keywords (includes self-focused goals)
                if any(kw in goal_lower for kw in ["mental", "stress", "calm", "mindful", "focus", "anxiety", "meditation", "awareness", "peace", "myself", "self", "tune", "inner", "wellbeing", "well-being", "emotion", "feeling"]):
                    inferred_pillars.append(Pillar.MENTAL)
                # Social keywords
                if any(kw in goal_lower for kw in ["social", "friend", "network", "relationship", "people", "connect", "communication", "talk"]):
                    inferred_pillars.append(Pillar.SOCIAL)
                
                # Default to CAREER if no match
                if not inferred_pillars:
                    inferred_pillars = [Pillar.CAREER]
                
                new_goal = Goal(name=goal_name, pillars=inferred_pillars)
                sheet.goals.append(new_goal)
                print(f"[Controller] Added new goal '{goal_name}' with pillars: {[p.value for p in inferred_pillars]}")
    
    print(f"[Controller] User Intent: {user_intent}")
    
    # Initialize pending debuffs (extracted from deltas if any "add_debuff" operations)
    new_pending_debuffs = []
    for delta in deltas:
        if delta.get("operation") == "add_debuff":
            debuff_name = delta.get("payload") or delta.get("content")
            if debuff_name:
                new_pending_debuffs.append({
                    "name": str(debuff_name),
                    "evidence": "Extracted from conversation",
                    "confidence": "medium"
                })
    
    # =========================================================================
    # 6. TRANSITION LOGIC (Phase 2)
    # =========================================================================
    architect_directive = None
    extracted_data_context = []
    
    # Log full sheet state after deltas
    print(f"\n[Controller] ========== STATE AFTER DELTAS ==========")
    for g in sheet.goals:
        print(f"[Controller] Goal: '{g.name}' | ID: {g.id} | Pillars: {[p.value for p in g.pillars]} | Quests: {list(g.current_quests)} | Skill: {g.skill_level}")
    print(f"[Controller] ==============================================\n")
    
    # Get the active goal object
    active_goal = _get_goal_by_id(sheet, active_goal_id) if active_goal_id else None
    
    print(f"[Controller] Active Goal: {active_goal.name if active_goal else 'None'}")
    
    if state.phase == "phase2" and active_goal:
        print(f"[Controller] Goal '{active_goal.name}': quests={len(active_goal.current_quests)}, skill_level={active_goal.skill_level}, intent={user_intent}")
        
        # Check if goal is now complete
        if _is_goal_complete(active_goal, state.phase):
            print(f"[Controller] Goal '{active_goal.name}' is COMPLETE!")
            # Find next incomplete goal
            next_goal_id = _find_next_incomplete_goal(sheet, state.phase)
            if next_goal_id:
                next_goal = _get_goal_by_id(sheet, next_goal_id)
                state.active_goal_id = next_goal_id
                architect_directive = f"Great! We've covered '{active_goal.name}'. Now let's move on to '{next_goal.name}'. What are you currently doing to work towards this goal?"
                print(f"[Controller] Moving to next goal: {next_goal.name}")
            else:
                # All goals complete for Phase 2
                print(f"[Controller] All goals complete for Phase 2!")
        
        # Check if we should ask for skill level (STOP_SIGNAL logic)
        elif user_intent == "STOP_SIGNAL" and active_goal.skill_level is None:
            if len(active_goal.current_quests) >= 1:
                print(f"[Controller] STOP_SIGNAL with quests. Asking for skill level.")
                architect_directive = f"The user has finished listing activities for '{active_goal.name}'. Acknowledge what they mentioned ({', '.join(active_goal.current_quests)}). Then, ask them to rate their current skill level on a scale of 1-10."
                extracted_data_context = list(active_goal.current_quests)
            else:
                print(f"[Controller] STOP_SIGNAL with 0 quests. Asking for skill level directly.")
                # Simplified: Don't require confirmation, just acknowledge and ask for skill level directly
                architect_directive = f"The user admits they are not currently doing anything for '{active_goal.name}'. Say something like 'That's okay, we all have to start somewhere.' Then IMMEDIATELY ask: 'On a scale of 1-10, how would you rate your current ability in this area?' DO NOT move to another goal."
        
        else:
            # Goal is NOT complete yet - need more quests or skill level
            quest_count = len(active_goal.current_quests)
            print(f"[Controller] Continuing Phase 2: Goal '{active_goal.name}' needs more quests ({quest_count}/2)")
            
            # Special case: If goal has 0 quests and user just responded with a short confirmation 
            # (like "yea", "yes", "ok"), they've likely confirmed they're doing nothing.
            # In this case, ask for skill level directly instead of asking about activities again.
            user_input_lower = payload.user_input.strip().lower()
            is_short_confirmation = user_input_lower in ["yea", "yeah", "yes", "yep", "ok", "okay", "sure", "right", "correct", "true", "that's right", "thats right"]
            
            if quest_count == 0 and is_short_confirmation:
                print(f"[Controller] Detected confirmation after 0 quests. Asking for skill level.")
                architect_directive = f"The user confirmed they're not doing anything for '{active_goal.name}'. That's okay. Now ask: 'On a scale of 1-10, how would you rate your current ability in this area?' DO NOT move to another goal until you get the skill rating."
            elif quest_count == 0:
                architect_directive = f"Ask the user what they are currently doing to work towards '{active_goal.name}'."
            else:
                # Has some quests but needs more - ask for additional activities
                architect_directive = f"The user mentioned they are doing: {', '.join(active_goal.current_quests)}. Acknowledge this briefly, then ask: 'What else are you doing to work towards {active_goal.name}? Any other activities or habits?' DO NOT move to a different goal yet - we need at least 2 activities for this goal."

    # Phase transition logic - Check AFTER processing current message
    # Check if all 4 pillars are covered by at least one goal (relaxed constraint)
    all_pillars_in_goals_set = set()
    for goal in sheet.goals:
        all_pillars_in_goals_set.update(goal.pillars)
    
    all_4_pillars_covered = len(all_pillars_in_goals_set) >= 4
    
    # Debug phase transition - ALWAYS initialize this
    phase_transition_debug = {
        "current_phase": state.phase,
        "all_4_pillars_covered": all_4_pillars_covered,
        "pillars_covered": [p.value for p in all_pillars_in_goals_set],
    }
    
    print(f"[Phase Transition Check] Current phase: {state.phase}")
    print(f"[Phase Transition Check] All 4 pillars covered: {all_4_pillars_covered} (pillars: {[p.value for p in all_pillars_in_goals_set]})")
    
    if state.phase == "phase1" and all_4_pillars_covered:
        print(f"[Phase Transition] Transitioning from phase1 to phase2!")
        state.phase = "phase2"
        phase_transition_debug["transition"] = "phase1 -> phase2"
    
    # Check if all goals are complete for Phase 2
    # A goal is complete if it has 2+ quests OR has skill_level assessed (for 0-1 quest cases)
    def is_goal_complete_for_phase2(goal):
        return len(goal.current_quests) >= 2 or goal.skill_level is not None
    
    all_goals_complete = all_4_pillars_covered and all(
        is_goal_complete_for_phase2(g) 
        for g in sheet.goals
    )
    
    if state.phase == "phase2" and all_goals_complete:
        # Check if there are pending debuffs
        if len(state.pending_debuffs) > 0:
            state.phase = "phase3"
        else:
            state.phase = "phase3.5"
    elif state.phase == "phase3" and len(state.pending_debuffs) == 0:
        state.phase = "phase3.5"
    
    # Handle Phase 1 goal queuing logic
    if state.phase == "phase1":
        # Determine which pillar is currently being asked about
        # Cycle through pillars in order: CAREER, PHYSICAL, MENTAL, SOCIAL
        def determine_current_pillar(pillars_asked_about, goals):
            """Determine which pillar should be asked about next."""
            all_pillars_in_goals = set()
            for goal in goals:
                all_pillars_in_goals.update(goal.pillars)
            
            # Find first missing pillar that hasn't been asked about yet
            for p in Pillar:  # This maintains order: CAREER, PHYSICAL, MENTAL, SOCIAL
                if p not in pillars_asked_about and p not in all_pillars_in_goals:
                    return p
            
            # If all pillars have been asked about but some are still missing, ask about first missing one
            missing_pillars = [p for p in Pillar if p not in all_pillars_in_goals]
            if missing_pillars:
                return missing_pillars[0]
            
            return None
        
        current_pillar = determine_current_pillar(state.pillars_asked_about, sheet.goals)
        
        # Process newly extracted goals
        goals_to_confirm = []
        new_goals_for_current_pillar = []
        
        for goal in sheet.goals:
            # Check if this is a new goal (wasn't in goals_before)
            is_new_goal = goal.name not in goals_before
            
            if is_new_goal:
                goal_pillars = set(goal.pillars)
                
                if current_pillar and current_pillar in goal_pillars:
                    # Goal for current pillar - save for processing
                    new_goals_for_current_pillar.append(goal)
                elif any(p in state.pillars_asked_about for p in goal_pillars):
                    # Goal for already-asked pillar - mark for confirmation
                    goals_to_confirm.append(goal)
                else:
                    # Goal for not-yet-asked pillar - queue it for presentation, but KEEP IT IN sheet.goals
                    # This ensures the Architect can see all accumulated goals to determine what's missing
                    if not any(pg.name == goal.name for pg in state.pending_goals):
                        state.pending_goals.append(PendingGoal(
                            name=goal.name,
                            pillars=goal.pillars,
                            description=goal.description
                        ))
                    # DO NOT remove from sheet - keep all goals in sheet.goals so Architect can see them
        
        # When we ask about a new pillar, mark its queued goals as presented (but they're already in sheet.goals)
        if current_pillar:
            queued_goals_for_pillar = [pg for pg in state.pending_goals if current_pillar in pg.pillars]
            if queued_goals_for_pillar:
                for pg in queued_goals_for_pillar:
                    # Goal is already in sheet.goals, just remove from pending queue to mark it as presented
                    state.pending_goals.remove(pg)
        
        # After processing all goals, mark current pillar as asked about if it has ANY goal
        if current_pillar and current_pillar not in state.pillars_asked_about:
            # Check if current pillar is covered by any goal
            is_covered = False
            for goal in sheet.goals:
                if current_pillar in goal.pillars:
                    is_covered = True
                    break
            
            if is_covered:
                state.pillars_asked_about.append(current_pillar)
    
    # Handle Phase 2 pillar cycling
    elif state.phase == "phase2":
        # Determine which pillar to ask about next (first pillar with incomplete goals)
        def get_pillars_with_incomplete_goals(goals):
            """Get pillars that have goals that are incomplete (need 2+ quests OR skill_level)."""
            pillars_with_incomplete = set()
            for goal in goals:
                if not is_goal_complete_for_phase2(goal):
                    pillars_with_incomplete.update(goal.pillars)
            return pillars_with_incomplete
        
        incomplete_pillars = get_pillars_with_incomplete_goals(sheet.goals)
        # Cycle through pillars in order, find first one with incomplete goals
        current_pillar_phase2 = None
        for p in Pillar:
            if p in incomplete_pillars:
                current_pillar_phase2 = p
                break
    else:
        current_pillar = None
        current_pillar_phase2 = None
    
    # Add new pending debuffs to the queue
    for debuff in new_pending_debuffs:
        # Check if already in queue or already confirmed
        if debuff["name"] not in sheet.debuffs and not any(
            d.name == debuff["name"] for d in state.pending_debuffs
        ):
            state.pending_debuffs.append(PendingDebuff(**debuff))
    
    # Convert pending debuffs to dict for response
    pending_debuffs_dict = [
        {"name": d.name, "evidence": d.evidence, "confidence": d.confidence}
        for d in state.pending_debuffs
    ]
    
    # Determine current pillar and queued goals for Architect
    current_pillar_value = None
    queued_goals_for_current_pillar = []
    
    if state.phase == "phase1":
        # Determine current pillar being asked about
        all_pillars_in_goals = set()
        for goal in sheet.goals:
            all_pillars_in_goals.update(goal.pillars)
        for p in Pillar:
            if p not in state.pillars_asked_about and p not in all_pillars_in_goals:
                current_pillar_value = p.value
                break
        if not current_pillar_value:
            missing_pillars = [p for p in Pillar if p not in all_pillars_in_goals]
            if missing_pillars:
                current_pillar_value = missing_pillars[0].value
        
        # Get queued goals for current pillar
        if current_pillar_value:
            current_pillar_enum = Pillar(current_pillar_value.upper())
            queued_goals_for_current_pillar = [
                {"name": pg.name, "pillars": [p.value for p in pg.pillars], "description": pg.description}
                for pg in state.pending_goals if current_pillar_enum in pg.pillars
            ]
    elif state.phase == "phase2":
        # Determine current pillar with incomplete goals
        incomplete_pillars = set()
        for goal in sheet.goals:
            if not is_goal_complete_for_phase2(goal):
                incomplete_pillars.update(goal.pillars)
        for p in Pillar:
            if p in incomplete_pillars:
                current_pillar_value = p.value
                break
    
    # Generate phase transition message if phase changed (do this BEFORE calling Architect)
    phase_transition_message = None
    custom_phase2_message = None  # For phase1->phase2, we'll create a custom message with the first goal
    if previous_phase != state.phase:
        if previous_phase == "phase1" and state.phase == "phase2":
            # For phase2 transition, create a custom message that includes the first goal
            # Find the first goal to ask about (cycle through pillars)
            first_goal_for_phase2 = None
            first_pillar_for_phase2 = None
            for p in Pillar:
                goals_for_pillar = [g for g in sheet.goals if p in g.pillars]
                if goals_for_pillar:
                    first_goal_for_phase2 = goals_for_pillar[0]
                    first_pillar_for_phase2 = p.value
                    break
            
            if first_goal_for_phase2:
                custom_phase2_message = f"Now that I've gotten a good grasp of your goals, let's talk about what you're currently doing to achieve them. Let's start with your {first_pillar_for_phase2.lower()} goal: '{first_goal_for_phase2.name}'. Tell me what you're currently doing to get closer to this goal."
            else:
                phase_transition_message = "Now that I've gotten a good grasp of your goals, let's talk about what you're currently doing to achieve them."
        elif previous_phase == "phase2" and state.phase == "phase3":
            phase_transition_message = "Good. I've noted what you're currently doing. Now, I noticed a few things we should confirm. Let me ask you about them one at a time."
        elif previous_phase == "phase2" and state.phase == "phase3.5":
            # List all goals for prioritization
            goal_list = []
            for goal in sheet.goals:
                pillars_str = ", ".join([p.value for p in goal.pillars])
                goal_list.append(f"- {goal.name} ({pillars_str})")
            goals_text = "\n".join(goal_list) if goal_list else "your goals"
            phase_transition_message = f"Perfect. I've got a clear picture of your goals and what you're doing. Now, let's prioritize. I need you to rank your goals from most to least important:\n\n{goals_text}"
        elif previous_phase == "phase3" and state.phase == "phase3.5":
            # List all goals for prioritization
            goal_list = []
            for goal in sheet.goals:
                pillars_str = ", ".join([p.value for p in goal.pillars])
                goal_list.append(f"- {goal.name} ({pillars_str})")
            goals_text = "\n".join(goal_list) if goal_list else "your goals"
            phase_transition_message = f"Good. Now that we've confirmed everything, let's prioritize. I need you to rank your goals from most to least important:\n\n{goals_text}"
        elif previous_phase == "phase3.5" and state.phase == "phase4":
            phase_transition_message = "Perfect! I've got everything I need. Let me generate your skill tree now."
    
    # Calculate granular progress percentage (before generating reply so we can add it)
    def calculate_progress(sheet, state):
        """Calculate progress percentage based on actual completion."""
        total_progress = 0
        
        if state.phase == "phase1":
            # Phase 1: 0-40% based on pillars with goals
            all_pillars_in_goals = set()
            for goal in sheet.goals:
                all_pillars_in_goals.update(goal.pillars)
            
            pillars_with_goals = len(all_pillars_in_goals)
            total_pillars = 4
            # Progress: 0-40% (10% per pillar)
            total_progress = int((pillars_with_goals / total_pillars) * 40)
            
        elif state.phase == "phase2":
            # Phase 2: 40-70% based on goals with quests/skill levels
            def is_goal_complete_for_phase2(goal):
                return len(goal.current_quests) >= 2 or goal.skill_level is not None
            
            if not sheet.goals:
                total_progress = 40  # Just started phase 2
            else:
                completed_goals = sum(1 for g in sheet.goals if is_goal_complete_for_phase2(g))
                total_goals = len(sheet.goals)
                # Progress: 40-70% (30% range, distributed across goals)
                phase2_progress = (completed_goals / total_goals) * 30 if total_goals > 0 else 0
                total_progress = 40 + int(phase2_progress)
                
        elif state.phase == "phase3":
            # Phase 3: 70-85% based on debuff confirmations
            # Assume we start at 70% and progress to 85% as debuffs are confirmed
            # For simplicity, if we're in phase3, we're at least 70%
            # Progress increases as pending_debuffs decrease
            total_debuffs = len(sheet.debuffs) + len(state.pending_debuffs)
            if total_debuffs == 0:
                total_progress = 85  # No debuffs to confirm
            else:
                confirmed_debuffs = len(sheet.debuffs)
                # Progress: 70-85% (15% range)
                phase3_progress = (confirmed_debuffs / total_debuffs) * 15 if total_debuffs > 0 else 0
                total_progress = 70 + int(phase3_progress)
                
        elif state.phase == "phase3.5":
            # Phase 3.5: 85-95% based on goal prioritization
            if state.goals_prioritized:
                total_progress = 95
            else:
                total_progress = 85  # Just started prioritization
                
        elif state.phase == "phase4":
            # Phase 4: 95-100% (skill tree generation)
            total_progress = 100
            
        else:
            # Fallback: use phase-based progress
            phase_progress_map = {
                "phase1": 20,
                "phase2": 55,
                "phase3": 77,
                "phase3.5": 90,
                "phase4": 100
            }
            total_progress = phase_progress_map.get(state.phase, 0)
        
        # Ensure progress is between 0-100
        return max(0, min(100, total_progress))
    
    # Calculate progress
    progress_percentage = calculate_progress(sheet, state)
    progress_tag = f"[Progress: {progress_percentage}%]"
    
    # Generate Architect response with Critic feedback
    # Skip Architect for phase3.5 transition (use only transition message) and phase4
    if phase_transition_message and previous_phase in ["phase2", "phase3"] and state.phase == "phase3.5":
        # For phase3.5 transition, use ONLY the transition message, don't call Architect
        reply = phase_transition_message
        architect_thinking = "Phase 3.5 transition - using transition message only."
    elif state.phase == "phase4":
        # For phase4, use transition message if available, otherwise simple acknowledgment
        reply = phase_transition_message if phase_transition_message else "Perfect! I've got everything I need. Your skill tree is being generated now."
        architect_thinking = "Phase 4 - Skill tree generation in progress. No further questions needed."
    elif custom_phase2_message:
        # For phase1->phase2, use the custom message instead of calling Architect
        reply = custom_phase2_message
        architect_thinking = "Phase 1->2 transition - using custom message with first goal."
    else:
        # For Phase 2, determine target_goal_name BEFORE calling Architect
        # This ensures we use the updated sheet state (including skill_level if just set by Critic)
        target_goal_name_for_architect = None
        if state.phase == "phase2":
            # Re-check incomplete goals after Critic processing (using updated sheet state)
            incomplete_goals_for_architect = []
            current_pillar_enum_for_target = None
            if current_pillar_phase2:
                current_pillar_enum_for_target = current_pillar_phase2
            elif current_pillar_value:
                try:
                    current_pillar_enum_for_target = Pillar(current_pillar_value.upper())
                except ValueError:
                    pass
            
            if current_pillar_enum_for_target:
                incomplete_goals_for_architect = [
                    g for g in sheet.goals 
                    if current_pillar_enum_for_target in g.pillars and not is_goal_complete_for_phase2(g)
                ]
            else:
                # If no current pillar, find first incomplete goal across all pillars
                for p in Pillar:
                    incomplete_goals_for_architect = [
                        g for g in sheet.goals 
                        if p in g.pillars and not is_goal_complete_for_phase2(g)
                    ]
                    if incomplete_goals_for_architect:
                        break
            
            if incomplete_goals_for_architect:
                target_goal_name_for_architect = incomplete_goals_for_architect[0].name
                print(f"[Phase 2] Target goal for Architect: {target_goal_name_for_architect} (quests: {len(incomplete_goals_for_architect[0].current_quests)}, skill_level: {incomplete_goals_for_architect[0].skill_level})")
        
        # DEBUG: Log what goals are in sheet.goals before passing to Architect
        print(f"[DEBUG] Sheet goals before Architect call: {[(g.name, [p.value for p in g.pillars]) for g in sheet.goals]}")
        print(f"[DEBUG] Sheet JSON: {sheet.model_dump_json()}")
        
        # =========================================================================
        # 7. GENERATE ARCHITECT RESPONSE (Directive-Driven)
        # =========================================================================
        # Build directive if not already set
        if not architect_directive:
            if state.phase == "phase1":
                # Phase 1: Ask about goals for missing pillars
                missing_pillars = [p.value for p in Pillar if p not in all_pillars_in_goals_set]
                if missing_pillars:
                    architect_directive = f"Ask the user about their goals for the {missing_pillars[0]} pillar of their life."
                else:
                    architect_directive = "Confirm the user's goals and prepare to transition to Phase 2."
            elif state.phase == "phase2":
                if active_goal:
                    architect_directive = f"Ask the user what they are currently doing to work towards '{active_goal.name}'."
                else:
                    architect_directive = "Ask about activities for the user's goals."
            elif state.phase == "phase3.5":
                architect_directive = "Ask the user to prioritize their goals in order of importance."
            else:
                architect_directive = "Continue the conversation naturally."
        
        reply = architect.generate_response(history_plus_user, architect_directive)
        architect_thinking = f"Directive: {architect_directive}"
        
        # Prepend phase transition message for other transitions
        if phase_transition_message:
            reply = f"{phase_transition_message}\n\n{reply}"
    
    # Add progress tag to the beginning of the reply (frontend will extract and remove it)
    if reply and progress_tag not in reply:
        reply = f"{progress_tag} {reply}"

    # Generate and log quest status and debugging info for Phase 2
    quest_status_message = None
    phase2_debug_info = None
    if state.phase == "phase2":
        # Find the first incomplete goal (same logic as in Phase 2 agent)
        def is_goal_complete_for_phase2(goal):
            return len(goal.current_quests) >= 2 or goal.skill_level is not None
        
        current_pillar_enum = None
        if current_pillar_value:
            try:
                current_pillar_enum = Pillar(current_pillar_value.upper())
            except ValueError:
                pass
        
        incomplete_goals = []
        if current_pillar_enum:
            incomplete_goals = [
                g for g in sheet.goals 
                if current_pillar_enum in g.pillars and not is_goal_complete_for_phase2(g)
            ]
        else:
            # If no current pillar, find first incomplete goal across all pillars
            for p in Pillar:
                incomplete_goals = [
                    g for g in sheet.goals 
                    if p in g.pillars and not is_goal_complete_for_phase2(g)
                ]
                if incomplete_goals:
                    break
        
        # Build comprehensive Phase 2 debug info
        all_goals_status = [
            {
                "name": g.name,
                "pillars": [p.value for p in g.pillars],
                "quest_count": len(g.current_quests),
                "skill_level": g.skill_level,
                "is_complete": is_goal_complete_for_phase2(g)
            }
            for g in sheet.goals
        ]
        
        target_goal_name = None
        target_quest_count = None
        if incomplete_goals:
            target_goal = incomplete_goals[0]
            target_goal_name = target_goal.name
            target_quest_count = len(target_goal.current_quests)
            quest_status_message = f"Current quest status: \"{target_goal.name}\" has {target_quest_count}/2 quests."
            # Log to backend console
            print(f"[Phase 2 Quest Status] {quest_status_message}")
        
        phase2_debug_info = {
            "target_goal": target_goal_name,
            "target_quest_count": target_quest_count,
            "incomplete_goals_count": len(incomplete_goals),
            "incomplete_goals": [g.name for g in incomplete_goals],
            "all_goals_status": all_goals_status,
            "current_pillar": current_pillar_value
        }
        print(f"[Phase 2 Debug] Target goal: {target_goal_name}, Incomplete goals: {[g.name for g in incomplete_goals]}")
        
        # Add temporary debug info to the reply for testing
        if target_goal_name and state.phase == "phase2":
            target_goal_for_debug = next((g for g in sheet.goals if g.name == target_goal_name), None)
            if target_goal_for_debug:
                debug_text = f"\n\n---\n**[DEBUG]** Target: `{target_goal_name}` | Quests: {len(target_goal_for_debug.current_quests)}/2 | Skill: {target_goal_for_debug.skill_level or 'None'} | Intent: {user_intent}"
                reply = reply + debug_text

    # Get accumulated goals for logging (include ID, current_quests and skill_level)
    accumulated_goals = [
        {
            "id": g.id,  # CRITICAL: Include ID for state tracking
            "name": g.name, 
            "pillars": [p.value for p in g.pillars], 
            "description": g.description, 
            "current_quests": g.current_quests,
            "skill_level": g.skill_level
        }
        for g in sheet.goals
    ]
    
    # Convert state back to dicts for frontend
    pillars_asked_about_dict = [p.value for p in state.pillars_asked_about]
    pending_goals_dict = [
        {"name": pg.name, "pillars": [p.value for p in pg.pillars], "description": pg.description}
        for pg in state.pending_goals
    ]
    
    return {
        "reply": reply,
        "phase": state.phase,
        "active_goal_id": state.active_goal_id,  # For state tracking
        "pending_debuffs": pending_debuffs_dict,
        "pillars_asked_about": pillars_asked_about_dict,
        "pending_goals": pending_goals_dict,
        "accumulated_goals": accumulated_goals,
        "goals_prioritized": state.goals_prioritized,
        "should_extract_profile": state.phase == "phase4" and state.goals_prioritized,
        "debug": {
            "critic_analysis": critic_raw_response,
            "architect_thinking": architect_thinking,
            "phase_transition": phase_transition_debug,
            "quest_status": quest_status_message,
            "phase2_debug": phase2_debug_info,
            "user_intent": user_intent,
            "architect_directive": architect_directive,
            "active_goal_id": state.active_goal_id
        }
    }


class ExtractProfileRequest(BaseModel):
    history: List[Message]
    user_id: str

class ReportingChatRequest(BaseModel):
    user_id: str
    message: str
    conversation_history: List[Message] = []


@app.post("/api/onboarding/extract-profile")
def extract_profile(payload: ExtractProfileRequest):
    """Extract character sheet and skill tree from onboarding conversation history.
    
    This processes the full conversation through the Critic agent to extract
    structured character sheet data, then generates the skill tree.
    Returns the complete profile ready to be saved.
    
    PHASE 4: Runs planners to generate needed_quests
    PHASE 5: Generates skill tree from needed_quests
    """
    # #region agent log
    import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:entry","message":"extract-profile called","data":{"user_id": payload.user_id, "history_length": len(payload.history)},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H1"})+'\n')
    # #endregion
    try:
        from src.onboarding.agent import CriticAgent
        from src.skill_tree.generator import SkillTreeGenerator
        from src.planners import get_planner
        
        # Initialize character sheet with the user's Firebase Auth UID
        sheet = CharacterSheet(user_id=payload.user_id)
        critic = CriticAgent()
        
        # Process conversation history through Critic to extract character sheet data
        conversation_history = [
            {"role": m.role, "content": m.content} for m in payload.history
        ]
        
        # Process all user messages through the new delta-based Critic
        # Build goal list progressively
        for i, msg in enumerate(conversation_history):
            if msg["role"] == "user":
                # Prepare existing goals context
                existing_goals_summary = [
                    f"ID: {g.id} | Name: {g.name}" for g in sheet.goals
                ]
                
                # Get active goal (first incomplete or None)
                active_goal_id = None
                for g in sheet.goals:
                    if len(g.current_quests) < 2 and g.skill_level is None:
                        active_goal_id = g.id
                        break
                
                # Analyze with new signature
                critic_response, _ = critic.analyze(
                    user_input=msg["content"],
                    active_goal_id=active_goal_id,
                    existing_goals=existing_goals_summary
                )
                
                # Apply deltas
                for delta in critic_response.get("deltas", []):
                    op = delta.get("operation")
                    target_id = delta.get("target_id") or active_goal_id
                    payload_data = delta.get("payload") or delta.get("content")
                    
                    if op == "add_goal" and payload_data:
                        exists = any(g.name.lower() == str(payload_data).lower() for g in sheet.goals)
                        if not exists:
                            from src.models import Goal
                            goal_name = str(payload_data)
                            
                            # Infer pillar from goal name keywords (same logic as architect-reply)
                            inferred_pillars = []
                            goal_lower = goal_name.lower()
                            
                            # Career keywords
                            if any(kw in goal_lower for kw in ["job", "career", "work", "accountant", "developer", "engineer", "business", "money", "income", "professional", "promotion"]):
                                inferred_pillars.append(Pillar.CAREER)
                            # Physical keywords
                            if any(kw in goal_lower for kw in ["fitness", "gym", "run", "exercise", "weight", "muscle", "health", "endurance", "sport", "physical"]):
                                inferred_pillars.append(Pillar.PHYSICAL)
                            # Mental keywords (includes self-focused goals)
                            if any(kw in goal_lower for kw in ["mental", "stress", "calm", "mindful", "focus", "anxiety", "meditation", "awareness", "peace", "myself", "self", "tune", "inner", "wellbeing", "well-being", "emotion", "feeling"]):
                                inferred_pillars.append(Pillar.MENTAL)
                            # Social keywords
                            if any(kw in goal_lower for kw in ["social", "friend", "network", "relationship", "people", "connect", "communication", "talk"]):
                                inferred_pillars.append(Pillar.SOCIAL)
                            
                            # Default to CAREER if no match
                            if not inferred_pillars:
                                inferred_pillars = [Pillar.CAREER]
                            
                            new_goal = Goal(name=goal_name, pillars=inferred_pillars)
                            sheet.goals.append(new_goal)
                            
                            # #region agent log
                            import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:add_goal","message":"Added goal with inferred pillars","data":{"goal_name": goal_name, "pillars": [p.value for p in inferred_pillars]},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H1"})+'\n')
                            # #endregion
                    
                    elif op == "add_quest" and target_id and payload_data:
                        target = next((g for g in sheet.goals if g.id == target_id), None)
                        if target and str(payload_data) not in target.current_quests:
                            target.current_quests.append(str(payload_data))
                    
                    elif op == "update_skill" and target_id:
                        target = next((g for g in sheet.goals if g.id == target_id), None)
                        if target:
                            try:
                                target.skill_level = int(payload_data)
                            except:
                                pass
        
        # Extract pillar_rankings from conversation history (phase 3.5)
        # Look for ranking mentions in recent conversation
        for msg in reversed(conversation_history[-10:]):  # Check last 10 messages
            if msg["role"] == "user":
                rankings = _extract_pillar_rankings(msg["content"])
                if rankings:
                    sheet.pillar_rankings = rankings
                    print(f"[extract_profile] Extracted pillar rankings from conversation: {[p.value for p in rankings]}")
                    break
        
        # Fallback: if no rankings found, infer from goal order
        if not sheet.pillar_rankings:
            seen_pillars = []
            for goal in sheet.goals:
                for pillar in goal.pillars:
                    if pillar not in seen_pillars:
                        seen_pillars.append(pillar)
            if seen_pillars:
                sheet.pillar_rankings = seen_pillars
                print(f"[extract_profile] Using inferred pillar order from goals: {[p.value for p in seen_pillars]}")
        
        # #region agent log
        import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:pre_planners","message":"Goals before planners","data":{"goals_count": len(sheet.goals), "goals": [{"name": g.name, "pillars": [p.value for p in g.pillars] if g.pillars else [], "current_quests": g.current_quests} for g in sheet.goals]},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H1-H2"})+'\n')
        # #endregion
        
        # STATROLLER PHASE: Derive skill levels and calculate initial XP
        print("[StatRoller] Deriving skill levels for goals missing them...")
        for goal in sheet.goals:
            if not goal.skill_level and goal.pillars:
                planner = get_planner(goal.pillars[0].value)
                goal.skill_level = planner.derive_skill_level(goal.name, goal.current_quests)
                print(f"[StatRoller] Derived skill level for '{goal.name}': {goal.skill_level}/10")
        
        print("[StatRoller] Calculating initial XP based on user's past experience...")
        from src.onboarding.stat_roller import StatRollerAgent
        stat_roller = StatRollerAgent()
        initial_xp = stat_roller.calculate_initial_xp(sheet)
        
        # Update sheet XP fields
        sheet.xp_career = initial_xp.get("xp_career", 0)
        sheet.xp_physical = initial_xp.get("xp_physical", 0)
        sheet.xp_mental = initial_xp.get("xp_mental", 0)
        sheet.xp_social = initial_xp.get("xp_social", 0)
        sheet.xp_total = sheet.xp_career + sheet.xp_physical + sheet.xp_mental + sheet.xp_social
        
        print(f"[StatRoller] Initial XP awarded: Career={sheet.xp_career}, Physical={sheet.xp_physical}, Mental={sheet.xp_mental}, Social={sheet.xp_social}, Total={sheet.xp_total}")
        print(f"[StatRoller] Justification: {initial_xp.get('justification', '')}")
        
        # PHASE 4: Run planners to generate needed_quests
        # For goals with multiple pillars, we'll use the first pillar's planner
        for goal in sheet.goals:
            # #region agent log
            import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:planner_check","message":"Checking goal for planner","data":{"goal_name": goal.name, "pillars": [p.value for p in goal.pillars] if goal.pillars else [], "has_pillars": bool(goal.pillars)},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H2"})+'\n')
            # #endregion
            # Use the first pillar for the planner (could be enhanced to use multiple planners)
            if goal.pillars:
                planner = get_planner(goal.pillars[0].value)
                # Pass skill_level to planner (now that we've derived it)
                needed_skill_nodes = planner.generate_roadmap(
                    north_star=goal.name,
                    current_quests=goal.current_quests,
                    debuffs=sheet.debuffs,
                    skill_level=goal.skill_level or 1
                )
                goal.needed_quests = [node.name for node in needed_skill_nodes]
                # #region agent log
                import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:planner_result","message":"Planner generated needed_quests","data":{"goal_name": goal.name, "needed_quests": goal.needed_quests},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H2-H3"})+'\n')
                # #endregion
            else:
                # #region agent log
                import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:no_pillars","message":"SKIPPED - Goal has no pillars!","data":{"goal_name": goal.name},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H1"})+'\n')
                # #endregion
        
        # #region agent log
        import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:pre_skilltree","message":"Goals before skill tree generation","data":{"goals": [{"name": g.name, "pillars": [p.value for p in g.pillars] if g.pillars else [], "needed_quests": g.needed_quests} for g in sheet.goals]},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H3"})+'\n')
        # #endregion
        
        # PHASE 5: Generate skill tree from needed_quests
        skill_tree_generator = SkillTreeGenerator()
        skill_tree = skill_tree_generator.generate_skill_tree(sheet)
        
        # #region agent log
        import json as _json; open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a').write(_json.dumps({"location":"api.py:extract_profile:post_skilltree","message":"Skill tree generated","data":{"nodes_count": len(skill_tree.nodes), "node_types": {n.type.value: sum(1 for x in skill_tree.nodes if x.type == n.type) for n in skill_tree.nodes[:1]} if skill_tree.nodes else {}},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H3"})+'\n')
        # #endregion
        
        # DIRECTOR PHASE: Select 3-5 starter habits from top 2 prioritized pillars
        print("[Director] Selecting starter directives from top 2 prioritized pillars...")
        from src.onboarding.director import DirectorAgent
        from src.models import HabitProgress, NodeStatus, NodeType
        
        director = DirectorAgent()
        selected_node_ids, onboarding_message = director.select_starter_directives(skill_tree, sheet)
        
        # Initialize HabitProgress for all habit nodes, activate selected ones
        for node in skill_tree.nodes:
            if node.type == NodeType.HABIT:
                if node.id not in sheet.habit_progress:
                    sheet.habit_progress[node.id] = HabitProgress(node_id=node.id)
                
                # Activate if selected, otherwise lock
                if node.id in selected_node_ids:
                    sheet.habit_progress[node.id].status = NodeStatus.ACTIVE
                    print(f"[Director] Activated habit: {node.name} (ID: {node.id})")
                else:
                    sheet.habit_progress[node.id].status = NodeStatus.LOCKED
        
        print(f"[Director] Selected {len(selected_node_ids)} starter habits from top 2 pillars")
        print(f"[Director] Onboarding message: {onboarding_message}")
        
        # Return the complete profile with onboarding message
        return {
            "character_sheet": sheet.model_dump(),
            "skill_tree": skill_tree.model_dump(),
            "onboarding_message": onboarding_message
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Failed to extract profile: {str(e)}")
        print(f"[ERROR] Traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to extract profile: {str(e)}")


def _activate_initial_habits(sheet, skill_tree):
    """Activate 1-2 habits per pillar from the skill tree.
    
    This should be called after skill tree generation to automatically
    unlock some habits for the user to start working on.
    """
    import random
    from src.models import HabitProgress, NodeStatus, NodeType
    
    # Group habit nodes by pillar
    habits_by_pillar = {}
    for node in skill_tree.nodes:
        if node.type == NodeType.HABIT:
            pillar = node.pillar.value if hasattr(node.pillar, 'value') else str(node.pillar)
            if pillar not in habits_by_pillar:
                habits_by_pillar[pillar] = []
            habits_by_pillar[pillar].append(node)
    
    # Initialize habit_progress if it doesn't exist
    if not hasattr(sheet, 'habit_progress') or sheet.habit_progress is None:
        sheet.habit_progress = {}
    
    # Activate 1-2 habits per pillar
    for pillar, habit_nodes in habits_by_pillar.items():
        if not habit_nodes:
            continue
        
        # Randomly select 1-2 habits to activate
        num_to_activate = min(2, len(habit_nodes))
        selected_habits = random.sample(habit_nodes, num_to_activate)
        
        for habit_node in habit_nodes:
            node_id = habit_node.id
            if node_id not in sheet.habit_progress:
                # Create new progress entry
                sheet.habit_progress[node_id] = HabitProgress(node_id=node_id)
            
            # Activate if selected, otherwise keep as LOCKED
            if habit_node in selected_habits:
                sheet.habit_progress[node_id].status = NodeStatus.ACTIVE
            else:
                sheet.habit_progress[node_id].status = NodeStatus.LOCKED


@app.get("/api/profile/{user_id}")
def get_profile(user_id: str):
    """Return the saved profile JSON (character_sheet + skill_tree) for a user.

    This simply exposes the data stored via save_profile so the frontend
    dashboard can render the real character instead of mock data.
    SECURITY: Strips active_quiz_rubric from all responses.
    """

    data = load_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # SECURITY PATCH: Strip rubrics before sending to client
    # Create a deep copy to avoid mutating the original (prevents accidental DB writes)
    import copy
    clean_data = copy.deepcopy(data)
    sheet = clean_data.get("character_sheet", {})
    if "habit_progress" in sheet:
        for prog in sheet["habit_progress"].values():
            if "active_quiz_rubric" in prog:
                prog.pop("active_quiz_rubric")  # Remove sensitive key from copy only
    
    return clean_data


@app.get("/api/user/{user_id}")
def get_user_profile(user_id: str):
    """Alias for get_profile with security patch. Strips active_quiz_rubric from all responses."""
    return get_profile(user_id)


@app.post("/api/profile/{user_id}")
def save_profile_endpoint(user_id: str, payload: dict):
    """Save/overwrite a user's profile (character_sheet + skill_tree).

    The payload should be a dict matching the structure returned by
    `load_profile`, typically containing `character_sheet` and optional
    `skill_tree`. This performs a light pydantic validation of the
    `character_sheet` before saving.
    """
    try:
        # Optional validation of the nested character_sheet to catch schema errors early
        cs = payload.get("character_sheet") if isinstance(payload, dict) else None
        if cs is not None:
            try:
                CharacterSheet(**cs)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"character_sheet validation error: {e}")

        # Persist using existing storage helper (writes local JSON and attempts Firestore write)
        from src.storage import save_profile
        save_profile(payload, user_id)
        return {"ok": True, "message": "Profile saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile/{user_id}/activate-habits")
def activate_habits_endpoint(user_id: str):
    """Manually activate 1-2 habits per pillar for an existing profile.
    
    This is useful if the skill tree exists but habits weren't activated
    during onboarding.
    """
    from src.storage import load_profile, save_profile
    from src.models import CharacterSheet, SkillTree
    
    data = load_profile(user_id) or {}
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Load character sheet and skill tree
    cs_dict = data.get("character_sheet", {})
    tree_dict = data.get("skill_tree", {})
    
    if not tree_dict or not tree_dict.get("nodes"):
        raise HTTPException(status_code=400, detail="Skill tree not found or empty")
    
    sheet = CharacterSheet(**cs_dict)
    skill_tree = SkillTree(**tree_dict)
    
    # Activate habits
    _activate_initial_habits(sheet, skill_tree)
    
    # Save updated profile
    data["character_sheet"] = sheet.model_dump()
    save_profile(data, user_id)
    
    return {
        "ok": True,
        "message": f"Activated habits for {user_id}",
        "character_sheet": sheet.model_dump()
    }


@app.get("/api/profile/{user_id}/calendar")
def get_profile_calendar(user_id: str):
    """Return only the `calendar_events` list for a user profile.

    This is a lightweight endpoint useful for the frontend calendar view
    to avoid fetching the full profile payload.
    """
    data = load_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")

    cs = data.get("character_sheet") or data
    calendar = cs.get("calendar_events") if isinstance(cs, dict) else None
    if calendar is None:
        # Return empty list for clients that expect an array
        return {"calendar_events": []}
    return {"calendar_events": calendar}


@app.post("/api/profile/{user_id}/calendar")
def create_calendar_event(user_id: str, event: dict):
    """Create a single calendar event and save it into the user's CharacterSheet."""
    data = load_profile(user_id) or {}
    cs = data.setdefault("character_sheet", {})
    events = cs.setdefault("calendar_events", [])

    # Try to validate with the pydantic model if available
    evt_dict = dict(event)
    try:
        from src.models import CalendarEvent
        validated = CalendarEvent(**evt_dict)
        evt_dict = validated.dict()
    except Exception:
        pass

    if not evt_dict.get("id"):
        import uuid
        evt_dict["id"] = str(uuid.uuid4())

    # If event with same id exists, replace it
    for i, e in enumerate(events):
        if e.get("id") == evt_dict.get("id"):
            events[i] = evt_dict
            break
    else:
        events.append(evt_dict)

    from src.storage import save_profile
    save_profile(data, user_id)
    return {"calendar_event": evt_dict}


@app.put("/api/profile/{user_id}/calendar/{event_id}")
def update_calendar_event(user_id: str, event_id: str, event: dict):
    """Update a single calendar event by id."""
    data = load_profile(user_id) or {}
    cs = data.setdefault("character_sheet", {})
    events = cs.setdefault("calendar_events", [])

    for i, e in enumerate(events):
        if e.get("id") == event_id:
            updated = dict(e)
            updated.update(event)
            updated["id"] = event_id
            try:
                from src.models import CalendarEvent
                CalendarEvent(**updated)
            except Exception:
                pass
            events[i] = updated
            from src.storage import save_profile
            save_profile(data, user_id)
            return {"calendar_event": updated}

    raise HTTPException(status_code=404, detail="Event not found")


@app.delete("/api/profile/{user_id}/calendar/{event_id}")
def delete_calendar_event(user_id: str, event_id: str):
    """Delete a single calendar event by id."""
    data = load_profile(user_id) or {}
    cs = data.setdefault("character_sheet", {})
    events = cs.setdefault("calendar_events", [])

    for i, e in enumerate(events):
        if e.get("id") == event_id:
            events.pop(i)
            from src.storage import save_profile
            save_profile(data, user_id)
            return {"ok": True, "message": "Event deleted"}

    raise HTTPException(status_code=404, detail="Event not found")


@app.post("/api/skill-tree/generate-quiz/{skill_id}")
def generate_quiz(skill_id: str, user_id: str):
    """Generate a quiz for a skill on-demand (lazy loading). SECURITY: Store rubric in HabitProgress, return only question. Prevent reroll by checking active_quiz_question (infinite persistence, no expiration)."""
    from src.llm import LLMClient
    from src.models import HabitProgress, NodeStatus
    
    data = load_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    skill_tree = data.get("skill_tree")
    if not skill_tree:
        raise HTTPException(status_code=404, detail="Skill tree not found")
    
    # Find skill node
    skill_node = next((n for n in skill_tree.get("nodes", []) if n.get("id") == skill_id), None)
    if not skill_node:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    sheet = data.get("character_sheet", {})
    if skill_id not in sheet.get("habit_progress", {}):
        sheet.setdefault("habit_progress", {})[skill_id] = HabitProgress(node_id=skill_id).dict()
    
    progress = sheet["habit_progress"][skill_id]
    
    # NO REROLL: If active question exists, return it forever.
    if progress.get("active_quiz_question"):
        return {"question": progress["active_quiz_question"]}
    
    # Generate new quiz on-demand
    llm_client = LLMClient()
    prompt = f"""
    Generate a quiz question to test if someone has mastered: {skill_node.get("name")}
    Description: {skill_node.get("description", "")}
    
    Return JSON:
    {{
        "question": "What is the difference between a list and a tuple in Python?",
        "correct_answer_rubric": "Must mention: mutability, syntax differences, use cases"
    }}
    """
    messages = [{"role": "user", "content": prompt}]
    response = llm_client.chat_completion(messages, json_mode=True)
    quiz_data = json.loads(response)
    
    # Store rubric server-side (NEVER send to frontend)
    question = quiz_data.get("question", "")
    rubric = quiz_data.get("correct_answer_rubric", "")
    
    progress["active_quiz_question"] = question
    progress["active_quiz_rubric"] = rubric  # Stored server-side
    # NO EXPIRATION FIELD SET
    
    save_profile(data, user_id)
    
    # Return ONLY the question (security: rubric stays on server)
    return {"question": question}


@app.post("/api/skill-tree/test-out")
def test_out_skill(user_id: str, payload: dict):
    """Grade user's answer to a skill quiz and handle lockout. SECURITY: Rubric retrieved from server. Use UTC timezone consistently."""
    from src.llm import LLMClient
    from src.models import HabitProgress, NodeStatus
    from datetime import datetime, timedelta, timezone
    
    skill_id = payload.get("skill_id")
    user_answer = payload.get("answer")
    
    data = load_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    sheet = data.get("character_sheet", {})
    if skill_id not in sheet.get("habit_progress", {}):
        raise HTTPException(status_code=404, detail="No active quiz found for this skill")
    
    progress = sheet["habit_progress"][skill_id]
    
    # TIMEZONE SAFE LOCKOUT CHECK
    lockout = progress.get("quiz_lockout_until")
    if lockout:
        # Normalize to UTC
        lockout_str = lockout.replace("Z", "+00:00")
        lockout_dt = datetime.fromisoformat(lockout_str)
        if lockout_dt.tzinfo is None:
            lockout_dt = lockout_dt.replace(tzinfo=timezone.utc)
        
        now_utc = datetime.now(timezone.utc)
        if now_utc < lockout_dt:
            remaining = (lockout_dt - now_utc).total_seconds() / 3600
            raise HTTPException(
                status_code=429,
                detail=f"Quiz locked. Try again in {remaining:.1f} hours."
            )
    
    # Retrieve rubric from server (security: never trust frontend)
    question = progress.get("active_quiz_question")
    rubric = progress.get("active_quiz_rubric")
    
    if not question or not rubric:
        raise HTTPException(status_code=404, detail="No active quiz found. Generate a quiz first.")
    
    # Grade answer using server-stored rubric
    llm_client = LLMClient()
    grade_prompt = f"""
    Grade this answer to the quiz question.
    
    Question: {question}
    Correct Answer Rubric: {rubric}
    User's Answer: {user_answer}
    
    Return JSON:
    {{
        "passed": true/false,
        "feedback": "Explanation of why they passed/failed"
    }}
    """
    messages = [{"role": "user", "content": grade_prompt}]
    response = llm_client.chat_completion(messages, json_mode=True)
    grade_data = json.loads(response)
    
    # Update progress (using UTC)
    now_utc = datetime.now(timezone.utc)
    progress["last_quiz_attempt"] = now_utc.isoformat()
    
    if grade_data.get("passed"):
        # Mark as MASTERED, award 50% XP, clear active quiz
        progress["status"] = NodeStatus.MASTERED.value
        progress["quiz_lockout_until"] = None
        progress["active_quiz_question"] = None
        progress["active_quiz_rubric"] = None
        # Award XP logic here (50% of skill.xp_reward)
    else:
        # Lockout for 24h (UTC), clear active quiz
        lockout_until = now_utc + timedelta(hours=24)
        progress["quiz_lockout_until"] = lockout_until.isoformat()
        progress["active_quiz_question"] = None
        progress["active_quiz_rubric"] = None
    
    save_profile(data, user_id)
    
    return {
        "passed": grade_data.get("passed", False),
        "feedback": grade_data.get("feedback", ""),
        "lockout_until": progress.get("quiz_lockout_until")
    }


@app.post("/api/profile/{user_id}/task/{node_id}/toggle")
def toggle_task_completion(user_id: str, node_id: str, payload: dict = None):
    """Toggle completion status of a task for today.
    
    Creates or updates a daily report entry for today with the task completion status.
    If payload.completed is True, marks as completed; if False, marks as not completed.
    """
    from datetime import date
    from src.models import DailyTaskStatus, DailyTaskReport, DailyReport
    
    data = load_profile(user_id) or {}
    cs = data.setdefault("character_sheet", {})
    skill_tree = data.get("skill_tree", {})
    
    # Get today's date
    today = date.today().isoformat()
    
    # Get the node to find the task name
    node = None
    if skill_tree.get("nodes"):
        node = next((n for n in skill_tree["nodes"] if n.get("id") == node_id), None)
    
    task_name = node.get("name", "Unknown Task") if node else "Unknown Task"
    
    # Get or create today's daily report
    daily_reports = cs.setdefault("daily_reports", [])
    today_report = next((r for r in daily_reports if r.get("date") == today), None)
    
    if not today_report:
        # Create a new daily report for today
        today_report = {
            "date": today,
            "summary": "",
            "sentiment": "neutral",
            "wins": [],
            "struggles": [],
            "reflections": [],
            "free_text": "",
            "tasks": [],
            "stats_delta": {
                "stats_career": {},
                "stats_physical": {},
                "stats_mental": {},
                "stats_social": {},
                "xp_career": 0,
                "xp_physical": 0,
                "xp_mental": 0,
                "xp_social": 0,
                "xp_total": 0
            },
            "new_tasks": [],
            "new_skill_nodes": []
        }
        daily_reports.append(today_report)
    
    # Get completion status from payload, default to toggle
    completed = payload.get("completed") if payload else None
    if completed is None:
        # Toggle: check if already completed
        existing_task = next((t for t in today_report.get("tasks", []) if t.get("node_id") == node_id), None)
        completed = not (existing_task and (existing_task.get("status") == "DONE" or existing_task.get("status") == "COMPLETED" or existing_task.get("completed_repetitions", 0) > 0))
    
    # Find or create task report
    tasks = today_report.setdefault("tasks", [])
    task_report = next((t for t in tasks if t.get("node_id") == node_id), None)
    
    if not task_report:
        # Create new task report
        task_report = {
            "task_id": f"{today}_{node_id}",
            "node_id": node_id,
            "status": DailyTaskStatus.DONE.value if completed else DailyTaskStatus.PENDING.value,
            "completed_repetitions": 1 if completed else 0,
            "user_comment": None
        }
        tasks.append(task_report)
    else:
        # Update existing task report
        task_report["status"] = DailyTaskStatus.DONE.value if completed else DailyTaskStatus.PENDING.value
        task_report["completed_repetitions"] = 1 if completed else 0
    
    # Update last_report_date
    cs["last_report_date"] = today
    
    # Save the profile
    from src.storage import save_profile
    save_profile(data, user_id)
    
    return {
        "ok": True,
        "completed": completed,
        "task_id": task_report["task_id"],
        "node_id": node_id
    }


@app.post("/api/reporting/chat")
def reporting_chat(payload: ReportingChatRequest):
    """Handle reporting agent conversation.
    
    Processes user messages through the ReportingAgent and returns responses.
    """
    from datetime import date
    from src.reporting import ReportingAgent
    from src.reporting.scheduler import get_todays_tasks, ensure_daily_schedule_for_date
    from src.models import ReportingState, CharacterSheet, SkillTree
    from src.storage import load_profile, save_profile
    
    # Load user profile
    data = load_profile(payload.user_id)
    if not data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    # Load character sheet and skill tree
    cs_dict = data.get("character_sheet", {})
    tree_dict = data.get("skill_tree", {})
    
    sheet = CharacterSheet(**cs_dict) if cs_dict else CharacterSheet(user_id=payload.user_id)
    tree = SkillTree(**tree_dict) if tree_dict else SkillTree(nodes=[])
    
    current_date = date.today().isoformat()
    
    # Get today's tasks
    todays_tasks = get_todays_tasks(sheet, tree, current_date=current_date)
    ensure_daily_schedule_for_date(sheet, todays_tasks, current_date=current_date)
    
    # Initialize or restore reporting state
    # For simplicity, we'll create a fresh state each time, but in production
    # you might want to persist this in the user's profile
    state = ReportingState(
        user_id=payload.user_id,
        current_date=current_date,
        todays_tasks=todays_tasks,
        phase="collecting",
        conversation_history=payload.conversation_history,
    )
    
    agent = ReportingAgent()
    
    # Handle the message
    user_message = payload.message.strip()
    
    # Check if this is the first message (initial greeting)
    if not state.conversation_history:
        # Return initial greeting
        initial_msg = agent.initial_message(state, sheet)
        state.conversation_history.append({"role": "assistant", "content": initial_msg})
        
        # If user provided a message, process it
        if user_message:
            state.conversation_history.append({"role": "user", "content": user_message})
            reply = agent.generate_reply(state, sheet, tree, user_message)
            state.conversation_history.append({"role": "assistant", "content": reply})
        else:
            # Just return the initial message
            reply = initial_msg
    else:
        # Add user message to history
        state.conversation_history.append({"role": "user", "content": user_message})
        
        # Check for confirmation
        lowered = user_message.lower()
        if "confirm" in lowered or "done" in lowered:
            if state.phase == "collecting":
                # Generate draft report
                draft = agent.finalize_report(state, sheet, tree)
                state.pending_report = draft
                state.phase = "review"
                reply = f"Here's a draft summary of your day:\n\n{draft.summary}\n\nDoes this work for you? Type 'confirm' again to save."
            elif state.phase == "review":
                # Finalize and save
                draft = state.pending_report
                if draft:
                    from src.reporting.apply_updates import apply_daily_report
                    apply_daily_report(sheet, tree, draft)
                    save_profile({
                        "character_sheet": sheet.model_dump(),
                        "skill_tree": tree.model_dump(),
                    }, payload.user_id)
                    reply = f"Report saved for {current_date}. Summary: {draft.summary}"
                    state.phase = "complete"
                else:
                    reply = "No draft report found. Starting over."
                    state.phase = "collecting"
            else:
                reply = agent.generate_reply(state, sheet, tree, user_message)
        else:
            # Regular conversation
            reply = agent.generate_reply(state, sheet, tree, user_message)
        
        state.conversation_history.append({"role": "assistant", "content": reply})
    
    return {
        "reply": reply,
        "conversation_history": state.conversation_history,
        "phase": state.phase,
        "is_complete": state.phase == "complete"
    }


@app.post("/api/profile/{user_id}/quest/add")
def add_quest_to_goal(user_id: str, payload: dict):
    """Add a new quest/task to a goal's current_quests list.
    
    Expects payload with:
    - task_name: str (the name of the new task/quest)
    - goal_name: str (the name of the goal to add it to)
    """
    data = load_profile(user_id) or {}
    cs = data.setdefault("character_sheet", {})
    
    task_name = payload.get("task_name", "").strip()
    goal_name = payload.get("goal_name", "").strip()
    
    if not task_name or not goal_name:
        raise HTTPException(status_code=400, detail="task_name and goal_name are required")
    
    # Find the goal - handle both array and dict formats
    goals = cs.get("goals", [])
    if isinstance(goals, dict):
        goals = list(goals.values())
    elif not isinstance(goals, list):
        goals = []
    
    goal = None
    goal_index = None
    for idx, g in enumerate(goals):
        if isinstance(g, dict) and g.get("name") == goal_name:
            goal = g
            goal_index = idx
            break
        elif isinstance(g, str) and g == goal_name:
            # Handle case where goals might be a list of strings
            goal = {"name": g, "current_quests": []}
            goal_index = idx
            break
    
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal '{goal_name}' not found")
    
    # If goal was a string, convert it to a dict
    if isinstance(goal, str):
        goal = {"name": goal, "current_quests": []}
        if goal_index is not None:
            goals[goal_index] = goal
    
    # Ensure current_quests exists and is a list
    if "current_quests" not in goal:
        goal["current_quests"] = []
    if not isinstance(goal["current_quests"], list):
        goal["current_quests"] = list(goal["current_quests"]) if goal["current_quests"] else []
    
    # Check if task already exists
    if task_name in goal["current_quests"]:
        raise HTTPException(status_code=400, detail=f"Task '{task_name}' already exists in goal '{goal_name}'")
    
    # Add the task
    goal["current_quests"].append(task_name)
    
    # Save the profile
    from src.storage import save_profile
    save_profile(data, user_id)
    
    return {
        "ok": True,
        "task_name": task_name,
        "goal_name": goal_name,
        "message": f"Task '{task_name}' added to goal '{goal_name}'"
    }


@app.post("/api/chat/gemini")
def gemini_chat(payload: dict):
    """Chat endpoint using Gemini API for lock-in mode."""
    from src.llm import LLMClient
    
    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Messages are required")
    
    try:
        llm_client = LLMClient()
        # Use the default model from LLMClient (which is configured via env var)
        # Don't specify a model, let it use the default
        response = llm_client.chat_completion(messages)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gemini-map/generate")
async def gemini_map_generate(payload: dict):
    """Endpoint for Gemini map view - proxies to Gemini API with file attachments support."""
    import os
    import urllib.request
    import urllib.parse
    import json
    import traceback
    import time
    import re
    
    # Support multiple API keys for rate limit rotation (like LLMClient)
    api_keys = []
    api_key_1 = os.getenv("GEMINI_API_KEY")
    api_key_2 = os.getenv("GEMINI_API_KEY_2")
    if api_key_1:
        api_keys.append(api_key_1)
    if api_key_2:
        api_keys.append(api_key_2)
    
    if not api_keys:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    # Map invalid model names to valid ones
    model_mapping = {
        "gemini-2.5-flash": "gemini-2.0-flash-exp",
        "gemini-2.5-pro": "gemini-1.5-pro-001",
    }
    
    requested_model = payload.get("model", "gemini-2.0-flash-exp")
    model = model_mapping.get(requested_model, requested_model)
    
    # Fallback to other valid models if the requested one fails
    fallback_models = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash-001",
        "gemini-1.5-flash",
        "gemini-1.5-pro-001",
        "gemini-1.5-pro"
    ]
    
    contents = payload.get("contents", [])
    if not contents:
        raise HTTPException(status_code=400, detail="No contents provided in request")
    
    # Try the requested model, then fallback models
    models_to_try = [model] + [m for m in fallback_models if m != model]
    last_error = None
    
    # Try each API key
    for api_key_idx, api_key in enumerate(api_keys):
        for model_to_try in models_to_try:
            try:
                # Use the REST API directly to match the original HTML implementation
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_try}:generateContent?key={api_key}"
                
                request_data = {
                    "contents": contents
                }
                
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(request_data).encode('utf-8'), 
                    headers={'Content-Type': 'application/json'}
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    # Check for API errors in response
                    if 'error' in data:
                        error_msg = data['error'].get('message', 'Unknown API error')
                        raise Exception(f"Gemini API error: {error_msg}")
                    return data
                    
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if hasattr(e, 'read') else ""
                error_data = {}
                retry_after = None
                
                try:
                    error_data = json.loads(error_body) if error_body else {}
                    error_msg = error_data.get('error', {}).get('message', str(e))
                except:
                    error_msg = str(e)
                
                # Handle rate limiting (429)
                if e.code == 429:
                    # Extract retry-after time from error message
                    retry_match = re.search(r'retry in ([\d.]+)s', error_msg, re.IGNORECASE)
                    if retry_match:
                        retry_after = float(retry_match.group(1))
                    
                    # If we have multiple API keys, try the next one
                    if api_key_idx < len(api_keys) - 1:
                        print(f"[Gemini Map] Rate limit on API key {api_key_idx + 1}, trying next key...")
                        break  # Break out of model loop, try next API key
                    else:
                        # Last API key, return rate limit error with retry info
                        detail = f"Rate limit exceeded. {error_msg}"
                        if retry_after:
                            detail += f" Please retry after {int(retry_after)} seconds."
                        raise HTTPException(
                            status_code=429, 
                            detail=detail,
                            headers={"Retry-After": str(int(retry_after)) if retry_after else "60"}
                        )
                
                # Handle model not found (404)
                if e.code == 404 and model_to_try != models_to_try[-1]:
                    print(f"[Gemini Map] Model {model_to_try} not found, trying fallback...")
                    continue
                
                # For other errors, try next API key if available
                if api_key_idx < len(api_keys) - 1 and e.code >= 500:
                    print(f"[Gemini Map] Error {e.code} on API key {api_key_idx + 1}, trying next key...")
                    break
                
                # Last attempt or non-retryable error
                last_error = f"HTTP {e.code}: {error_msg}"
                raise HTTPException(status_code=500, detail=f"Gemini API error with model {model_to_try}: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                error_trace = traceback.format_exc()
                print(f"[Gemini Map] Error with model {model_to_try} on API key {api_key_idx + 1}: {error_trace}")
                
                # If this is the last model and last API key, raise the error
                if model_to_try == models_to_try[-1] and api_key_idx == len(api_keys) - 1:
                    raise HTTPException(status_code=500, detail=f"All models and API keys failed. Last error: {last_error}")
                
                # Otherwise, try next model or API key
                if model_to_try != models_to_try[-1]:
                    continue
                elif api_key_idx < len(api_keys) - 1:
                    break  # Try next API key
    
    # Should never reach here, but just in case
    raise HTTPException(status_code=500, detail=f"Failed to generate content: {last_error}")


@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    """Relay architect text to ElevenLabs TTS and send back audio.

    The browser sends JSON text frames of the form:

        {"type": "tts-text", "text": "..."}

    This endpoint calls ElevenLabs' HTTP text-to-speech API (configured to
    return 16-bit PCM) and forwards the resulting audio bytes back to the
    browser as a single binary frame per request. This avoids relying on
    client WebSocket headers, which aren't supported by the current
    websockets library version in this environment.
    """

    await websocket.accept()

    if not ELEVENLABS_API_KEY:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "code": "missing_api_key",
                    "message": "ELEVENLABS_API_KEY is not configured on the server.",
                }
            )
        )
        await websocket.close()
        return

    async def fetch_tts_audio(text: str) -> bytes | None:
        """Call ElevenLabs HTTP TTS API and return compressed audio bytes.

        We run the blocking HTTP call in a thread via asyncio.to_thread so we
        don't block the event loop.
        """

        def _call() -> bytes | None:
            try:
                url = (
                    f"https://api.elevenlabs.io/v1/text-to-speech/"
                    f"{ELEVENLABS_VOICE_ID}"
                )
                payload = {
                    "text": text,
                    "model_id": ELEVENLABS_MODEL_ID,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                        "speed": 1.1,  # Max speed (20% faster) - maintains pitch (ElevenLabs limit: 0.7-1.2)
                    },
                    # Request MP3 output and let the browser decode it via
                    # AudioContext.decodeAudioData, which is more robust than
                    # manually handling raw PCM across environments.
                    "output_format": "mp3_44100_128",
                }
                data = json.dumps(payload).encode("utf-8")
                headers = {
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                }
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:  # nosec: B310
                    return resp.read()
            except urllib.error.HTTPError as exc:  # noqa: PERF203
                try:
                    body = exc.read().decode("utf-8", errors="ignore")
                except Exception:
                    body = ""
                try:
                    print("[voice_ws] ElevenLabs HTTP error:", exc.code, body[:200])
                except Exception:
                    pass
                return None
            except Exception as exc:  # noqa: BLE001
                try:
                    print("[voice_ws] error calling ElevenLabs REST TTS:", repr(exc))
                except Exception:
                    pass
                return None

        return await asyncio.to_thread(_call)

    try:
        while True:
            message = await websocket.receive()

            # Starlette sends a final `websocket.disconnect` message before closing;
            # if we see it, break the loop so we don't call receive() again.
            msg_scope_type = message.get("type")
            if msg_scope_type == "websocket.disconnect":
                break

            # Debug: log everything received from the browser.
            try:
                print("[voice_ws] received from browser:", message)
            except Exception:
                pass

            data_bytes = message.get("bytes")
            data_text = message.get("text")

            # Mic audio (binary) is currently ignored in this TTS-only phase.
            if data_bytes is not None:
                continue

            if data_text is None:
                continue

            try:
                payload = json.loads(data_text)
            except json.JSONDecodeError:
                # If client sends plain text, treat it as a TTS request body.
                payload = {"type": "tts-text", "text": data_text}

            msg_type = payload.get("type")
            if msg_type != "tts-text":
                # Ignore unknown message types for now.
                continue

            text = (payload.get("text") or "").strip()
            if not text:
                continue

            # Call ElevenLabs HTTP TTS and forward the resulting audio bytes
            # to the browser as a single binary frame.
            try:
                print("[voice_ws] requesting ElevenLabs REST TTS for text:", text[:80])
            except Exception:
                pass

            audio_bytes = await fetch_tts_audio(text)
            if not audio_bytes:
                # Inform the frontend that TTS failed so it can surface a
                # helpful message in the UI if desired.
                try:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "code": "eleven_tts_failed",
                                "message": "Failed to generate audio from ElevenLabs.",
                            }
                        )
                    )
                except Exception:
                    pass
                continue

            try:
                print(
                    "[voice_ws] sending audio bytes to browser:",
                    len(audio_bytes),
                )
            except Exception:
                pass

            await websocket.send_bytes(audio_bytes)
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError("Cannot call 'receive' once a disconnect message has been received.")
        # can occur if the client disconnects mid-loop; treat it the same as
        # a normal WebSocketDisconnect and clean up.
        pass
    finally:
        # Nothing additional to clean up; the only external resource is the
        # HTTP client in fetch_tts_pcm, which is created and torn down per
        # request.
        pass


@app.post("/api/skill-tree/node/question")
def ask_node_question(payload: dict):
    """Handle user questions about a skill tree node (clarification only, no modifications)."""
    from src.llm import LLMClient
    from src.models import SkillNode, NodeType
    
    user_id = payload.get("user_id")
    node_id = payload.get("node_id")
    question = payload.get("question")
    
    if not user_id or not node_id or not question:
        raise HTTPException(status_code=400, detail="Missing required fields: user_id, node_id, question")
    
    # Load profile and skill tree
    data = load_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    skill_tree_dict = data.get("skill_tree")
    if not skill_tree_dict:
        raise HTTPException(status_code=404, detail="Skill tree not found")
    
    # Find the node
    nodes = skill_tree_dict.get("nodes", [])
    node_dict = next((n for n in nodes if n.get("id") == node_id), None)
    if not node_dict:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Convert to SkillNode for easier access
    node = SkillNode(**node_dict)
    
    # Generate clarification using LLM
    llm_client = LLMClient()
    prompt = f"""The user is asking a question about a skill/habit in a Life RPG system.

NODE INFORMATION:
- Name: {node.name}
- Type: {node.type.value}
- Description: {node.description or "No description provided"}
- Required completions: {node.required_completions or 30}
- Pillar: {node.pillar.value if hasattr(node.pillar, 'value') else node.pillar}
- XP Reward: {node.xp_reward}

USER'S QUESTION:
"{question}"

Provide a helpful, clear answer that clarifies what this node/habit/skill is about and how to approach it. 
Be encouraging and practical. If the question is about difficulty or completion, explain the requirements clearly.
Keep your response concise (2-4 sentences) and actionable.

Answer:"""
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        answer = llm_client.chat_completion(messages, json_mode=False)
        return {
            "answer": answer.strip(),
            "node": node.model_dump()
        }
    except Exception as e:
        print(f"Error generating answer: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")


@app.post("/api/skill-tree/node/adjust-difficulty")
def adjust_node_difficulty(payload: dict):
    """Adjust the difficulty of a habit or sub-skill node.
    
    For "easier": Creates intermediate prerequisite nodes that lead up to the target node.
    For "harder": Modifies the current node to be harder (increases difficulty/complexity).
    """
    # #region agent log
    import json as json_log
    import time
    try:
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:entry","message":"Endpoint called","data":{"payload_keys":list(payload.keys()),"user_id":payload.get("user_id"),"node_id":payload.get("node_id"),"direction":payload.get("direction"),"amount":payload.get("amount"),"has_reason":bool(payload.get("reason"))},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1,H2"}) + '\n')
    except: pass
    # #endregion
    
    try:
        from src.skill_tree.node_regenerator import regenerate_node_with_difficulty, generate_easier_prerequisite_nodes
        from src.models import SkillNode, SkillTree, NodeType
    except Exception as import_err:
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:import-error","message":"Import failed","data":{"error":str(import_err),"errorType":type(import_err).__name__},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H3"}) + '\n')
        except: pass
        # #endregion
        raise HTTPException(status_code=500, detail=f"Import error: {str(import_err)}")
    
    user_id = payload.get("user_id")
    node_id = payload.get("node_id")
    direction = payload.get("direction")  # "easier" or "harder"
    amount = payload.get("amount")  # "little", "moderate", "a_lot"
    reason = payload.get("reason")  # Optional user-provided reason
    
    # #region agent log
    try:
        import time
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:params_extracted","message":"Extracted parameters from payload","data":{"user_id":user_id,"node_id":node_id,"direction":direction,"amount":amount,"reason":reason},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1"}) + '\n')
    except: pass
    # #endregion
    
    # #region agent log
    try:
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:validation","message":"Validating parameters","data":{"user_id":user_id,"node_id":node_id,"direction":direction,"amount":amount,"hasAllRequired":bool(user_id and node_id and direction and amount)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H1"}) + '\n')
    except: pass
    # #endregion
    
    if not user_id or not node_id or not direction or not amount:
        raise HTTPException(status_code=400, detail="Missing required fields: user_id, node_id, direction, amount")
    
    if direction not in ["easier", "harder"]:
        raise HTTPException(status_code=400, detail="direction must be 'easier' or 'harder'")
    
    if amount not in ["little", "moderate", "a_lot"]:
        raise HTTPException(status_code=400, detail="amount must be 'little', 'moderate', or 'a_lot'")
    
    # Load profile and skill tree
    # #region agent log
    try:
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:pre-load","message":"About to load profile","data":{"user_id":user_id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H2"}) + '\n')
    except: pass
    # #endregion
    
    try:
        from src.storage import load_profile
        from src.models import CharacterSheet
        data = load_profile(user_id)
    except Exception as load_err:
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:load-error","message":"load_profile failed","data":{"error":str(load_err),"errorType":type(load_err).__name__},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H2"}) + '\n')
        except: pass
        # #endregion
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {str(load_err)}")
    
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Load character sheet for planner context
    character_sheet_dict = data.get("character_sheet")
    if character_sheet_dict:
        try:
            character_sheet = CharacterSheet(**character_sheet_dict)
        except Exception as cs_err:
            print(f"Warning: Failed to load character sheet, using empty one: {cs_err}")
            character_sheet = CharacterSheet(user_id=user_id)
    else:
        character_sheet = CharacterSheet(user_id=user_id)
    
    skill_tree_dict = data.get("skill_tree")
    if not skill_tree_dict:
        raise HTTPException(status_code=404, detail="Skill tree not found")
    
    # Find the node
    nodes = skill_tree_dict.get("nodes", [])
    node_dict = next((n for n in nodes if n.get("id") == node_id), None)
    if not node_dict:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Convert to SkillNode
    # #region agent log
    try:
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:pre-convert","message":"About to convert to SkillNode","data":{"node_dict_keys":list(node_dict.keys()),"node_type":node_dict.get("type")},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H3"}) + '\n')
    except: pass
    # #endregion
    
    try:
        node = SkillNode(**node_dict)
    except Exception as convert_err:
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:convert-error","message":"SkillNode conversion failed","data":{"error":str(convert_err),"errorType":type(convert_err).__name__,"node_dict":node_dict},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H3"}) + '\n')
        except: pass
        # #endregion
        raise HTTPException(status_code=500, detail=f"Failed to convert node: {str(convert_err)}")
    
    # Only allow difficulty adjustment for Habits and Sub-Skills
    if node.type not in [NodeType.HABIT, NodeType.SUB_SKILL]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot adjust difficulty for {node.type.value} nodes. Only Habits and Sub-Skills can be adjusted."
        )
    
    # Build set of used IDs to avoid conflicts
    used_ids = {n.get("id") for n in nodes if n.get("id")}
    
    # #region agent log
    try:
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:pre-process","message":"About to process difficulty adjustment","data":{"direction":direction,"node_type":node.type.value if hasattr(node.type,'value') else str(node.type),"node_id":node.id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H4,H5"}) + '\n')
    except: pass
    # #endregion
    
    try:
        if direction == "easier":
            # #region agent log
            try:
                with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:pre-generate-easier","message":"About to generate easier nodes","data":{"amount":amount,"used_ids_count":len(used_ids)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H4"}) + '\n')
            except: pass
            # #endregion
            # Convert existing skill tree nodes to SkillNode objects for deduplication
            existing_skill_tree_nodes = []
            node_dict_to_index_map = {}  # Map node ID to index in nodes list for updates
            for i, node_dict_item in enumerate(nodes):
                try:
                    existing_node = SkillNode(**node_dict_item)
                    existing_skill_tree_nodes.append(existing_node)
                    node_dict_to_index_map[existing_node.id] = i
                except Exception:
                    # Skip invalid nodes
                    continue
            
            # Generate intermediate prerequisite nodes using planner system (with deduplication)
            intermediate_nodes = generate_easier_prerequisite_nodes(
                node, 
                amount=amount, 
                reason=reason, 
                used_ids=used_ids,
                character_sheet=character_sheet,
                existing_skill_tree_nodes=existing_skill_tree_nodes  # Pass for pillar-scoped deduplication
            )
            
            if not intermediate_nodes:
                raise HTTPException(status_code=500, detail="Failed to generate easier prerequisite nodes")
            
            # The function returns only NEW nodes. Reused nodes were modified in-place in existing_skill_tree_nodes.
            # Update the skill tree's nodes list to reflect changes to reused nodes (prerequisites merged).
            # Create a mapping of modified existing nodes by ID
            modified_existing_nodes_by_id = {n.id: n for n in existing_skill_tree_nodes}
            
            # Update existing nodes in the skill tree that were reused and modified
            for node_id, node_index in node_dict_to_index_map.items():
                if node_id in modified_existing_nodes_by_id:
                    # This node was potentially modified (prerequisites merged), update it
                    updated_node = modified_existing_nodes_by_id[node_id]
                    nodes[node_index] = updated_node.model_dump()
            
            # Separate Sub-Skills from Habits in the NEW nodes returned
            new_subskill_nodes = [n for n in intermediate_nodes if n.type == NodeType.SUB_SKILL]
            habit_nodes = [n for n in intermediate_nodes if n.type == NodeType.HABIT]
            
            # Find terminal Sub-Skill nodes from BOTH new nodes AND potentially reused nodes
            # Terminal nodes = Sub-Skills that are NOT prerequisites for other Sub-Skills in the same pillar
            all_subskill_ids_in_pillar = {n.id for n in existing_skill_tree_nodes if n.type == NodeType.SUB_SKILL and n.pillar == node.pillar}
            all_subskill_ids_in_pillar.update({n.id for n in new_subskill_nodes})
            
            # Collect all prerequisite IDs from all Sub-Skills in this pillar (including reused ones)
            all_subskill_prereq_ids = set()
            for existing_node in existing_skill_tree_nodes:
                if existing_node.type == NodeType.SUB_SKILL and existing_node.pillar == node.pillar:
                    for prereq_id in (existing_node.prerequisites or []):
                        if prereq_id in all_subskill_ids_in_pillar:
                            all_subskill_prereq_ids.add(prereq_id)
            for subskill in new_subskill_nodes:
                for prereq_id in (subskill.prerequisites or []):
                    if prereq_id in all_subskill_ids_in_pillar:
                        all_subskill_prereq_ids.add(prereq_id)
            
            # Terminal nodes are Sub-Skills that are not prerequisites of any other Sub-Skill
            terminal_subskill_ids = []
            
            # Terminal nodes from new Sub-Skills
            for subskill in new_subskill_nodes:
                if subskill.id not in all_subskill_prereq_ids:
                    terminal_subskill_ids.append(subskill.id)
            
            # Terminal nodes from existing/reused Sub-Skills in this pillar
            for existing_node in existing_skill_tree_nodes:
                if (existing_node.type == NodeType.SUB_SKILL and 
                    existing_node.pillar == node.pillar and 
                    existing_node.id not in all_subskill_prereq_ids):
                    # Only include if this node was actually used in the breakdown (check if it's in our processed set)
                    # For now, include all terminal Sub-Skills in the pillar (safe but might be too broad)
                    # TODO: Track which nodes were actually reused to be more precise
                    terminal_subskill_ids.append(existing_node.id)
            
            # Remove duplicates
            terminal_subskill_ids = list(set(terminal_subskill_ids))
            
            # If no terminal nodes found, use new Sub-Skills with no prerequisites
            if not terminal_subskill_ids:
                terminal_subskill_ids = [n.id for n in new_subskill_nodes if not n.prerequisites]
            
            # Update original node's prerequisites: add terminal Sub-Skill nodes
            original_node_dict = node_dict.copy()
            original_prereqs = list(original_node_dict.get("prerequisites", []) or [])
            
            # Add terminal nodes to original node's prerequisites
            for terminal_id in terminal_subskill_ids:
                if terminal_id not in original_prereqs:
                    original_prereqs.append(terminal_id)
            
            original_node_dict["prerequisites"] = original_prereqs
            
            # Add all intermediate nodes to the skill tree
            for intermediate_node in intermediate_nodes:
                nodes.append(intermediate_node.model_dump())
                used_ids.add(intermediate_node.id)
            
            # Update the original node in the tree
            node_index = next((i for i, n in enumerate(nodes) if n.get("id") == node_id), None)
            if node_index is not None:
                nodes[node_index] = original_node_dict
            
            # Return the last intermediate node as the "updated_node" (closest to original)
            result_node = intermediate_nodes[-1].model_dump()
            
        else:  # direction == "harder"
            # #region agent log
            try:
                with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:pre-regenerate","message":"About to regenerate node harder","data":{"amount":amount},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H5"}) + '\n')
            except: pass
            # #endregion
            # Modify the current node to be harder
            updated_node = regenerate_node_with_difficulty(node, direction, amount, reason=reason)
            
            # Update the node in the skill tree
            node_index = next((i for i, n in enumerate(nodes) if n.get("id") == node_id), None)
            if node_index is not None:
                nodes[node_index] = updated_node.model_dump()
            
            result_node = updated_node.model_dump()
            intermediate_nodes = []  # No intermediate nodes for harder
        
    except ValueError as e:
        # This is the "easier" case error from regenerate_node_with_difficulty
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:value-error","message":"ValueError caught","data":{"error":str(e)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H4"}) + '\n')
        except: pass
        # #endregion
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # #region agent log
        try:
            import traceback
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_log.dumps({"location":"api.py:adjust_node_difficulty:exception","message":"Exception caught","data":{"error":str(e),"errorType":type(e).__name__,"traceback":traceback.format_exc()},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H4,H5"}) + '\n')
        except: pass
        # #endregion
        print(f"Error adjusting node difficulty: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to adjust difficulty: {str(e)}")
    
    # Save updated profile
    skill_tree_dict["nodes"] = nodes
    data["skill_tree"] = skill_tree_dict
    save_profile(data, user_id)
    
    return {
        "updated_node": result_node,
        "new_nodes": [n.model_dump() for n in intermediate_nodes] if direction == "easier" else [],
        "skill_tree": skill_tree_dict
    }
