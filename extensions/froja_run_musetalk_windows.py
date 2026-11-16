"""Windows launcher for MuseTalk using its built-in face detector fallback.

MuseTalk's default preprocessing imports compiled MMCV operations solely to
refine the mouth crop. Official Windows wheels are not available for the
current Torch build, so this launcher supplies the fallback face boxes that
MuseTalk already uses whenever refined landmarks are unavailable.
"""
import runpy
import sys
import types

import cv2
import numpy as np
from face_detection import FaceAlignment, LandmarksType
from tqdm import tqdm


coord_placeholder = (0.0, 0.0, 0.0, 0.0)
device = "cuda"
fa = FaceAlignment(LandmarksType._2D, flip_input=False, device=device)


def read_imgs(img_list):
    print("reading images...")
    return [cv2.imread(img_path) for img_path in tqdm(img_list)]


def get_landmark_and_bbox(img_list, upperbondrange=0):
    frames = read_imgs(img_list)
    coords = []
    print("Windows face-box fallback active")
    for frame in tqdm(frames):
        detected = fa.get_detections_for_batch(np.asarray([frame]))[0]
        if detected is None:
            coords.append(coord_placeholder)
            continue
        x1, y1, x2, y2 = [int(v) for v in detected[:4]]
        if upperbondrange:
            y1 = max(0, y1 + int(upperbondrange))
        coords.append((x1, y1, x2, y2))
    return coords, frames


def get_bbox_range(img_list, upperbondrange=0):
    return f"Total frames: {len(img_list)}; Windows fallback bbox shift: {upperbondrange}"


stub = types.ModuleType("musetalk.utils.preprocessing")
stub.coord_placeholder = coord_placeholder
stub.read_imgs = read_imgs
stub.get_landmark_and_bbox = get_landmark_and_bbox
stub.get_bbox_range = get_bbox_range
sys.modules[stub.__name__] = stub

runpy.run_module("scripts.inference", run_name="__main__")
