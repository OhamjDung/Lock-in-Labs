#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include "detector.h"
#include <iostream>

namespace py = pybind11;

// Convert cv::Mat to numpy array (zero-copy if possible)
py::array_t<uint8_t> mat_to_numpy(const cv::Mat& mat) {
    if (mat.empty()) {
        return py::array_t<uint8_t>();
    }
    
    // Create numpy array from OpenCV Mat (zero-copy if Mat is contiguous)
    py::array_t<uint8_t> array({mat.rows, mat.cols, mat.channels()}, 
                                {mat.step[0], mat.step[1], mat.step[2]},
                                mat.data, py::cast(mat));
    
    return array;
}

// Convert numpy array to cv::Mat (zero-copy if possible)
cv::Mat numpy_to_mat(py::array_t<uint8_t> input) {
    py::buffer_info buf_info = input.request();
    
    if (buf_info.ndim != 3 && buf_info.ndim != 2) {
        throw std::runtime_error("Number of dimensions must be 2 or 3");
    }
    
    int rows = static_cast<int>(buf_info.shape[0]);
    int cols = static_cast<int>(buf_info.shape[1]);
    int channels = buf_info.ndim == 3 ? static_cast<int>(buf_info.shape[2]) : 1;
    
    // Determine CV type
    int type;
    if (buf_info.format == py::format_descriptor<uint8_t>::format()) {
        type = channels == 1 ? CV_8UC1 : (channels == 3 ? CV_8UC3 : CV_8UC4);
    } else {
        throw std::runtime_error("Unsupported buffer format");
    }
    
    // Create cv::Mat header (zero-copy if input is contiguous)
    // Check if array is C-contiguous
    bool is_contiguous = true;
    if (buf_info.ndim > 1) {
        size_t expected_stride = buf_info.itemsize;
        for (int i = buf_info.ndim - 1; i >= 0; --i) {
            if (buf_info.strides[i] != expected_stride) {
                is_contiguous = false;
                break;
            }
            expected_stride *= buf_info.shape[i];
        }
    }
    
    if (is_contiguous) {
        // Contiguous array - can use zero-copy (but clone to ensure ownership)
        cv::Mat mat(rows, cols, type, const_cast<void*>(buf_info.ptr));
        return mat.clone();  // Clone to ensure Mat owns the data
    } else {
        // Non-contiguous - need to copy
        cv::Mat mat(rows, cols, type, const_cast<void*>(buf_info.ptr), buf_info.strides[0]);
        return mat.clone();
    }
}

// StateVector to Python dict converter
py::dict state_vector_to_dict(const StateVector& state) {
    py::dict result;
    result["blink_rate"] = state.blink_rate;
    result["blink_count_total"] = state.blink_count_total;  // Total blink counter
    result["perclos"] = state.perclos;
    result["current_ear"] = state.current_ear;  // Expose EAR for calibration
    result["current_mar"] = state.current_mar;  // Expose MAR for calibration
    result["yawn_count_5min"] = state.yawn_count_5min;
    result["gaze_stability"] = state.gaze_stability;
    result["fidgeting_score"] = state.fidgeting_score;
    result["neck_crack_count_1min"] = state.neck_crack_count_1min;
    
    // Face detection regions for visualization
    result["face_bbox"] = py::dict();
    result["face_bbox"]["x"] = state.face_bbox_x;
    result["face_bbox"]["y"] = state.face_bbox_y;
    result["face_bbox"]["width"] = state.face_bbox_width;
    result["face_bbox"]["height"] = state.face_bbox_height;
    
    result["left_eye_points"] = state.left_eye_points;
    result["right_eye_points"] = state.right_eye_points;
    result["mouth_points"] = state.mouth_points;
    result["nose_tip"] = state.nose_tip;
    result["scale_factor"] = state.scale_factor;  // For scaling landmarks to original frame
    
    // Scaled coordinates (already scaled to original frame size)
    result["face_bbox_scaled"] = state.face_bbox_scaled;  // [x, y, width, height]
    result["landmarks_scaled"] = state.landmarks_scaled;  // All 68 landmarks (x,y pairs)
    result["z_score_blink"] = state.z_score_blink;
    result["z_score_gaze"] = state.z_score_gaze;
    result["z_score_posture"] = state.z_score_posture;
    result["z_score_fidget"] = state.z_score_fidget;
    result["fatigue_score"] = state.fatigue_score;
    result["energy_state"] = state.energy_state;
    result["fatigue_level"] = state.fatigue_level;
    result["energy_type"] = state.energy_type;
    result["recommendation"] = state.recommendation;
    
    // THREE-GATE SYSTEM fields
    result["active_window"] = state.active_window;
    result["context_multiplier"] = state.context_multiplier;
    result["looking_at_screen"] = state.looking_at_screen;
    result["phone_detected"] = state.phone_detected;
    result["focus_multiplier"] = state.focus_multiplier;
    result["fatigue_multiplier"] = state.fatigue_multiplier;
    result["lock_in_score"] = state.lock_in_score;
    
    result["events"] = state.events;
    // Note: EAR is not stored in StateVector, it's internal to GazeDetector
    // We'd need to expose it separately if needed for calibration
    return result;
}

