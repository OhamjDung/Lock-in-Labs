#include "face_engine.h"
#include <dlib/opencv.h>
#include <dlib/image_processing/frontal_face_detector.h>
#include <dlib/image_processing/shape_predictor.h>
#include <iostream>
#include <memory>

struct FaceEngine::Impl {
    dlib::frontal_face_detector face_detector;
    dlib::shape_predictor landmark_predictor;
    bool predictor_loaded = false;
    
    Impl() : face_detector(dlib::get_frontal_face_detector()) {
        // Face detector is always available (built-in)
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
    
    // Face detector is built-in, no loading needed
    
    // Load landmark predictor if path provided
    if (!landmark_predictor_model.empty()) {
        try {
            dlib::deserialize(landmark_predictor_model) >> pimpl_->landmark_predictor;
            pimpl_->predictor_loaded = true;
            initialized_ = true;
            std::cout << "[FaceEngine] Loaded landmark predictor: " << landmark_predictor_model << std::endl;
            return true;
        } catch (const std::exception& e) {
            std::cerr << "[FaceEngine] Failed to load landmark predictor: " << e.what() << std::endl;
            return false;
        }
    } else {
        // Try default path
        std::string default_path = "models/shape_predictor_68_face_landmarks.dat";
        try {
            dlib::deserialize(default_path) >> pimpl_->landmark_predictor;
            pimpl_->predictor_loaded = true;
            initialized_ = true;
            std::cout << "[FaceEngine] Loaded default landmark predictor" << std::endl;
            return true;
        } catch (const std::exception& e) {
            std::cerr << "[FaceEngine] Warning: Could not load default landmark predictor: " << e.what() << std::endl;
            std::cerr << "[FaceEngine] Continuing without landmarks (face detection only)" << std::endl;
            initialized_ = true; // Face detection still works
            return true;
        }
    }
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
    
    try {
        // Convert OpenCV Mat to dlib image
        dlib::cv_image<dlib::bgr_pixel> dlib_img(frame);
        
        // Detect faces
        std::vector<dlib::rectangle> faces = pimpl_->face_detector(dlib_img);
        
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
        
        // Extract landmarks if predictor is loaded
        if (pimpl_->predictor_loaded) {
            dlib::full_object_detection shape = pimpl_->landmark_predictor(dlib_img, largest_face);
            
            landmarks.reserve(68);
            for (unsigned int i = 0; i < shape.num_parts(); ++i) {
                dlib::point pt = shape.part(i);
                landmarks.emplace_back(pt.x(), pt.y());
            }
        }
        
        return true;
    } catch (const std::exception& e) {
        std::cerr << "[FaceEngine] Error during detection: " << e.what() << std::endl;
        return false;
    }
}
