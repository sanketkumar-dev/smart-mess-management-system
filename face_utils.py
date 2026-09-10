"""
==================================================
SMART MESS MANAGEMENT SYSTEM - FACE UTILITIES
==================================================
Description:
Real face detection and recognition module using
OpenCV Haar Cascade and LBPH Face Recognizer.
==================================================
"""

import os
import json
import base64

import cv2
import numpy as np

from database import get_db_connection


# ==================================================
# PROJECT DIRECTORIES & FILES - START
# ==================================================

# Current project directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Main face data directory
FACE_DATA_DIR = os.path.join(
    BASE_DIR,
    "face_data"
)

# Student face samples directory
FACES_DIR = os.path.join(
    FACE_DATA_DIR,
    "faces"
)

# Trained LBPH model
MODEL_PATH = os.path.join(
    FACE_DATA_DIR,
    "face_model.xml"
)

# Student label mapping
LABELS_PATH = os.path.join(
    FACE_DATA_DIR,
    "labels.json"
)

# Haar Cascade XML file
HAAR_CASCADE_PATH = os.path.join(
    FACE_DATA_DIR,
    "haarcascade_frontalface_default.xml"
)

student_recognizer_cache = {}

student_recognizer_cache = {}

# Required folders automatically create karo.
os.makedirs(
    FACE_DATA_DIR,
    exist_ok=True
)

os.makedirs(
    FACES_DIR,
    exist_ok=True
)

# ==================================================
# PROJECT DIRECTORIES & FILES - END
# ==================================================


# ==================================================
# HAAR CASCADE FACE DETECTOR - START
# ==================================================

# Haar Cascade XML project ke face_data folder
# se load ki ja rahi hai.
#
# IMPORTANT:
# OpenCV 5 installation me cascade XML bundled
# nahi hai, isliye cv2.data.haarcascades use nahi
# kar rahe hain.

if not os.path.isfile(HAAR_CASCADE_PATH):
    raise FileNotFoundError(
        "Haar Cascade XML file nahi mili.\n"
        f"Expected location:\n{HAAR_CASCADE_PATH}\n\n"
        "Please make sure "
        "haarcascade_frontalface_default.xml "
        "face_data folder ke andar hai."
    )


try:

    # Haar Cascade classifier load karo.
    face_cascade = cv2.CascadeClassifier(
        HAAR_CASCADE_PATH
    )

except Exception as e:

    raise RuntimeError(
        "Haar Cascade XML load karte waqt error aaya.\n"
        f"File: {HAAR_CASCADE_PATH}\n"
        f"Error: {e}"
    )


# Check karo classifier successfully load hua.
if face_cascade.empty():

    raise RuntimeError(
        "Haar Cascade classifier load nahi ho paya.\n"
        f"XML file: {HAAR_CASCADE_PATH}\n"
        "Please check ki XML file valid hai."
    )


print(
    "[FaceUtils] Haar Cascade loaded successfully."
)


# ==================================================
# HAAR CASCADE FACE DETECTOR - END
# ==================================================


# ==================================================
# LBPH RECOGNIZER AVAILABILITY CHECK - START
# ==================================================

# opencv-contrib-python me cv2.face available hona chahiye.
FACE_MODULE = getattr(
    cv2,
    "face",
    None
)

if FACE_MODULE is None:

    raise RuntimeError(
        "OpenCV Face module available nahi hai.\n"
        "Please install opencv-contrib-python."
    )


LBPH_CREATE = getattr(
    FACE_MODULE,
    "LBPHFaceRecognizer_create",
    None
)

if LBPH_CREATE is None:

    raise RuntimeError(
        "LBPH Face Recognizer available nahi hai.\n"
        "Please install opencv-contrib-python."
    )


print(
    "[FaceUtils] LBPH Face Recognizer available."
)


# ==================================================
# LBPH RECOGNIZER AVAILABILITY CHECK - END
# ==================================================


# ==================================================
# IMAGE DECODING & PREPROCESSING - START
# ==================================================

