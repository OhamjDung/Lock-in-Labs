from typing import List, Dict

import asyncio
import base64
import json
import os
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


load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "kqVT88a5QfII1HNAEPTJ") 
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")


app = FastAPI()

# Allow the Vite dev server to talk to this API during development
app.add_middleware(
    CORSMiddleware,
    # Allow both common Vite dev ports so the noir UI can
    # talk to this API even if the dev server changes ports.
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
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


@app.post("/api/onboarding/architect-reply")
def architect_reply(payload: ArchitectRequest):
    """Return a single Architect reply for the given history and user input.

    This is a thin HTTP wrapper around ArchitectAgent.generate_response so the
    frontend can drive the noir onboarding chat.
    """

    from src.onboarding.agent import CriticAgent
    from src.models import PendingDebuff, PendingGoal, Pillar

    sheet = CharacterSheet(user_id="user_01")
    state = ConversationState(
        missing_fields=[
            "north_star_goals",
            "current_quests",
            "stats_career",
            "stats_physical",
            "stats_mental",
            "stats_social",
        ],
        current_topic="Intro",
        phase=payload.phase,
    )
    
    # Convert pending debuffs from frontend to PendingDebuff objects
    state.pending_debuffs = [
        PendingDebuff(**d) for d in payload.pending_debuffs
    ]
    
    # Convert pillars asked about from frontend
    state.pillars_asked_about = []
    for p in payload.pillars_asked_about:
        try:
            state.pillars_asked_about.append(Pillar(p.upper()))
        except (ValueError, AttributeError):
            print(f"[Warning] Invalid pillar value: {p}")
            continue
    
    # Convert pending goals from frontend to PendingGoal objects
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

    # Seed conversation history with what the frontend has seen so far.
    state.conversation_history = [
        {"role": m.role, "content": m.content} for m in payload.history
    ]

    architect = ArchitectAgent()
    critic = CriticAgent()

    # Process ALL previous user messages through Critic to build up the character sheet
    # This ensures progress is calculated correctly based on accumulated goals
    # Process conversation history to build up the sheet state
    # CRITICAL: This must preserve ALL goals from previous messages
    for msg in state.conversation_history:
        if msg["role"] == "user":
            # Store goals before processing to ensure we don't lose any
            goals_before_processing = {g.name.lower(): g for g in sheet.goals}
            sheet, _, _, _ = critic.analyze(
                msg["content"], 
                sheet, 
                state.conversation_history[:state.conversation_history.index(msg) + 1],
                state.phase
            )
            # Ensure all previous goals are still present (safety check)
            for goal_name, goal_obj in goals_before_processing.items():
                if not any(g.name.lower() == goal_name for g in sheet.goals):
                    # Goal was lost - restore it
                    print(f"[WARNING] Goal '{goal_obj.name}' was lost during processing, restoring it")
                    sheet.goals.append(goal_obj)

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
    
    # Store goals before processing to detect new ones
    goals_before = {g.name: g for g in sheet.goals}
    
    sheet, feedback, critic_analysis, new_pending_debuffs = critic.analyze(
        payload.user_input, 
        sheet, 
        history_plus_user,
        state.phase
    )
    
    # Phase transition logic - Check AFTER processing current message
    # Check if all 4 pillars have at least 1 goal AND each has at least one pure goal
    all_pillars_in_goals_set = set()
    for goal in sheet.goals:
        all_pillars_in_goals_set.update(goal.pillars)
    
    def has_pure_goal_for_pillar(goals, pillar):
        """Check if a pillar has at least one pure goal (single-pillar goal)."""
        return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
    
    all_4_pillars_covered = len(all_pillars_in_goals_set) >= 4
    all_pillars_have_pure_goals = all(
        has_pure_goal_for_pillar(sheet.goals, p) for p in Pillar if p in all_pillars_in_goals_set
    ) if all_4_pillars_covered else False
    
    # Debug phase transition - ALWAYS initialize this
    phase_transition_debug = {
        "current_phase": state.phase,
        "all_4_pillars_covered": all_4_pillars_covered,
        "pillars_covered": [p.value for p in all_pillars_in_goals_set],
        "all_pillars_have_pure_goals": all_pillars_have_pure_goals,
        "pillar_pure_goals": {}
    }
    if all_4_pillars_covered:
        for p in Pillar:
            if p in all_pillars_in_goals_set:
                has_pure = has_pure_goal_for_pillar(sheet.goals, p)
                phase_transition_debug["pillar_pure_goals"][p.value] = has_pure
                print(f"[Phase Transition Check] Pillar {p.value} has pure goal: {has_pure}")
    
    print(f"[Phase Transition Check] Current phase: {state.phase}")
    print(f"[Phase Transition Check] All 4 pillars covered: {all_4_pillars_covered} (pillars: {[p.value for p in all_pillars_in_goals_set]})")
    print(f"[Phase Transition Check] All pillars have pure goals: {all_pillars_have_pure_goals}")
    
    if state.phase == "phase1" and all_4_pillars_covered and all_pillars_have_pure_goals:
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
        
        def has_pure_goal_for_pillar(goals, pillar):
            """Check if a pillar has at least one pure goal (single-pillar goal)."""
            return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
        
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
        
        # After processing all goals, check if current pillar has a pure goal
        # Only mark pillar as asked about if it has a pure goal
        if current_pillar and current_pillar not in state.pillars_asked_about:
            if has_pure_goal_for_pillar(sheet.goals, current_pillar):
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
        # DEBUG: Log what goals are in sheet.goals before passing to Architect
        print(f"[DEBUG] Sheet goals before Architect call: {[(g.name, [p.value for p in g.pillars]) for g in sheet.goals]}")
        print(f"[DEBUG] Sheet JSON: {sheet.model_dump_json()}")
        
        reply, architect_thinking = architect.generate_response(
            history_plus_user, 
            sheet, 
            feedback,
            ask_for_prioritization=(state.phase == "phase3.5" and not state.goals_prioritized),
            phase=state.phase,
            pending_debuffs=pending_debuffs_dict,
            current_pillar=current_pillar_value,
            queued_goals=queued_goals_for_current_pillar
        )
        
        # Prepend phase transition message for other transitions
        if phase_transition_message:
            reply = f"{phase_transition_message}\n\n{reply}"

    # Get accumulated goals for logging (include current_quests and skill_level)
    accumulated_goals = [
        {
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
        "pending_debuffs": pending_debuffs_dict,
        "pillars_asked_about": pillars_asked_about_dict,
        "pending_goals": pending_goals_dict,
        "accumulated_goals": accumulated_goals,
        "goals_prioritized": state.goals_prioritized,
        "should_extract_profile": state.phase == "phase4" and state.goals_prioritized,
        "debug": {
            "critic_analysis": critic_analysis,
            "architect_thinking": architect_thinking,
            "phase_transition": phase_transition_debug
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
        
        # PHASE 1: Extract goals
        phase = "phase1"
        for i, msg in enumerate(conversation_history):
            if msg["role"] == "user":
                history_up_to_now = conversation_history[:i+1]
                sheet, _, _, _ = critic.analyze(msg["content"], sheet, history_up_to_now, phase)
                # Check if we should move to phase 2 (all 4 pillars have at least 1 goal)
                all_pillars_in_goals = set()
                for goal in sheet.goals:
                    all_pillars_in_goals.update(goal.pillars)
                if len(all_pillars_in_goals) >= 4:
                    phase = "phase2"
        
        # PHASE 2: Extract current_quests
        phase = "phase2"
        for i, msg in enumerate(conversation_history):
            if msg["role"] == "user":
                history_up_to_now = conversation_history[:i+1]
                sheet, _, _, _ = critic.analyze(msg["content"], sheet, history_up_to_now, phase)
        
        # PHASE 4: Run planners to generate needed_quests
        # For goals with multiple pillars, we'll use the first pillar's planner
        for goal in sheet.goals:
            # Use the first pillar for the planner (could be enhanced to use multiple planners)
            if goal.pillars:
                planner = get_planner(goal.pillars[0].value)
                needed_skill_nodes = planner.generate_roadmap(
                    north_star=goal.name,
                    current_quests=goal.current_quests,
                    debuffs=sheet.debuffs
                )
                goal.needed_quests = [node.name for node in needed_skill_nodes]
        
        # PHASE 5: Generate skill tree from needed_quests
        skill_tree_generator = SkillTreeGenerator()
        skill_tree = skill_tree_generator.generate_skill_tree(sheet)
        
        # Activate 1-2 habits per pillar automatically
        _activate_initial_habits(sheet, skill_tree)
        
        # Return the complete profile
        return {
            "character_sheet": sheet.model_dump(),
            "skill_tree": skill_tree.model_dump()
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
    """

    data = load_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return data


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
            return {"message": "Event deleted", "event_id": event_id}

    raise HTTPException(status_code=404, detail="Event not found")


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
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    model = payload.get("model", "gemini-2.5-flash")
    contents = payload.get("contents", [])
    
    try:
        # Use the REST API directly to match the original HTML implementation
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        request_data = {
            "contents": contents
        }
        
        req = urllib.request.Request(url, data=json.dumps(request_data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
