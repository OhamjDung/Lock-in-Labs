#include "profile_manager.h"
#include <fstream>
#include <sstream>
#include <cmath>
#include <algorithm>

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
    
    if (!profile_loaded_) {
        // No profile loaded, use raw metrics without Z-score adjustment
        result.fatigue_score = (current_state.perclos + current_state.fidgeting_score) / 2.0;
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
    
    // Calculate clamped Z-scores
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
    
    // Weighted fusion of Z-scores
    // Eye metrics (40%), Gaze (30%), Fidgeting (20%), Yawning (10%)
    double eye_score = (result.z_score_blink + (1.0 - current_state.perclos)) / 2.0;
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
    
    // Determine fatigue level and recommendation
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

void ProfileManager::update_baseline(const StateVector& session_stats, double user_rating) {
    // User rating multiplier: 10/10 = 1.0, 5/10 = 0.1
    double rating_multiplier = std::max(0.0, std::min(1.0, (user_rating - 4.0) / 6.0));
    
    if (rating_multiplier < 0.1) {
        // Rating too low, don't update
        return;
    }
    
    // Weighted moving average update
    double alpha = LEARNING_RATE * rating_multiplier;
    
    // Update blink rate
    baseline_stats_.avg_blink_rate = (1.0 - alpha) * baseline_stats_.avg_blink_rate + 
                                     alpha * session_stats.blink_rate;
    
    // Update gaze stability (simplified - would need session average)
    // For now, update variance estimates
    
    // Note: Full implementation would require session statistics collection
    // This is a simplified version
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
    
    // Simplified parsing - full implementation would use nlohmann/json
    // For now, just check if file exists and has content
    std::string line;
    bool has_content = false;
    while (std::getline(file, line)) {
        if (!line.empty() && line.find_first_not_of(" \t\n\r") != std::string::npos) {
            has_content = true;
            break;
        }
    }
    
    // TODO: Parse actual JSON values
    // For now, assume default baseline if file exists but can't parse
    profile_loaded_ = has_content;
    return profile_loaded_;
}

bool ProfileManager::write_json_file(const std::string& path) const {
    std::ofstream file(path);
    if (!file.is_open()) {
        return false;
    }
    
    // Simplified JSON writing - full implementation would use nlohmann/json
    file << "{\n";
    file << "  \"user_id\": \"default\",\n";
    file << "  \"baseline_stats\": {\n";
    file << "    \"avg_blink_rate\": " << baseline_stats_.avg_blink_rate << ",\n";
    file << "    \"blink_rate_std\": " << baseline_stats_.blink_rate_std << ",\n";
    file << "    \"gaze_stability_baseline\": " << baseline_stats_.gaze_stability_baseline << ",\n";
    file << "    \"gaze_stability_std\": " << baseline_stats_.gaze_stability_std << "\n";
    file << "  }\n";
    file << "}\n";
    
    return true;
}

bool ProfileManager::save_profile(const std::string& profile_path) const {
    std::string path = profile_path.empty() ? profile_path_ : profile_path;
    if (path.empty()) {
        return false;
    }
    return write_json_file(path);
}