def decode_base64_image(base64_str):
    """
    Browser webcam se received Base64 image ko
    OpenCV BGR image me convert karta hai.
    """

    try:

        # Invalid input check
        if not base64_str:
            return None

        # Agar data URL format hai:
        #
        # data:image/jpeg;base64,XXXX
        #
        # to sirf Base64 wala part rakho.
        if "," in base64_str:

            base64_str = base64_str.split(
                ",",
                1
            )[1]

        # Base64 ko bytes me convert karo.
        img_bytes = base64.b64decode(
            base64_str
        )

        # Bytes ko NumPy array me convert karo.
        np_arr = np.frombuffer(
            img_bytes,
            dtype=np.uint8
        )

        # NumPy array ko OpenCV image me decode karo.
        img = cv2.imdecode(
            np_arr,
            cv2.IMREAD_COLOR
        )

        return img

    except Exception as e:

        print(
            f"[FaceUtils] Image decoding error: {e}"
        )

        return None


def preprocess_face(
    face_roi,
    target_size=(200, 200)
):
    """
    Face image ko LBPH recognition ke liye
    standard format me convert karta hai.

    Steps:
    1. Grayscale conversion
    2. Resize
    3. Histogram equalization
    """

    # Agar image color me hai,
    # grayscale me convert karo.
    if len(face_roi.shape) == 3:

        gray = cv2.cvtColor(
            face_roi,
            cv2.COLOR_BGR2GRAY
        )

    else:

        gray = face_roi

    # Standard 200 x 200 size.
    resized = cv2.resize(
        gray,
        target_size,
        interpolation=cv2.INTER_AREA
    )

    # Contrast improve karo.
    equalized = cv2.equalizeHist(
        resized
    )

    return equalized


# ==================================================
# IMAGE DECODING & PREPROCESSING - END
# ==================================================


# ==================================================
# FACE DETECTION ENGINE - START
# ==================================================

def detect_faces(image_b64):
    """
    Base64 image me faces detect karta hai.

    Returns:
        count
        faces_data
        original_img
    """

    # Base64 image decode karo.
    img = decode_base64_image(
        image_b64
    )

    # Image decode nahi hui.
    if img is None:

        return (
            0,
            [],
            None
        )

    # Face detection grayscale image par hota hai.
    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    # Haar Cascade se face detect karo.
    detected = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.15,
        minNeighbors=5,
        minSize=(60, 60)
    )

    faces_data = []

    # Har detected face process karo.
    for (
        x,
        y,
        w,
        h
    ) in detected:

        # Face ke around 10% margin.
        h_pad = int(
            h * 0.10
        )

        w_pad = int(
            w * 0.10
        )

        # Image boundaries ke andar coordinates.
        y1 = max(
            0,
            y - h_pad
        )

        y2 = min(
            img.shape[0],
            y + h + h_pad
        )

        x1 = max(
            0,
            x - w_pad
        )

        x2 = min(
            img.shape[1],
            x + w + w_pad
        )

        # Face ROI grayscale me.
        roi = gray[
            y1:y2,
            x1:x2
        ]

        # Recognition ke liye preprocess.
        processed_roi = preprocess_face(
            roi
        )

        faces_data.append({

            "rect": (
                int(x),
                int(y),
                int(w),
                int(h)
            ),

            "processed": processed_roi,

            "raw_roi": img[
                y1:y2,
                x1:x2
            ]
        })

    return (
        len(detected),
        faces_data,
        img
    )


# ==================================================
# FACE DETECTION ENGINE - END
# ==================================================


# ==================================================
# MODEL TRAINING & MANAGEMENT - START
# ==================================================

