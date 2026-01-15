"""
Analyze labeled examples to extract detection patterns and tune parameters.
"""

import cv2
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import ImageFormat

# Import vision system to reuse MediaPipe processing
import sys
sys.path.insert(0, str(Path(__file__).parent))
from face_tracking.vision_system import VisionSystem, LEFT_EYE_INDICES, RIGHT_EYE_INDICES, MOUTH_INDICES, NOSE_TIP_INDEX

EXAMPLES_DIR = Path(__file__).parent / "examples"
NECK_CRACK_DIR = EXAMPLES_DIR / "neck_cracks"
YAWN_DIR = EXAMPLES_DIR / "yawns"


def extract_metrics_from_video(video_path: Path, vision_system: VisionSystem) -> List[Dict]:
    """Extract metrics from all frames in a video."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[ERROR] Failed to open {video_path}")
        return []
    
    metrics_list = []
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process frame with MediaPipe
        vision_results = vision_system.process(frame)
        if vision_results and vision_results.get("face_detected"):
            metrics_list.append({
                "frame": frame_count,
                "ear": vision_results.get("ear", 0.0),
                "mar": vision_results.get("mar", 0.0),
                "gaze_x": vision_results.get("gaze_x", 0.0),
                "gaze_y": vision_results.get("gaze_y", 0.0),
                "head_pitch": vision_results.get("head_pitch", 0.0),
                "head_yaw": vision_results.get("head_yaw", 0.0),
                "head_roll": vision_results.get("head_roll", 0.0),
            })
        
        frame_count += 1
    
    cap.release()
    return metrics_list


def analyze_neck_cracks(neck_crack_dir: Path, vision_system: VisionSystem) -> Dict:
    """Analyze neck crack examples to find velocity patterns."""
    print("\n" + "="*60)
    print("ANALYZING NECK CRACK EXAMPLES")
    print("="*60)
    
    video_files = list(neck_crack_dir.glob("*.mp4"))
    if not video_files:
        print(f"[WARN] No neck crack videos found in {neck_crack_dir}")
        return {}
    
    print(f"Found {len(video_files)} neck crack examples")
    
    all_yaw_velocities = []
    all_roll_velocities = []
    all_pitch_velocities = []
    all_yaw_accelerations = []
    all_roll_accelerations = []
    
    for video_path in video_files:
        print(f"\nProcessing: {video_path.name}")
        metrics = extract_metrics_from_video(video_path, vision_system)
        
        if len(metrics) < 3:
            print(f"  [SKIP] Too few frames ({len(metrics)})")
            continue
        
        # Calculate velocities and accelerations (degrees per frame)
        prev_velocity_yaw = 0.0
        prev_velocity_roll = 0.0
        
        for i in range(1, len(metrics)):
            prev = metrics[i-1]
            curr = metrics[i]
            
            # Velocity (change in angle)
            d_yaw = abs(curr["head_yaw"] - prev["head_yaw"])
            d_roll = abs(curr["head_roll"] - prev["head_roll"])
            d_pitch = abs(curr["head_pitch"] - prev["head_pitch"])
            
            all_yaw_velocities.append(d_yaw)
            all_roll_velocities.append(d_roll)
            all_pitch_velocities.append(d_pitch)
            
            # Acceleration (change in velocity) - requires at least 2 frames
            if i >= 2:
                yaw_acceleration = abs(d_yaw - prev_velocity_yaw)
                roll_acceleration = abs(d_roll - prev_velocity_roll)
                all_yaw_accelerations.append(yaw_acceleration)
                all_roll_accelerations.append(roll_acceleration)
            
            prev_velocity_yaw = d_yaw
            prev_velocity_roll = d_roll
    
    if not all_yaw_velocities:
        print("[ERROR] No velocity data extracted")
        return {}
    
    # Calculate statistics
    stats = {
        "yaw": {
            "mean": np.mean(all_yaw_velocities),
            "std": np.std(all_yaw_velocities),
            "min": np.min(all_yaw_velocities),
            "max": np.max(all_yaw_velocities),
            "median": np.median(all_yaw_velocities),
            "p75": np.percentile(all_yaw_velocities, 75),
            "p90": np.percentile(all_yaw_velocities, 90),
            "p95": np.percentile(all_yaw_velocities, 95),
        },
        "roll": {
            "mean": np.mean(all_roll_velocities),
            "std": np.std(all_roll_velocities),
            "min": np.min(all_roll_velocities),
            "max": np.max(all_roll_velocities),
            "median": np.median(all_roll_velocities),
            "p75": np.percentile(all_roll_velocities, 75),
            "p90": np.percentile(all_roll_velocities, 90),
            "p95": np.percentile(all_roll_velocities, 95),
        },
        "yaw_acceleration": {
            "mean": np.mean(all_yaw_accelerations) if all_yaw_accelerations else 0,
            "std": np.std(all_yaw_accelerations) if all_yaw_accelerations else 0,
            "min": np.min(all_yaw_accelerations) if all_yaw_accelerations else 0,
            "max": np.max(all_yaw_accelerations) if all_yaw_accelerations else 0,
            "median": np.median(all_yaw_accelerations) if all_yaw_accelerations else 0,
            "p75": np.percentile(all_yaw_accelerations, 75) if all_yaw_accelerations else 0,
            "p90": np.percentile(all_yaw_accelerations, 90) if all_yaw_accelerations else 0,
        },
        "roll_acceleration": {
            "mean": np.mean(all_roll_accelerations) if all_roll_accelerations else 0,
            "std": np.std(all_roll_accelerations) if all_roll_accelerations else 0,
            "min": np.min(all_roll_accelerations) if all_roll_accelerations else 0,
            "max": np.max(all_roll_accelerations) if all_roll_accelerations else 0,
            "median": np.median(all_roll_accelerations) if all_roll_accelerations else 0,
            "p75": np.percentile(all_roll_accelerations, 75) if all_roll_accelerations else 0,
            "p90": np.percentile(all_roll_accelerations, 90) if all_roll_accelerations else 0,
        },
        "pitch": {
            "mean": np.mean(all_pitch_velocities),
            "std": np.std(all_pitch_velocities),
            "min": np.min(all_pitch_velocities),
            "max": np.max(all_pitch_velocities),
        }
    }
    
    print("\n" + "-"*60)
    print("NECK CRACK VELOCITY STATISTICS (degrees per frame)")
    print("-"*60)
    print(f"Yaw (left-right):")
    print(f"  Mean: {stats['yaw']['mean']:.2f}, Std: {stats['yaw']['std']:.2f}")
    print(f"  Min: {stats['yaw']['min']:.2f}, Max: {stats['yaw']['max']:.2f}")
    print(f"  Median: {stats['yaw']['median']:.2f}, P75: {stats['yaw']['p75']:.2f}, P90: {stats['yaw']['p90']:.2f}, P95: {stats['yaw']['p95']:.2f}")
    print(f"\nRoll (tilt):")
    print(f"  Mean: {stats['roll']['mean']:.2f}, Std: {stats['roll']['std']:.2f}")
    print(f"  Min: {stats['roll']['min']:.2f}, Max: {stats['roll']['max']:.2f}")
    print(f"  Median: {stats['roll']['median']:.2f}, P75: {stats['roll']['p75']:.2f}, P90: {stats['roll']['p90']:.2f}, P95: {stats['roll']['p95']:.2f}")
    print(f"\nPitch (up-down):")
    print(f"  Mean: {stats['pitch']['mean']:.2f}, Std: {stats['pitch']['std']:.2f}")
    print(f"  Min: {stats['pitch']['min']:.2f}, Max: {stats['pitch']['max']:.2f}")
    
    print(f"\nYaw Acceleration (change in velocity):")
    print(f"  Mean: {stats['yaw_acceleration']['mean']:.2f}, Std: {stats['yaw_acceleration']['std']:.2f}")
    print(f"  Min: {stats['yaw_acceleration']['min']:.2f}, Max: {stats['yaw_acceleration']['max']:.2f}")
    print(f"  Median: {stats['yaw_acceleration']['median']:.2f}, P75: {stats['yaw_acceleration']['p75']:.2f}, P90: {stats['yaw_acceleration']['p90']:.2f}")
    
    print(f"\nRoll Acceleration (change in velocity):")
    print(f"  Mean: {stats['roll_acceleration']['mean']:.2f}, Std: {stats['roll_acceleration']['std']:.2f}")
    print(f"  Min: {stats['roll_acceleration']['min']:.2f}, Max: {stats['roll_acceleration']['max']:.2f}")
    print(f"  Median: {stats['roll_acceleration']['median']:.2f}, P75: {stats['roll_acceleration']['p75']:.2f}, P90: {stats['roll_acceleration']['p90']:.2f}")
    
    # Recommendation
    recommended_velocity = min(stats['yaw']['p75'], stats['roll']['p75'])
    recommended_acceleration = min(stats['yaw_acceleration']['p75'], stats['roll_acceleration']['p75'])
    print(f"\n[RECOMMENDATION]")
    print(f"  Current velocity threshold: 3.20 degrees/frame")
    print(f"  Recommended velocity threshold: {recommended_velocity:.2f} degrees/frame (75th percentile)")
    print(f"  Current acceleration threshold: 2.0 degrees/frame")
    print(f"  Recommended acceleration threshold: {recommended_acceleration:.2f} degrees/frame (75th percentile)")
    
    return stats


def analyze_yawns(yawn_dir: Path, vision_system: VisionSystem) -> Dict:
    """Analyze yawn examples to find MAR patterns."""
    print("\n" + "="*60)
    print("ANALYZING YAWN EXAMPLES")
    print("="*60)
    
    video_files = list(yawn_dir.glob("*.mp4"))
    if not video_files:
        print(f"[WARN] No yawn videos found in {yawn_dir}")
        return {}
    
    print(f"Found {len(video_files)} yawn examples")
    
    all_mar_values = []
    yawn_durations = []
    yawn_mar_variations = []
    yawn_ear_decreases = []
    
    for video_path in video_files:
        print(f"\nProcessing: {video_path.name}")
        metrics = extract_metrics_from_video(video_path, vision_system)
        
        if len(metrics) < 10:
            print(f"  [SKIP] Too few frames ({len(metrics)})")
            continue
        
        # Find yawn period (MAR > threshold)
        mar_threshold = 0.336
        yawn_frames = [m for m in metrics if m["mar"] > mar_threshold]
        
        if len(yawn_frames) < 5:
            print(f"  [SKIP] Too few yawn frames ({len(yawn_frames)})")
            continue
        
        # Extract MAR values during yawn
        mar_values = [m["mar"] for m in yawn_frames]
        all_mar_values.extend(mar_values)
        
        # Extract EAR values during yawn
        ear_values = [m["ear"] for m in yawn_frames]
        if len(ear_values) > 1:
            initial_ear = ear_values[0]
            min_ear = min(ear_values)
            ear_decrease = initial_ear - min_ear
            yawn_ear_decreases.append(ear_decrease)
        
        # Calculate duration (assuming 30 FPS)
        duration_seconds = len(yawn_frames) / 30.0
        yawn_durations.append(duration_seconds)
        
        # Calculate variation (std dev)
        if len(mar_values) > 1:
            variation = np.std(mar_values)
            yawn_mar_variations.append(variation)
    
    if not all_mar_values:
        print("[ERROR] No MAR data extracted")
        return {}
    
    # Calculate statistics
    stats = {
        "mar": {
            "mean": np.mean(all_mar_values),
            "std": np.std(all_mar_values),
            "min": np.min(all_mar_values),
            "max": np.max(all_mar_values),
            "median": np.median(all_mar_values),
            "p25": np.percentile(all_mar_values, 25),
            "p75": np.percentile(all_mar_values, 75),
        },
        "duration": {
            "mean": np.mean(yawn_durations) if yawn_durations else 0,
            "min": np.min(yawn_durations) if yawn_durations else 0,
            "max": np.max(yawn_durations) if yawn_durations else 0,
        },
        "variation": {
            "mean": np.mean(yawn_mar_variations) if yawn_mar_variations else 0,
            "max": np.max(yawn_mar_variations) if yawn_mar_variations else 0,
        },
        "ear_decrease": {
            "mean": np.mean(yawn_ear_decreases) if yawn_ear_decreases else 0,
            "min": np.min(yawn_ear_decreases) if yawn_ear_decreases else 0,
            "max": np.max(yawn_ear_decreases) if yawn_ear_decreases else 0,
            "median": np.median(yawn_ear_decreases) if yawn_ear_decreases else 0,
        }
    }
    
    print("\n" + "-"*60)
    print("YAWN STATISTICS")
    print("-"*60)
    print(f"MAR (Mouth Aspect Ratio) during yawns:")
    print(f"  Mean: {stats['mar']['mean']:.3f}, Std: {stats['mar']['std']:.3f}")
    print(f"  Min: {stats['mar']['min']:.3f}, Max: {stats['mar']['max']:.3f}")
    print(f"  Median: {stats['mar']['median']:.3f}, P25: {stats['mar']['p25']:.3f}, P75: {stats['mar']['p75']:.3f}")
    print(f"\nYawn duration:")
    print(f"  Mean: {stats['duration']['mean']:.2f}s, Min: {stats['duration']['min']:.2f}s, Max: {stats['duration']['max']:.2f}s")
    print(f"\nMAR variation (std dev) during yawns:")
    print(f"  Mean: {stats['variation']['mean']:.3f}, Max: {stats['variation']['max']:.3f}")
    
    print(f"\nEAR decrease during yawns (eyes closing):")
    print(f"  Mean: {stats['ear_decrease']['mean']:.3f}, Min: {stats['ear_decrease']['min']:.3f}, Max: {stats['ear_decrease']['max']:.3f}")
    print(f"  Median: {stats['ear_decrease']['median']:.3f}")
    
    # Recommendation
    recommended_threshold = stats['mar']['p25']  # 25th percentile (most yawns are above this)
    recommended_variation = stats['variation']['mean'] * 1.5  # 1.5x mean variation
    recommended_duration = max(0.5, stats['duration']['min'])  # At least min duration
    recommended_ear_decrease = max(0.03, stats['ear_decrease']['min'])  # At least min EAR decrease
    
    print(f"\n[RECOMMENDATION]")
    print(f"  Current MAR threshold: 0.336")
    print(f"  Recommended MAR threshold: {recommended_threshold:.3f} (25th percentile)")
    print(f"  Current variation threshold: 0.292")
    print(f"  Recommended variation threshold: {recommended_variation:.3f}")
    print(f"  Current min duration: 0.5s")
    print(f"  Recommended min duration: {recommended_duration:.2f}s")
    print(f"  Current EAR decrease threshold: 0.05")
    print(f"  Recommended EAR decrease threshold: {recommended_ear_decrease:.3f}")
    
    return stats


def generate_code_updates(neck_crack_stats: Dict, yawn_stats: Dict) -> str:
    """Generate code update suggestions."""
    updates = []
    
    if neck_crack_stats:
        yaw_p75 = neck_crack_stats.get("yaw", {}).get("p75", 3.20)
        roll_p75 = neck_crack_stats.get("roll", {}).get("p75", 3.20)
        recommended_velocity = min(yaw_p75, roll_p75)
        
        yaw_acc_p75 = neck_crack_stats.get("yaw_acceleration", {}).get("p75", 2.0)
        roll_acc_p75 = neck_crack_stats.get("roll_acceleration", {}).get("p75", 2.0)
        recommended_acceleration = min(yaw_acc_p75, roll_acc_p75) if (yaw_acc_p75 > 0 or roll_acc_p75 > 0) else 2.0
        
        updates.append(f"""
