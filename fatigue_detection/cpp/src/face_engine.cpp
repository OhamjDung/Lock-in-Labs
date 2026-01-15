#include "face_engine.h"
#include <dlib/opencv.h>
#include <dlib/image_processing/frontal_face_detector.h>
#include <dlib/image_processing/shape_predictor.h>
#include <opencv2/objdetect.hpp>
#include <iostream>
#include <memory>
#include <fstream>

struct FaceEngine::Impl {
    // YuNet Face Detector (OpenCV) - Modern CNN-based detector
    cv::Ptr<cv::FaceDetectorYN> yunet_detector;
    bool yunet_available = false;
    
    // Dlib Landmark Predictor (for accurate 68-point landmarks)
    dlib::shape_predictor landmark_predictor;
    bool predictor_loaded = false;
    
    // Fallback: dlib HOG detector (if YuNet not available)
    dlib::frontal_face_detector dlib_detector;
    bool use_dlib_fallback = false;
    
    // Detection parameters
    float score_threshold = 0.6f;  // YuNet confidence threshold
    float nms_threshold = 0.3f;   // Non-maximum suppression threshold
    
    // Manual offsets for landmark adjustment
    // Separate offsets for eyes and mouth
    float eye_offset_x = 0.0f;
    float eye_offset_y = 0.0f;
    float mouth_offset_x = 0.0f;
    float mouth_offset_y = 0.0f;
    
    // Legacy: Combined offset
    float offset_x = 0.0f;
    float offset_y = 0.0f;
    
    Impl() : dlib_detector(dlib::get_frontal_face_detector()) {
        // Dlib detector always available as fallback
    }
    
    void load_yunet(const std::string& yunet_path) {
        if (yunet_path.empty()) {
            return;
        }
        
        // Check if file exists
        std::ifstream file(yunet_path);
        if (!file.good()) {
            std::cout << "[FaceEngine] YuNet model not found: " << yunet_path << std::endl;
            std::cout << "[FaceEngine] Will use dlib HOG detector (fallback)" << std::endl;
            use_dlib_fallback = true;
            return;
        }
        
        try {
            // Initialize with default size (will be updated per frame)
            yunet_detector = cv::FaceDetectorYN::create(
                yunet_path,
                "",
                cv::Size(320, 320),  // Default size, updated per frame
                score_threshold,
                nms_threshold,
                5000  // Top K
            );
            
            if (yunet_detector.empty()) {
                throw std::runtime_error("Failed to create YuNet detector");
            }
            
            yunet_available = true;
            use_dlib_fallback = false;
            std::cout << "[FaceEngine] Loaded YuNet face detector: " << yunet_path << std::endl;
        } catch (const cv::Exception& e) {
            std::cerr << "[FaceEngine] Failed to load YuNet: " << e.what() << std::endl;
            std::cerr << "[FaceEngine] Falling back to dlib HOG detector" << std::endl;
            yunet_available = false;
            use_dlib_fallback = true;
        }
    }
    
    bool detect_with_yunet(const cv::Mat& frame, cv::Rect& face_bbox) {
        if (!yunet_available || yunet_detector.empty()) {
            return false;
        }
        
        try {
            // CRITICAL: Update input size for each frame
            yunet_detector->setInputSize(frame.size());
            
            // Detect faces
            cv::Mat faces;
            yunet_detector->detect(frame, faces);
            
            // Check if any faces found
            if (faces.rows < 1) {
                return false;
            }
            
            // Find face with highest confidence
            // YuNet output format: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, confidence]
            int best_face_idx = 0;
            float max_conf = 0.0f;
            
            for (int i = 0; i < faces.rows; ++i) {
                float conf = faces.at<float>(i, 14);  // Confidence is at index 14
                if (conf > max_conf) {
                    max_conf = conf;
                    best_face_idx = i;
                }
            }
            
            // Extract bounding box
            float x = faces.at<float>(best_face_idx, 0);
            float y = faces.at<float>(best_face_idx, 1);
            float w = faces.at<float>(best_face_idx, 2);
            float h = faces.at<float>(best_face_idx, 3);
            
            face_bbox = cv::Rect(
                static_cast<int>(x),
                static_cast<int>(y),
                static_cast<int>(w),
                static_cast<int>(h)
            );
            
            return true;
        } catch (const cv::Exception& e) {
            std::cerr << "[FaceEngine] YuNet detection error: " << e.what() << std::endl;
            return false;
        }
    }
    
