#include "detector.h"
#include "face_engine.h"
#include "detectors/yawn_detector.h"
#include "detectors/gaze_detector.h"
#include "detectors/fidget_detector.h"
#include "detectors/neck_crack_detector.h"
#include "profile_manager.h"
#include <iostream>

// StateVector::StateVector() = default; // Removed - using default constructor

std::string StateVector::to_json() const {
    // Simple JSON serialization (nlohmann/json would be better, but this works)
    std::string json = "{";
    json += "\"blink_rate\":" + std::to_string(blink_rate) + ",";
    json += "\"perclos\":" + std::to_string(perclos) + ",";
    json += "\"current_ear\":" + std::to_string(current_ear) + ",";
    json += "\"yawn_count_5min\":" + std::to_string(yawn_count_5min) + ",";
    json += "\"gaze_stability\":" + std::to_string(gaze_stability) + ",";
    json += "\"fidgeting_score\":" + std::to_string(fidgeting_score) + ",";
    json += "\"neck_crack_count_1min\":" + std::to_string(neck_crack_count_1min) + ",";
    json += "\"fatigue_score\":" + std::to_string(fatigue_score) + ",";
    json += "\"fatigue_level\":\"" + fatigue_level + "\",";
    json += "\"recommendation\":\"" + recommendation + "\"";
    json += "}";
    return json;
}

FatigueEngine::FatigueEngine(const std::string& user_id, const std::string& profile_path)
    : user_id_(user_id) {
    
    // Initialize components
    face_engine_ = std::make_unique<FaceEngine>();
    yawn_detector_ = std::make_unique<YawnDetector>();
    gaze_detector_ = std::make_unique<GazeDetector>();
    fidget_detector_ = std::make_unique<FidgetDetector>();
    neck_crack_detector_ = std::make_unique<NeckCrackDetector>();
    profile_manager_ = std::make_unique<ProfileManager>();
    
    // Initialize face engine with landmark predictor model
    // Try multiple paths relative to common execution locations
    std::vector<std::string> model_paths = {
        "models/shape_predictor_68_face_landmarks.dat",
        "fatigue_detection/models/shape_predictor_68_face_landmarks.dat",
        "../models/shape_predictor_68_face_landmarks.dat",
        "../../fatigue_detection/models/shape_predictor_68_face_landmarks.dat"
    };
    
    bool model_loaded = false;
    for (const auto& model_path : model_paths) {
        if (face_engine_->initialize("", model_path)) {
            std::cout << "[FatigueEngine] Successfully loaded landmark model from: " << model_path << std::endl;
            model_loaded = true;
            break;
        }
    }
    
    if (!model_loaded) {
        std::cerr << "[FatigueEngine] WARNING: Failed to load landmark predictor model!" << std::endl;
        std::cerr << "[FatigueEngine] Tried paths: ";
        for (const auto& path : model_paths) {
            std::cerr << path << " ";
        }
        std::cerr << std::endl;
        std::cerr << "[FatigueEngine] Face detection will work, but landmarks (blinks, yawns) will not." << std::endl;
    }
    
    // Load profile if provided
    if (!profile_path.empty()) {
        load_profile(profile_path);
    } else {
        // Try default path
        std::string default_path = "fatigue_detection/profiles/" + user_id + ".json";
        load_profile(default_path);
    }
}

FatigueEngine::~FatigueEngine() = default;

StateVector FatigueEngine::process_frame(const cv::Mat& frame, int64_t /*timestamp_ms*/) {
    frame_counter_++;
    
    // MANDATORY: Downscale for Dlib (it's not scale-invariant)
    cv::Mat small_frame;
    double scale_factor = static_cast<double>(downscale_width_) / frame.cols;
    int new_height = static_cast<int>(frame.rows * scale_factor);
    cv::resize(frame, small_frame, cv::Size(downscale_width_, new_height));
    
    // Store scale factor for mapping landmarks back if needed
    // (For ratios like MAR/EAR, we don't need original scale)
    
    // Every frame (30/sec): Face detection
    process_face_landmarks(small_frame);
    
    // Every 5th frame (6/sec): Motion Energy
    if (frame_counter_ % MOTION_FRAME_INTERVAL == 0) {
        if (!prev_frame_.empty()) {
            process_motion_energy(small_frame);
        }
        prev_frame_ = small_frame.clone();
    } else if (prev_frame_.empty()) {
        prev_frame_ = small_frame.clone();
    }
    
    // Every 30th frame (1/sec): Z-score calculation and fatigue fusion
    if (frame_counter_ % ZSCORE_FRAME_INTERVAL == 0) {
        calculate_z_scores_and_fatigue();
    }
    
    return current_state_;
}

