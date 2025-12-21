from typing import List

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

from src.models import CharacterSheet, ConversationState
from src.onboarding.agent import ArchitectAgent
from src.storage import load_profile, save_profile


class Message(BaseModel):
    role: str
    content: str


class ArchitectRequest(BaseModel):
    history: List[Message]
    user_input: str


load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "GorLj2SsI4u2JqL58gAA")
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
    )

    # Seed conversation history with what the frontend has seen so far.
    state.conversation_history = [
        {"role": m.role, "content": m.content} for m in payload.history
    ]

    architect = ArchitectAgent()

    # For now we ignore Critic feedback and let the Architect drive the turn.
    history_plus_user = state.conversation_history + [
        {"role": "user", "content": payload.user_input}
    ]
    reply = architect.generate_response(history_plus_user, sheet)

    return {"reply": reply}


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