    bool detect_with_dlib(const cv::Mat& frame, cv::Rect& face_bbox) {
        try {
            // Convert OpenCV Mat to dlib image
            dlib::cv_image<dlib::bgr_pixel> dlib_img(frame);
            
            // Detect faces with upsampling (helps with glasses)
            // The '1' means upscale image 1 time (2x bigger) for better edge detection
            std::vector<dlib::rectangle> faces = dlib_detector(dlib_img, 1);
            
            if (faces.empty()) {
                return false;
            }
            
            // Use the largest face
            dlib::rectangle largest_face = faces[0];
            double largest_area = faces[0].area();
            for (const auto& face : faces) {
                if (face.area() > largest_area) {
                    largest_area = face.area();
                    largest_face = face;
                }
            }
            
            // Convert dlib rectangle to OpenCV Rect
            face_bbox = cv::Rect(
                largest_face.left(),
                largest_face.top(),
                largest_face.width(),
                largest_face.height()
            );
            
            return true;
        } catch (const std::exception& e) {
            std::cerr << "[FaceEngine] Dlib detection error: " << e.what() << std::endl;
            return false;
        }
    }
    
    void calculate_head_pose(const dlib::full_object_detection& shape, 
                             float& yaw, float& pitch, float& roll) {
        // Calculate head pose angles from 2D landmarks
        // Using simple geometric approach based on facial feature positions
        
        // Get key points for pose estimation
        dlib::point nose_tip = shape.part(30);  // Nose tip
        dlib::point chin = shape.part(8);       // Chin center
        dlib::point left_eye_corner = shape.part(36);   // Left eye outer corner
        dlib::point right_eye_corner = shape.part(45);  // Right eye outer corner
        
        // Calculate pitch (up/down) from nose tip to chin vertical distance
        double nose_chin_dy = chin.y() - nose_tip.y();
        double face_height = chin.y() - (shape.part(27).y() + shape.part(28).y()) / 2.0; // Nose bridge to chin
        if (face_height > 0) {
            pitch = static_cast<float>(std::asin(std::clamp(nose_chin_dy / face_height, -1.0, 1.0)));
        }
        
        // Calculate yaw (left/right) from eye positions
        double eye_center_x = (left_eye_corner.x() + right_eye_corner.x()) / 2.0;
        double eye_width = std::abs(right_eye_corner.x() - left_eye_corner.x());
        double face_center_x = nose_tip.x();
        if (eye_width > 0) {
            double yaw_ratio = (eye_center_x - face_center_x) / eye_width;
            yaw = static_cast<float>(std::asin(std::clamp(yaw_ratio, -1.0, 1.0)));
        }
        
        // Calculate roll (tilt) from eye line angle
        double eye_dy = right_eye_corner.y() - left_eye_corner.y();
        double eye_dx = right_eye_corner.x() - left_eye_corner.x();
        if (std::abs(eye_dx) > 0.1) {
            roll = static_cast<float>(std::atan2(eye_dy, eye_dx));
        }
    }
    
    void apply_angle_offset_correction(float& offset_x, float& offset_y,
                                      float yaw, float pitch, bool is_eyes) {
        // Apply angle-dependent correction to offsets
        // When head is rotated, offsets need to be rotated too
        
        // Convert angles to degrees for easier adjustment
        float yaw_deg = yaw * 180.0f / 3.14159f;
        float pitch_deg = pitch * 180.0f / 3.14159f;
        
        // Rotation matrix for yaw (left/right turn)
        float cos_yaw = std::cos(yaw);
        
        // Rotation matrix for pitch (up/down)
        float cos_pitch = std::cos(pitch);
        
        // Apply rotation to offsets (compensate for head rotation)
        float orig_x = offset_x;
        float orig_y = offset_y;
        
        // Rotate by yaw (around Y-axis - affects X and Z, but we approximate)
        offset_x = orig_x * cos_yaw;
        
        // Rotate by pitch (around X-axis - affects Y and Z, but we approximate)
        offset_y = orig_y * cos_pitch;
        
        // Additional adjustment based on angle magnitude
        // When looking left/right or up/down, offsets need more adjustment
        float yaw_factor = 1.0f + std::abs(yaw_deg) * 0.02f;  // 2% per degree
        float pitch_factor = 1.0f + std::abs(pitch_deg) * 0.02f;
        
        offset_x *= yaw_factor;
        offset_y *= pitch_factor;
    }
};

