#include "profile_manager.h"
#include <fstream>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <nlohmann/json.hpp>

ProfileManager::ProfileManager() {
    // Initialize with default baseline stats
    baseline_stats_ = BaselineStats();
}

double ProfileManager::calculate_clamped_z_score(double current, double baseline, double std_dev) const {
    // Prevent division by zero
    if (std_dev < MIN_STD_DEV) {
        std_dev = MIN_STD_DEV;
    }
    
    // Calculate Z-score
    double z_score = (current - baseline) / std_dev;
    
    // Sigmoid clamp: tanh maps [-inf, inf] -> [-1, 1]
    double clamped = std::tanh(z_score / 2.0);
    
    // Map to [0, 1] range
    return (clamped + 1.0) / 2.0;
}

StateVector ProfileManager::calculate_fatigue_state(const StateVector& current_state) const {
    StateVector result = current_state;
    
    if (!profile_loaded_ || !baseline_stats_.work_session_calibrated) {
        // No profile loaded or not calibrated, use raw metrics without Z-score adjustment
        result.fatigue_score = (current_state.perclos + current_state.fidgeting_score) / 2.0;
        result.energy_state = 0.5;  // Neutral
        result.energy_type = "unknown";
        
        if (result.fatigue_score < 0.3) {
            result.fatigue_level = "focused";
            result.recommendation = "continue";
        } else if (result.fatigue_score < 0.7) {
            result.fatigue_level = "moderate";
            result.recommendation = "take_short_break";
        } else {
            result.fatigue_level = "high";
            result.recommendation = "take_long_break";
        }
        return result;
    }
    
    // Calculate clamped Z-scores for deviation from baseline
    result.z_score_blink = calculate_clamped_z_score(
        current_state.blink_rate,
        baseline_stats_.avg_blink_rate,
        baseline_stats_.blink_rate_std
    );
    
    result.z_score_gaze = calculate_clamped_z_score(
        current_state.gaze_stability,
        baseline_stats_.gaze_stability_baseline,
        baseline_stats_.gaze_stability_std
    );
    
    result.z_score_fidget = calculate_clamped_z_score(
        current_state.fidgeting_score,
        1.0 - (baseline_stats_.motion_energy_baseline / 255.0),  // Normalized
        baseline_stats_.motion_energy_std / 255.0
    );
    
    result.z_score_posture = calculate_clamped_z_score(
        current_state.perclos,
        baseline_stats_.perclos_baseline,
        baseline_stats_.perclos_std
    );
    
    // FUSION ENGINE: Distinguish "Sleepy" (Low Energy) vs "Restless" (High Anxiety)
    // Sleepy indicators: High PERCLOS, Low blink rate, Low fidgeting, Low gaze stability
    // Restless indicators: High fidgeting, High gaze instability, Normal blink rate, Low PERCLOS
    
    double sleepy_score = (result.z_score_posture + (1.0 - result.z_score_blink) + 
                          (1.0 - result.z_score_fidget) + (1.0 - result.z_score_gaze)) / 4.0;
    
    double restless_score = (result.z_score_fidget + (1.0 - result.z_score_gaze) + 
                            result.z_score_blink + (1.0 - result.z_score_posture)) / 4.0;
    
    // Energy state: 0.0 = Sleepy, 1.0 = Restless
    result.energy_state = restless_score / (sleepy_score + restless_score + 0.01);  // Avoid division by zero
    
    // Overall fatigue score (weighted fusion)
    double eye_score = (result.z_score_blink + result.z_score_posture) / 2.0;
    double gaze_score = 1.0 - result.z_score_gaze;  // Lower stability = higher fatigue
    double fidget_score = result.z_score_fidget;
    double yawn_score = current_state.yawn_count_5min > 3 ? 1.0 : 
                       (current_state.yawn_count_5min / 3.0);
    
    result.fatigue_score = 0.4 * eye_score + 
                          0.3 * gaze_score + 
                          0.2 * fidget_score + 
                          0.1 * yawn_score;
    
    // Clamp to [0, 1]
    result.fatigue_score = std::max(0.0, std::min(1.0, result.fatigue_score));
    result.energy_state = std::max(0.0, std::min(1.0, result.energy_state));
    
    // === THREE-GATE SYSTEM: Calculate Lock-In Score ===
    // Gate 3: Fatigue multiplier (inverted from fatigue_score)
    result.fatigue_multiplier = 1.0 - result.fatigue_score;
    
    // Gates 1 & 2 are set from Python (context_multiplier, focus_multiplier)
    // Preserve their values from current_state if already set
    result.context_multiplier = current_state.context_multiplier;
    result.focus_multiplier = current_state.focus_multiplier;
    result.looking_at_screen = current_state.looking_at_screen;
    result.phone_detected = current_state.phone_detected;
    result.active_window = current_state.active_window;
    
    // Combined Lock-In Score = Context × Focus × (1 - Fatigue)
    result.lock_in_score = result.context_multiplier * 
                          result.focus_multiplier * 
                          result.fatigue_multiplier;
    result.lock_in_score = std::max(0.0, std::min(1.0, result.lock_in_score));
    
    // Determine fatigue level, energy type, and recommendation
    if (result.fatigue_score < 0.3) {
        result.fatigue_level = "focused";
        result.energy_type = "focused";
        result.recommendation = "continue";
    } else if (result.fatigue_score < 0.7) {
        result.fatigue_level = "moderate";
        if (result.energy_state < 0.4) {
            result.energy_type = "sleepy";
            result.recommendation = "take_short_break";  // Nap/rest
        } else if (result.energy_state > 0.6) {
            result.energy_type = "restless";
            result.recommendation = "take_walk";  // Walk/stretch
        } else {
            result.energy_type = "moderate";
        result.recommendation = "take_short_break";
        }
    } else {
        result.fatigue_level = "high";
        if (result.energy_state < 0.4) {
            result.energy_type = "sleepy";
            result.recommendation = "take_long_break";  // Sleep/rest
        } else {
            result.energy_type = "anxious";
            result.recommendation = "take_walk";  // Physical activity
        }
    }
    
    return result;
}