// Neck Crack Detection Threshold (from example analysis)
// Velocity threshold: Recommended {recommended_velocity:.2f} degrees/frame (75th percentile), Current 3.20
constexpr double CRACK_VELOCITY_THRESHOLD = {recommended_velocity:.2f};
// Acceleration threshold: Recommended {recommended_acceleration:.2f} degrees/frame (75th percentile), Current 2.0
constexpr double CRACK_ACCELERATION_THRESHOLD = {recommended_acceleration:.2f};
""")
    
    if yawn_stats:
        mar_p25 = yawn_stats.get("mar", {}).get("p25", 0.336)
        variation_mean = yawn_stats.get("variation", {}).get("mean", 0.292)
        recommended_variation = variation_mean * 1.5
        duration_min = yawn_stats.get("duration", {}).get("min", 0.5)
        ear_decrease_median = yawn_stats.get("ear_decrease", {}).get("median", 0.05)
        # Use median or a reasonable minimum (0.03) to ensure some eye closure
        ear_decrease_threshold = max(0.03, min(ear_decrease_median, 0.05))
        
        updates.append(f"""
// Yawn Detection Parameters (from example analysis)
// MAR threshold: Recommended {mar_p25:.3f} (25th percentile), Current 0.336
static double mar_threshold = {mar_p25:.3f};