def train_model():
    """
    Stored student face samples se LBPH model train karta hai.

    Model:
        face_data/face_model.xml

    Labels:
        face_data/labels.json
    """

    faces = []

    labels = []

    label_to_student = {}

    current_label_id = 0

    # Face directory check.
    if not os.path.exists(
        FACES_DIR
    ):

        return (
            False,
            "Face dataset directory not found."
        )

    # Student folders read karo.
    student_folders = sorted(
        os.listdir(
            FACES_DIR
        )
    )

    if not student_folders:

        return (
            False,
            "No student face data available to train."
        )

    # Har student folder process karo.
    for folder_name in student_folders:

        student_folder_path = os.path.join(
            FACES_DIR,
            folder_name
        )

        # Sirf folders process karo.
        if not os.path.isdir(
            student_folder_path
        ):

            continue

        # Folder name = student ID.
        student_id = folder_name

        # Numeric label ko student ID se map karo.
        label_to_student[
            current_label_id
        ] = student_id

        # Student ke face samples.
        for img_name in os.listdir(
            student_folder_path
        ):

            # Supported image formats.
            if not img_name.lower().endswith(
                (
                    ".png",
                    ".jpg",
                    ".jpeg"
                )
            ):

                continue

            img_path = os.path.join(
                student_folder_path,
                img_name
            )

            # Grayscale image read karo.
            img = cv2.imread(
                img_path,
                cv2.IMREAD_GRAYSCALE
            )

            # Invalid image skip.
            if img is None:

                print(
                    f"[FaceUtils] Invalid image skipped: "
                    f"{img_path}"
                )

                continue

            # Image preprocess karo.
            processed = preprocess_face(
                img
            )

            # Training arrays me add.
            faces.append(
                processed
            )

            labels.append(
                current_label_id
            )

        current_label_id += 1

    # Training data available nahi.
    if not faces or not labels:

        return (
            False,
            "No valid face samples found for training."
        )

    # ==================================================
    # CREATE LBPH MODEL - START
    # ==================================================

    recognizer = LBPH_CREATE(
        radius=1,
        neighbors=8,
        grid_x=8,
        grid_y=8
    )

    # Model train karo.
    recognizer.train(
        faces,
        np.array(
            labels,
            dtype=np.int32
        )
    )

    # Model save karo.
    recognizer.save(
        MODEL_PATH
    )

    student_recognizer_cache.clear()

    student_recognizer_cache.clear()

    # Label mapping save karo.
    with open(
        LABELS_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            label_to_student,
            f,
            indent=2
        )

    # ==================================================
    # CREATE LBPH MODEL - END
    # ==================================================

    print(
        "[FaceUtils] Model successfully trained."
    )

    print(
        f"[FaceUtils] Samples: {len(faces)}"
    )

    print(
        f"[FaceUtils] Students: "
        f"{len(label_to_student)}"
    )

    return (
        True,
        f"Trained on {len(faces)} samples."
    )


# ==================================================
# MODEL TRAINING & MANAGEMENT - END
# ==================================================


# ==================================================
# STUDENT FACE REGISTRATION - START
# ==================================================

def register_student_face(
    student_id,
    image_b64
):
    """
    Student ka face webcam image se register karta hai.

    Steps:
    1. Face detection
    2. Single face validation
    3. Face samples save
    4. Database update
    5. LBPH model retrain
    """

    return register_student_faces(student_id, [image_b64])