PYBIND11_MODULE(lockin_core, m) {
    m.doc() = "Fatigue Detection Engine - C++ Core Module";
    
    // StateVector class binding
    py::class_<StateVector>(m, "StateVector")
        .def(py::init<>())
        .def_readwrite("blink_rate", &StateVector::blink_rate)
        .def_readwrite("perclos", &StateVector::perclos)
        .def_readwrite("yawn_count_5min", &StateVector::yawn_count_5min)
        .def_readwrite("gaze_stability", &StateVector::gaze_stability)
        .def_readwrite("fidgeting_score", &StateVector::fidgeting_score)
        .def_readwrite("neck_crack_count_1min", &StateVector::neck_crack_count_1min)
        .def_readwrite("fatigue_score", &StateVector::fatigue_score)
        .def_readwrite("fatigue_level", &StateVector::fatigue_level)
        .def_readwrite("recommendation", &StateVector::recommendation)
        .def_readwrite("events", &StateVector::events)
        // THREE-GATE SYSTEM fields
        .def_readwrite("active_window", &StateVector::active_window)
        .def_readwrite("context_multiplier", &StateVector::context_multiplier)
        .def_readwrite("looking_at_screen", &StateVector::looking_at_screen)
        .def_readwrite("phone_detected", &StateVector::phone_detected)
        .def_readwrite("focus_multiplier", &StateVector::focus_multiplier)
        .def_readwrite("fatigue_multiplier", &StateVector::fatigue_multiplier)
        .def_readwrite("lock_in_score", &StateVector::lock_in_score)
        .def("to_dict", &state_vector_to_dict)
        .def("__repr__", [](const StateVector& s) {
            return "StateVector(fatigue_score=" + std::to_string(s.fatigue_score) + 
                   ", level=" + s.fatigue_level + ")";
        });
    
    // FatigueEngine class binding
    py::class_<FatigueEngine>(m, "FatigueEngine")
        .def(py::init<const std::string&, const std::string&>(),
             py::arg("user_id"),
             py::arg("profile_path") = "",
             "Initialize FatigueEngine with user_id and optional profile path")
        
        .def("process_frame", 
             [](FatigueEngine& self, py::array_t<uint8_t> frame, int64_t timestamp_ms) -> py::dict {
                 // Convert numpy array to cv::Mat (zero-copy if contiguous)
                 cv::Mat mat = numpy_to_mat(frame);
                 
                 // Process frame
                 StateVector state = self.process_frame(mat, timestamp_ms);
                 
                 // Convert StateVector to Python dict
                 return state_vector_to_dict(state);
             },
             py::arg("frame"),
             py::arg("timestamp_ms") = -1,
             "Process a frame and return fatigue metrics as dict. "
             "Frame must be numpy array (H, W, 3) uint8. "
             "Zero-copy if frame is contiguous.")
        
        .def("update_metrics",
             [](FatigueEngine& self, double ear, double mar, double gaze_x, double gaze_y, 
                int64_t timestamp_ms, bool face_detected, double head_pitch, double head_yaw, double head_roll) -> py::dict {
                 // Update metrics directly (for MediaPipe integration)
                 StateVector state = self.update_metrics(ear, mar, gaze_x, gaze_y, timestamp_ms, face_detected, 
                                                        head_pitch, head_yaw, head_roll);
                 
                 // Convert StateVector to Python dict
                 return state_vector_to_dict(state);
             },
             py::arg("ear"), py::arg("mar"), py::arg("gaze_x"), py::arg("gaze_y"), 
             py::arg("timestamp_ms"), py::arg("face_detected") = true,
             py::arg("head_pitch") = 0.0, py::arg("head_yaw") = 0.0, py::arg("head_roll") = 0.0,
             "Update metrics directly from MediaPipe (bypasses face detection)")
        
        .def("load_profile",
             &FatigueEngine::load_profile,
             py::arg("profile_path"),
             "Load user profile from JSON file")
        
        .def("update_profile",
             [](FatigueEngine& self, py::dict session_stats_dict, double user_rating) {
                 // Convert dict to StateVector (simplified)
                 StateVector session_stats;
                 if (session_stats_dict.contains("blink_rate")) {
                     session_stats.blink_rate = py::cast<double>(session_stats_dict["blink_rate"]);
                 }
                 if (session_stats_dict.contains("gaze_stability")) {
                     session_stats.gaze_stability = py::cast<double>(session_stats_dict["gaze_stability"]);
                 }
                 // ... add more fields as needed
                 
                 self.update_profile(session_stats, user_rating);
             },
             py::arg("session_stats"),
             py::arg("user_rating"),
             "Update profile baseline with session statistics and user rating")
        
        .def("set_downscale_width", &FatigueEngine::set_downscale_width,
             py::arg("width"),
             "Set downscale width for face detection (default: 640)")
        
        .def("set_downscale_height", &FatigueEngine::set_downscale_height,
             py::arg("height"),
             "Set downscale height for face detection (default: 480)")
        
        .def("set_ear_threshold", &FatigueEngine::set_ear_threshold,
             py::arg("threshold"),
             "Set Eye Aspect Ratio threshold for blink detection (calibration)")
        
        .def("set_mar_threshold", &FatigueEngine::set_mar_threshold,
             py::arg("threshold"),
             "Set Mouth Aspect Ratio threshold for yawn detection (calibration)")
        
        .def("get_ear_threshold", &FatigueEngine::get_ear_threshold,
             "Get current EAR threshold")
        
        .def("get_mar_threshold", &FatigueEngine::get_mar_threshold,
             "Get current MAR threshold")
        
        .def("adjust_neck_crack_thresholds",
             &FatigueEngine::adjust_neck_crack_thresholds,
             py::arg("velocity_multiplier"), py::arg("acceleration_multiplier"),
             "Adjust neck crack detection thresholds by multiplying current values (for false positive feedback)")
        
        .def("get_neck_crack_thresholds",
             [](const FatigueEngine& self) -> py::dict {
                 double vel, acc;
                 self.get_neck_crack_thresholds(vel, acc);
                 py::dict result;
                 result["velocity"] = vel;
                 result["acceleration"] = acc;
                 return result;
             },
             "Get current neck crack detection thresholds")
        
        .def("start_calibration_session",
             &FatigueEngine::start_calibration_session,
             py::arg("session_type"),
             "Start a calibration session ('work' or 'break')")
        
        .def("end_calibration_session",
             [](FatigueEngine& self, py::dict session_stats_dict, double user_rating) {
                 // Convert dict to StateVector
                 StateVector session_stats;
                 if (session_stats_dict.contains("blink_rate")) {
                     session_stats.blink_rate = py::cast<double>(session_stats_dict["blink_rate"]);
                 }
                 if (session_stats_dict.contains("gaze_stability")) {
                     session_stats.gaze_stability = py::cast<double>(session_stats_dict["gaze_stability"]);
                 }
                 if (session_stats_dict.contains("perclos")) {
                     session_stats.perclos = py::cast<double>(session_stats_dict["perclos"]);
                 }
                 if (session_stats_dict.contains("fidgeting_score")) {
                     session_stats.fidgeting_score = py::cast<double>(session_stats_dict["fidgeting_score"]);
                 }
                 // Add more fields as needed
                 
                 self.end_calibration_session(session_stats, user_rating);
             },
             py::arg("session_stats"),
             py::arg("user_rating"),
             "End calibration session and save baseline (only if rating >= 8)")
        
        .def("is_calibrated",
             &FatigueEngine::is_calibrated,
             "Check if user profile is calibrated")
        .def("set_landmark_offset", &FatigueEngine::set_landmark_offset,
             py::arg("x"), py::arg("y"),
             "Set manual offset for all landmarks (legacy - applies to both eyes and mouth)")
        .def("set_eye_offset", &FatigueEngine::set_eye_offset,
             py::arg("x"), py::arg("y"),
             "Set manual offset for eye landmarks only (36-47)")
        .def("set_mouth_offset", &FatigueEngine::set_mouth_offset,
             py::arg("x"), py::arg("y"),
             "Set manual offset for mouth landmarks only (48-67)");
    
    // Version info
    m.attr("__version__") = "1.0.0";
}