void FatigueEngine::process_face_landmarks(const cv::Mat& frame) {
    if (!face_engine_) return;
    
    // Detect face and landmarks
    bool detected = face_engine_->detect_landmarks(frame, landmarks_, face_bbox_);
    
    if (detected && !landmarks_.empty()) {
        // Update detectors with landmarks
        yawn_detector_->update(landmarks_, frame);
        gaze_detector_->update(landmarks_, frame);
        neck_crack_detector_->update(landmarks_, face_bbox_);
        
        // Update current state with detector outputs
        current_state_.blink_rate = gaze_detector_->get_blink_rate();
        current_state_.perclos = gaze_detector_->get_perclos();
        current_state_.current_ear = gaze_detector_->get_current_ear();  // Expose EAR for calibration
        current_state_.yawn_count_5min = yawn_detector_->get_yawn_count_5min();
        current_state_.gaze_stability = gaze_detector_->get_gaze_stability();
        current_state_.neck_crack_count_1min = neck_crack_detector_->get_crack_count_1min();
        
        // Store face bounding box for visualization
        current_state_.face_bbox_x = face_bbox_.x;
        current_state_.face_bbox_y = face_bbox_.y;
        current_state_.face_bbox_width = face_bbox_.width;
        current_state_.face_bbox_height = face_bbox_.height;
        
        // Store key landmarks for visualization (68-point model indices)
        // Left eye: 36-41
        current_state_.left_eye_points.clear();
        for (int i = 36; i <= 41; ++i) {
            if (i < static_cast<int>(landmarks_.size())) {
                current_state_.left_eye_points.push_back(landmarks_[i].x);
                current_state_.left_eye_points.push_back(landmarks_[i].y);
            }
        }
        
        // Right eye: 42-47
        current_state_.right_eye_points.clear();
        for (int i = 42; i <= 47; ++i) {
            if (i < static_cast<int>(landmarks_.size())) {
                current_state_.right_eye_points.push_back(landmarks_[i].x);
                current_state_.right_eye_points.push_back(landmarks_[i].y);
            }
        }
        
        // Mouth: 48-67 (outer mouth)
        current_state_.mouth_points.clear();
        for (int i = 48; i <= 67; ++i) {
            if (i < static_cast<int>(landmarks_.size())) {
                current_state_.mouth_points.push_back(landmarks_[i].x);
                current_state_.mouth_points.push_back(landmarks_[i].y);
            }
        }
        
        // Nose tip: 30
        current_state_.nose_tip.clear();
        if (30 < static_cast<int>(landmarks_.size())) {
            current_state_.nose_tip.push_back(landmarks_[30].x);
            current_state_.nose_tip.push_back(landmarks_[30].y);
        }
    } else {
        // No face detected - reset metrics
        current_state_.blink_rate = 0.0;
        current_state_.perclos = 0.0;
        current_state_.gaze_stability = 0.0;
        current_state_.face_bbox_width = 0;  // Signal no face
    }
}

void FatigueEngine::process_motion_energy(const cv::Mat& frame) {
    if (!fidget_detector_ || prev_frame_.empty() || face_bbox_.width == 0) {
        return;
    }
    
    // Calculate fidgeting with relative ROI
    double fidget_score = fidget_detector_->calculate_motion_energy(
        frame, prev_frame_, face_bbox_
    );
    
    current_state_.fidgeting_score = fidget_score;
}

void FatigueEngine::calculate_z_scores_and_fatigue() {
    if (!profile_manager_) return;
    
    // Calculate Z-scores and fatigue score using profile baseline
    current_state_ = profile_manager_->calculate_fatigue_state(current_state_);
}

bool FatigueEngine::load_profile(const std::string& profile_path) {
    if (!profile_manager_) return false;
    return profile_manager_->load_profile(profile_path);
}

void FatigueEngine::update_profile(const StateVector& session_stats, double user_rating) {
    if (!profile_manager_) return;
    profile_manager_->update_baseline(session_stats, user_rating);
}