def register_student_faces(student_id, images_b64):
    """Register several validated webcam captures for one student."""
    if not images_b64:
        return {"success": False, "status": "no_face", "message": "No face samples received."}

    captured_faces = []
    for image_b64 in images_b64:
        count, faces_data, original_img = detect_faces(image_b64)
        if count == 0:
            return {"success": False, "status": "no_face", "message": "A capture did not contain a detectable face. Please try again."}
        if count > 1:
            return {"success": False, "status": "multiple_faces", "message": "Multiple faces detected in a capture. Please ensure only one student is visible."}
        captured_faces.append(faces_data[0])

    # Student face folder.
    student_dir = os.path.join(
        FACES_DIR,
        str(student_id)
    )

    os.makedirs(
        student_dir,
        exist_ok=True
    )

    for img_name in os.listdir(student_dir):
        if img_name.lower().endswith((".png", ".jpg", ".jpeg")):
            os.remove(os.path.join(student_dir, img_name))

    cv2.imwrite(os.path.join(student_dir, "face_primary.jpg"), captured_faces[0]["raw_roi"])
    for sample_number, face_item in enumerate(captured_faces, start=1):
        cv2.imwrite(os.path.join(student_dir, f"sample_{sample_number}.jpg"), face_item["processed"])

    if len(captured_faces) == 1:
        processed_face = captured_faces[0]["processed"]
        cv2.imwrite(os.path.join(student_dir, "sample_2.jpg"), cv2.convertScaleAbs(processed_face, alpha=1.10, beta=10))
        cv2.imwrite(os.path.join(student_dir, "sample_3.jpg"), cv2.convertScaleAbs(processed_face, alpha=0.90, beta=-10))
        cv2.imwrite(os.path.join(student_dir, "sample_4.jpg"), cv2.flip(processed_face, 1))


    # ==================================================
    # DATABASE UPDATE - START
    # ==================================================

    db_image_path = (
        f"face_data/faces/"
        f"{student_id}/face_primary.jpg"
    )

    conn = get_db_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE students
            SET
                face_registered = 1,
                face_image_path = ?
            WHERE student_id = ?
            """,
            (
                db_image_path,
                student_id
            )
        )

        conn.commit()

    finally:

        conn.close()

    # ==================================================
    # DATABASE UPDATE - END
    # ==================================================


    # ==================================================
    # RETRAIN MODEL - START
    # ==================================================

    trained, training_message = train_model()

    # ==================================================
    # RETRAIN MODEL - END
    # ==================================================

    # Browser ke liye image path.
    web_face_path = (
        f"/static/face_data/faces/"
        f"{student_id}/face_primary.jpg"
    )

    return {

        "success": True,

        "status": "registered",

        "message": (
            f"Face for {student_id} "
            "successfully captured and registered!"
        ),

        "image_path": web_face_path,

        "model_trained": trained,

        "training_message": training_message
    }


# ==================================================
# STUDENT FACE REGISTRATION - END
# ==================================================


# ==================================================
# LIVE FACE ATTENDANCE SCANNER - START
# ==================================================

def recognize_face_from_stream(
    image_b64
):
    """
    Live webcam frame se student recognize karta hai.

    Returns:
        success
        status
        student_id
        student information
        confidence
        message
    """

    # ==================================================
    # FACE DETECTION - START
    # ==================================================

    count, faces_data, original_img = detect_faces(
        image_b64
    )

    # ==================================================
    # FACE DETECTION - END
    # ==================================================


    # ==================================================
    # NO FACE CHECK - START
    # ==================================================

    if count == 0:

        return {
            "success": False,
            "status": "no_face",
            "message": "No face detected."
        }

    # ==================================================
    # NO FACE CHECK - END
    # ==================================================


    # ==================================================
    # MULTIPLE FACE CHECK - START
    # ==================================================

    if count > 1:

        return {
            "success": False,
            "status": "multiple_faces",
            "message": (
                "Please ensure only one student "
                "is visible."
            )
        }

    # ==================================================
    # MULTIPLE FACE CHECK - END
    # ==================================================


    # ==================================================
    # MODEL CHECK - START
    # ==================================================

    if (
        not os.path.exists(MODEL_PATH)
        or not os.path.exists(LABELS_PATH)
    ):

        trained, training_message = train_model()

        if not trained:

            return {
                "success": False,
                "status": "unknown",
                "message": (
                    "Student not recognized. "
                    "No trained face model available."
                )
            }

    # ==================================================
    # MODEL CHECK - END
    # ==================================================


    # ==================================================
    # LBPH RECOGNITION - START
    # ==================================================

    try:
        # Current face preprocess.
        processed_face = faces_data[0][
            "processed"
        ]

        # Score each student's own samples independently. A global LBPH
        # model always returns its closest label, even for an unknown face.
        candidate_scores = []
        for student_id in sorted(os.listdir(FACES_DIR)):
            student_folder_path = os.path.join(FACES_DIR, student_id)
            if not os.path.isdir(student_folder_path):
                continue

            student_images = []
            for img_name in os.listdir(student_folder_path):
                if not img_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
                img_path = os.path.join(student_folder_path, img_name)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    student_images.append(preprocess_face(img))

            if not student_images:
                continue

            student_recognizer = student_recognizer_cache.get(student_id)
            if student_recognizer is None:
                student_recognizer = student_recognizer_cache.get(student_id)
                if student_recognizer is None:
                    student_recognizer = LBPH_CREATE(
                        radius=1,
                        neighbors=8,
                        grid_x=8,
                        grid_y=8
                    )
                    student_recognizer.train(
                        student_images,
                        np.zeros(len(student_images), dtype=np.int32)
                    )
                    student_recognizer_cache[student_id] = student_recognizer
                student_recognizer_cache[student_id] = student_recognizer
            _, student_distance = student_recognizer.predict(processed_face)
            candidate_scores.append((float(student_distance), student_id))

        if not candidate_scores:
            return {
                "success": False,
                "status": "unknown",
                "message": "No valid student face samples are available."
            }

        candidate_scores.sort(key=lambda item: item[0])
        distance, student_id = candidate_scores[0]
        second_distance = candidate_scores[1][0] if len(candidate_scores) > 1 else None

    except Exception as e:

        print(
            f"[FaceUtils] Recognition error: {e}"
        )

        return {
            "success": False,
            "status": "unknown",
            "message": (
                "Face recognition could not "
                "be completed."
            )
        }

    print(
        "[FaceUtils] Recognition Result - "
        f"Student: {student_id}, "
        f"Distance: {distance:.2f}"
    )

    # ==================================================
    # LBPH RECOGNITION - END
    # ==================================================


    # ==================================================
    # RECOGNITION THRESHOLD - START
    # ==================================================

    # Lower LBPH distance is a better match. Reject weak or ambiguous
    # matches instead of assigning every face to the nearest student.
    RECOGNITION_THRESHOLD = 55.0
    MINIMUM_MATCH_MARGIN = 8.0

    # ==================================================
    # RECOGNITION THRESHOLD - END
    # ==================================================


    # ==================================================
    # STUDENT MATCH - START
    # ==================================================

    if (
        distance <= RECOGNITION_THRESHOLD
        and (
            second_distance is None
            or second_distance - distance >= MINIMUM_MATCH_MARGIN
        )
    ):

        # Database connection.
        conn = get_db_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    student_id,
                    full_name,
                    roll_number,
                    branch,
                    semester,
                    payment_status,
                    face_image_path
                FROM students
                WHERE student_id = ?
                """,
                (student_id,)
            )

            student = cursor.fetchone()

        finally:

            conn.close()

        # Student database me mil gaya.
        if student:

            # Approximate confidence percentage.
            confidence_score = max(
                50.0,
                round(
                    100.0 - (
                        distance * 0.5
                    ),
                    1
                )
            )

            return {

                "success": True,

                "status": "recognized",

                "student_id": student[
                    "student_id"
                ],

                "student": {

                    "student_id": student[
                        "student_id"
                    ],

                    "full_name": student[
                        "full_name"
                    ],

                    "roll_number": student[
                        "roll_number"
                    ],

                    "branch": student[
                        "branch"
                    ],

                    "semester": student[
                        "semester"
                    ],

                    "payment_status": student[
                        "payment_status"
                    ],

                    "face_image_path": student[
                        "face_image_path"
                    ]
                },

                "confidence": confidence_score,

                "message": (
                    "Student recognized successfully."
                )
            }

    # ==================================================
    # STUDENT MATCH - END
    # ==================================================


    # ==================================================
    # UNKNOWN STUDENT - START
    # ==================================================

    return {

        "success": False,

        "status": "unknown",

        "message": (
            "Student not recognized."
        )
    }

    # ==================================================
    # UNKNOWN STUDENT - END
    # ==================================================


# ==================================================
# BACKWARD COMPATIBILITY - START
# ==================================================

# Agar app.py ya kisi aur old code me
# train_lbph_model() use hua hai,
# to woh bhi work karega.

train_lbph_model = train_model

# ==================================================
# BACKWARD COMPATIBILITY - END
# ==================================================