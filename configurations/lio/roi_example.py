import numpy as np
from itertools import product

from configurations import j0_luna_weighted
from scripts.elias.extract_nodules import extract_nodules_blob_detection
from application.stage1 import Stage1DataLoader
from interfaces.data_loader import VALIDATION, TRAINING, TEST, TRAIN, INPUT
from application.preprocessors.dicom_to_HU import DicomToHU
from utils.transformation_3d import affine_transform, apply_affine_transform


model = j0_luna_weighted

nodule_extractor = extract_nodules_blob_detection

patch_shape = 64, 64, 64  # in pixels
norm_patch_shape = 64, 64, 64  # in mms
evaluation_stride = norm_patch_shape # in mms

replace_input_tags = {"luna:3d": "stage1:3d"}

preprocessors = [DicomToHU(tags=["stage1:3d"])]
postpreprocessors = [] #lol

data_loader= Stage1DataLoader(
    sets=[TRAINING, VALIDATION],
    preprocessors=preprocessors,
    epochs=1,
    multiprocess=False,
    crash_on_exception=True)

batch_size = 1

def patch_generator(sample):
    for prep in preprocessors: prep.process(sample)

    patch = {}
    data = sample[INPUT]["stage1:3d"]
    spacing = sample[INPUT]["stage1:pixelspacing"]

    input_shape = np.asarray(data.shape, np.float)
    pixel_spacing = np.asarray(spacing, np.float)
    output_shape = np.asarray(patch_shape, np.float)
    mm_patch_shape = np.asarray(norm_patch_shape, np.float)
    stride = np.asarray(evaluation_stride, np.float)

    norm_shape = input_shape * pixel_spacing
    _patch_shape = norm_shape * output_shape / mm_patch_shape

    patch_count = norm_shape / stride

    for x,y,z in product(range(patch_count[0]), range(patch_count[1]), range(patch_count[2])):

        offset = np.array([stride[0]*x, stride[1]*y, stride[2]*z], np.float)

        shift_center = affine_transform(translation=-input_shape / 2. - 0.5)
        normscale = affine_transform(scale=norm_shape / input_shape)
        offset_patch = affine_transform(translation=norm_shape/2.-0.5-offset)
        patchscale = affine_transform(scale=_patch_shape / norm_shape)
        unshift_center = affine_transform(translation=output_shape / 2. - 0.5)
        matrix = shift_center.dot(normscale).dot(offset_patch).dot(patchscale).dot(unshift_center)
        output = apply_affine_transform(data, matrix, output_shape=output_shape.astype(np.int))

        patch["stage1:3d"] = output
        patch["offset"] = offset
        yield patch


def extract_nodules(pred, patch):
    rois = nodule_extractor(pred)
    #local to global roi
    rois += patch["offset"]
    return rois