void ProfileManager::update_baseline(const StateVector& session_stats, double user_rating) {
    // User rating multiplier: 10/10 = 1.0, 5/10 = 0.1, <5 = 0.0
    // Formula: multiplier = max(0, min(1, (rating - 4) / 6))
    double rating_multiplier = std::max(0.0, std::min(1.0, (user_rating - 4.0) / 6.0));
    
    if (rating_multiplier < 0.1) {
        // Rating too low (<5), don't update (garbage input = garbage output)
        return;
    }
    
    // Weighted moving average: NewMean = OldMean + LearningRate * (SessionMean - OldMean) * RatingMultiplier
    double alpha = LEARNING_RATE * rating_multiplier;
    
    // Update all baseline statistics
    baseline_stats_.avg_blink_rate = (1.0 - alpha) * baseline_stats_.avg_blink_rate + 
                                     alpha * session_stats.blink_rate;
    
    baseline_stats_.gaze_stability_baseline = (1.0 - alpha) * baseline_stats_.gaze_stability_baseline + 
                                               alpha * session_stats.gaze_stability;
    
    baseline_stats_.perclos_baseline = (1.0 - alpha) * baseline_stats_.perclos_baseline + 
                                       alpha * session_stats.perclos;
    
    // Update motion energy (fidgeting) - normalize from score
    double motion_energy = session_stats.fidgeting_score * 255.0;
    baseline_stats_.motion_energy_baseline = (1.0 - alpha) * baseline_stats_.motion_energy_baseline + 
                                             alpha * motion_energy;
    
    // Update standard deviations (simplified - would ideally use running variance)
    // For now, use a smaller learning rate for variance
    double variance_alpha = alpha * 0.5;
    baseline_stats_.blink_rate_std = (1.0 - variance_alpha) * baseline_stats_.blink_rate_std + 
                                     variance_alpha * std::abs(session_stats.blink_rate - baseline_stats_.avg_blink_rate);
    baseline_stats_.gaze_stability_std = (1.0 - variance_alpha) * baseline_stats_.gaze_stability_std + 
                                         variance_alpha * std::abs(session_stats.gaze_stability - baseline_stats_.gaze_stability_baseline);
    baseline_stats_.perclos_std = (1.0 - variance_alpha) * baseline_stats_.perclos_std + 
                                  variance_alpha * std::abs(session_stats.perclos - baseline_stats_.perclos_baseline);
    baseline_stats_.motion_energy_std = (1.0 - variance_alpha) * baseline_stats_.motion_energy_std + 
                                        variance_alpha * std::abs(motion_energy - baseline_stats_.motion_energy_baseline);
    
    // Ensure minimum std dev to prevent division by zero
    baseline_stats_.blink_rate_std = std::max(baseline_stats_.blink_rate_std, MIN_STD_DEV);
    baseline_stats_.gaze_stability_std = std::max(baseline_stats_.gaze_stability_std, MIN_STD_DEV);
    baseline_stats_.perclos_std = std::max(baseline_stats_.perclos_std, MIN_STD_DEV);
    baseline_stats_.motion_energy_std = std::max(baseline_stats_.motion_energy_std, MIN_STD_DEV);
}

void ProfileManager::start_calibration_session(const std::string& session_type) {
    // Store current session type
    current_session_type_ = session_type;
    
    // Reset calibration flags if starting new calibration
    if (session_type == "work") {
        baseline_stats_.work_session_calibrated = false;
    } else if (session_type == "break") {
        baseline_stats_.break_session_calibrated = false;
    }
}

void ProfileManager::end_calibration_session(const StateVector& session_stats, double user_rating) {
    // Only accept high-quality calibration data (rating >= 8)
    if (user_rating < 8.0) {
        return;  // Discard low-quality data
    }
    
    // For work session: This becomes the "Golden Standard" baseline
    // For break session: This becomes the "Chaos" signature (for comparison)
    update_baseline(session_stats, user_rating);
    
    // Mark appropriate session as calibrated
    if (current_session_type_ == "work") {
        baseline_stats_.work_session_calibrated = true;
    } else if (current_session_type_ == "break") {
        baseline_stats_.break_session_calibrated = true;
    }
    
    // Clear session type
    current_session_type_.clear();
    
    // Save profile after calibration
    save_profile("");
}

