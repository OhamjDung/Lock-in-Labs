#include "detector.h"
#include "face_engine.h"
#include "detectors/yawn_detector.h"
#include "detectors/gaze_detector.h"
#include "detectors/fidget_detector.h"
#include "detectors/neck_crack_detector.h"
#include "profile_manager.h"
#include <nlohmann/json.hpp>
#include <iostream>
#include <fstream>

// StateVector::StateVector() = default; // Removed - using default constructor

std::string StateVector::to_json() const {
    // Use nlohmann/json for proper JSON serialization
    nlohmann::json j;
    j["blink_rate"] = blink_rate;
    j["blink_count_total"] = blink_count_total;
    j["perclos"] = perclos;
    j["current_ear"] = current_ear;
    j["current_mar"] = current_mar;
    j["yawn_count_5min"] = yawn_count_5min;
    j["gaze_stability"] = gaze_stability;
    j["fidgeting_score"] = fidgeting_score;
    j["neck_crack_count_1min"] = neck_crack_count_1min;
    j["z_score_blink"] = z_score_blink;
    j["z_score_gaze"] = z_score_gaze;
    j["z_score_posture"] = z_score_posture;
    j["z_score_fidget"] = z_score_fidget;
    j["fatigue_score"] = fatigue_score;
    j["energy_state"] = energy_state;
    j["fatigue_level"] = fatigue_level;
    j["energy_type"] = energy_type;
    j["recommendation"] = recommendation;
    j["events"] = events;
    return j.dump();
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
    // Try multiple paths for YuNet and landmark models
    std::vector<std::string> yunet_paths = {
        "models/face_detection_yunet_2023mar.onnx",
        "fatigue_detection/models/face_detection_yunet_2023mar.onnx",
        "../models/face_detection_yunet_2023mar.onnx",
        "../../fatigue_detection/models/face_detection_yunet_2023mar.onnx"
    };
    
    std::vector<std::string> landmark_paths = {
        "models/shape_predictor_68_face_landmarks.dat",
        "fatigue_detection/models/shape_predictor_68_face_landmarks.dat",
        "../models/shape_predictor_68_face_landmarks.dat",
        "../../fatigue_detection/models/shape_predictor_68_face_landmarks.dat"
    };
    
    // Find YuNet model
    std::string yunet_path = "";
    for (const auto& path : yunet_paths) {
        std::ifstream file(path);
        if (file.good()) {
            yunet_path = path;
            break;
        }
    }
    
    // Find landmark model
    std::string landmark_path = "";
    for (const auto& path : landmark_paths) {
        std::ifstream file(path);
        if (file.good()) {
            landmark_path = path;
            break;
        }
    }
    
    // Initialize face engine with both models
    if (face_engine_->initialize(yunet_path, landmark_path)) {
        if (!yunet_path.empty()) {
            std::cout << "[FatigueEngine] Successfully loaded YuNet face detector from: " << yunet_path << std::endl;
        }
        if (!landmark_path.empty()) {
            std::cout << "[FatigueEngine] Successfully loaded landmark model from: " << landmark_path << std::endl;
        }
    } else {
        std::cerr << "[FatigueEngine] WARNING: Failed to initialize face engine!" << std::endl;
        std::cerr << "[FatigueEngine] Face detection may not work properly." << std::endl;
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
    
    // Store scale factor for mapping landmarks back to original frame
    current_state_.scale_factor = 1.0 / scale_factor;  // Inverse: to scale up from small to original
    
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

StateVector FatigueEngine::update_metrics(double ear, double mar, double gaze_x, double gaze_y, 
                                         int64_t timestamp_ms, bool face_detected,
                                         double /* head_pitch */, double head_yaw, double head_roll) {
    frame_counter_++;
    
    if (!face_detected) {
        // No face detected - reset metrics
        current_state_.blink_rate = 0.0;
        current_state_.perclos = 0.0;
        current_state_.gaze_stability = 0.0;
        current_state_.current_ear = 0.0;
        current_state_.current_mar = 0.0;
        current_state_.face_bbox_width = 0;  // Signal no face
        return current_state_;
    }
    
    // Update current metrics directly
    current_state_.current_ear = ear;
    current_state_.current_mar = mar;
    
    // Update gaze detector with EAR for blink detection
    // We'll create a minimal update that uses EAR directly
    // For now, we'll update the gaze detector's internal state manually
    // Note: This is a simplified path - full integration would require detector API changes
    if (gaze_detector_) {
        // Update gaze stability from gaze_x, gaze_y
        // Calculate stability as inverse of gaze movement variance
        static double prev_gaze_x = 0.0;
        static double prev_gaze_y = 0.0;
        static std::deque<double> gaze_variance_history;
        
        double gaze_delta_x = std::abs(gaze_x - prev_gaze_x);
        double gaze_delta_y = std::abs(gaze_y - prev_gaze_y);
        double gaze_movement = std::sqrt(gaze_delta_x * gaze_delta_x + gaze_delta_y * gaze_delta_y);
        
        gaze_variance_history.push_back(gaze_movement);
        if (gaze_variance_history.size() > 30) {  // Keep last 30 frames (~1 second at 30fps)
            gaze_variance_history.pop_front();
        }
        
        // Calculate average movement (lower = more stable)
        double avg_movement = 0.0;
        for (double val : gaze_variance_history) {
            avg_movement += val;
        }
        if (!gaze_variance_history.empty()) {
            avg_movement /= gaze_variance_history.size();
        }
        
        // Convert to stability score (0-1, higher = more stable)
        // Increased sensitivity: movement of 0.025 = stability of 0.75, movement of 0.05 = stability of 0.5
        // This makes the metric more responsive to head movements
        current_state_.gaze_stability = std::max(0.0, std::min(1.0, 1.0 - avg_movement * 10.0));
        
        prev_gaze_x = gaze_x;
        prev_gaze_y = gaze_y;
        
        // Update blink detection from EAR
        // Simple blink detection: EAR drops below threshold
        static double ear_threshold = 0.20;  // Default threshold
        static std::deque<std::pair<int64_t, double>> ear_history;
        static std::deque<int64_t> blink_timestamps;
        static double prev_ear = 0.5;
        static bool eyes_closed = false;
        
        ear_history.push_back({timestamp_ms, ear});
        // Keep only last minute of history
        while (!ear_history.empty() && (timestamp_ms - ear_history.front().first) > 60000) {
            ear_history.pop_front();
        }
        
        // Detect blink: EAR drops below threshold then rises
        if (ear < ear_threshold && prev_ear >= ear_threshold) {
            // Eye closing
            eyes_closed = true;
        } else if (ear >= ear_threshold && prev_ear < ear_threshold && eyes_closed) {
            // Eye opening - blink detected
            blink_timestamps.push_back(timestamp_ms);
            eyes_closed = false;
            // Keep only last minute
            while (!blink_timestamps.empty() && (timestamp_ms - blink_timestamps.front()) > 60000) {
                blink_timestamps.pop_front();
            }
        }
        prev_ear = ear;
        
        // Calculate blink rate (blinks per minute)
        if (!blink_timestamps.empty()) {
            int64_t window_start = timestamp_ms - 60000;  // Last minute
            int blink_count = 0;
            for (int64_t ts : blink_timestamps) {
                if (ts >= window_start) {
                    blink_count++;
                }
            }
            current_state_.blink_rate = static_cast<double>(blink_count);
            current_state_.blink_count_total = static_cast<int>(blink_timestamps.size());
        } else {
            current_state_.blink_rate = 0.0;
            current_state_.blink_count_total = 0;
        }
        
        // Calculate PERCLOS (percentage of time eyes are closed)
        if (!ear_history.empty()) {
            int closed_frames = 0;
            for (const auto& entry : ear_history) {
                if (entry.second < ear_threshold) {
                    closed_frames++;
                }
            }
            current_state_.perclos = static_cast<double>(closed_frames) / ear_history.size();
        } else {
            current_state_.perclos = 0.0;
        }
    }
    
    // Update yawn detector with MAR - Improved detection
    if (yawn_detector_) {
        static double mar_threshold = 0.582;  // Tuned from example analysis (25th percentile from 7 examples)
        static std::deque<std::pair<int64_t, double>> mar_history;  // Sliding window (doesn't reset on face loss)
        static std::deque<int64_t> yawn_timestamps;
        static int64_t yawn_start_time = -1;  // When current yawn started
        static bool in_yawn = false;
        
        // Add to history (sliding window - continues even if face is lost)
        if (face_detected) {
            mar_history.push_back({timestamp_ms, mar});
        }
        
        // Keep only last 5 minutes (sliding window)
        while (!mar_history.empty() && (timestamp_ms - mar_history.front().first) > 300000) {
            mar_history.pop_front();
        }
        
        // Improved yawn detection: Prolonged mouth opening with low variation AND eye closure
        if (face_detected) {
            // Track EAR history for yawn detection
            static std::deque<std::pair<int64_t, double>> ear_history_yawn;
            ear_history_yawn.push_back({timestamp_ms, ear});
            // Keep only last 10 seconds
            while (!ear_history_yawn.empty() && (timestamp_ms - ear_history_yawn.front().first) > 10000) {
                ear_history_yawn.pop_front();
            }
            
            // Check if mouth is open (MAR exceeds threshold)
            if (mar > mar_threshold) {
                if (!in_yawn) {
                    // Start tracking a potential yawn
                    yawn_start_time = timestamp_ms;
                    in_yawn = true;
                }
            } else {
                // Mouth closed - check if this was a yawn
                if (in_yawn && yawn_start_time > 0) {
                    // Check if yawn was open long enough (prolonged: at least 0.2 seconds)
                    // Tuned from example analysis (min duration from 7 real yawns)
                    constexpr int64_t MIN_YAWN_DURATION_MS = 200;  // 0.2 seconds minimum
                    int64_t yawn_duration = timestamp_ms - yawn_start_time;
                    
                    if (yawn_duration >= MIN_YAWN_DURATION_MS) {
                        // Get MAR values from history during yawn period
                        std::vector<double> yawn_mar_values;
                        std::vector<double> yawn_ear_values;
                        
                        for (const auto& entry : mar_history) {
                            if (entry.first >= yawn_start_time && entry.first <= timestamp_ms) {
                                yawn_mar_values.push_back(entry.second);
                            }
                        }
                        
                        // Get EAR values during yawn period
                        for (const auto& entry : ear_history_yawn) {
                            if (entry.first >= yawn_start_time && entry.first <= timestamp_ms) {
                                yawn_ear_values.push_back(entry.second);
                            }
                        }
                        
                        if (yawn_mar_values.size() >= 10 && yawn_ear_values.size() >= 10) {
                            // Calculate MAR variation (standard deviation)
                            double mean_mar = 0.0;
                            for (double val : yawn_mar_values) {
                                mean_mar += val;
                            }
                            mean_mar /= yawn_mar_values.size();
                            
                            double variance = 0.0;
                            for (double val : yawn_mar_values) {
                                variance += (val - mean_mar) * (val - mean_mar);
                            }
                            variance /= yawn_mar_values.size();
                            double std_dev = std::sqrt(variance);
                            
                            // Calculate EAR decrease (eyes should close slightly during yawn)
                            double initial_ear = yawn_ear_values[0];
                            double min_ear = *std::min_element(yawn_ear_values.begin(), yawn_ear_values.end());
                            double ear_decrease = initial_ear - min_ear;
                            // Tuned from example analysis: median is 0.065, using 0.03 as minimum (some yawns have less closure)
                            constexpr double MIN_EAR_DECREASE = 0.03;  // Eyes must close at least 0.03 (3%)
                            
        // Low variation threshold: std dev < 0.190 (stable opening, not talking)
                        // Tuned from example analysis (1.5x mean variation from 7 real yawns)
                        constexpr double MAX_VARIATION = 0.190;
                            
                            // Yawn requires: low MAR variation AND eye closure
                            if (std_dev < MAX_VARIATION && ear_decrease >= MIN_EAR_DECREASE) {
                                // This is a yawn! Check if we haven't already counted it
                                bool already_counted = false;
                                for (int64_t ts : yawn_timestamps) {
                                    // If yawn was detected within last 3 seconds, don't count again
                                    if (std::abs(ts - yawn_start_time) < 3000) {
                                        already_counted = true;
                                        break;
                                    }
                                }
                                
                                if (!already_counted) {
                                    yawn_timestamps.push_back(yawn_start_time);
                                    // Keep only last 5 minutes
                                    while (!yawn_timestamps.empty() && 
                                           (timestamp_ms - yawn_timestamps.front()) > 300000) {
                                        yawn_timestamps.pop_front();
                                    }
                                }
                            }
                        }
                    }
                }
                // Reset yawn tracking
                in_yawn = false;
                yawn_start_time = -1;
            }
        }
        // Note: If face is lost, we don't reset in_yawn or yawn_start_time
        // This allows the sliding window to continue tracking
        
        // Count yawns in last 5 minutes (sliding window)
        int64_t window_start = timestamp_ms - 300000;  // Last 5 minutes
        int yawn_count = 0;
        for (int64_t ts : yawn_timestamps) {
            if (ts >= window_start) {
                yawn_count++;
            }
        }
        current_state_.yawn_count_5min = yawn_count;
    }
    
    // Update neck crack detector with head pose
    if (neck_crack_detector_ && face_detected) {
        // Calculate head pose velocity and acceleration for neck crack detection
        static double last_yaw = 0.0;
        static double last_roll = 0.0;
        static double last_yaw_velocity = 0.0;
        static double last_roll_velocity = 0.0;
        static int frames_since_last_crack = 0;
        static std::deque<int64_t> crack_timestamps;
        
        // Calculate rotation velocity (degrees per frame)
        double d_roll = std::abs(head_roll - last_roll);
        double d_yaw = std::abs(head_yaw - last_yaw);
        
        // Calculate acceleration (change in velocity) - this catches sudden movements
        double yaw_acceleration = std::abs(d_yaw - last_yaw_velocity);
        double roll_acceleration = std::abs(d_roll - last_roll_velocity);
        
        // Neck crack detection requires BOTH high velocity AND high acceleration
        // This prevents slow, smooth rotations from triggering
        // Adjusted to be more strict: slow head turns should NOT trigger
        // Real neck cracks are sudden jerky movements with both high velocity AND acceleration
        // Thresholds are now member variables (adjustable via adjust_neck_crack_thresholds)
        constexpr int CRACK_DEBOUNCE_FRAMES = 90;  // 3 seconds at 30fps
        
        // Smoothing: use longer window to better distinguish slow vs sudden movements
        static std::deque<double> yaw_velocities;
        static std::deque<double> roll_velocities;
        static std::deque<double> yaw_accelerations;
        static std::deque<double> roll_accelerations;
        
        yaw_velocities.push_back(d_yaw);
        roll_velocities.push_back(d_roll);
        yaw_accelerations.push_back(yaw_acceleration);
        roll_accelerations.push_back(roll_acceleration);
        
        // Keep only last 5 frames for better smoothing (filters out slow sustained movements)
        if (yaw_velocities.size() > 5) yaw_velocities.pop_front();
        if (roll_velocities.size() > 5) roll_velocities.pop_front();
        if (yaw_accelerations.size() > 5) yaw_accelerations.pop_front();
        if (roll_accelerations.size() > 5) roll_accelerations.pop_front();
        
        // Require at least 3 frames of history before checking (prevents false positives on startup)
        if (yaw_velocities.size() < 3) {
            last_yaw = head_yaw;
            last_roll = head_roll;
            last_yaw_velocity = d_yaw;
            last_roll_velocity = d_roll;
            frames_since_last_crack++;
            // Reset count if no face
            if (!face_detected) {
                frames_since_last_crack = CRACK_DEBOUNCE_FRAMES + 1; // Allow immediate detection after face returns
            }
            current_state_.neck_crack_count_1min = 0;
            return current_state_;
        }
        
        // Average velocity and acceleration over last 5 frames
        double avg_yaw_vel = 0.0;
        double avg_roll_vel = 0.0;
        double avg_yaw_acc = 0.0;
        double avg_roll_acc = 0.0;
        
        for (double v : yaw_velocities) avg_yaw_vel += v;
        for (double v : roll_velocities) avg_roll_vel += v;
        for (double a : yaw_accelerations) avg_yaw_acc += a;
        for (double a : roll_accelerations) avg_roll_acc += a;
        
        if (!yaw_velocities.empty()) avg_yaw_vel /= yaw_velocities.size();
        if (!roll_velocities.empty()) avg_roll_vel /= roll_velocities.size();
        if (!yaw_accelerations.empty()) avg_yaw_acc /= yaw_accelerations.size();
        if (!roll_accelerations.empty()) avg_roll_acc /= roll_accelerations.size();
        
        // Neck crack requires BOTH high velocity AND high acceleration (sudden jerky movement)
        // Slow head turns will have low acceleration (smooth), so they won't trigger
        bool roll_crack = (avg_roll_vel > crack_velocity_threshold_) && (avg_roll_acc > crack_acceleration_threshold_);
        bool yaw_crack = (avg_yaw_vel > crack_velocity_threshold_) && (avg_yaw_acc > crack_acceleration_threshold_);
        
        // Update last values for next frame
        last_yaw_velocity = d_yaw;
        last_roll_velocity = d_roll;
        
        if ((roll_crack || yaw_crack) && frames_since_last_crack > CRACK_DEBOUNCE_FRAMES) {
            crack_timestamps.push_back(timestamp_ms);
            frames_since_last_crack = 0;
            
            // Keep only last minute
            while (!crack_timestamps.empty() && (timestamp_ms - crack_timestamps.front()) > 60000) {
                crack_timestamps.pop_front();
            }
        }
        
        frames_since_last_crack++;
        last_yaw = head_yaw;
        last_roll = head_roll;
        
        // Count cracks in last minute
        int64_t window_start = timestamp_ms - 60000;
        int crack_count = 0;
        for (int64_t ts : crack_timestamps) {
            if (ts >= window_start) {
                crack_count++;
            }
        }
        current_state_.neck_crack_count_1min = crack_count;
    } else if (!face_detected) {
        // Don't reset neck crack count when face is lost (sliding window)
        current_state_.neck_crack_count_1min = 0;  // Will be updated from history if available
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
        current_state_.blink_count_total = gaze_detector_->get_blink_count_total();  // Total blink counter
        current_state_.perclos = gaze_detector_->get_perclos();
        current_state_.current_ear = gaze_detector_->get_current_ear();  // Expose EAR for calibration
        current_state_.current_mar = yawn_detector_->get_current_mar();  // Expose MAR for calibration
        current_state_.yawn_count_5min = yawn_detector_->get_yawn_count_5min();
        current_state_.gaze_stability = gaze_detector_->get_gaze_stability();
        current_state_.neck_crack_count_1min = neck_crack_detector_->get_crack_count_1min();
        
        // Store face bounding box for visualization
        current_state_.face_bbox_x = face_bbox_.x;
        current_state_.face_bbox_y = face_bbox_.y;
        current_state_.face_bbox_width = face_bbox_.width;
        current_state_.face_bbox_height = face_bbox_.height;
        
        // Store key landmarks for visualization (68-point model indices)
        // Scale factor to convert from downscaled to original frame
        double scale = current_state_.scale_factor;
        
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
        
        // Mouth: 48-67 (outer mouth) - ALL 20 points
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
        
        // Store SCALED coordinates for visualization (original frame size)
        // Face bounding box scaled
        current_state_.face_bbox_scaled.clear();
        current_state_.face_bbox_scaled.push_back(face_bbox_.x * scale);
        current_state_.face_bbox_scaled.push_back(face_bbox_.y * scale);
        current_state_.face_bbox_scaled.push_back(face_bbox_.width * scale);
        current_state_.face_bbox_scaled.push_back(face_bbox_.height * scale);
        
        // All 68 landmarks scaled (x,y pairs)
        current_state_.landmarks_scaled.clear();
        for (size_t i = 0; i < landmarks_.size() && i < 68; ++i) {
            current_state_.landmarks_scaled.push_back(landmarks_[i].x * scale);
            current_state_.landmarks_scaled.push_back(landmarks_[i].y * scale);
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
    // Save profile after update
    profile_manager_->save_profile("");
}

void FatigueEngine::start_calibration_session(const std::string& session_type) {
    if (!profile_manager_) return;
    profile_manager_->start_calibration_session(session_type);
}

void FatigueEngine::end_calibration_session(const StateVector& session_stats, double user_rating) {
    if (!profile_manager_) return;
    profile_manager_->end_calibration_session(session_stats, user_rating);
    // Save profile after calibration
    profile_manager_->save_profile("");
}

bool FatigueEngine::is_calibrated() const {
    if (!profile_manager_) return false;
    return profile_manager_->is_calibrated();
}

void FatigueEngine::set_landmark_offset(float x, float y) {
    // Legacy: Combined offset (applies to both eyes and mouth)
    if (face_engine_) {
        face_engine_->set_offset(x, y);
    }
}

void FatigueEngine::set_eye_offset(float x, float y) {
    if (face_engine_) {
        face_engine_->set_eye_offset(x, y);
    }
}

void FatigueEngine::set_mouth_offset(float x, float y) {
    if (face_engine_) {
        face_engine_->set_mouth_offset(x, y);
    }
}

void FatigueEngine::set_ear_threshold(double threshold) {
    if (gaze_detector_) {
        gaze_detector_->set_ear_threshold(threshold);
    }
}

void FatigueEngine::set_mar_threshold(double threshold) {
    if (yawn_detector_) {
        yawn_detector_->set_mar_threshold(threshold);
    }
}

double FatigueEngine::get_ear_threshold() const {
    if (gaze_detector_) {
        return gaze_detector_->get_ear_threshold();
    }
    return 0.20;  // Default
}

double FatigueEngine::get_mar_threshold() const {
    if (yawn_detector_) {
        return yawn_detector_->get_mar_threshold();
    }
    return 0.8;  // Default
}

void FatigueEngine::adjust_neck_crack_thresholds(double velocity_multiplier, double acceleration_multiplier) {
    crack_velocity_threshold_ *= velocity_multiplier;
    crack_acceleration_threshold_ *= acceleration_multiplier;
    // Clamp to reasonable bounds
    if (crack_velocity_threshold_ < 1.0) crack_velocity_threshold_ = 1.0;
    if (crack_velocity_threshold_ > 20.0) crack_velocity_threshold_ = 20.0;
    if (crack_acceleration_threshold_ < 0.5) crack_acceleration_threshold_ = 0.5;
    if (crack_acceleration_threshold_ > 10.0) crack_acceleration_threshold_ = 10.0;
}

void FatigueEngine::get_neck_crack_thresholds(double& velocity, double& acceleration) const {
    velocity = crack_velocity_threshold_;
    acceleration = crack_acceleration_threshold_;
}