// Variation threshold: Recommended {recommended_variation:.3f}, Current 0.292
constexpr double MAX_VARIATION = {recommended_variation:.3f};

// Min duration: Recommended {duration_min:.2f}s, Current 0.5s
constexpr int64_t MIN_YAWN_DURATION_MS = {int(duration_min * 1000)};

// EAR decrease threshold: Recommended {ear_decrease_threshold:.3f} (median-based), Current 0.05
constexpr double MIN_EAR_DECREASE = {ear_decrease_threshold:.3f};

// EAR decrease threshold: Recommended {ear_decrease_min:.3f}, Current 0.05
constexpr double MIN_EAR_DECREASE = {ear_decrease_min:.3f};
""")
    
    return "\n".join(updates)


def main():
    print("="*60)
    print("FATIGUE DETECTION EXAMPLE ANALYZER")
    print("="*60)
    
    # Initialize vision system
    print("\n[INFO] Initializing MediaPipe vision system...")
    vision_system = VisionSystem(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    print("[OK] Vision system initialized")
    
    # Analyze examples
    neck_crack_stats = {}
    yawn_stats = {}
    
    if NECK_CRACK_DIR.exists():
        neck_crack_stats = analyze_neck_cracks(NECK_CRACK_DIR, vision_system)
    
    if YAWN_DIR.exists():
        yawn_stats = analyze_yawns(YAWN_DIR, vision_system)
    
    # Generate recommendations
    if neck_crack_stats or yawn_stats:
        print("\n" + "="*60)
        print("CODE UPDATE RECOMMENDATIONS")
        print("="*60)
        code_updates = generate_code_updates(neck_crack_stats, yawn_stats)
        print(code_updates)
        
        # Save to file
        output_file = EXAMPLES_DIR / "analysis_results.txt"
        with open(output_file, "w") as f:
            f.write("FATIGUE DETECTION PARAMETER ANALYSIS\n")
            f.write("="*60 + "\n\n")
            if neck_crack_stats:
                f.write("NECK CRACK STATISTICS:\n")
                f.write(json.dumps(neck_crack_stats, indent=2))
                f.write("\n\n")
            if yawn_stats:
                f.write("YAWN STATISTICS:\n")
                f.write(json.dumps(yawn_stats, indent=2))
                f.write("\n\n")
            f.write("CODE UPDATES:\n")
            f.write(code_updates)
        
        print(f"\n[INFO] Full analysis saved to: {output_file}")
    
    print("\n[INFO] Analysis complete!")


if __name__ == "__main__":
    main()