bool ProfileManager::is_calibrated() const {
    return baseline_stats_.work_session_calibrated;
}

bool ProfileManager::load_profile(const std::string& profile_path) {
    profile_path_ = profile_path;
    // Simplified JSON parsing - full implementation would use nlohmann/json
    // For now, return false to indicate profile needs to be created
    profile_loaded_ = parse_json_file(profile_path);
    return profile_loaded_;
}

bool ProfileManager::parse_json_file(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        // Profile doesn't exist yet - that's OK
        return false;
    }
    
    try {
        nlohmann::json j;
        file >> j;
        
        // Parse baseline_stats
        if (j.contains("baseline_stats")) {
            auto& stats = j["baseline_stats"];
            
            if (stats.contains("avg_blink_rate")) {
                baseline_stats_.avg_blink_rate = stats["avg_blink_rate"];
            }
            if (stats.contains("blink_rate_std")) {
                baseline_stats_.blink_rate_std = stats["blink_rate_std"];
            }
            if (stats.contains("avg_posture_height")) {
                baseline_stats_.avg_posture_height = stats["avg_posture_height"];
            }
            if (stats.contains("posture_height_std")) {
                baseline_stats_.posture_height_std = stats["posture_height_std"];
            }
            if (stats.contains("head_movement_variance")) {
                baseline_stats_.head_movement_variance = stats["head_movement_variance"];
            }
            if (stats.contains("head_movement_std")) {
                baseline_stats_.head_movement_std = stats["head_movement_std"];
            }
            if (stats.contains("gaze_stability_baseline")) {
                baseline_stats_.gaze_stability_baseline = stats["gaze_stability_baseline"];
            }
            if (stats.contains("gaze_stability_std")) {
                baseline_stats_.gaze_stability_std = stats["gaze_stability_std"];
            }
            if (stats.contains("motion_energy_baseline")) {
                baseline_stats_.motion_energy_baseline = stats["motion_energy_baseline"];
            }
            if (stats.contains("motion_energy_std")) {
                baseline_stats_.motion_energy_std = stats["motion_energy_std"];
        }
            if (stats.contains("mar_baseline")) {
                baseline_stats_.mar_baseline = stats["mar_baseline"];
            }
            if (stats.contains("mar_std")) {
                baseline_stats_.mar_std = stats["mar_std"];
            }
            if (stats.contains("perclos_baseline")) {
                baseline_stats_.perclos_baseline = stats["perclos_baseline"];
            }
            if (stats.contains("perclos_std")) {
                baseline_stats_.perclos_std = stats["perclos_std"];
            }
            if (stats.contains("work_session_calibrated")) {
                baseline_stats_.work_session_calibrated = stats["work_session_calibrated"];
            }
            if (stats.contains("break_session_calibrated")) {
                baseline_stats_.break_session_calibrated = stats["break_session_calibrated"];
            }
        }
        
        profile_loaded_ = true;
        return true;
    } catch (const std::exception& e) {
        // JSON parsing failed, use defaults
        profile_loaded_ = false;
        return false;
    }
}

bool ProfileManager::write_json_file(const std::string& path) const {
    try {
        nlohmann::json j;
        j["user_id"] = "default";  // TODO: Get from ProfileManager
        
        // Write baseline_stats
        nlohmann::json stats;
        stats["avg_blink_rate"] = baseline_stats_.avg_blink_rate;
        stats["blink_rate_std"] = baseline_stats_.blink_rate_std;
        stats["avg_posture_height"] = baseline_stats_.avg_posture_height;
        stats["posture_height_std"] = baseline_stats_.posture_height_std;
        stats["head_movement_variance"] = baseline_stats_.head_movement_variance;
        stats["head_movement_std"] = baseline_stats_.head_movement_std;
        stats["gaze_stability_baseline"] = baseline_stats_.gaze_stability_baseline;
        stats["gaze_stability_std"] = baseline_stats_.gaze_stability_std;
        stats["motion_energy_baseline"] = baseline_stats_.motion_energy_baseline;
        stats["motion_energy_std"] = baseline_stats_.motion_energy_std;
        stats["mar_baseline"] = baseline_stats_.mar_baseline;
        stats["mar_std"] = baseline_stats_.mar_std;
        stats["perclos_baseline"] = baseline_stats_.perclos_baseline;
        stats["perclos_std"] = baseline_stats_.perclos_std;
        stats["work_session_calibrated"] = baseline_stats_.work_session_calibrated;
        stats["break_session_calibrated"] = baseline_stats_.break_session_calibrated;
        
        j["baseline_stats"] = stats;
        
    std::ofstream file(path);
    if (!file.is_open()) {
        return false;
    }
    
        file << j.dump(2);  // Pretty print with 2-space indent
    return true;
    } catch (const std::exception& e) {
        return false;
    }
}

bool ProfileManager::save_profile(const std::string& profile_path) const {
    std::string path = profile_path.empty() ? profile_path_ : profile_path;
    if (path.empty()) {
        return false;
    }
    return write_json_file(path);
}