FaceEngine::FaceEngine() : pimpl_(std::make_unique<Impl>()) {
}

FaceEngine::~FaceEngine() = default;

bool FaceEngine::initialize(const std::string& face_detector_model,
                            const std::string& landmark_predictor_model) {
    if (initialized_) {
        return true;
    }
    
    // Load YuNet face detector
    if (!face_detector_model.empty()) {
        pimpl_->load_yunet(face_detector_model);
    } else {
        // Try default paths for YuNet
        std::vector<std::string> yunet_paths = {
            "models/face_detection_yunet_2023mar.onnx",
            "fatigue_detection/models/face_detection_yunet_2023mar.onnx",
            "../models/face_detection_yunet_2023mar.onnx",
            "../../fatigue_detection/models/face_detection_yunet_2023mar.onnx"
        };
        
        bool yunet_loaded = false;
        for (const auto& path : yunet_paths) {
            std::ifstream file(path);
            if (file.good()) {
                pimpl_->load_yunet(path);
                if (pimpl_->yunet_available) {
                    yunet_loaded = true;
                    break;
                }
            }
        }
        
        if (!yunet_loaded) {
            std::cout << "[FaceEngine] YuNet model not found. Using dlib HOG detector (fallback)" << std::endl;
            std::cout << "[FaceEngine] For better detection (rotation/glasses), download YuNet model:" << std::endl;
            std::cout << "[FaceEngine]   https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" << std::endl;
        }
    }
    
    // Load dlib landmark predictor
    if (!landmark_predictor_model.empty()) {
        try {
            dlib::deserialize(landmark_predictor_model) >> pimpl_->landmark_predictor;
            pimpl_->predictor_loaded = true;
            initialized_ = true;
            std::cout << "[FaceEngine] Loaded landmark predictor: " << landmark_predictor_model << std::endl;
            return true;
        } catch (const std::exception& e) {
            std::cerr << "[FaceEngine] Failed to load landmark predictor: " << e.what() << std::endl;
        }
    }
    
    // Try default paths for landmark predictor
    std::vector<std::string> landmark_paths = {
        "models/shape_predictor_68_face_landmarks.dat",
        "fatigue_detection/models/shape_predictor_68_face_landmarks.dat",
        "../models/shape_predictor_68_face_landmarks.dat",
        "../../fatigue_detection/models/shape_predictor_68_face_landmarks.dat"
    };
    
    for (const auto& path : landmark_paths) {
        try {
            dlib::deserialize(path) >> pimpl_->landmark_predictor;
            pimpl_->predictor_loaded = true;
            initialized_ = true;
            std::cout << "[FaceEngine] Loaded default landmark predictor: " << path << std::endl;
            return true;
        } catch (const std::exception& e) {
            // Continue trying other paths
        }
    }
    
    std::cerr << "[FaceEngine] Warning: Could not load landmark predictor" << std::endl;
    std::cerr << "[FaceEngine] Face detection will work, but landmarks (blinks, yawns) will not." << std::endl;
    initialized_ = true; // Face detection still works without landmarks
    return true;
}

bool FaceEngine::detect_landmarks(const cv::Mat& frame, 
                                  std::vector<cv::Point2f>& landmarks,
                                  cv::Rect& face_bbox) {
    if (!initialized_) {
        // Auto-initialize on first use
        initialize();
    }
    
    landmarks.clear();
    face_bbox = cv::Rect();
    
    bool face_detected = false;
    
    // Try YuNet first (better for rotation and glasses)
    if (pimpl_->yunet_available && !pimpl_->use_dlib_fallback) {
        face_detected = pimpl_->detect_with_yunet(frame, face_bbox);
    }
    
    // Fallback to dlib if YuNet failed or not available
    if (!face_detected) {
        face_detected = pimpl_->detect_with_dlib(frame, face_bbox);
    }
    
    if (!face_detected || face_bbox.width == 0 || face_bbox.height == 0) {
        return false;
    }
    
    // Extract landmarks using dlib (more accurate than YuNet landmarks)
    if (pimpl_->predictor_loaded) {
        try {
            // Convert OpenCV Rect to dlib rectangle
            dlib::rectangle dlib_rect(
                face_bbox.x,
                face_bbox.y,
                face_bbox.x + face_bbox.width,
                face_bbox.y + face_bbox.height
            );
            
            // Convert OpenCV Mat to dlib image
            dlib::cv_image<dlib::bgr_pixel> dlib_img(frame);
            
            // Predict landmarks
            dlib::full_object_detection shape = pimpl_->landmark_predictor(dlib_img, dlib_rect);
            
            // Store landmarks with region-specific offsets applied
            // Simple fixed offsets - no angle-dependent correction
            landmarks.reserve(68);
            for (unsigned int i = 0; i < shape.num_parts(); ++i) {
                dlib::point pt = shape.part(i);
                float offset_x_applied = 0.0f;
                float offset_y_applied = 0.0f;
                
                // Determine which region this landmark belongs to
                // Eyes: landmarks 36-47 (left eye: 36-41, right eye: 42-47)
                // Mouth: landmarks 48-67
                // Other: 0-16 (jawline), 17-26 (eyebrows), 27-35 (nose)
                
                if (i >= 36 && i <= 47) {
                    // Eye region - use eye offset + combined offset
                    offset_x_applied = pimpl_->eye_offset_x + pimpl_->offset_x;
                    offset_y_applied = pimpl_->eye_offset_y + pimpl_->offset_y;
                } else if (i >= 48 && i <= 67) {
                    // Mouth region - use mouth offset + combined offset
                    offset_x_applied = pimpl_->mouth_offset_x + pimpl_->offset_x;
                    offset_y_applied = pimpl_->mouth_offset_y + pimpl_->offset_y;
                } else {
                    // Other regions - use combined offset only
                    offset_x_applied = pimpl_->offset_x;
                    offset_y_applied = pimpl_->offset_y;
                }
                
                landmarks.emplace_back(pt.x() + offset_x_applied, pt.y() + offset_y_applied);
            }
        } catch (const std::exception& e) {
            std::cerr << "[FaceEngine] Error extracting landmarks: " << e.what() << std::endl;
            // Face detected but landmarks failed - still return true for face detection
        }
    }
    
    return true;
}

void FaceEngine::set_offset(float x, float y) {
    if (pimpl_) {
        pimpl_->offset_x = x;
        pimpl_->offset_y = y;
    }
}

std::pair<float, float> FaceEngine::get_offset() const {
    if (pimpl_) {
        return {pimpl_->offset_x, pimpl_->offset_y};
    }
    return {0.0f, 0.0f};
}

void FaceEngine::set_eye_offset(float x, float y) {
    if (pimpl_) {
        pimpl_->eye_offset_x = x;
        pimpl_->eye_offset_y = y;
    }
}

void FaceEngine::set_mouth_offset(float x, float y) {
    if (pimpl_) {
        pimpl_->mouth_offset_x = x;
        pimpl_->mouth_offset_y = y;
    }
}

std::pair<float, float> FaceEngine::get_eye_offset() const {
    if (pimpl_) {
        return {pimpl_->eye_offset_x, pimpl_->eye_offset_y};
    }
    return {0.0f, 0.0f};
}

std::pair<float, float> FaceEngine::get_mouth_offset() const {
    if (pimpl_) {
        return {pimpl_->mouth_offset_x, pimpl_->mouth_offset_y};
    }
    return {0.0f, 0.0f};
}
